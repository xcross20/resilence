import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.runtime_reader import fetch_runtime_case
from app.domain.gates import SYNTHETIC_DEMO_POLICY_VERSION, SYNTHETIC_EVIDENCE_ORIGIN, SYNTHETIC_LABEL_ORIGIN
from app.domain.ids import stable_id
from app.domain.release import (
    ReleaseDecision,
    claims_independent_holdout,
    classify_verification,
    judge_activation,
    judge_restore,
)
from app.domain.runtime_scope import server_runtime_scope
from app.fixtures.seed import manifest_sha256
from app.services.errors import ApiError
from app.services.run_case import ACTOR, _digest, _stored_response, execute_case_in_transaction, run_idempotent

ACTIVATE_OPERATION = "activate_release"
VERIFY_OPERATION = "start_verification"
RESTORE_OPERATION = "restore_release"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _require_workflow(session: Session, workflow_id: str) -> None:
    row = session.execute(
        text("SELECT workflow_id FROM workflow_definition WHERE workflow_id = :workflow_id"),
        {"workflow_id": workflow_id},
    ).one_or_none()
    if row is None:
        raise ApiError(404, "workflow_not_found", "Workflow does not exist")


def _lock_pointer(session: Session, workflow_id: str) -> dict:
    session.execute(
        text(
            """
            INSERT INTO active_policy_pointer (workflow_id, generation)
            VALUES (:workflow_id, 0)
            ON CONFLICT (workflow_id) DO NOTHING
            """
        ),
        {"workflow_id": workflow_id},
    )
    return dict(
        session.execute(
            text(
                """
                SELECT workflow_id, generation, revision_sha256, prior_revision_sha256, evaluation_id
                FROM active_policy_pointer
                WHERE workflow_id = :workflow_id
                FOR UPDATE
                """
            ),
            {"workflow_id": workflow_id},
        ).mappings().one()
    )


def _append_event(session: Session, event: dict) -> None:
    session.execute(
        text(
            """
            INSERT INTO release_event (
                event_id, workflow_id, event_type, reason_code, actor, idempotency_key,
                prior_revision, target_revision, prior_generation, resulting_generation,
                evaluation_id, verification_id, correlation_id, occurred_at, details_json
            )
            VALUES (
                :event_id, :workflow_id, :event_type, :reason_code, :actor, :idempotency_key,
                :prior_revision, :target_revision, :prior_generation, :resulting_generation,
                :evaluation_id, :verification_id, :correlation_id, :occurred_at, CAST(:details_json AS json)
            )
            """
        ),
        event,
    )


def _store(session: Session, operation: str, idempotency_key: str, body: dict, status_code: int, payload: dict) -> None:
    session.execute(
        text(
            """
            INSERT INTO idempotency_key (
                actor, operation, idempotency_key, body_sha256, status_code, response_json
            )
            VALUES (
                :actor, :operation, :idempotency_key, :body_sha256, :status_code, CAST(:response_json AS json)
            )
            """
        ),
        {
            "actor": ACTOR,
            "operation": operation,
            "idempotency_key": idempotency_key,
            "body_sha256": _digest(body),
            "status_code": status_code,
            "response_json": json.dumps(payload),
        },
    )
    session.commit()


def _event_fields(
    *,
    workflow_id: str,
    decision: ReleaseDecision,
    idempotency_key: str,
    pointer: dict,
    target_revision: str | None,
    evaluation_id: str | None,
    verification_id: str | None,
    correlation_id: str,
    details: dict,
    resulting_generation: int,
) -> dict:
    return {
        "event_id": stable_id("rel", workflow_id, decision.event_type, idempotency_key),
        "workflow_id": workflow_id,
        "event_type": decision.event_type,
        "reason_code": decision.reason_code,
        "actor": ACTOR,
        "idempotency_key": idempotency_key,
        "prior_revision": pointer["revision_sha256"],
        "target_revision": target_revision,
        "prior_generation": pointer["generation"],
        "resulting_generation": resulting_generation,
        "evaluation_id": evaluation_id,
        "verification_id": verification_id,
        "correlation_id": correlation_id,
        "occurred_at": datetime.now(timezone.utc),
        "details_json": json.dumps(details),
    }


def _response(decision: ReleaseDecision, event: dict, pointer_after: dict, correlation_id: str, details: dict) -> dict:
    return {
        "code": decision.reason_code,
        "message": decision.event_type.replace("_", " "),
        "correlation_id": correlation_id,
        "event_id": event["event_id"],
        "event_type": decision.event_type,
        "generation": pointer_after["generation"],
        "active_revision": pointer_after["revision_sha256"],
        "prior_revision": pointer_after["prior_revision_sha256"],
        "details": details,
    }


def _load_evaluation(session: Session, evaluation_id: str) -> dict | None:
    row = session.execute(
        text(
            """
            SELECT evaluation_id, workflow_id, cohort_id, candidate_revision, baseline_revision,
                   status, eligible, gate_policy_version, fixture_version, price_book_version
            FROM evaluation_run
            WHERE evaluation_id = :evaluation_id
            """
        ),
        {"evaluation_id": evaluation_id},
    ).mappings().one_or_none()
    return None if row is None else dict(row)


def _gate_statuses(session: Session, evaluation_id: str) -> dict[str, str]:
    rows = session.execute(
        text("SELECT gate_id, status FROM evaluation_gate WHERE evaluation_id = :evaluation_id"),
        {"evaluation_id": evaluation_id},
    ).mappings().all()
    return {row["gate_id"]: row["status"] for row in rows}


def _activation_provenance(session: Session, evaluation: dict | None) -> dict:
    """Read attempt and label origins. Missing rows are not treated as synthetic."""
    if evaluation is None:
        return {"evidence_origin": None, "label_origin": None, "live_provider_attempt_count": 0}
    attempts = session.execute(
        text(
            """
            SELECT count(*) AS attempt_count,
                   count(*) FILTER (WHERE attempt.evidence_origin <> :expected) AS foreign_count
            FROM attempt_record AS attempt
            JOIN evaluation_case AS pair
              ON attempt.run_id = pair.baseline_run_id OR attempt.run_id = pair.candidate_run_id
            WHERE pair.evaluation_id = :evaluation_id
            """
        ),
        {"evaluation_id": evaluation["evaluation_id"], "expected": SYNTHETIC_EVIDENCE_ORIGIN},
    ).mappings().one()
    labels = session.execute(
        text(
            """
            SELECT count(*) AS label_count,
                   count(*) FILTER (WHERE label.label_origin <> :expected) AS foreign_count
            FROM reference_label AS label
            JOIN evaluation_case AS pair ON label.case_id = pair.case_id
            WHERE pair.evaluation_id = :evaluation_id
              AND label.cohort_id = :cohort_id
            """
        ),
        {
            "evaluation_id": evaluation["evaluation_id"],
            "cohort_id": evaluation["cohort_id"],
            "expected": SYNTHETIC_LABEL_ORIGIN,
        },
    ).mappings().one()
    foreign_attempts = int(attempts["foreign_count"])
    return {
        "evidence_origin": SYNTHETIC_EVIDENCE_ORIGIN if int(attempts["attempt_count"]) > 0 and foreign_attempts == 0 else None,
        "label_origin": SYNTHETIC_LABEL_ORIGIN if int(labels["label_count"]) > 0 and int(labels["foreign_count"]) == 0 else None,
        "live_provider_attempt_count": foreign_attempts,
    }


def _apply_activation(
    session: Session,
    workflow_id: str,
    body: dict,
    expected_prior: str | None,
    baseline_revision: str | None,
) -> int:
    # Generation 0 has no active revision. Record the compared baseline so a later
    # restore returns to that revision instead of finding nothing to restore.
    return session.execute(
        text(
            """
            UPDATE active_policy_pointer
            SET generation = generation + 1,
                prior_revision_sha256 = COALESCE(revision_sha256, :baseline_revision),
                revision_sha256 = :target_revision,
                evaluation_id = :evaluation_id
            WHERE workflow_id = :workflow_id
              AND generation = :expected_generation
              AND revision_sha256 IS NOT DISTINCT FROM :expected_prior
            """
        ),
        {
            "workflow_id": workflow_id,
            "target_revision": body["candidate_revision"],
            "evaluation_id": body["evaluation_id"],
            "expected_generation": body["expected_generation"],
            "expected_prior": expected_prior,
            "baseline_revision": baseline_revision,
        },
    ).rowcount


def _apply_restore(session: Session, workflow_id: str, pointer: dict, expected_generation: int) -> int:
    return session.execute(
        text(
            """
            UPDATE active_policy_pointer
            SET generation = generation + 1,
                revision_sha256 = prior_revision_sha256,
                prior_revision_sha256 = revision_sha256,
                evaluation_id = NULL
            WHERE workflow_id = :workflow_id
              AND generation = :expected_generation
              AND revision_sha256 IS NOT DISTINCT FROM :actual_revision
            """
        ),
        {
            "workflow_id": workflow_id,
            "expected_generation": expected_generation,
            "actual_revision": pointer["revision_sha256"],
        },
    ).rowcount


def _activate_once(session: Session, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    stored = _stored_response(session, idempotency_key, _digest(body), ACTIVATE_OPERATION)
    if stored is not None:
        return stored
    _require_workflow(session, body["workflow_id"])
    pointer = _lock_pointer(session, body["workflow_id"])
    evaluation = _load_evaluation(session, body["evaluation_id"])
    gates = {} if evaluation is None else _gate_statuses(session, body["evaluation_id"])
    provenance = _activation_provenance(session, evaluation)
    decision = judge_activation(
        confirmation=body.get("confirmation"),
        expected_generation=body["expected_generation"],
        actual_generation=pointer["generation"],
        expected_prior_revision=body.get("expected_prior_revision"),
        actual_prior_revision=pointer["revision_sha256"],
        evaluation_found=evaluation is not None,
        evaluation_workflow_matches=evaluation is not None and evaluation["workflow_id"] == body["workflow_id"],
        requested_revision=body["candidate_revision"],
        evaluation_candidate_revision=None if evaluation is None else evaluation["candidate_revision"],
        evaluation_status=None if evaluation is None else evaluation["status"],
        evaluation_eligible=bool(evaluation and evaluation["eligible"]),
        gate_policy_version=None if evaluation is None else evaluation["gate_policy_version"],
        gate_statuses=gates,
        workflow_id=body["workflow_id"],
        runtime_scope=server_runtime_scope(),
        fixture_version=None if evaluation is None else evaluation["fixture_version"],
        price_book_version=None if evaluation is None else evaluation["price_book_version"],
        evidence_origin=provenance["evidence_origin"],
        label_origin=provenance["label_origin"],
        live_provider_attempt_count=provenance["live_provider_attempt_count"],
    )
    baseline_revision = None if evaluation is None else evaluation["baseline_revision"]
    if (
        decision.commit_transition
        and _apply_activation(session, body["workflow_id"], body, pointer["revision_sha256"], baseline_revision) != 1
    ):
        decision = ReleaseDecision(409, "stale_generation", False, "activation_denied")
    pointer_after = pointer if not decision.commit_transition else _lock_pointer(session, body["workflow_id"])
    policy = None if evaluation is None else evaluation["gate_policy_version"]
    details = {
        "evaluation_status": None if evaluation is None else evaluation["status"],
        "gate_policy_version": policy,
        "eligibility_authoritative": bool(
            decision.commit_transition and policy == SYNTHETIC_DEMO_POLICY_VERSION and evaluation and evaluation["eligible"]
        ),
        "production_authority": False,
        "gate_statuses": gates,
    }
    event = _event_fields(
        workflow_id=body["workflow_id"],
        decision=decision,
        idempotency_key=idempotency_key,
        pointer=pointer,
        target_revision=body["candidate_revision"],
        evaluation_id=body["evaluation_id"],
        verification_id=None,
        correlation_id=correlation_id,
        details=details,
        resulting_generation=pointer_after["generation"],
    )
    _append_event(session, event)
    payload = _response(decision, event, pointer_after, correlation_id, details)
    _store(session, ACTIVATE_OPERATION, idempotency_key, body, decision.status_code, payload)
    return decision.status_code, payload


def _case_ids(raw: object) -> list[str]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _acceptance_case_ids(session: Session, workflow_id: str) -> set[str]:
    rows = session.execute(
        text(
            """
            SELECT case_ids FROM cohort_manifest
            WHERE workflow_id = :workflow_id AND purpose = 'acceptance'
            """
        ),
        {"workflow_id": workflow_id},
    ).scalars().all()
    found: set[str] = set()
    for raw in rows:
        found.update(_case_ids(raw))
    return found


def _verify_once(session: Session, workflow_id: str, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    request_body = {"workflow_id": workflow_id, **body}
    stored = _stored_response(session, idempotency_key, _digest(request_body), VERIFY_OPERATION)
    if stored is not None:
        return stored
    _require_workflow(session, workflow_id)
    pointer = _lock_pointer(session, workflow_id)
    cohort = session.execute(
        text(
            """
            SELECT cohort_id, workflow_id, purpose, fixture_version, manifest_sha256, case_ids
            FROM cohort_manifest WHERE cohort_id = :cohort_id
            """
        ),
        {"cohort_id": body["cohort_id"]},
    ).mappings().one_or_none()
    if cohort is None or cohort["workflow_id"] != workflow_id:
        raise ApiError(404, "cohort_not_found", "Verification cohort does not exist")
    case_ids = _case_ids(cohort["case_ids"])
    overlap = [case_id for case_id in case_ids if case_id in _acceptance_case_ids(session, workflow_id)]
    bound_manifest = manifest_sha256(case_ids, cohort["fixture_version"])
    status = "inconclusive"
    reason = "inconclusive"
    http_status = 409
    execute = False
    if cohort["purpose"] != "verification":
        status, reason = "denied_cohort_purpose", "cohort_purpose"
    elif body["expected_manifest_sha256"] != cohort["manifest_sha256"] or body["expected_manifest_sha256"] != bound_manifest:
        status, reason = "denied_version_mismatch", "version_mismatch"
    elif body["expected_fixture_version"] != cohort["fixture_version"]:
        status, reason = "denied_version_mismatch", "version_mismatch"
    elif body["expected_generation"] != pointer["generation"]:
        status, reason = "denied_stale_generation", "stale_generation"
    elif overlap:
        status, reason = "denied_overlap", "verification_cohort_overlap"
    elif pointer["revision_sha256"] is None:
        status, reason = "denied_no_active_policy", "no_active_policy"
    elif body.get("expected_active_revision") != pointer["revision_sha256"]:
        status, reason = "denied_wrong_revision", "wrong_revision"
    else:
        missing = [case_id for case_id in case_ids if fetch_runtime_case(session, body["cohort_id"], case_id) is None]
        if missing or not case_ids:
            status, reason = "denied_incomplete", "cohort_incomplete"
        else:
            execute = True
    verification_id = stable_id("ver", workflow_id, body["cohort_id"], cohort["manifest_sha256"], idempotency_key)
    assessments: list[dict] = []
    if execute:
        for ordinal, case_id in enumerate(case_ids, start=1):
            _code, evidence = execute_case_in_transaction(
                session,
                {
                    "workflow_id": workflow_id,
                    "cohort_id": body["cohort_id"],
                    "case_id": case_id,
                    "revision_sha256": pointer["revision_sha256"],
                },
                f"{verification_id}:verify",
                correlation_id,
            )
            assessment = evidence["assessment"]
            assessments.append(
                {
                    "case_ordinal": ordinal,
                    "case_id": case_id,
                    "run_id": evidence["run"]["run_id"],
                    "assessment_id": assessment["assessment_id"],
                    "verdict": assessment["verdict"],
                    "critical_violation": assessment["critical_violation"],
                }
            )
        status = classify_verification(assessments, overlap)
        reason = status
        http_status = 201
    holdout = claims_independent_holdout(status=status, overlap_case_ids=overlap)
    session.execute(
        text(
            """
            INSERT INTO verification_run (
                verification_id, workflow_id, cohort_id, manifest_sha256, activated_revision,
                overlap_case_ids, claims_independent_holdout, status, reason_code, correlation_id, created_at
            )
            VALUES (
                :verification_id, :workflow_id, :cohort_id, :manifest_sha256, :activated_revision,
                CAST(:overlap_case_ids AS json), :claims_independent_holdout, :status, :reason_code,
                :correlation_id, :created_at
            )
            """
        ),
        {
            "verification_id": verification_id,
            "workflow_id": workflow_id,
            "cohort_id": body["cohort_id"],
            "manifest_sha256": cohort["manifest_sha256"],
            "activated_revision": pointer["revision_sha256"],
            "overlap_case_ids": json.dumps(overlap),
            "claims_independent_holdout": holdout,
            "status": status,
            "reason_code": reason,
            "correlation_id": correlation_id,
            "created_at": datetime.now(timezone.utc),
        },
    )
    for item in assessments:
        session.execute(
            text(
                """
                INSERT INTO verification_case (
                    verification_id, case_ordinal, case_id, run_id, assessment_id, verdict, critical_violation
                )
                VALUES (
                    :verification_id, :case_ordinal, :case_id, :run_id, :assessment_id, :verdict, :critical_violation
                )
                """
            ),
            {"verification_id": verification_id, **item},
        )
    event_type = "verification_recorded" if execute else "verification_denied"
    decision = ReleaseDecision(http_status, reason, False, event_type)
    details = {
        "verification_id": verification_id,
        "status": status,
        "overlap_case_ids": overlap,
        "claims_independent_holdout": holdout,
        "release_authorized": False,
        "limitation": "Synthetic paired results are not statistical proof of real-world model equivalence.",
    }
    event = _event_fields(
        workflow_id=workflow_id,
        decision=decision,
        idempotency_key=idempotency_key,
        pointer=pointer,
        target_revision=pointer["revision_sha256"],
        evaluation_id=pointer["evaluation_id"],
        verification_id=verification_id,
        correlation_id=correlation_id,
        details=details,
        resulting_generation=pointer["generation"],
    )
    _append_event(session, event)
    payload = _response(decision, event, pointer, correlation_id, details)
    payload["verification_id"] = verification_id
    _store(session, VERIFY_OPERATION, idempotency_key, request_body, http_status, payload)
    return http_status, payload


def _restore_once(session: Session, workflow_id: str, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    request_body = {"workflow_id": workflow_id, **body}
    stored = _stored_response(session, idempotency_key, _digest(request_body), RESTORE_OPERATION)
    if stored is not None:
        return stored
    _require_workflow(session, workflow_id)
    pointer = _lock_pointer(session, workflow_id)
    decision = judge_restore(
        confirmation=body.get("confirmation"),
        expected_generation=body["expected_generation"],
        actual_generation=pointer["generation"],
        actual_revision=pointer["revision_sha256"],
        recorded_prior_revision=pointer["prior_revision_sha256"],
    )
    if decision.commit_transition and _apply_restore(session, workflow_id, pointer, body["expected_generation"]) != 1:
        decision = ReleaseDecision(409, "stale_generation", False, "restoration_denied")
    pointer_after = pointer if not decision.commit_transition else _lock_pointer(session, workflow_id)
    details = {"release_authorized": False}
    event = _event_fields(
        workflow_id=workflow_id,
        decision=decision,
        idempotency_key=idempotency_key,
        pointer=pointer,
        target_revision=pointer["prior_revision_sha256"],
        evaluation_id=pointer["evaluation_id"],
        verification_id=None,
        correlation_id=correlation_id,
        details=details,
        resulting_generation=pointer_after["generation"],
    )
    _append_event(session, event)
    payload = _response(decision, event, pointer_after, correlation_id, details)
    _store(session, RESTORE_OPERATION, idempotency_key, request_body, decision.status_code, payload)
    return decision.status_code, payload


def activate_release(session: Session, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    return run_idempotent(
        session,
        operation=ACTIVATE_OPERATION,
        body=body,
        idempotency_key=idempotency_key,
        work=lambda: _activate_once(session, body, idempotency_key, correlation_id),
    )


def start_verification(session: Session, workflow_id: str, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    stored_body = {"workflow_id": workflow_id, **body}
    return run_idempotent(
        session,
        operation=VERIFY_OPERATION,
        body=stored_body,
        idempotency_key=idempotency_key,
        work=lambda: _verify_once(session, workflow_id, body, idempotency_key, correlation_id),
    )


def restore_release(session: Session, workflow_id: str, body: dict, idempotency_key: str, correlation_id: str) -> tuple[int, dict]:
    stored_body = {"workflow_id": workflow_id, **body}
    return run_idempotent(
        session,
        operation=RESTORE_OPERATION,
        body=stored_body,
        idempotency_key=idempotency_key,
        work=lambda: _restore_once(session, workflow_id, body, idempotency_key, correlation_id),
    )


def read_pointer(session: Session, workflow_id: str) -> dict:
    _require_workflow(session, workflow_id)
    row = session.execute(
        text(
            """
            SELECT generation, revision_sha256, prior_revision_sha256, evaluation_id
            FROM active_policy_pointer WHERE workflow_id = :workflow_id
            """
        ),
        {"workflow_id": workflow_id},
    ).mappings().one_or_none()
    if row is None or row["generation"] == 0:
        return {
            "workflow_id": workflow_id,
            "generation": 0 if row is None else row["generation"],
            "active_revision": None,
            "prior_revision": None,
            "evaluation_id": None,
        }
    return {
        "workflow_id": workflow_id,
        "generation": row["generation"],
        "active_revision": row["revision_sha256"],
        "prior_revision": row["prior_revision_sha256"],
        "evaluation_id": row["evaluation_id"],
    }


def read_events(session: Session, workflow_id: str) -> dict:
    _require_workflow(session, workflow_id)
    rows = session.execute(
        text(
            """
            SELECT event_seq, event_id, event_type, reason_code, actor, idempotency_key,
                   prior_revision, target_revision, prior_generation, resulting_generation,
                   evaluation_id, verification_id, correlation_id, occurred_at
            FROM release_event
            WHERE workflow_id = :workflow_id
            ORDER BY event_seq
            """
        ),
        {"workflow_id": workflow_id},
    ).mappings().all()
    events = []
    for row in rows:
        item = dict(row)
        item["occurred_at"] = _iso(item["occurred_at"])
        events.append(item)
    return {"workflow_id": workflow_id, "events": events}
