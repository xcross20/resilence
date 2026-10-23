import json
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = json.loads((ROOT / "app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))
ALTERNATE_STRATEGY = {
    "schema_version": "1",
    "workflow_id": "service-desk",
    "rules": [],
    "default_method": "economy",
    "fallback_method": "premium",
}


def test_same_key_replays_and_a_different_body_conflicts(client, engine) -> None:
    created = client.post("/api/v1/strategies/revisions", json=STRATEGY)
    assert created.status_code == 201
    revision = created.json()["revision_sha256"]
    other = client.post(
        "/api/v1/strategies/revisions",
        json={
            "schema_version": "1",
            "workflow_id": "service-desk",
            "rules": [],
            "default_method": "economy",
            "fallback_method": "premium",
        },
    )
    assert other.status_code == 201
    body = {
        "workflow_id": "service-desk",
        "cohort_id": "acceptance-sd081",
        "case_id": "SD-081",
        "revision_sha256": revision,
    }
    headers = {"Idempotency-Key": "sd081-replay"}
    first = client.post("/api/v1/executions", json=body, headers=headers)
    second = client.post("/api/v1/executions", json=body, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["run"]["run_id"] == first.json()["run"]["run_id"]
    conflict = client.post(
        "/api/v1/executions",
        json=dict(body, revision_sha256=other.json()["revision_sha256"]),
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    with engine.connect() as connection:
        runs = connection.execute(text("SELECT count(*) FROM execution_run")).scalar_one()
    assert runs == 1


def _publish(client, document: dict) -> str:
    created = client.post("/api/v1/strategies/revisions", json=document)
    assert created.status_code == 201
    return created.json()["revision_sha256"]


def _execution_body(revision: str) -> dict:
    return {
        "workflow_id": "service-desk",
        "cohort_id": "acceptance-sd081",
        "case_id": "SD-081",
        "revision_sha256": revision,
    }


def _post_execution(app, body: dict, key: str, correlation: str) -> dict:
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(
                "/api/v1/executions",
                json=body,
                headers={"Idempotency-Key": key, "X-Correlation-Id": correlation},
            )
        try:
            payload = response.json()
        except Exception:
            payload = {"raw": response.text[:300]}
        return {"status": response.status_code, "body": payload}
    except Exception as exc:  # noqa: BLE001 — the test records an unhandled driver error
        return {"status": "EXCEPTION", "body": {"type": type(exc).__name__, "message": str(exc)[:300]}}


def _release_when_both_block(locker) -> int:
    """Hold the insert lock until both requests are waiting on execution_run."""
    deadline = time.time() + 20
    waiting = 0
    while time.time() < deadline:
        waiting = locker.execute(
            text(
                """
                SELECT count(*)
                FROM pg_locks
                WHERE relation = 'execution_run'::regclass
                  AND NOT granted
                """
            )
        ).scalar_one()
        if waiting >= 2:
            return waiting
        time.sleep(0.05)
    return waiting


def _race_same_key(engine, app, bodies: list[dict], key: str) -> list[dict]:
    barrier = threading.Barrier(3)
    results: list[dict | None] = [None, None]

    def worker(index: int) -> None:
        barrier.wait(timeout=30)
        results[index] = _post_execution(app, bodies[index], key, f"{key}-{index}")

    locker = engine.connect()
    transaction = locker.begin()
    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    try:
        locker.execute(text("LOCK TABLE execution_run IN ACCESS EXCLUSIVE MODE"))
        for thread in threads:
            thread.start()
        barrier.wait(timeout=30)
        waiting = _release_when_both_block(locker)
        transaction.commit()
        for thread in threads:
            thread.join(timeout=90)
    finally:
        if transaction.is_active:
            transaction.rollback()
        locker.close()
    assert all(result is not None for result in results)
    assert waiting >= 2, results
    return results


def _durable_counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "runs": connection.execute(text("SELECT count(*) FROM execution_run")).scalar_one(),
            "attempts": connection.execute(text("SELECT count(*) FROM attempt_record")).scalar_one(),
            "costs": connection.execute(text("SELECT count(*) FROM cost_entry")).scalar_one(),
            "keys": connection.execute(text("SELECT count(*) FROM idempotency_key")).scalar_one(),
        }


def test_concurrent_same_key_and_body_replay_one_run(client, engine) -> None:
    revision = _publish(client, STRATEGY)
    body = _execution_body(revision)
    results = _race_same_key(engine, client.app, [body, body], "sd081-concurrent-same")
    assert [item["status"] for item in results] == [201, 201]
    run_ids = {item["body"]["run"]["run_id"] for item in results}
    assert len(run_ids) == 1
    counts = _durable_counts(engine)
    assert counts == {"runs": 1, "attempts": 1, "costs": 1, "keys": 1}
    replay = client.post("/api/v1/executions", json=body, headers={"Idempotency-Key": "sd081-concurrent-same"})
    assert replay.status_code == 201
    assert replay.json()["run"]["run_id"] == next(iter(run_ids))
    assert _durable_counts(engine) == counts


def test_concurrent_same_key_and_different_body_conflicts(client, engine) -> None:
    first_revision = _publish(client, STRATEGY)
    second_revision = _publish(client, ALTERNATE_STRATEGY)
    bodies = [_execution_body(first_revision), _execution_body(second_revision)]
    results = _race_same_key(engine, client.app, bodies, "sd081-concurrent-conflict")
    statuses = sorted(item["status"] for item in results)
    assert statuses == [201, 409]
    winner = next(item for item in results if item["status"] == 201)
    loser = next(item for item in results if item["status"] == 409)
    assert loser["body"]["code"] == "idempotency_conflict"
    winner_body = bodies[results.index(winner)]
    loser_body = bodies[results.index(loser)]
    counts = _durable_counts(engine)
    assert counts == {"runs": 1, "attempts": 1, "costs": 1, "keys": 1}
    replay = client.post(
        "/api/v1/executions",
        json=winner_body,
        headers={"Idempotency-Key": "sd081-concurrent-conflict"},
    )
    assert replay.status_code == 201
    assert replay.json()["run"]["run_id"] == winner["body"]["run"]["run_id"]
    conflict = client.post(
        "/api/v1/executions",
        json=loser_body,
        headers={"Idempotency-Key": "sd081-concurrent-conflict"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    assert _durable_counts(engine) == counts
