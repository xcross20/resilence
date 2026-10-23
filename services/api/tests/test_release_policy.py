from app.domain.release import (
    APPROVED_ACTIVATION_POLICIES,
    claims_independent_holdout,
    classify_verification,
    judge_activation,
    judge_restore,
)

GATES = {gate: "pass" for gate in ("safety", "quality", "latency", "completeness", "economic")}


def _activation(**overrides):
    payload = {
        "confirmation": "activate_synthetic_revision",
        "expected_generation": 0,
        "actual_generation": 0,
        "expected_prior_revision": None,
        "actual_prior_revision": None,
        "evaluation_found": True,
        "evaluation_workflow_matches": True,
        "requested_revision": "sha256:" + ("a" * 64),
        "evaluation_candidate_revision": "sha256:" + ("a" * 64),
        "evaluation_status": "completed_blocked",
        "evaluation_eligible": False,
        "gate_policy_version": "gate-policy-v0-fail-closed",
        "gate_statuses": {"safety": "blocked", "quality": "not_authoritative", "latency": "not_authoritative", "completeness": "pass", "economic": "inconclusive"},
    }
    payload.update(overrides)
    return judge_activation(**payload)


def test_v0_evaluation_cannot_activate_even_if_every_gate_passes() -> None:
    decision = _activation(
        evaluation_status="completed_eligible",
        evaluation_eligible=True,
        gate_statuses=dict(GATES),
    )
    assert decision.commit_transition is False
    assert decision.reason_code == "evaluation_not_eligible"
    assert APPROVED_ACTIVATION_POLICIES == frozenset()


def test_an_approved_policy_argument_is_required_before_commit() -> None:
    denied = _activation(evaluation_status="completed_eligible", evaluation_eligible=True, gate_statuses=dict(GATES))
    approved = judge_activation(
        confirmation="activate_synthetic_revision",
        expected_generation=0,
        actual_generation=0,
        expected_prior_revision=None,
        actual_prior_revision=None,
        evaluation_found=True,
        evaluation_workflow_matches=True,
        requested_revision="sha256:" + ("b" * 64),
        evaluation_candidate_revision="sha256:" + ("b" * 64),
        evaluation_status="completed_eligible",
        evaluation_eligible=True,
        gate_policy_version="gate-policy-approved-by-human",
        gate_statuses=dict(GATES),
        approved_policies=frozenset({"gate-policy-approved-by-human"}),
    )
    assert denied.commit_transition is False
    assert approved.commit_transition is True
    assert approved.reason_code == "activation_committed"


def test_activation_denies_missing_approval_stale_generation_wrong_revision_and_missing_evidence() -> None:
    assert _activation(confirmation=None).reason_code == "missing_approval"
    assert _activation(expected_generation=7).reason_code == "stale_generation"
    assert _activation(requested_revision="sha256:" + ("c" * 64)).reason_code == "wrong_revision"
    assert _activation(evaluation_found=False).reason_code == "evaluation_not_found"
    assert _activation(gate_statuses={}).reason_code == "missing_evidence"


def test_restore_requires_a_recorded_prior_revision() -> None:
    denied = judge_restore(
        confirmation="restore_prior_revision",
        expected_generation=0,
        actual_generation=0,
        actual_revision=None,
        recorded_prior_revision=None,
    )
    assert denied.reason_code == "nothing_to_restore"
    assert denied.commit_transition is False
    stale = judge_restore(
        confirmation="restore_prior_revision",
        expected_generation=0,
        actual_generation=1,
        actual_revision="sha256:" + ("a" * 64),
        recorded_prior_revision="sha256:" + ("b" * 64),
    )
    assert stale.reason_code == "stale_generation"
    ready = judge_restore(
        confirmation="restore_prior_revision",
        expected_generation=1,
        actual_generation=1,
        actual_revision="sha256:" + ("a" * 64),
        recorded_prior_revision="sha256:" + ("b" * 64),
    )
    assert ready.commit_transition is True


def test_overlap_and_critical_verification_do_not_claim_holdout() -> None:
    assert classify_verification([{"verdict": "verified_success", "critical_violation": False}], ["SD-081"]) == "denied_overlap"
    assert classify_verification([{"verdict": "incorrect_completion", "critical_violation": True}], []) == "regressed"
    assert classify_verification([{"verdict": "inconclusive", "critical_violation": False}], []) == "inconclusive"
    assert classify_verification([{"verdict": "verified_success", "critical_violation": False}], []) == "recorded"
    assert claims_independent_holdout(status="recorded", overlap_case_ids=[]) is False
    assert claims_independent_holdout(status="recorded", overlap_case_ids=[], approved=True) is True
