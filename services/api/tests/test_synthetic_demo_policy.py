from dataclasses import replace

import pytest

from app.domain.gates import (
    SYNTHETIC_DEMO_POLICY_VERSION,
    DemoCase,
    DemoCohortEvidence,
    FailClosedInputs,
    case_execution_cost_micro_usd,
    case_execution_latency_ms,
    judge_named_policy,
    judge_synthetic_demo_gates,
    nearest_rank_p95_ms,
    rational_cost_is_strictly_lower,
)
from app.domain.demo_execution import fail_methods_for
from app.domain.release import APPROVED_ACTIVATION_POLICIES
from app.domain.runtime_scope import server_runtime_scope


def _case(case_id: str, **overrides) -> DemoCase:
    payload = {
        "case_id": case_id,
        "verdict": "verified_success",
        "reason_code": "verified_resolution",
        "critical_violation": False,
        "escalation_required": False,
        "latency_ms": 1700,
        "execution_cost_micro_usd": 8760,
        "price_ok": True,
        "assessment_present": True,
    }
    payload.update(overrides)
    return DemoCase(**payload)


def _replace(cases: tuple[DemoCase, ...], index: int, **overrides) -> tuple[DemoCase, ...]:
    updated = replace(cases[index], **overrides)
    return cases[:index] + (updated,) + cases[index + 1 :]


def _cohort(n: int = 100, **overrides) -> DemoCohortEvidence:
    ids = tuple(f"SYN-{index:03d}" for index in range(n))
    baseline = []
    candidate = []
    for index, case_id in enumerate(ids):
        if index < n - 4:
            baseline.append(_case(case_id, latency_ms=3000, execution_cost_micro_usd=19800))
            candidate.append(_case(case_id, latency_ms=1700, execution_cost_micro_usd=8760))
        else:
            shared = {
                "verdict": "correct_escalation",
                "reason_code": "correct_escalation",
                "escalation_required": True,
                "latency_ms": 3000,
                "execution_cost_micro_usd": 19800,
            }
            baseline.append(_case(case_id, **shared))
            candidate.append(_case(case_id, **shared))
    payload = {
        "manifest_case_ids": ids,
        "baseline": tuple(baseline),
        "candidate": tuple(candidate),
        "evidence_origin": "synthetic_simulated",
        "label_origin": "synthetic_rubric",
        "runtime_scope": "synthetic-demo",
        "live_provider_attempt_count": 0,
    }
    payload.update(overrides)
    return DemoCohortEvidence(**payload)


def _gate(evidence: DemoCohortEvidence, gate_id: str):
    judgment = judge_synthetic_demo_gates(evidence)
    return judgment, {gate.gate_id: gate for gate in judgment.gates}[gate_id]


def test_fail_first_hook_is_only_the_named_economy_case() -> None:
    assert fail_methods_for("SYN-D-000", "economy") == frozenset({"economy"})
    assert fail_methods_for("SYN-D-000", "premium") == frozenset()
    assert fail_methods_for("SD-081", "economy") == frozenset()


def test_unset_runtime_scope_stays_synthetic_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXECUTION_OPTIMIZER_RUNTIME_SCOPE", raising=False)
    assert server_runtime_scope() == "synthetic-demo"


def test_nearest_rank_p95_uses_ceil_without_interpolation() -> None:
    assert nearest_rank_p95_ms([40]) == 40
    assert nearest_rank_p95_ms(list(range(1, 101))) == 95
    assert (95 * 100 + 99) // 100 == 95


def test_failed_attempts_add_to_latency_and_cost() -> None:
    assert case_execution_latency_ms((3000, 40)) == 3040
    assert case_execution_cost_micro_usd((19800, 400)) == 20200
    with pytest.raises(ValueError):
        case_execution_latency_ms(())
    with pytest.raises(ValueError):
        case_execution_cost_micro_usd((-1,))


def test_exact_rational_comparison_is_not_the_integer_quotient() -> None:
    assert rational_cost_is_strictly_lower(
        candidate_cost_micro_usd=2,
        candidate_verified_success_count=3,
        baseline_cost_micro_usd=3,
        baseline_verified_success_count=4,
    )
    assert not rational_cost_is_strictly_lower(
        candidate_cost_micro_usd=10,
        candidate_verified_success_count=2,
        baseline_cost_micro_usd=15,
        baseline_verified_success_count=3,
    )


def test_eligible_synthetic_candidate_passes_every_demo_gate() -> None:
    judgment = judge_synthetic_demo_gates(_cohort())
    assert judgment.eligible is True
    assert judgment.status == "completed_eligible"
    assert {gate.status for gate in judgment.gates} == {"pass"}
    assert nearest_rank_p95_ms([1700] * 96 + [3000] * 4) == 1700


def test_safety_violation_blocks_eligibility() -> None:
    evidence = _cohort()
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=_replace(evidence.candidate, 0, critical_violation=True, verdict="incorrect_completion", reason_code="automated_when_escalation_required"),
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=evidence.live_provider_attempt_count,
    )
    judgment, safety = _gate(evidence, "safety")
    assert safety.reason_code == "critical_violation"
    assert judgment.status == "completed_blocked"
    assert judgment.eligible is False


def test_incorrect_required_escalation_blocks_and_quality_shows_regression() -> None:
    evidence = _cohort()
    candidate = _replace(
        evidence.candidate,
        96,
        verdict="incorrect_completion",
        reason_code="automated_when_escalation_required",
        critical_violation=False,
    )
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=candidate,
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, safety = _gate(evidence, "safety")
    quality = {gate.gate_id: gate for gate in judgment.gates}["quality"]
    assert safety.reason_code == "incorrect_required_escalation"
    assert quality.reason_code == "required_escalation_regression"
    assert judgment.eligible is False


def test_verified_success_regression_blocks_quality_without_a_safety_block() -> None:
    evidence = _cohort()
    candidate = _replace(evidence.candidate, 0, verdict="incorrect_completion", reason_code="resolution_mismatch")
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=candidate,
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, quality = _gate(evidence, "quality")
    safety = {gate.gate_id: gate for gate in judgment.gates}["safety"]
    assert safety.status == "pass"
    assert quality.reason_code == "verified_success_regression"
    assert judgment.eligible is False


def test_latency_regression_blocks() -> None:
    evidence = _cohort()
    replaced = evidence.candidate
    for index in range(len(replaced)):
        replaced = _replace(replaced, index, latency_ms=5000)
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=replaced,
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, latency = _gate(evidence, "latency")
    assert latency.reason_code == "latency_regression"
    assert judgment.eligible is False


def test_missing_case_missing_cost_and_invalid_pricing_are_inconclusive() -> None:
    evidence = _cohort()
    missing_case = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=evidence.candidate[:-1],
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    assert _gate(missing_case, "completeness")[1].reason_code == "unmatched_pair"

    missing_cost = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=_replace(evidence.candidate, 1, execution_cost_micro_usd=None),
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    assert _gate(missing_cost, "completeness")[1].reason_code == "missing_cost"
    assert _gate(missing_cost, "economic")[1].reason_code == "missing_cost"

    invalid_price = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=_replace(evidence.candidate, 1, price_ok=False),
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, economic = _gate(invalid_price, "economic")
    assert economic.reason_code == "invalid_pricing"
    assert judgment.eligible is False


def test_zero_verified_success_denominator_is_inconclusive() -> None:
    evidence = _cohort()
    candidate = tuple(
        _case(
            case.case_id,
            verdict="correct_escalation",
            reason_code="correct_escalation",
            escalation_required=True,
            latency_ms=3000,
            execution_cost_micro_usd=19800,
        )
        for case in evidence.candidate
    )
    baseline = tuple(
        _case(
            case.case_id,
            verdict="correct_escalation",
            reason_code="correct_escalation",
            escalation_required=True,
            latency_ms=3000,
            execution_cost_micro_usd=19800,
        )
        for case in evidence.baseline
    )
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=baseline,
        candidate=candidate,
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, economic = _gate(evidence, "economic")
    assert economic.reason_code == "zero_verified_success_denominator"
    assert judgment.eligible is False


def test_fewer_than_100_matched_cases_is_insufficient_sample() -> None:
    judgment, completeness = _gate(_cohort(99), "completeness")
    assert completeness.reason_code == "insufficient_sample"
    assert judgment.status == "inconclusive"
    assert judgment.eligible is False


def test_v0_policy_does_not_inherit_demo_eligibility() -> None:
    judgment = judge_named_policy(
        "gate-policy-v0-fail-closed",
        fail_closed=FailClosedInputs(1, 1, True, False, 0, 1, True),
        demo=_cohort(),
    )
    assert judgment.eligible is False
    assert judgment.status == "completed_ineligible"
    assert {gate.reason_code for gate in judgment.gates} >= {"threshold_not_approved", "noninferiority_not_approved"}


def test_unknown_policy_and_a_forged_call_shape_cannot_pass() -> None:
    unknown = judge_named_policy("gate-policy-synthetic-demo-v1-forged")
    assert unknown.eligible is False
    assert unknown.gates[0].reason_code == "unknown_policy"
    missing = judge_named_policy(SYNTHETIC_DEMO_POLICY_VERSION, demo=None)
    assert missing.eligible is False
    assert missing.gates[0].reason_code == "missing_evidence"
    assert "gate-policy-synthetic-demo-v1-forged" not in APPROVED_ACTIVATION_POLICIES
    assert APPROVED_ACTIVATION_POLICIES == frozenset({SYNTHETIC_DEMO_POLICY_VERSION})


def test_production_runtime_and_live_provider_execution_are_blocked() -> None:
    production = _cohort(runtime_scope="production")
    assert _gate(production, "safety")[1].reason_code == "production_runtime"
    assert _gate(production, "safety")[0].eligible is False
    live = _cohort(live_provider_attempt_count=1)
    assert _gate(live, "safety")[1].reason_code == "live_provider_execution"


def test_inconclusive_assessment_does_not_become_a_quality_regression() -> None:
    evidence = _cohort()
    candidate = _replace(evidence.candidate, 0, verdict="inconclusive", reason_code="insufficient_evidence")
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=candidate,
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, quality = _gate(evidence, "quality")
    assert quality.reason_code == "inconclusive_assessment"
    assert judgment.status == "inconclusive"
    assert judgment.eligible is False


def test_equal_rational_cost_is_not_strictly_cheaper() -> None:
    evidence = _cohort()
    replaced = evidence.candidate
    for index, baseline_case in enumerate(evidence.baseline):
        replaced = _replace(replaced, index, execution_cost_micro_usd=baseline_case.execution_cost_micro_usd)
    evidence = DemoCohortEvidence(
        manifest_case_ids=evidence.manifest_case_ids,
        baseline=evidence.baseline,
        candidate=replaced,
        evidence_origin=evidence.evidence_origin,
        label_origin=evidence.label_origin,
        runtime_scope=evidence.runtime_scope,
        live_provider_attempt_count=0,
    )
    judgment, economic = _gate(evidence, "economic")
    assert economic.reason_code == "not_strictly_cheaper"
    assert judgment.eligible is False
