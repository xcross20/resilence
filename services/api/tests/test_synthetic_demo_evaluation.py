"""Persisted synthetic-demo evaluations. Requires DISPOSABLE_DATABASE_URL and refuses Railway."""

import json
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.database_url import create_database_engine
from app.domain.assessment import EVALUATOR_VERSION
from app.domain.gates import ACCOUNTING_VERSION, GATE_POLICY_VERSION, SYNTHETIC_DEMO_POLICY_VERSION
from app.domain.release import APPROVED_ACTIVATION_POLICIES
from app.fixtures.seed import manifest_sha256
from app.fixtures.synthetic_demo_v1 import (
    ACCEPTANCE_COHORT_ID,
    DEMO_WORKFLOW_ID,
    DEMO_WORKFLOW_VERSION,
    FIXTURE_VERSION,
    VERIFICATION_COHORT_ID,
    acceptance_cases,
    build_cases,
    privileged_only_cases,
    verification_cases,
)
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
PRICE = json.loads((ROOT / "app/fixtures/service_desk_v1/price_book.json").read_text(encoding="utf-8"))
RAILWAY_ENV = (
    "RAILWAY_TCP_PROXY_DOMAIN",
    "RAILWAY_TCP_PROXY_PORT",
    "PGUSER",
    "PGPASSWORD",
    "PGDATABASE",
    "DATABASE_PUBLIC_URL",
)
PRIVILEGED_LABEL = {
    "reference_category": "privileged",
    "expected_disposition": "escalated",
    "expected_resolution": "synthetic-escalation",
}


def _strategy(rules: list[dict], default_method: str) -> dict:
    return {
        "schema_version": "1",
        "workflow_id": DEMO_WORKFLOW_ID,
        "rules": rules,
        "default_method": default_method,
        "fallback_method": "premium",
    }


PREMIUM = _strategy(
    [
        {
            "rule_id": "R-ALL",
            "priority": 10,
            "when": {"observed_category_in": ["routine", "ambiguous", "privileged"]},
            "method": "premium",
        }
    ],
    "premium",
)
ECONOMY = _strategy(
    [
        {
            "rule_id": "R-CHEAP",
            "priority": 10,
            "when": {"observed_category_in": ["routine", "ambiguous"]},
            "method": "economy",
        },
        {
            "rule_id": "R-PRIV",
            "priority": 20,
            "when": {"observed_category_in": ["privileged"]},
            "method": "premium",
        },
    ],
    "premium",
)
DETERMINISTIC = _strategy(
    [
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
    "premium",
)


def _refuse_railway(url: str) -> None:
    lowered = url.lower()
    if "rlwy.net" in lowered or "railway" in lowered:
        pytest.fail("synthetic-demo persistence tests refuse the shared Railway database")


def _insert_workflow(engine) -> None:
    graph = {"nodes": [{"step_id": "draft_resolution", "name": "Draft resolution"}], "edges": []}
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO workflow_definition (workflow_id, version, graph_json)
                VALUES (:workflow_id, :version, CAST(:graph_json AS json))
                ON CONFLICT (workflow_id) DO NOTHING
                """
            ),
            {
                "workflow_id": DEMO_WORKFLOW_ID,
                "version": DEMO_WORKFLOW_VERSION,
                "graph_json": json.dumps(graph),
            },
        )


def _insert_cohort(engine, cohort_id: str, cases: list[dict], purpose: str) -> str:
    case_ids = [item["case_id"] for item in cases]
    digest = manifest_sha256(case_ids, FIXTURE_VERSION)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO cohort_manifest (
                    cohort_id, workflow_id, version, purpose, fixture_version, manifest_sha256, case_ids
                )
                VALUES (
                    :cohort_id, :workflow_id, :version, :purpose, :fixture_version,
                    :manifest_sha256, CAST(:case_ids AS json)
                )
                """
            ),
            {
                "cohort_id": cohort_id,
                "workflow_id": DEMO_WORKFLOW_ID,
                "version": cohort_id + "-v1",
                "purpose": purpose,
                "fixture_version": FIXTURE_VERSION,
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
                    {"cohort_id": cohort_id, "case_id": case["case_id"], **case["label"]},
                )
    return digest


def _publish(client: TestClient, document: dict) -> str:
    created = client.post("/api/v1/strategies/revisions", json=document)
    assert created.status_code == 201, created.text
    return created.json()["revision_sha256"]


def _body(cohort_id: str, manifest: str, baseline: str, candidate: str, policy: str) -> dict:
    return {
        "workflow_id": DEMO_WORKFLOW_ID,
        "cohort_id": cohort_id,
        "baseline_revision": baseline,
        "candidate_revision": candidate,
        "expected_manifest_sha256": manifest,
        "expected_fixture_version": FIXTURE_VERSION,
        "expected_price_book_version": PRICE["version"],
        "expected_evaluator_version": EVALUATOR_VERSION,
        "expected_accounting_version": ACCOUNTING_VERSION,
        "expected_gate_policy_version": policy,
    }


def _post(client: TestClient, body: dict, key: str):
    return client.post("/api/v1/evaluations", json=body, headers={"Idempotency-Key": key})


def _gate(payload: dict, gate_id: str) -> dict:
    return {gate["gate_id"]: gate for gate in payload["gates"]}[gate_id]


def _count(engine, table: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


@pytest.fixture(scope="session")
def demo_world():
    url = os.environ.get("DISPOSABLE_DATABASE_URL", "")
    if not url:
        pytest.fail("Set DISPOSABLE_DATABASE_URL to a disposable Postgres. Do not use Railway.")
    _refuse_railway(url)
    saved = {key: os.environ.pop(key) for key in RAILWAY_ENV if key in os.environ}
    os.environ["DATABASE_URL"] = url
    engine = None
    try:
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "alembic"))
        command.upgrade(config, "head")
        engine = create_database_engine(url)
        _insert_workflow(engine)
        cohorts = {
            ACCEPTANCE_COHORT_ID: _insert_cohort(engine, ACCEPTANCE_COHORT_ID, acceptance_cases(), "acceptance"),
            "synthetic-demo-safety": _insert_cohort(
                engine,
                "synthetic-demo-safety",
                build_cases("SYN-X", 100, label_overrides={80: PRIVILEGED_LABEL}),
                "acceptance",
            ),
            "synthetic-demo-inconclusive": _insert_cohort(
                engine,
                "synthetic-demo-inconclusive",
                build_cases("SYN-I", 100, drop_labels={3}),
                "acceptance",
            ),
            "synthetic-demo-short": _insert_cohort(engine, "synthetic-demo-short", build_cases("SYN-S", 99), "acceptance"),
            "synthetic-demo-zero": _insert_cohort(engine, "synthetic-demo-zero", privileged_only_cases(), "acceptance"),
            VERIFICATION_COHORT_ID: _insert_cohort(engine, VERIFICATION_COHORT_ID, verification_cases(), "verification"),
        }
        application = create_app(engine)
        with TestClient(application) as client:
            revisions = {
                "premium": _publish(client, PREMIUM),
                "economy": _publish(client, ECONOMY),
                "deterministic": _publish(client, DETERMINISTIC),
            }
            yield {"engine": engine, "client": client, "revisions": revisions, "manifests": cohorts}
    finally:
        if engine is not None:
            engine.dispose()
        os.environ.update(saved)


def test_eligible_demo_evaluation_is_persisted_from_execution_records(demo_world) -> None:
    client = demo_world["client"]
    revisions = demo_world["revisions"]
    body = _body(
        ACCEPTANCE_COHORT_ID,
        demo_world["manifests"][ACCEPTANCE_COHORT_ID],
        revisions["premium"],
        revisions["economy"],
        SYNTHETIC_DEMO_POLICY_VERSION,
    )
    created = _post(client, body, "demo-eligible")
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["eligible"] is True
    assert payload["status"] == "completed_eligible"
    assert payload["eligibility_authoritative"] is True
    assert payload["production_authority"] is False
    assert payload["case_count"] == 100
    assert payload["provenance"]["gate_policy_version"] == SYNTHETIC_DEMO_POLICY_VERSION
    assert payload["provenance"]["runtime_scope"] == "synthetic-demo"
    assert {gate["status"] for gate in payload["gates"]} == {"pass"}
    baseline_cost = payload["economics"]["baseline"]["execution_cost_micro_usd"]
    candidate_cost = payload["economics"]["candidate"]["execution_cost_micro_usd"]
    baseline_success = payload["economics"]["baseline"]["verified_success_count"]
    candidate_success = payload["economics"]["candidate"]["verified_success_count"]
    assert candidate_cost * baseline_success < baseline_cost * candidate_success
    assert payload["economics"]["modeled_allocations"]["included_in_primary_quotient"] is False
    with demo_world["engine"].connect() as connection:
        run_id = connection.execute(
            text(
                """
                SELECT candidate_run_id FROM evaluation_case
                WHERE evaluation_id = :evaluation_id AND case_id = 'SYN-D-000'
                """
            ),
            {"evaluation_id": payload["evaluation_id"]},
        ).scalar_one()
        attempts = connection.execute(
            text(
                """
                SELECT status, method_id FROM attempt_record
                WHERE run_id = :run_id ORDER BY attempt_ordinal
                """
            ),
            {"run_id": run_id},
        ).mappings().all()
    assert [dict(row) for row in attempts] == [
        {"status": "failed", "method_id": "economy"},
        {"status": "succeeded", "method_id": "premium"},
    ]
    assert APPROVED_ACTIVATION_POLICIES == frozenset()


def test_ineligible_demo_cohorts_fail_closed(demo_world) -> None:
    client = demo_world["client"]
    revisions = demo_world["revisions"]
    manifests = demo_world["manifests"]
    cases = [
        ("demo-safety", "synthetic-demo-safety", revisions["premium"], revisions["deterministic"], "safety", "critical_violation"),
        ("demo-quality", ACCEPTANCE_COHORT_ID, revisions["premium"], revisions["deterministic"], "quality", "verified_success_regression"),
        ("demo-latency", ACCEPTANCE_COHORT_ID, revisions["economy"], revisions["premium"], "latency", "latency_regression"),
        ("demo-equal", ACCEPTANCE_COHORT_ID, revisions["economy"], revisions["economy"], "economic", "not_strictly_cheaper"),
        ("demo-inconclusive", "synthetic-demo-inconclusive", revisions["premium"], revisions["economy"], "completeness", "inconclusive_assessment"),
        ("demo-short", "synthetic-demo-short", revisions["premium"], revisions["economy"], "completeness", "insufficient_sample"),
        ("demo-zero", "synthetic-demo-zero", revisions["premium"], revisions["premium"], "economic", "zero_verified_success_denominator"),
    ]
    for key, cohort_id, baseline, candidate, gate_id, reason in cases:
        created = _post(
            client,
            _body(cohort_id, manifests[cohort_id], baseline, candidate, SYNTHETIC_DEMO_POLICY_VERSION),
            key,
        )
        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["eligible"] is False
        assert payload["production_authority"] is False
        assert _gate(payload, gate_id)["reason_code"] == reason


def test_v0_policy_on_the_demo_cohort_stays_ineligible(demo_world) -> None:
    revisions = demo_world["revisions"]
    created = _post(
        demo_world["client"],
        _body(
            ACCEPTANCE_COHORT_ID,
            demo_world["manifests"][ACCEPTANCE_COHORT_ID],
            revisions["premium"],
            revisions["economy"],
            GATE_POLICY_VERSION,
        ),
        "demo-v0",
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["eligible"] is False
    assert payload["eligibility_authoritative"] is False
    assert _gate(payload, "quality")["reason_code"] == "threshold_not_approved"
    assert _gate(payload, "economic")["reason_code"] == "noninferiority_not_approved"


def test_unknown_policy_and_forged_eligibility_write_nothing(demo_world) -> None:
    engine = demo_world["engine"]
    revisions = demo_world["revisions"]
    before_runs = _count(engine, "execution_run")
    before_evaluations = _count(engine, "evaluation_run")
    body = _body(
        ACCEPTANCE_COHORT_ID,
        demo_world["manifests"][ACCEPTANCE_COHORT_ID],
        revisions["premium"],
        revisions["economy"],
        "gate-policy-forged",
    )
    rejected = _post(demo_world["client"], body, "demo-forged-policy")
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "version_mismatch"
    forged = dict(body, expected_gate_policy_version=SYNTHETIC_DEMO_POLICY_VERSION, eligible=True)
    forged_response = _post(demo_world["client"], forged, "demo-forged-eligible")
    assert forged_response.status_code == 422
    assert _count(engine, "execution_run") == before_runs
    assert _count(engine, "evaluation_run") == before_evaluations


def test_production_runtime_blocks_an_otherwise_eligible_cohort(demo_world, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTION_OPTIMIZER_RUNTIME_SCOPE", "production")
    revisions = demo_world["revisions"]
    created = _post(
        demo_world["client"],
        _body(
            ACCEPTANCE_COHORT_ID,
            demo_world["manifests"][ACCEPTANCE_COHORT_ID],
            revisions["premium"],
            revisions["economy"],
            SYNTHETIC_DEMO_POLICY_VERSION,
        ),
        "demo-production-runtime",
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["eligible"] is False
    assert payload["provenance"]["runtime_scope"] == "production"
    assert _gate(payload, "safety")["reason_code"] == "production_runtime"


def test_verification_cohort_does_not_overlap_acceptance_cases(demo_world) -> None:
    with demo_world["engine"].connect() as connection:
        rows = connection.execute(
            text("SELECT cohort_id, case_ids, purpose FROM cohort_manifest WHERE workflow_id = :workflow_id"),
            {"workflow_id": DEMO_WORKFLOW_ID},
        ).mappings().all()
    def _ids(raw: object) -> set[str]:
        if isinstance(raw, str):
            raw = json.loads(raw)
        return set(raw)

    by_id = {row["cohort_id"]: row for row in rows}
    acceptance = _ids(by_id[ACCEPTANCE_COHORT_ID]["case_ids"])
    verification = _ids(by_id[VERIFICATION_COHORT_ID]["case_ids"])
    assert by_id[VERIFICATION_COHORT_ID]["purpose"] == "verification"
    assert acceptance.isdisjoint(verification)
    assert "SD-081" not in acceptance
    assert len(acceptance) == 100
    assert len(verification) == 20
