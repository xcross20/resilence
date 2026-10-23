import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.fixtures.seed import manifest_sha256

ROOT = Path(__file__).resolve().parents[1]
PRICE = json.loads((ROOT / "app/fixtures/service_desk_v1/price_book.json").read_text(encoding="utf-8"))
STRATEGY = json.loads((ROOT / "app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))
FIXTURE_VERSION = "service-desk-fixture-v1"
ACCEPTANCE_COHORT = "acceptance-sd081"
EVALUATOR_VERSION = "rubric-assessor-v1"
ACCOUNTING_VERSION = "accounting-v0-integer-micro-usd"
GATE_POLICY_VERSION = "gate-policy-v0-fail-closed"
MODELED_LABOR_MICRO_USD = 250_000
MODELED_INFRASTRUCTURE_MICRO_USD = 10_000
MODELED_RISK_MICRO_USD = 50_000

DETERMINISTIC = {
    "schema_version": "1",
    "workflow_id": "service-desk",
    "rules": [
        {
            "rule_id": "R-DET",
            "priority": 10,
            "when": {"observed_category_in": ["routine", "ambiguous"]},
            "method": "deterministic",
        },
        {
            "rule_id": "R-PRIV",
            "priority": 20,
            "when": {"observed_category_in": ["privileged"]},
            "method": "premium",
        },
    ],
    "default_method": "premium",
    "fallback_method": "premium",
}


def _method_strategy(method: str, rule_id: str) -> dict:
    return {
        "schema_version": "1",
        "workflow_id": "service-desk",
        "rules": [
            {
                "rule_id": rule_id,
                "priority": 10,
                "when": {"observed_category_in": ["routine", "ambiguous", "privileged"]},
                "method": method,
            }
        ],
        "default_method": method,
        "fallback_method": "premium",
    }


def _publish(client, document: dict) -> str:
    created = client.post("/api/v1/strategies/revisions", json=document)
    assert created.status_code == 201, created.text
    return created.json()["revision_sha256"]


def _evaluation_body(cohort_id: str, manifest: str, fixture_version: str, baseline: str, candidate: str) -> dict:
    return {
        "workflow_id": "service-desk",
        "cohort_id": cohort_id,
        "baseline_revision": baseline,
        "candidate_revision": candidate,
        "expected_manifest_sha256": manifest,
        "expected_fixture_version": fixture_version,
        "expected_price_book_version": PRICE["version"],
        "expected_evaluator_version": EVALUATOR_VERSION,
        "expected_accounting_version": ACCOUNTING_VERSION,
        "expected_gate_policy_version": GATE_POLICY_VERSION,
    }


def _insert_cohort(engine, cohort_id: str, fixture_version: str, cases: list[dict], manifest_case_ids: list[str] | None = None) -> str:
    case_ids = manifest_case_ids or [item["case_id"] for item in cases]
    digest = manifest_sha256(case_ids, fixture_version)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO cohort_manifest (
                    cohort_id, workflow_id, version, purpose, fixture_version, manifest_sha256, case_ids
                )
                VALUES (
                    :cohort_id, 'service-desk', :version, 'acceptance', :fixture_version,
                    :manifest_sha256, CAST(:case_ids AS json)
                )
                """
            ),
            {
                "cohort_id": cohort_id,
                "version": cohort_id + "-v1",
                "fixture_version": fixture_version,
                "manifest_sha256": digest,
                "case_ids": json.dumps(case_ids),
            },
        )
        for case in cases:
            connection.execute(
                text(
                    """
                    INSERT INTO case_input (cohort_id, case_id, request_text)
                    VALUES (:cohort_id, :case_id, :request_text)
                    """
                ),
                {"cohort_id": cohort_id, "case_id": case["case_id"], "request_text": case["request_text"]},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO classification_observation (
                        observation_id, cohort_id, case_id, classifier_version,
                        observed_category, confidence_bps, evidence_origin
                    )
                    VALUES (
                        :observation_id, :cohort_id, :case_id, 'synthetic-classifier-v1',
                        :observed_category, :confidence_bps, 'synthetic_simulated'
                    )
                    """
                ),
                {
                    "observation_id": case["observation_id"],
                    "cohort_id": cohort_id,
                    "case_id": case["case_id"],
                    "observed_category": case["observed_category"],
                    "confidence_bps": case["confidence_bps"],
                },
            )
            if case.get("label") is not None:
                label = case["label"]
                connection.execute(
                    text(
                        """
                        INSERT INTO reference_label (
                            cohort_id, case_id, reference_category, expected_disposition,
                            expected_resolution, rubric_version, label_origin
                        )
                        VALUES (
                            :cohort_id, :case_id, :reference_category, :expected_disposition,
                            :expected_resolution, 'rubric-v1', 'synthetic_rubric'
                        )
                        """
                    ),
                    {"cohort_id": cohort_id, "case_id": case["case_id"], **label},
                )
    return digest


def _counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "evaluations": connection.execute(text("SELECT count(*) FROM evaluation_run")).scalar_one(),
            "pairs": connection.execute(text("SELECT count(*) FROM evaluation_case")).scalar_one(),
            "gates": connection.execute(text("SELECT count(*) FROM evaluation_gate")).scalar_one(),
            "runs": connection.execute(text("SELECT count(*) FROM execution_run")).scalar_one(),
            "attempts": connection.execute(text("SELECT count(*) FROM attempt_record")).scalar_one(),
            "costs": connection.execute(text("SELECT count(*) FROM cost_entry")).scalar_one(),
            "keys": connection.execute(text("SELECT count(*) FROM idempotency_key")).scalar_one(),
        }


def test_sd081_pair_blocks_on_the_critical_violation_and_a_zero_denominator(client, engine) -> None:
    baseline = _publish(client, STRATEGY)
    candidate = _publish(client, DETERMINISTIC)
    manifest = manifest_sha256(["SD-081"], FIXTURE_VERSION)
    body = _evaluation_body(ACCEPTANCE_COHORT, manifest, FIXTURE_VERSION, baseline, candidate)
    created = client.post("/api/v1/evaluations", json=body, headers={"Idempotency-Key": "ev-sd081"})
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["eligible"] is False
    assert payload["eligibility_authoritative"] is False
    assert payload["status"] == "completed_blocked"
    assert payload["baseline_revision"] == baseline
    assert payload["candidate_revision"] == candidate
    assert payload["case_count"] == 1
    assert payload["divergent_case_ids"] == ["SD-081"]
    assert payload["provenance"]["manifest_sha256"] == manifest
    assert payload["provenance"]["price_book_version"] == "synthetic-price-v2"
    assert payload["provenance"]["execution_evidence_origin"] == "synthetic_simulated"
    assert "real-world model equivalence" in payload["provenance"]["limitation"]
    assert "reference_category" not in created.text
    economics = payload["economics"]
    premium = PRICE["methods"]["premium"]["amount_micro_usd"]
    deterministic = PRICE["methods"]["deterministic"]["amount_micro_usd"]
    assert economics["baseline"]["execution_cost_micro_usd"] == premium
    assert economics["candidate"]["execution_cost_micro_usd"] == deterministic
    assert economics["baseline"]["verified_success_count"] == 0
    assert economics["candidate"]["verified_success_count"] == 0
    assert economics["baseline"]["correct_escalation_count"] == 1
    assert economics["candidate"]["correct_escalation_count"] == 0
    assert economics["baseline"]["cost_per_verified_success_micro_usd"] is None
    assert economics["candidate"]["cost_per_verified_success_micro_usd"] is None
    modeled = economics["modeled_allocations"]
    assert modeled["labor_micro_usd"] == MODELED_LABOR_MICRO_USD
    assert modeled["infrastructure_micro_usd"] == MODELED_INFRASTRUCTURE_MICRO_USD
    assert modeled["risk_micro_usd"] == MODELED_RISK_MICRO_USD
    assert modeled["evidence_origin"] == "synthetic_modeled"
    assert modeled["included_in_primary_quotient"] is False
    gates = {gate["gate_id"]: gate for gate in payload["gates"]}
    assert gates["safety"]["status"] == "blocked"
    assert gates["safety"]["reason_code"] == "critical_violation"
    assert gates["quality"]["status"] == "not_authoritative"
    assert gates["latency"]["status"] == "not_authoritative"
    assert gates["completeness"]["status"] == "pass"
    assert gates["economic"]["reason_code"] == "zero_verified_success_denominator"
    fetched = client.get(f"/api/v1/evaluations/{payload['evaluation_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == payload
    cases = client.get(f"/api/v1/evaluations/{payload['evaluation_id']}/cases")
    assert cases.status_code == 200
    pair = cases.json()["cases"][0]
    assert pair["case_id"] == "SD-081"
    assert pair["route_changed"] is True
    assert pair["verdict_changed"] is True
    assert pair["execution_cost_delta_micro_usd"] == deterministic - premium
    assert pair["baseline_verdict"] == "correct_escalation"
    assert pair["candidate_verdict"] == "incorrect_completion"
    assert pair["candidate_critical_violation"] is True
    assert pair["candidate_reason_code"] == "automated_when_escalation_required"
    evidence = client.get(f"/api/v1/executions/{pair['candidate_run_id']}/evidence")
    assert evidence.status_code == 200
    candidate_evidence = evidence.json()
    assert candidate_evidence["observation"]["observed_category"] == "ambiguous"
    assert candidate_evidence["reference_label"]["reference_category"] == "privileged"
    decision = candidate_evidence["decisions"][0]
    attempt = candidate_evidence["attempts"][0]
    assert decision["selected_method"] == "deterministic"
    assert decision["matched_rule_id"] == "R-DET"
    assert "reference_category" not in decision
    assert attempt["method_version"] == "synthetic-code-v1"
    assert attempt["produced_disposition"] == "automated"
    assert attempt["produced_resolution"] == "synthetic-deterministic-template"
    assert pair["first_divergent_decision_id"] == decision["decision_id"]
    counts = _counts(engine)
    assert counts == {"evaluations": 1, "pairs": 1, "gates": 5, "runs": 2, "attempts": 2, "costs": 2, "keys": 1}
    with engine.connect() as connection:
        operation = connection.execute(text("SELECT operation FROM idempotency_key")).scalar_one()
        reconciled = connection.execute(
            text(
                """
                SELECT count(*) FROM attempt_record AS attempt
                JOIN cost_entry AS cost ON cost.attempt_id = attempt.attempt_id
                """
            )
        ).scalar_one()
    assert operation == "start_evaluation"
    assert reconciled == counts["attempts"]
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("UPDATE evaluation_run SET eligible = true"))
    assert _counts(engine)["evaluations"] == 1
    with engine.connect() as connection:
        eligible = connection.execute(text("SELECT eligible FROM evaluation_run")).scalar_one()
    assert eligible is False


def test_replay_returns_the_same_evaluation_and_a_different_body_conflicts(client, engine) -> None:
    baseline = _publish(client, STRATEGY)
    candidate = _publish(client, DETERMINISTIC)
    other = _publish(client, _method_strategy("economy", "R-ECO"))
    manifest = manifest_sha256(["SD-081"], FIXTURE_VERSION)
    body = _evaluation_body(ACCEPTANCE_COHORT, manifest, FIXTURE_VERSION, baseline, candidate)
    headers = {"Idempotency-Key": "ev-replay"}
    first = client.post("/api/v1/evaluations", json=body, headers=headers)
    second = client.post("/api/v1/evaluations", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json() == first.json()
    conflict = client.post(
        "/api/v1/evaluations",
        json=dict(body, candidate_revision=other),
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    assert _counts(engine)["evaluations"] == 1
    assert _counts(engine)["runs"] == 2


def test_routine_pair_publishes_quotients_without_granting_eligibility(client, engine) -> None:
    fixture_version = "qa-routine-fixture-v1"
    manifest = _insert_cohort(
        engine,
        "qa-routine",
        fixture_version,
        [
            {
                "case_id": "QA-RT",
                "request_text": "Reset a printer tray",
                "observation_id": "OBS-QA-RT",
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
    baseline = _publish(client, _method_strategy("premium", "R-PREM"))
    candidate = _publish(client, _method_strategy("economy", "R-ECO"))
    created = client.post(
        "/api/v1/evaluations",
        json=_evaluation_body("qa-routine", manifest, fixture_version, baseline, candidate),
        headers={"Idempotency-Key": "ev-routine"},
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    premium = PRICE["methods"]["premium"]["amount_micro_usd"]
    economy = PRICE["methods"]["economy"]["amount_micro_usd"]
    assert payload["status"] == "completed_ineligible"
    assert payload["eligible"] is False
    assert payload["economics"]["baseline"]["verified_success_count"] == 1
    assert payload["economics"]["candidate"]["verified_success_count"] == 1
    assert payload["economics"]["baseline"]["cost_per_verified_success_micro_usd"] == premium
    assert payload["economics"]["candidate"]["cost_per_verified_success_micro_usd"] == economy
    assert payload["economics"]["candidate"]["remainder_micro_usd"] == 0
    assert payload["economics"]["candidate"]["cost_per_verified_success_micro_usd"] != economy + MODELED_LABOR_MICRO_USD
    gates = {gate["gate_id"]: gate for gate in payload["gates"]}
    assert gates["safety"]["status"] == "pass"
    assert gates["completeness"]["status"] == "pass"
    assert gates["economic"]["status"] == "not_authoritative"
    assert gates["economic"]["reason_code"] == "noninferiority_not_approved"
    cases = client.get(f"/api/v1/evaluations/{payload['evaluation_id']}/cases").json()["cases"]
    assert cases[0]["baseline_verdict"] == "verified_success"
    assert cases[0]["candidate_verdict"] == "verified_success"
    assert cases[0]["route_changed"] is True
    with engine.connect() as connection:
        stored_cost = connection.execute(
            text(
                """
                SELECT amount_micro_usd
                FROM cost_entry
                JOIN attempt_record ON attempt_record.attempt_id = cost_entry.attempt_id
                WHERE attempt_record.run_id = :run_id
                """
            ),
            {"run_id": cases[0]["candidate_run_id"]},
        ).scalar_one()
    assert stored_cost == economy
    assert stored_cost == payload["economics"]["candidate"]["cost_per_verified_success_micro_usd"]


def test_missing_label_is_persisted_as_inconclusive(client, engine) -> None:
    fixture_version = "qa-nolabel-fixture-v1"
    manifest = _insert_cohort(
        engine,
        "qa-nolabel",
        fixture_version,
        [
            {
                "case_id": "QA-NL",
                "request_text": "Unlabeled request",
                "observation_id": "OBS-QA-NL",
                "observed_category": "routine",
                "confidence_bps": 5000,
                "label": None,
            }
        ],
    )
    revision = _publish(client, STRATEGY)
    created = client.post(
        "/api/v1/evaluations",
        json=_evaluation_body("qa-nolabel", manifest, fixture_version, revision, revision),
        headers={"Idempotency-Key": "ev-nolabel"},
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["status"] == "inconclusive"
    assert payload["eligible"] is False
    gates = {gate["gate_id"]: gate for gate in payload["gates"]}
    assert gates["completeness"]["reason_code"] == "inconclusive_assessment"
    assert payload["economics"]["candidate"]["cost_per_verified_success_micro_usd"] is None
    assert _counts(engine)["evaluations"] == 1


def test_unmatched_manifest_case_writes_nothing(client, engine) -> None:
    fixture_version = "qa-gap-fixture-v1"
    manifest = _insert_cohort(
        engine,
        "qa-gap",
        fixture_version,
        [
            {
                "case_id": "QA-THERE",
                "request_text": "Present case",
                "observation_id": "OBS-QA-THERE",
                "observed_category": "routine",
                "confidence_bps": 8000,
                "label": {
                    "reference_category": "routine",
                    "expected_disposition": "automated",
                    "expected_resolution": "synthetic-automation",
                },
            }
        ],
        manifest_case_ids=["QA-THERE", "QA-GONE"],
    )
    revision = _publish(client, STRATEGY)
    rejected = client.post(
        "/api/v1/evaluations",
        json=_evaluation_body("qa-gap", manifest, fixture_version, revision, revision),
        headers={"Idempotency-Key": "ev-gap"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "cohort_incomplete"
    assert rejected.json()["details"]["missing_case_ids"] == ["QA-GONE"]
    counts = _counts(engine)
    assert counts["evaluations"] == 0
    assert counts["runs"] == 0
    assert counts["keys"] == 0


def test_version_mismatch_and_client_eligible_flag_write_nothing(client, engine) -> None:
    baseline = _publish(client, STRATEGY)
    candidate = _publish(client, DETERMINISTIC)
    manifest = manifest_sha256(["SD-081"], FIXTURE_VERSION)
    body = _evaluation_body(ACCEPTANCE_COHORT, manifest, FIXTURE_VERSION, baseline, candidate)
    mismatch = dict(body, expected_price_book_version="synthetic-price-v1")
    rejected = client.post("/api/v1/evaluations", json=mismatch, headers={"Idempotency-Key": "ev-mismatch"})
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "version_mismatch"
    assert rejected.json()["details"]["field"] == "expected_price_book_version"
    forged = dict(body, eligible=True)
    forged_response = client.post("/api/v1/evaluations", json=forged, headers={"Idempotency-Key": "ev-forged"})
    assert forged_response.status_code == 422
    assert forged_response.json()["code"] == "validation_error"
    assert "eligible" in forged_response.text
    missing_key = client.post("/api/v1/evaluations", json=body)
    assert missing_key.status_code == 422
    counts = _counts(engine)
    assert counts["evaluations"] == 0
    assert counts["runs"] == 0
    assert counts["keys"] == 0


def _post_evaluation(app, body: dict, key: str) -> dict:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/evaluations",
            json=body,
            headers={"Idempotency-Key": key, "X-Correlation-Id": key},
        )
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:300]}
    return {"status": response.status_code, "body": payload}


def test_concurrent_same_evaluation_keeps_one_pair(client, engine) -> None:
    baseline = _publish(client, STRATEGY)
    candidate = _publish(client, DETERMINISTIC)
    manifest = manifest_sha256(["SD-081"], FIXTURE_VERSION)
    body = _evaluation_body(ACCEPTANCE_COHORT, manifest, FIXTURE_VERSION, baseline, candidate)
    barrier = threading.Barrier(3)
    results: list[dict | None] = [None, None]

    def worker(index: int) -> None:
        barrier.wait(timeout=30)
        results[index] = _post_evaluation(client.app, body, "ev-concurrent")

    locker = engine.connect()
    transaction = locker.begin()
    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    waiting = 0
    try:
        locker.execute(text("LOCK TABLE execution_run IN ACCESS EXCLUSIVE MODE"))
        for thread in threads:
            thread.start()
        barrier.wait(timeout=30)
        deadline = time.time() + 20
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
    assert [item["status"] for item in results] == [201, 201]
    assert results[0]["body"]["evaluation_id"] == results[1]["body"]["evaluation_id"]
    counts = _counts(engine)
    assert counts["evaluations"] == 1
    assert counts["runs"] == 2
    assert counts["attempts"] == 2
    assert counts["costs"] == 2
    assert counts["keys"] == 1
    replay = client.post("/api/v1/evaluations", json=body, headers={"Idempotency-Key": "ev-concurrent"})
    assert replay.status_code == 201
    assert replay.json()["evaluation_id"] == results[0]["body"]["evaluation_id"]
    assert _counts(engine) == counts
