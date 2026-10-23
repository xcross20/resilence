from app.domain.gates import SYNTHETIC_DEMO_POLICY_VERSION
from app.domain.pricing import load_price_book
from app.domain.release import (
    APPROVED_ACTIVATION_POLICIES,
    SYNTHETIC_DEMO_ACTIVATION_FIXTURE_VERSION,
    SYNTHETIC_DEMO_ACTIVATION_PRICE_BOOK_VERSION,
    SYNTHETIC_DEMO_ACTIVATION_WORKFLOW_ID,
    claims_independent_holdout,
    classify_verification,
    judge_activation,
    judge_restore,
)
from app.fixtures.synthetic_demo_v1 import DEMO_WORKFLOW_ID, FIXTURE_VERSION

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
    assert APPROVED_ACTIVATION_POLICIES == frozenset({SYNTHETIC_DEMO_POLICY_VERSION})
    assert "gate-policy-v0-fail-closed" not in APPROVED_ACTIVATION_POLICIES


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


def _demo_activation(**overrides):
    revision = "sha256:" + ("d" * 64)
    payload = {
        "confirmation": "activate_synthetic_revision",
        "expected_generation": 0,
        "actual_generation": 0,
        "expected_prior_revision": None,
        "actual_prior_revision": None,
        "evaluation_found": True,
        "evaluation_workflow_matches": True,
        "requested_revision": revision,
        "evaluation_candidate_revision": revision,
        "evaluation_status": "completed_eligible",
        "evaluation_eligible": True,
        "gate_policy_version": SYNTHETIC_DEMO_POLICY_VERSION,
        "gate_statuses": dict(GATES),
        "workflow_id": SYNTHETIC_DEMO_ACTIVATION_WORKFLOW_ID,
        "runtime_scope": "synthetic-demo",
        "fixture_version": SYNTHETIC_DEMO_ACTIVATION_FIXTURE_VERSION,
        "price_book_version": SYNTHETIC_DEMO_ACTIVATION_PRICE_BOOK_VERSION,
        "evidence_origin": "synthetic_simulated",
        "label_origin": "synthetic_rubric",
        "live_provider_attempt_count": 0,
    }
    payload.update(overrides)
    return judge_activation(**payload)


def test_synthetic_demo_activation_requires_server_provenance() -> None:
    assert SYNTHETIC_DEMO_ACTIVATION_WORKFLOW_ID == DEMO_WORKFLOW_ID
    assert SYNTHETIC_DEMO_ACTIVATION_FIXTURE_VERSION == FIXTURE_VERSION
    assert SYNTHETIC_DEMO_ACTIVATION_PRICE_BOOK_VERSION == load_price_book()["version"]
    committed = _demo_activation()
    assert committed.commit_transition is True
    assert committed.reason_code == "activation_committed"
    assert _demo_activation(runtime_scope="production").reason_code == "production_runtime"
    assert _demo_activation(runtime_scope=None).reason_code == "runtime_not_synthetic_demo"
    assert _demo_activation(runtime_scope="lab").reason_code == "runtime_not_synthetic_demo"
    assert _demo_activation(workflow_id="service-desk").reason_code == "workflow_not_synthetic_demo"
    assert _demo_activation(live_provider_attempt_count=1).reason_code == "live_provider_execution"
    assert _demo_activation(evidence_origin="live_measured").reason_code == "nonsynthetic_evidence"
    assert _demo_activation(label_origin=None).reason_code == "nonsynthetic_evidence"
    assert _demo_activation(fixture_version="service-desk-fixture-v1").reason_code == "provenance_rejected"
    assert _demo_activation(price_book_version="synthetic-price-v1").reason_code == "provenance_rejected"
    assert _demo_activation(confirmation=None).reason_code == "missing_approval"
    assert _demo_activation(evaluation_eligible=False, evaluation_status="completed_blocked").reason_code == "evaluation_not_eligible"


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
