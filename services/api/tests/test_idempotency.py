import json
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = json.loads((ROOT / "app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))


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
