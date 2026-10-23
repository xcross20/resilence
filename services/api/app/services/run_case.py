import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.label_reader import fetch_reference_label
from app.db.runtime_reader import fetch_runtime_case
from app.domain.assessment import assess_outcome
from app.domain.execution import execute_observed
from app.domain.ids import stable_id
from app.domain.routing import STEP_ID
from app.domain.strategy import StrategyDocument, canonical_json, revision_sha256
from app.services.errors import ApiError

ACTOR = "local-operator"
OPERATION = "execute_case"


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _load_strategy(session: Session, workflow_id: str, revision: str) -> StrategyDocument:
    row = session.execute(
        text(
            """
            SELECT workflow_id, canonical_json
            FROM strategy_revision
            WHERE revision_sha256 = :revision
            """
        ),
        {"revision": revision},
    ).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "revision_not_found", "Strategy revision does not exist")
    if row["workflow_id"] != workflow_id:
        raise ApiError(409, "revision_workflow_mismatch", "Strategy revision belongs to a different workflow")
    document = StrategyDocument.model_validate(json.loads(row["canonical_json"]))
    if revision_sha256(document) != revision:
        raise ApiError(409, "revision_integrity", "Stored strategy does not match its revision id")
    return document


def _evidence(session: Session, run_id: str) -> dict:
    run = session.execute(
        text(
            """
            SELECT run_id, cohort_id, case_id, strategy_revision, workflow_version,
                   fixture_version, status, correlation_id, started_at, completed_at
            FROM execution_run WHERE run_id = :run_id
            """
        ),
        {"run_id": run_id},
    ).mappings().one()
    case = session.execute(
        text("SELECT case_id, cohort_id, request_text FROM case_input WHERE cohort_id = :cohort_id AND case_id = :case_id"),
        {"cohort_id": run["cohort_id"], "case_id": run["case_id"]},
    ).mappings().one()
    observation = session.execute(
        text(
            """
            SELECT observation_id, observed_category, confidence_bps, classifier_version, evidence_origin
            FROM classification_observation
            WHERE cohort_id = :cohort_id AND case_id = :case_id
            """
        ),
        {"cohort_id": run["cohort_id"], "case_id": run["case_id"]},
    ).mappings().one()
    label = session.execute(
        text(
            """
            SELECT reference_category, expected_disposition, expected_resolution, rubric_version, label_origin
            FROM reference_label
            WHERE cohort_id = :cohort_id AND case_id = :case_id
            """
        ),
        {"cohort_id": run["cohort_id"], "case_id": run["case_id"]},
    ).mappings().one_or_none()
    decisions = session.execute(
        text(
            """
            SELECT d.decision_id, d.run_id, d.step_id, d.observation_id, d.matched_rule_id,
                   d.selected_method, d.reason_code
            FROM decision_record AS d
            JOIN attempt_record AS a ON a.decision_id = d.decision_id
            WHERE d.run_id = :run_id
            ORDER BY a.attempt_ordinal
            """
        ),
        {"run_id": run_id},
    ).mappings().all()
    attempts = session.execute(
        text(
            """
            SELECT attempt_id, decision_id, attempt_ordinal, method_id, method_version, input_digest,
                   output_digest, produced_disposition, produced_resolution, simulated_latency_ms,
                   status, evidence_origin
            FROM attempt_record WHERE run_id = :run_id ORDER BY attempt_ordinal
            """
        ),
        {"run_id": run_id},
    ).mappings().all()
    costs = session.execute(
        text(
            """
            SELECT c.cost_entry_id, c.attempt_id, c.amount_micro_usd, c.cost_type,
                   c.price_book_version, c.evidence_origin
            FROM cost_entry AS c
            JOIN attempt_record AS a ON a.attempt_id = c.attempt_id
            WHERE a.run_id = :run_id
            ORDER BY a.attempt_ordinal
            """
        ),
        {"run_id": run_id},
    ).mappings().all()
    assessment = session.execute(
        text(
            """
            SELECT assessment_id, evaluator_version, rubric_version, disposition_correct, resolution_correct,
                   verdict, reason_code, correct_escalation, critical_violation, supporting_evidence_ids
            FROM outcome_assessment WHERE run_id = :run_id
            """
        ),
        {"run_id": run_id},
    ).mappings().one()
    return {
        "run": {
            "run_id": run["run_id"],
            "strategy_revision": run["strategy_revision"],
            "workflow_version": run["workflow_version"],
            "fixture_version": run["fixture_version"],
            "status": run["status"],
            "correlation_id": run["correlation_id"],
            "started_at": run["started_at"].isoformat(),
            "completed_at": run["completed_at"].isoformat(),
        },
        "case": dict(case),
        "observation": dict(observation),
        "reference_label": None if label is None else dict(label),
        "decisions": [dict(row) for row in decisions],
        "attempts": [dict(row) for row in attempts],
        "costs": [dict(row) for row in costs],
        "assessment": dict(assessment),
    }


def _is_unique_violation(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == "23505"


def _stored_response(session: Session, idempotency_key: str, body_sha256: str, operation: str) -> tuple[int, dict] | None:
    existing = session.execute(
        text(
            """
            SELECT body_sha256, status_code, response_json
            FROM idempotency_key
            WHERE actor = :actor AND operation = :operation AND idempotency_key = :idempotency_key
            """
        ),
        {"actor": ACTOR, "operation": operation, "idempotency_key": idempotency_key},
    ).mappings().one_or_none()
    if existing is None:
        return None
    if existing["body_sha256"] != body_sha256:
        raise ApiError(409, "idempotency_conflict", "Idempotency-Key was reused with a different request body")
    stored = existing["response_json"]
    if isinstance(stored, str):
        stored = json.loads(stored)
    return existing["status_code"], stored


def run_idempotent(session: Session, *, operation: str, body: dict, idempotency_key: str, work) -> tuple[int, dict]:
    """Replay a committed winner after SQLSTATE 23505. A second miss stays a 409."""
    body_sha256 = _digest(body)
    try:
        return work()
    except IntegrityError as exc:
        # PostgreSQL aborts the losing transaction. The winner has committed.
        session.rollback()
        if not _is_unique_violation(exc):
            raise
        stored = _stored_response(session, idempotency_key, body_sha256, operation)
        if stored is not None:
            return stored
        try:
            return work()
        except IntegrityError as retry_exc:
            session.rollback()
            if not _is_unique_violation(retry_exc):
                raise
            stored = _stored_response(session, idempotency_key, body_sha256, operation)
            if stored is None:
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "Idempotency-Key conflicted and no stored result was found",
                ) from retry_exc
            return stored


def execute_case(session: Session, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    """Persist one run. A concurrent unique conflict replays the committed winner."""
    return run_idempotent(
        session,
        operation=OPERATION,
        body=body,
        idempotency_key=idempotency_key,
        work=lambda: _execute_case_once(session, body, idempotency_key, correlation_id),
    )


def load_strategy(session: Session, workflow_id: str, revision: str) -> StrategyDocument:
    return _load_strategy(session, workflow_id, revision)


def execute_case_in_transaction(session: Session, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    """Insert one run into the caller's transaction. The caller commits and owns idempotency."""
    return _execute_case_once(
        session,
        body,
        idempotency_key,
        correlation_id,
        commit=False,
        persist_idempotency=False,
    )


def _execute_case_once(
    session: Session,
    body: dict,
    idempotency_key: str,
    correlation_id: str,
    *,
    commit: bool = True,
    persist_idempotency: bool = True,
) -> tuple[int, dict]:
    body_sha256 = _digest(body)
    if persist_idempotency:
        stored = _stored_response(session, idempotency_key, body_sha256, OPERATION)
        if stored is not None:
            return stored

    runtime = fetch_runtime_case(session, body["cohort_id"], body["case_id"])
    if runtime is None or runtime.workflow_id != body["workflow_id"]:
        raise ApiError(404, "case_not_found", "Case is not in the requested workflow cohort")
    document = _load_strategy(session, body["workflow_id"], body["revision_sha256"])
    trace = execute_observed(document, runtime.observed_category)
    expectation = fetch_reference_label(session, runtime.cohort_id, runtime.case_id)
    final = trace.final_attempt
    verdict = assess_outcome(
        produced_disposition=final.produced_disposition,
        produced_resolution=final.produced_resolution,
        expectation=expectation,
    )
    now = datetime.now(timezone.utc)
    run_id = stable_id("run", runtime.cohort_id, runtime.case_id, body["revision_sha256"], idempotency_key)
    session.execute(
        text(
            """
            INSERT INTO execution_run (
                run_id, cohort_id, case_id, strategy_revision, workflow_version, fixture_version,
                status, correlation_id, started_at, completed_at
            )
            VALUES (
                :run_id, :cohort_id, :case_id, :strategy_revision, :workflow_version, :fixture_version,
                'completed', :correlation_id, :started_at, :completed_at
            )
            """
        ),
        {
            "run_id": run_id,
            "cohort_id": runtime.cohort_id,
            "case_id": runtime.case_id,
            "strategy_revision": body["revision_sha256"],
            "workflow_version": runtime.workflow_version,
            "fixture_version": runtime.fixture_version,
            "correlation_id": correlation_id,
            "started_at": now,
            "completed_at": now,
        },
    )
    evidence_ids: list[str] = []
    for ordinal, step in enumerate(trace.steps, start=1):
        decision_id = stable_id("dec", run_id, str(ordinal))
        attempt_id = stable_id("att", run_id, str(ordinal))
        cost_id = stable_id("cost", attempt_id)
        evidence_ids.extend([decision_id, attempt_id, cost_id])
        session.execute(
            text(
                """
                INSERT INTO decision_record (
                    decision_id, run_id, step_id, observation_id, matched_rule_id, selected_method, reason_code
                )
                VALUES (
                    :decision_id, :run_id, :step_id, :observation_id, :matched_rule_id, :selected_method, :reason_code
                )
                """
            ),
            {
                "decision_id": decision_id,
                "run_id": run_id,
                "step_id": STEP_ID,
                "observation_id": runtime.observation_id,
                "matched_rule_id": step.decision.matched_rule_id,
                "selected_method": step.decision.selected_method,
                "reason_code": step.decision.reason_code,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO attempt_record (
                    attempt_id, run_id, decision_id, attempt_ordinal, method_id, method_version,
                    input_digest, output_digest, produced_disposition, produced_resolution,
                    simulated_latency_ms, status, evidence_origin
                )
                VALUES (
                    :attempt_id, :run_id, :decision_id, :attempt_ordinal, :method_id, :method_version,
                    :input_digest, :output_digest, :produced_disposition, :produced_resolution,
                    :simulated_latency_ms, :status, :evidence_origin
                )
                """
            ),
            {
                "attempt_id": attempt_id,
                "run_id": run_id,
                "decision_id": decision_id,
                "attempt_ordinal": ordinal,
                "method_id": step.attempt.method_id,
                "method_version": step.attempt.method_version,
                "input_digest": step.attempt.input_digest,
                "output_digest": step.attempt.output_digest,
                "produced_disposition": step.attempt.produced_disposition,
                "produced_resolution": step.attempt.produced_resolution,
                "simulated_latency_ms": step.attempt.simulated_latency_ms,
                "status": step.attempt.status,
                "evidence_origin": step.attempt.evidence_origin,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO cost_entry (
                    cost_entry_id, attempt_id, amount_micro_usd, cost_type, price_book_version, evidence_origin
                )
                VALUES (
                    :cost_entry_id, :attempt_id, :amount_micro_usd, 'execution', :price_book_version, :evidence_origin
                )
                """
            ),
            {
                "cost_entry_id": cost_id,
                "attempt_id": attempt_id,
                "amount_micro_usd": step.attempt.amount_micro_usd,
                "price_book_version": step.attempt.price_book_version,
                "evidence_origin": step.attempt.evidence_origin,
            },
        )
    session.execute(
        text(
            """
            INSERT INTO outcome_assessment (
                assessment_id, run_id, evaluator_version, rubric_version, disposition_correct,
                resolution_correct, verdict, reason_code, correct_escalation, critical_violation,
                supporting_evidence_ids
            )
            VALUES (
                :assessment_id, :run_id, :evaluator_version, :rubric_version, :disposition_correct,
                :resolution_correct, :verdict, :reason_code, :correct_escalation, :critical_violation,
                CAST(:supporting_evidence_ids AS json)
            )
            """
        ),
        {
            "assessment_id": stable_id("oa", run_id),
            "run_id": run_id,
            "evaluator_version": verdict.evaluator_version,
            "rubric_version": verdict.rubric_version,
            "disposition_correct": verdict.disposition_correct,
            "resolution_correct": verdict.resolution_correct,
            "verdict": verdict.verdict,
            "reason_code": verdict.reason_code,
            "correct_escalation": verdict.correct_escalation,
            "critical_violation": verdict.critical_violation,
            "supporting_evidence_ids": json.dumps(evidence_ids),
        },
    )
    evidence = _evidence(session, run_id)
    if persist_idempotency:
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
                "operation": OPERATION,
                "idempotency_key": idempotency_key,
                "body_sha256": body_sha256,
                "response_json": json.dumps(evidence),
            },
        )
    if commit:
        session.commit()
    return 201, evidence


def read_evidence(session: Session, run_id: str) -> dict:
    exists = session.execute(text("SELECT run_id FROM execution_run WHERE run_id = :run_id"), {"run_id": run_id}).one_or_none()
    if exists is None:
        raise ApiError(404, "run_not_found", "Execution run does not exist")
    return _evidence(session, run_id)


def store_revision(session: Session, document: StrategyDocument) -> tuple[int, dict]:
    revision = revision_sha256(document)
    canonical = canonical_json(document)
    inserted = session.execute(
        text(
            """
            INSERT INTO strategy_revision (revision_sha256, workflow_id, schema_version, canonical_json)
            VALUES (:revision_sha256, :workflow_id, :schema_version, :canonical_json)
            ON CONFLICT (revision_sha256) DO NOTHING
            """
        ),
        {
            "revision_sha256": revision,
            "workflow_id": document.workflow_id,
            "schema_version": document.schema_version,
            "canonical_json": canonical,
        },
    ).rowcount
    session.commit()
    status = 201 if inserted else 200
    return status, {"revision_sha256": revision, "workflow_id": document.workflow_id, "canonical_json": json.loads(canonical)}
