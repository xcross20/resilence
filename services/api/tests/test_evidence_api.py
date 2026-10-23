import json
from pathlib import Path

from sqlalchemy import text

from app.db.models import FORBIDDEN_ON_RUNTIME_VIEW, RUNTIME_VIEW_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = json.loads((ROOT / "app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))
BODY = {
    "workflow_id": "service-desk",
    "cohort_id": "acceptance-sd081",
    "case_id": "SD-081",
    "revision_sha256": "",
}


def post_strategy(client) -> str:
    response = client.post("/api/v1/strategies/revisions", json=STRATEGY)
    assert response.status_code == 201, response.text
    return response.json()["revision_sha256"]


def test_sd081_evidence_chain_keeps_the_label_out_of_the_decision(client, engine) -> None:
    revision = post_strategy(client)
    body = dict(BODY)
    body["revision_sha256"] = revision
    created = client.post("/api/v1/executions", json=body, headers={"Idempotency-Key": "sd081-once"})
    assert created.status_code == 201, created.text
    evidence = created.json()
    fetched = client.get(f"/api/v1/executions/{evidence['run']['run_id']}/evidence")
    assert fetched.status_code == 200
    assert fetched.json() == evidence

    assert evidence["observation"]["observed_category"] == "ambiguous"
    assert evidence["reference_label"]["reference_category"] == "privileged"
    assert evidence["observation"]["evidence_origin"] == "synthetic_simulated"
    assert evidence["reference_label"]["label_origin"] == "synthetic_rubric"
    decision = evidence["decisions"][0]
    attempt = evidence["attempts"][0]
    cost = evidence["costs"][0]
    assessment = evidence["assessment"]
    assert decision["reason_code"] == "matched_rule"
    assert decision["matched_rule_id"] == "R2"
    assert decision["selected_method"] == "premium"
    assert "reference_category" not in decision
    assert "expected_disposition" not in decision
    assert "verdict" not in decision
    assert attempt["produced_disposition"] == "escalated"
    assert attempt["produced_resolution"] == "synthetic-escalation"
    assert attempt["evidence_origin"] == "synthetic_simulated"
    assert cost["amount_micro_usd"] == 19800
    assert cost["cost_type"] == "execution"
    assert cost["price_book_version"] == "synthetic-price-v2"
    assert cost["evidence_origin"] == "synthetic_simulated"
    assert assessment["verdict"] == "correct_escalation"
    assert assessment["disposition_correct"] is True
    assert assessment["resolution_correct"] is True
    assert assessment["verdict"] != "verified_success"
    assert assessment["critical_violation"] is False

    with engine.connect() as connection:
        columns = connection.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'runtime_case_v' ORDER BY ordinal_position
                """
            )
        ).scalars().all()
    assert tuple(columns) == RUNTIME_VIEW_COLUMNS
    assert not set(columns) & set(FORBIDDEN_ON_RUNTIME_VIEW)


def test_malformed_strategy_and_execution_write_nothing(client, engine) -> None:
    broken = json.loads(json.dumps(STRATEGY))
    broken["rules"][0]["when"]["observed_category_in"] = ["vpn-outage"]
    response = client.post("/api/v1/strategies/revisions", json=broken)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    extra = dict(BODY)
    extra["revision_sha256"] = "sha256:" + ("a" * 64)
    extra["reference_category"] = "privileged"
    rejected = client.post("/api/v1/executions", json=extra, headers={"Idempotency-Key": "bad"})
    assert rejected.status_code == 422
    missing_key = client.post("/api/v1/executions", json={key: value for key, value in extra.items() if key != "reference_category"})
    assert missing_key.status_code == 422
    with engine.connect() as connection:
        revisions = connection.execute(text("SELECT count(*) FROM strategy_revision")).scalar_one()
        runs = connection.execute(text("SELECT count(*) FROM execution_run")).scalar_one()
    assert revisions == 0
    assert runs == 0


def test_workflow_read_model_has_no_active_policy(client) -> None:
    response = client.get("/api/v1/workflows/service-desk")
    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "service-desk"
    assert body["active_policy"] is None
    assert body["cohorts"][0]["cohort_id"] == "acceptance-sd081"
    assert body["cohorts"][0]["case_ids"] == ["SD-081"]
