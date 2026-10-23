import json
import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.fixtures.seed import manifest_sha256
from test_evaluation_api import (
    ACCEPTANCE_COHORT,
    DETERMINISTIC,
    FIXTURE_VERSION,
    STRATEGY,
    _evaluation_body,
    _insert_cohort,
    _publish,
)

ACTIVATE = "activate_synthetic_revision"
RESTORE = "restore_prior_revision"


def _events(engine) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT event_type, reason_code, resulting_generation FROM release_event ORDER BY event_seq")
        ).mappings().all()
    return [dict(row) for row in rows]


def _generation(engine) -> int:
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT generation FROM active_policy_pointer WHERE workflow_id = 'service-desk'")
        ).scalar_one_or_none()
    return 0 if value is None else value


def _runs(engine) -> int:
    with engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM execution_run")).scalar_one()


def _blocked_pair(client) -> dict:
    baseline = _publish(client, STRATEGY)
    candidate = _publish(client, DETERMINISTIC)
    manifest = manifest_sha256(["SD-081"], FIXTURE_VERSION)
    created = client.post(
        "/api/v1/evaluations",
        json=_evaluation_body(ACCEPTANCE_COHORT, manifest, FIXTURE_VERSION, baseline, candidate),
        headers={"Idempotency-Key": "rel-eval-sd081"},
    )
    assert created.status_code == 201, created.text
    return {"baseline": baseline, "candidate": candidate, "evaluation": created.json()}


def _activation(evaluation_id: str, revision: str, **overrides) -> dict:
    body = {
        "workflow_id": "service-desk",
        "evaluation_id": evaluation_id,
        "candidate_revision": revision,
        "expected_prior_revision": None,
        "expected_generation": 0,
        "confirmation": ACTIVATE,
    }
    body.update(overrides)
    return body


def test_blocked_inconclusive_and_ineligible_evaluations_cannot_activate(client, engine) -> None:
    pair = _blocked_pair(client)
    blocked = client.post(
        "/api/v1/releases",
        json=_activation(pair["evaluation"]["evaluation_id"], pair["candidate"]),
        headers={"Idempotency-Key": "rel-blocked"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "evaluation_not_eligible"
    assert blocked.json()["details"]["evaluation_status"] == "completed_blocked"
    assert blocked.json()["details"]["eligibility_authoritative"] is False
    assert blocked.json()["generation"] == 0
    assert blocked.json()["active_revision"] is None
    fixture_version = "qa-nolabel-fixture-v1"
    manifest = _insert_cohort(
        engine,
        "qa-rel-nolabel",
        fixture_version,
        [
            {
                "case_id": "QA-REL-NL",
                "request_text": "No label",
                "observation_id": "OBS-REL-NL",
                "observed_category": "routine",
                "confidence_bps": 5000,
                "label": None,
            }
        ],
    )
    revision = pair["baseline"]
    inconclusive = client.post(
        "/api/v1/evaluations",
        json=_evaluation_body("qa-rel-nolabel", manifest, fixture_version, revision, revision),
        headers={"Idempotency-Key": "rel-eval-nl"},
    )
    assert inconclusive.status_code == 201, inconclusive.text
    denied = client.post(
        "/api/v1/releases",
        json=_activation(inconclusive.json()["evaluation_id"], revision),
        headers={"Idempotency-Key": "rel-inconclusive"},
    )
    assert denied.status_code == 409
    assert denied.json()["details"]["evaluation_status"] == "inconclusive"
    routine_fixture = "qa-rel-routine-fixture-v1"
    routine_manifest = _insert_cohort(
        engine,
        "qa-rel-routine",
        routine_fixture,
        [
            {
                "case_id": "QA-REL-RT",
                "request_text": "Routine",
                "observation_id": "OBS-REL-RT",
                "observed_category": "routine",
                "confidence_bps": 9000,
                "label": {
                    "reference_category": "routine",
                    "expected_disposition": "automated",
                    "expected_resolution": "synthetic-automation",
                },
            }
        ],
    )
    economy = _publish(client, {**STRATEGY, "rules": [], "default_method": "economy", "fallback_method": "premium"})
    recorded = client.post(
        "/api/v1/evaluations",
        json=_evaluation_body("qa-rel-routine", routine_manifest, routine_fixture, economy, economy),
        headers={"Idempotency-Key": "rel-eval-rt"},
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["status"] == "completed_ineligible"
    still_denied = client.post(
        "/api/v1/releases",
        json=_activation(recorded.json()["evaluation_id"], economy),
        headers={"Idempotency-Key": "rel-ineligible"},
    )
    assert still_denied.status_code == 409
    assert still_denied.json()["code"] == "evaluation_not_eligible"
    assert _generation(engine) == 0
    assert [row["reason_code"] for row in _events(engine)] == [
        "evaluation_not_eligible",
        "evaluation_not_eligible",
        "evaluation_not_eligible",
    ]


def test_release_denials_are_distinct_idempotent_and_append_only(client, engine) -> None:
    pair = _blocked_pair(client)
    evaluation_id = pair["evaluation"]["evaluation_id"]
    missing = client.post(
        "/api/v1/releases",
        json=_activation(evaluation_id, pair["candidate"], confirmation=None),
        headers={"Idempotency-Key": "rel-approval"},
    )
    assert missing.status_code == 409
    assert missing.json()["code"] == "missing_approval"
    stale = client.post(
        "/api/v1/releases",
        json=_activation(evaluation_id, pair["candidate"], expected_generation=7),
        headers={"Idempotency-Key": "rel-stale"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_generation"
    wrong = client.post(
        "/api/v1/releases",
        json=_activation(evaluation_id, pair["baseline"]),
        headers={"Idempotency-Key": "rel-wrong"},
    )
    assert wrong.status_code == 409
    assert wrong.json()["code"] == "wrong_revision"
    forged = dict(_activation(evaluation_id, pair["candidate"]), eligible=True)
    rejected = client.post("/api/v1/releases", json=forged, headers={"Idempotency-Key": "rel-forged"})
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "validation_error"
    absent = client.post(
        "/api/v1/releases",
        json=_activation("missing-evaluation", pair["candidate"]),
        headers={"Idempotency-Key": "rel-missing-eval"},
    )
    assert absent.status_code == 404
    assert absent.json()["code"] == "evaluation_not_found"
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM evaluation_gate WHERE evaluation_id = :evaluation_id"), {"evaluation_id": evaluation_id})
    missing_evidence = client.post(
        "/api/v1/releases",
        json=_activation(evaluation_id, pair["candidate"]),
        headers={"Idempotency-Key": "rel-missing-evidence"},
    )
    assert missing_evidence.status_code == 409
    assert missing_evidence.json()["code"] == "missing_evidence"
    replay = client.post(
        "/api/v1/releases",
        json=_activation(evaluation_id, pair["candidate"], confirmation=None),
        headers={"Idempotency-Key": "rel-approval"},
    )
    assert replay.status_code == 409
    assert replay.json()["event_id"] == missing.json()["event_id"]
    conflict = client.post(
        "/api/v1/releases",
        json=_activation(evaluation_id, pair["candidate"], expected_generation=3),
        headers={"Idempotency-Key": "rel-approval"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    history = client.get("/api/v1/releases/service-desk/events")
    assert history.status_code == 200
    reasons = [event["reason_code"] for event in history.json()["events"]]
    assert reasons == [
        "missing_approval",
        "stale_generation",
        "wrong_revision",
        "evaluation_not_found",
        "missing_evidence",
    ]
    assert _generation(engine) == 0
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM release_event")).scalar_one() == 5
    with pytest_database_error():
        with engine.begin() as connection:
            connection.execute(text("UPDATE release_event SET reason_code = 'rewritten'"))
    assert [row["reason_code"] for row in _events(engine)] == reasons


class pytest_database_error:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None or not issubclass(exc_type, DatabaseError):
            return False
        assert "append-only" in str(exc)
        return True


def test_verification_overlap_inactive_policy_and_injected_regression(client, engine) -> None:
    overlap_manifest = _insert_cohort(
        engine,
        "qa-overlap",
        "qa-overlap-fixture-v1",
        [],
        manifest_case_ids=["SD-081"],
        purpose="verification",
    )
    # _insert_cohort with no cases still inserts a manifest. Overlap is the case id list.
    overlap = client.post(
        "/api/v1/releases/service-desk/verifications",
        json={
            "cohort_id": "qa-overlap",
            "expected_manifest_sha256": overlap_manifest,
            "expected_fixture_version": "qa-overlap-fixture-v1",
            "expected_active_revision": None,
            "expected_generation": 0,
        },
        headers={"Idempotency-Key": "rel-overlap"},
    )
    assert overlap.status_code == 409, overlap.text
    assert overlap.json()["code"] == "verification_cohort_overlap"
    assert overlap.json()["details"]["overlap_case_ids"] == ["SD-081"]
    assert overlap.json()["details"]["claims_independent_holdout"] is False
    assert overlap.json()["details"]["release_authorized"] is False
    assert _runs(engine) == 0
    holdout_manifest = _insert_cohort(
        engine,
        "qa-holdout",
        "qa-holdout-fixture-v1",
        [],
        manifest_case_ids=["QA-HOLD"],
        purpose="verification",
    )
    inactive = client.post(
        "/api/v1/releases/service-desk/verifications",
        json={
            "cohort_id": "qa-holdout",
            "expected_manifest_sha256": holdout_manifest,
            "expected_fixture_version": "qa-holdout-fixture-v1",
            "expected_active_revision": None,
            "expected_generation": 0,
        },
        headers={"Idempotency-Key": "rel-inactive"},
    )
    assert inactive.status_code == 409, inactive.text
    assert inactive.json()["code"] == "no_active_policy"
    assert _runs(engine) == 0
    purpose = client.post(
        "/api/v1/releases/service-desk/verifications",
        json={
            "cohort_id": ACCEPTANCE_COHORT,
            "expected_manifest_sha256": manifest_sha256(["SD-081"], FIXTURE_VERSION),
            "expected_fixture_version": FIXTURE_VERSION,
            "expected_active_revision": None,
            "expected_generation": 0,
        },
        headers={"Idempotency-Key": "rel-purpose"},
    )
    assert purpose.status_code == 409
    assert purpose.json()["code"] == "cohort_purpose"
    regression_manifest = _insert_cohort(
        engine,
        "qa-regression",
        "qa-regression-fixture-v1",
        [
            {
                "case_id": "QA-REG",
                "request_text": "Privileged action observed as ambiguous",
                "observation_id": "OBS-QA-REG",
                "observed_category": "ambiguous",
                "confidence_bps": 6100,
                "label": {
                    "reference_category": "privileged",
                    "expected_disposition": "escalated",
                    "expected_resolution": "synthetic-escalation",
                },
            }
        ],
        purpose="verification",
    )
    candidate = _publish(client, DETERMINISTIC)
    prior = _publish(client, STRATEGY)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO active_policy_pointer (
                    workflow_id, generation, revision_sha256, prior_revision_sha256, evaluation_id
                )
                VALUES ('service-desk', 1, :revision, :prior, NULL)
                ON CONFLICT (workflow_id) DO UPDATE
                SET generation = 1,
                    revision_sha256 = EXCLUDED.revision_sha256,
                    prior_revision_sha256 = EXCLUDED.prior_revision_sha256,
                    evaluation_id = NULL
                """
            ),
            {"revision": candidate, "prior": prior},
        )
    regressed = client.post(
        "/api/v1/releases/service-desk/verifications",
        json={
            "cohort_id": "qa-regression",
            "expected_manifest_sha256": regression_manifest,
            "expected_fixture_version": "qa-regression-fixture-v1",
            "expected_active_revision": candidate,
            "expected_generation": 1,
        },
        headers={"Idempotency-Key": "rel-regression"},
    )
    assert regressed.status_code == 201, regressed.text
    assert regressed.json()["code"] == "regressed"
    assert regressed.json()["details"]["claims_independent_holdout"] is False
    assert regressed.json()["generation"] == 1
    assert _generation(engine) == 1
    with engine.connect() as connection:
        critical = connection.execute(
            text(
                """
                SELECT critical_violation, verdict FROM verification_case
                WHERE verification_id = :verification_id
                """
            ),
            {"verification_id": regressed.json()["verification_id"]},
        ).one()
    assert critical.critical_violation is True
    assert critical.verdict == "incorrect_completion"


def test_restore_fails_without_a_prior_and_replays_a_planted_prior(client, engine) -> None:
    failed = client.post(
        "/api/v1/releases/service-desk/restore",
        json={"expected_generation": 0, "confirmation": RESTORE},
        headers={"Idempotency-Key": "rel-restore-fail"},
    )
    assert failed.status_code == 409, failed.text
    assert failed.json()["code"] == "nothing_to_restore"
    assert _generation(engine) == 0
    current = _publish(client, DETERMINISTIC)
    previous = _publish(client, STRATEGY)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO active_policy_pointer (
                    workflow_id, generation, revision_sha256, prior_revision_sha256, evaluation_id
                )
                VALUES ('service-desk', 1, :current, :previous, NULL)
                ON CONFLICT (workflow_id) DO UPDATE
                SET generation = 1,
                    revision_sha256 = EXCLUDED.revision_sha256,
                    prior_revision_sha256 = EXCLUDED.prior_revision_sha256,
                    evaluation_id = NULL
                """
            ),
            {"current": current, "previous": previous},
        )
    stale = client.post(
        "/api/v1/releases/service-desk/restore",
        json={"expected_generation": 0, "confirmation": RESTORE},
        headers={"Idempotency-Key": "rel-restore-stale"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_generation"
    assert _generation(engine) == 1
    restored = client.post(
        "/api/v1/releases/service-desk/restore",
        json={"expected_generation": 1, "confirmation": RESTORE},
        headers={"Idempotency-Key": "rel-restore-ok"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["code"] == "restoration_committed"
    assert restored.json()["active_revision"] == previous
    assert restored.json()["prior_revision"] == current
    assert restored.json()["generation"] == 2
    replay = client.post(
        "/api/v1/releases/service-desk/restore",
        json={"expected_generation": 1, "confirmation": RESTORE},
        headers={"Idempotency-Key": "rel-restore-ok"},
    )
    assert replay.status_code == 200
    assert replay.json() == restored.json()
    assert _generation(engine) == 2
    workflow = client.get("/api/v1/workflows/service-desk")
    assert workflow.json()["active_policy"]["revision_sha256"] == previous
    assert workflow.json()["active_policy"]["generation"] == 2
    reasons = [row["reason_code"] for row in _events(engine)]
    assert reasons == ["nothing_to_restore", "stale_generation", "restoration_committed"]


def _post_release(app, body: dict, key: str) -> dict:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post("/api/v1/releases", json=body, headers={"Idempotency-Key": key})
    return {"status": response.status_code, "body": response.json()}


def test_concurrent_activation_denial_keeps_generation_zero(client, engine) -> None:
    pair = _blocked_pair(client)
    body = _activation(pair["evaluation"]["evaluation_id"], pair["candidate"])
    barrier = threading.Barrier(3)
    results: list[dict | None] = [None, None]

    def worker(index: int) -> None:
        barrier.wait(timeout=30)
        results[index] = _post_release(client.app, body, "rel-concurrent-deny")

    locker = engine.connect()
    transaction = locker.begin()
    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    waiting = 0
    try:
        locker.execute(text("LOCK TABLE active_policy_pointer IN ACCESS EXCLUSIVE MODE"))
        for thread in threads:
            thread.start()
        barrier.wait(timeout=30)
        deadline = time.time() + 20
        while time.time() < deadline:
            waiting = locker.execute(
                text(
                    """
                    SELECT count(*) FROM pg_locks
                    WHERE relation = 'active_policy_pointer'::regclass AND NOT granted
                    """
                )
            ).scalar_one()
            if waiting >= 2:
                break
            time.sleep(0.05)
        transaction.commit()
        for thread in threads:
            thread.join(timeout=90)
    finally:
        if transaction.is_active:
            transaction.rollback()
        locker.close()
    assert waiting >= 2, results
    assert [item["status"] for item in results] == [409, 409]
    assert results[0]["body"]["event_id"] == results[1]["body"]["event_id"]
    assert _generation(engine) == 0
    assert len(_events(engine)) == 1
