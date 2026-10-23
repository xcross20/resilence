import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.runtime_reader import fetch_runtime_case
from app.domain.assessment import EVALUATOR_VERSION
from app.domain.gates import (
    ACCOUNTING_VERSION,
    GATE_POLICY_VERSION,
    MODELED_INFRASTRUCTURE_MICRO_USD,
    MODELED_LABOR_MICRO_USD,
    MODELED_ORIGIN,
    MODELED_RISK_MICRO_USD,
    PRIMARY_LIMITATION,
    execution_cost_per_verified_success,
    judge_gates,
)
from app.domain.ids import stable_id
from app.domain.pricing import load_price_book
from app.services.errors import ApiError
from app.services.run_case import ACTOR, _digest, _stored_response, execute_case_in_transaction, load_strategy, run_idempotent

EVALUATION_OPERATION = "start_evaluation"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _version_mismatch(field: str, expected: str, actual: str) -> None:
    if expected != actual:
        raise ApiError(
            409,
            "version_mismatch",
            "Evaluation version binding does not match stored evidence",
            {"field": field, "expected": expected, "actual": actual},
        )


def _case_ids(raw: object) -> list[str]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list) or not raw:
        raise ApiError(409, "cohort_incomplete", "Cohort manifest case list is unusable")
    if any(not isinstance(item, str) or not item for item in raw):
        raise ApiError(409, "cohort_incomplete", "Cohort manifest case list is unusable")
    if len(set(raw)) != len(raw):
        raise ApiError(409, "cohort_incomplete", "Cohort manifest repeats a case id")
    return list(raw)


def _sum_cost(evidence: dict) -> int:
    return sum(item["amount_micro_usd"] for item in evidence["costs"])


def _prices_match(evidence: dict, price_book_version: str) -> bool:
    costs = evidence["costs"]
    return bool(costs) and all(item["price_book_version"] == price_book_version for item in costs)


def _pair_fields(baseline: dict, candidate: dict) -> dict:
    baseline_decision = baseline["decisions"][0]
    candidate_decision = candidate["decisions"][0]
    baseline_attempt = baseline["attempts"][0]
    candidate_attempt = candidate["attempts"][0]
    route_changed = (
        baseline_decision["selected_method"] != candidate_decision["selected_method"]
        or baseline_decision["matched_rule_id"] != candidate_decision["matched_rule_id"]
        or baseline_decision["reason_code"] != candidate_decision["reason_code"]
    )
    output_changed = (
        baseline_attempt["produced_disposition"] != candidate_attempt["produced_disposition"]
        or baseline_attempt["produced_resolution"] != candidate_attempt["produced_resolution"]
    )
    verdict_changed = baseline["assessment"]["verdict"] != candidate["assessment"]["verdict"]
    return {
        "baseline_run_id": baseline["run"]["run_id"],
        "candidate_run_id": candidate["run"]["run_id"],
        "baseline_assessment_id": baseline["assessment"]["assessment_id"],
        "candidate_assessment_id": candidate["assessment"]["assessment_id"],
        "route_changed": route_changed,
        "verdict_changed": verdict_changed,
        "execution_cost_delta_micro_usd": _sum_cost(candidate) - _sum_cost(baseline),
        "first_divergent_decision_id": candidate_decision["decision_id"] if route_changed or output_changed else None,
    }


def _load_response(session: Session, evaluation_id: str) -> dict:
    row = session.execute(
        text(
            """
            SELECT evaluation_id, workflow_id, cohort_id, manifest_sha256, fixture_version,
                   price_book_version, evaluator_version, accounting_version, gate_policy_version,
                   baseline_revision, candidate_revision, status, eligible, correlation_id, created_at,
                   modeled_labor_micro_usd, modeled_infrastructure_micro_usd, modeled_risk_micro_usd,
                   modeled_origin, baseline_verified_success_count, candidate_verified_success_count,
                   baseline_correct_escalation_count, candidate_correct_escalation_count,
                   baseline_execution_cost_micro_usd, candidate_execution_cost_micro_usd,
                   baseline_quotient_micro_usd, candidate_quotient_micro_usd,
                   baseline_remainder_micro_usd, candidate_remainder_micro_usd, case_count
            FROM evaluation_run
            WHERE evaluation_id = :evaluation_id
            """
        ),
        {"evaluation_id": evaluation_id},
    ).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "evaluation_not_found", "Evaluation does not exist")
    gates = session.execute(
        text(
            """
            SELECT gate_id, status, reason_code
            FROM evaluation_gate
            WHERE evaluation_id = :evaluation_id
            ORDER BY CASE gate_id
                WHEN 'safety' THEN 1
                WHEN 'quality' THEN 2
                WHEN 'latency' THEN 3
                WHEN 'completeness' THEN 4
                WHEN 'economic' THEN 5
            END
            """
        ),
        {"evaluation_id": evaluation_id},
    ).mappings().all()
    divergent = session.execute(
        text(
            """
            SELECT case_id
            FROM evaluation_case
            WHERE evaluation_id = :evaluation_id
              AND (route_changed OR verdict_changed)
            ORDER BY case_ordinal
            """
        ),
        {"evaluation_id": evaluation_id},
    ).scalars().all()
    return {
        "evaluation_id": row["evaluation_id"],
        "workflow_id": row["workflow_id"],
        "cohort_id": row["cohort_id"],
        "status": row["status"],
        "eligible": row["eligible"],
        "eligibility_authoritative": row["gate_policy_version"] != GATE_POLICY_VERSION,
        "baseline_revision": row["baseline_revision"],
        "candidate_revision": row["candidate_revision"],
        "case_count": row["case_count"],
        "divergent_case_ids": list(divergent),
        "correlation_id": row["correlation_id"],
        "created_at": _iso(row["created_at"]),
        "provenance": {
            "manifest_sha256": row["manifest_sha256"],
            "fixture_version": row["fixture_version"],
            "price_book_version": row["price_book_version"],
            "evaluator_version": row["evaluator_version"],
            "accounting_version": row["accounting_version"],
            "gate_policy_version": row["gate_policy_version"],
            "execution_evidence_origin": "synthetic_simulated",
            "label_origin": "synthetic_rubric",
            "modeled_allocation_origin": row["modeled_origin"],
            "limitation": PRIMARY_LIMITATION,
        },
        "economics": {
            "baseline": {
                "execution_cost_micro_usd": row["baseline_execution_cost_micro_usd"],
                "verified_success_count": row["baseline_verified_success_count"],
                "correct_escalation_count": row["baseline_correct_escalation_count"],
                "cost_per_verified_success_micro_usd": row["baseline_quotient_micro_usd"],
                "remainder_micro_usd": row["baseline_remainder_micro_usd"],
            },
            "candidate": {
                "execution_cost_micro_usd": row["candidate_execution_cost_micro_usd"],
                "verified_success_count": row["candidate_verified_success_count"],
                "correct_escalation_count": row["candidate_correct_escalation_count"],
                "cost_per_verified_success_micro_usd": row["candidate_quotient_micro_usd"],
                "remainder_micro_usd": row["candidate_remainder_micro_usd"],
            },
            "modeled_allocations": {
                "labor_micro_usd": row["modeled_labor_micro_usd"],
                "infrastructure_micro_usd": row["modeled_infrastructure_micro_usd"],
                "risk_micro_usd": row["modeled_risk_micro_usd"],
                "evidence_origin": row["modeled_origin"],
                "included_in_primary_quotient": False,
            },
        },
        "gates": [dict(gate) for gate in gates],
    }


def _insert_evaluation(session: Session, evaluation_id: str, body: dict, cohort: dict, pairs: list[tuple[dict, dict]], correlation_id: str) -> dict:
    baseline_cost = sum(_sum_cost(baseline) for baseline, _candidate in pairs)
    candidate_cost = sum(_sum_cost(candidate) for _baseline, candidate in pairs)
    baseline_verified = sum(1 for baseline, _candidate in pairs if baseline["assessment"]["verdict"] == "verified_success")
    candidate_verified = sum(1 for _baseline, candidate in pairs if candidate["assessment"]["verdict"] == "verified_success")
    baseline_escalations = sum(1 for baseline, _candidate in pairs if baseline["assessment"]["verdict"] == "correct_escalation")
    candidate_escalations = sum(1 for _baseline, candidate in pairs if candidate["assessment"]["verdict"] == "correct_escalation")
    candidate_critical = sum(1 for _baseline, candidate in pairs if candidate["assessment"]["critical_violation"])
    prices_match = all(
        _prices_match(evidence, body["expected_price_book_version"])
        for pair in pairs
        for evidence in pair
    )
    any_inconclusive = any(evidence["assessment"]["verdict"] == "inconclusive" for pair in pairs for evidence in pair)
    judgment = judge_gates(
        case_count=len(cohort["case_ids"]),
        pair_count=len(pairs),
        manifest_matches=True,
        any_inconclusive=any_inconclusive,
        candidate_critical_violations=candidate_critical,
        candidate_verified_success_count=candidate_verified,
        prices_match=prices_match,
    )
    if judgment.eligible and body["expected_gate_policy_version"] == GATE_POLICY_VERSION:
        raise ApiError(409, "eligibility_not_authoritative", "Fail-closed gate policy cannot be stored as eligible")
    baseline_ratio = execution_cost_per_verified_success(baseline_cost, baseline_verified)
    candidate_ratio = execution_cost_per_verified_success(candidate_cost, candidate_verified)
    created_at = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO evaluation_run (
                evaluation_id, workflow_id, cohort_id, manifest_sha256, fixture_version,
                price_book_version, evaluator_version, accounting_version, gate_policy_version,
                baseline_revision, candidate_revision, status, eligible, correlation_id, created_at,
                modeled_labor_micro_usd, modeled_infrastructure_micro_usd, modeled_risk_micro_usd,
                modeled_origin, baseline_verified_success_count, candidate_verified_success_count,
                baseline_correct_escalation_count, candidate_correct_escalation_count,
                baseline_execution_cost_micro_usd, candidate_execution_cost_micro_usd,
                baseline_quotient_micro_usd, candidate_quotient_micro_usd,
                baseline_remainder_micro_usd, candidate_remainder_micro_usd, case_count
            )
            VALUES (
                :evaluation_id, :workflow_id, :cohort_id, :manifest_sha256, :fixture_version,
                :price_book_version, :evaluator_version, :accounting_version, :gate_policy_version,
                :baseline_revision, :candidate_revision, :status, :eligible, :correlation_id, :created_at,
                :modeled_labor_micro_usd, :modeled_infrastructure_micro_usd, :modeled_risk_micro_usd,
                :modeled_origin, :baseline_verified_success_count, :candidate_verified_success_count,
                :baseline_correct_escalation_count, :candidate_correct_escalation_count,
                :baseline_execution_cost_micro_usd, :candidate_execution_cost_micro_usd,
                :baseline_quotient_micro_usd, :candidate_quotient_micro_usd,
                :baseline_remainder_micro_usd, :candidate_remainder_micro_usd, :case_count
            )
            """
        ),
        {
            "evaluation_id": evaluation_id,
            "workflow_id": body["workflow_id"],
            "cohort_id": body["cohort_id"],
            "manifest_sha256": cohort["manifest_sha256"],
            "fixture_version": cohort["fixture_version"],
            "price_book_version": body["expected_price_book_version"],
            "evaluator_version": body["expected_evaluator_version"],
            "accounting_version": body["expected_accounting_version"],
            "gate_policy_version": body["expected_gate_policy_version"],
            "baseline_revision": body["baseline_revision"],
            "candidate_revision": body["candidate_revision"],
            "status": judgment.status,
            "eligible": judgment.eligible,
            "correlation_id": correlation_id,
            "created_at": created_at,
            "modeled_labor_micro_usd": MODELED_LABOR_MICRO_USD,
            "modeled_infrastructure_micro_usd": MODELED_INFRASTRUCTURE_MICRO_USD,
            "modeled_risk_micro_usd": MODELED_RISK_MICRO_USD,
            "modeled_origin": MODELED_ORIGIN,
            "baseline_verified_success_count": baseline_ratio.verified_success_count,
            "candidate_verified_success_count": candidate_ratio.verified_success_count,
            "baseline_correct_escalation_count": baseline_escalations,
            "candidate_correct_escalation_count": candidate_escalations,
            "baseline_execution_cost_micro_usd": baseline_ratio.execution_cost_micro_usd,
            "candidate_execution_cost_micro_usd": candidate_ratio.execution_cost_micro_usd,
            "baseline_quotient_micro_usd": baseline_ratio.quotient_micro_usd,
            "candidate_quotient_micro_usd": candidate_ratio.quotient_micro_usd,
            "baseline_remainder_micro_usd": baseline_ratio.remainder_micro_usd,
            "candidate_remainder_micro_usd": candidate_ratio.remainder_micro_usd,
            "case_count": len(pairs),
        },
    )
    for ordinal, (case_id, (baseline, candidate)) in enumerate(zip(cohort["case_ids"], pairs, strict=True), start=1):
        fields = _pair_fields(baseline, candidate)
        session.execute(
            text(
                """
                INSERT INTO evaluation_case (
                    evaluation_id, case_ordinal, case_id, baseline_run_id, candidate_run_id,
                    baseline_assessment_id, candidate_assessment_id, route_changed, verdict_changed,
                    execution_cost_delta_micro_usd, first_divergent_decision_id
                )
                VALUES (
                    :evaluation_id, :case_ordinal, :case_id, :baseline_run_id, :candidate_run_id,
                    :baseline_assessment_id, :candidate_assessment_id, :route_changed, :verdict_changed,
                    :execution_cost_delta_micro_usd, :first_divergent_decision_id
                )
                """
            ),
            {"evaluation_id": evaluation_id, "case_ordinal": ordinal, "case_id": case_id, **fields},
        )
    for gate in judgment.gates:
        session.execute(
            text(
                """
                INSERT INTO evaluation_gate (evaluation_id, gate_id, status, reason_code)
                VALUES (:evaluation_id, :gate_id, :status, :reason_code)
                """
            ),
            {
                "evaluation_id": evaluation_id,
                "gate_id": gate.gate_id,
                "status": gate.status,
                "reason_code": gate.reason_code,
            },
        )
    return _load_response(session, evaluation_id)


def _start_evaluation_once(session: Session, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    stored = _stored_response(session, idempotency_key, _digest(body), EVALUATION_OPERATION)
    if stored is not None:
        return stored
    cohort_row = session.execute(
        text(
            """
            SELECT cohort_id, workflow_id, fixture_version, manifest_sha256, case_ids
            FROM cohort_manifest
            WHERE cohort_id = :cohort_id
            """
        ),
        {"cohort_id": body["cohort_id"]},
    ).mappings().one_or_none()
    if cohort_row is None:
        raise ApiError(404, "cohort_not_found", "Cohort does not exist")
    if cohort_row["workflow_id"] != body["workflow_id"]:
        raise ApiError(409, "cohort_workflow_mismatch", "Cohort belongs to a different workflow")
    case_ids = _case_ids(cohort_row["case_ids"])
    _version_mismatch("expected_manifest_sha256", body["expected_manifest_sha256"], cohort_row["manifest_sha256"])
    _version_mismatch("expected_fixture_version", body["expected_fixture_version"], cohort_row["fixture_version"])
    _version_mismatch("expected_price_book_version", body["expected_price_book_version"], load_price_book()["version"])
    _version_mismatch("expected_evaluator_version", body["expected_evaluator_version"], EVALUATOR_VERSION)
    _version_mismatch("expected_accounting_version", body["expected_accounting_version"], ACCOUNTING_VERSION)
    _version_mismatch("expected_gate_policy_version", body["expected_gate_policy_version"], GATE_POLICY_VERSION)
    load_strategy(session, body["workflow_id"], body["baseline_revision"])
    load_strategy(session, body["workflow_id"], body["candidate_revision"])
    missing = [
        case_id
        for case_id in case_ids
        if fetch_runtime_case(session, body["cohort_id"], case_id) is None
    ]
    if missing:
        raise ApiError(
            409,
            "cohort_incomplete",
            "Cohort case has no runtime observation",
            {"missing_case_ids": missing},
        )
    evaluation_id = stable_id(
        "ev",
        body["cohort_id"],
        cohort_row["manifest_sha256"],
        body["baseline_revision"],
        body["candidate_revision"],
        idempotency_key,
    )
    pairs: list[tuple[dict, dict]] = []
    for case_id in case_ids:
        execution = {
            "workflow_id": body["workflow_id"],
            "cohort_id": body["cohort_id"],
            "case_id": case_id,
        }
        _status, baseline = execute_case_in_transaction(
            session,
            {**execution, "revision_sha256": body["baseline_revision"]},
            f"{evaluation_id}:baseline",
            correlation_id,
        )
        _status, candidate = execute_case_in_transaction(
            session,
            {**execution, "revision_sha256": body["candidate_revision"]},
            f"{evaluation_id}:candidate",
            correlation_id,
        )
        pairs.append((baseline, candidate))
    response = _insert_evaluation(
        session,
        evaluation_id,
        body,
        {
            "manifest_sha256": cohort_row["manifest_sha256"],
            "fixture_version": cohort_row["fixture_version"],
            "case_ids": case_ids,
        },
        pairs,
        correlation_id,
    )
    session.execute(
        text(
            """
            INSERT INTO idempotency_key (
                actor, operation, idempotency_key, body_sha256, status_code, response_json
            )
            VALUES (
                :actor, :operation, :idempotency_key, :body_sha256, 201, CAST(:response_json AS json)
            )
            """
        ),
        {
            "actor": ACTOR,
            "operation": EVALUATION_OPERATION,
            "idempotency_key": idempotency_key,
            "body_sha256": _digest(body),
            "response_json": json.dumps(response),
        },
    )
    session.commit()
    return 201, response


def start_evaluation(session: Session, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    return run_idempotent(
        session,
        operation=EVALUATION_OPERATION,
        body=body,
        idempotency_key=idempotency_key,
        work=lambda: _start_evaluation_once(session, body, idempotency_key, correlation_id),
    )


def read_evaluation(session: Session, evaluation_id: str) -> dict:
    return _load_response(session, evaluation_id)


def read_evaluation_cases(session: Session, evaluation_id: str, limit: int, offset: int) -> dict:
    if limit < 1 or limit > 100 or offset < 0:
        raise ApiError(422, "validation_error", "limit must be 1..100 and offset must be non-negative")
    exists = session.execute(
        text("SELECT evaluation_id FROM evaluation_run WHERE evaluation_id = :evaluation_id"),
        {"evaluation_id": evaluation_id},
    ).one_or_none()
    if exists is None:
        raise ApiError(404, "evaluation_not_found", "Evaluation does not exist")
    rows = session.execute(
        text(
            """
            SELECT case_id, case_ordinal, baseline_run_id, candidate_run_id,
                   baseline_assessment_id, candidate_assessment_id, route_changed, verdict_changed,
                   execution_cost_delta_micro_usd, first_divergent_decision_id,
                   b.verdict AS baseline_verdict, b.critical_violation AS baseline_critical_violation,
                   b.reason_code AS baseline_reason_code,
                   c.verdict AS candidate_verdict, c.critical_violation AS candidate_critical_violation,
                   c.reason_code AS candidate_reason_code
            FROM evaluation_case AS pair
            JOIN outcome_assessment AS b ON b.assessment_id = pair.baseline_assessment_id
            JOIN outcome_assessment AS c ON c.assessment_id = pair.candidate_assessment_id
            WHERE pair.evaluation_id = :evaluation_id
            ORDER BY pair.case_ordinal
            LIMIT :limit OFFSET :offset
            """
        ),
        {"evaluation_id": evaluation_id, "limit": limit, "offset": offset},
    ).mappings().all()
    return {
        "evaluation_id": evaluation_id,
        "limit": limit,
        "offset": offset,
        "cases": [dict(row) for row in rows],
    }
