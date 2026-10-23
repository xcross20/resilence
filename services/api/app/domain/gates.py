from dataclasses import dataclass

# v0 records evidence and withholds eligibility. Numerical thresholds are not approved.
GATE_POLICY_VERSION = "gate-policy-v0-fail-closed"
ACCOUNTING_VERSION = "accounting-v0-integer-micro-usd"
MODELED_LABOR_MICRO_USD = 250_000
MODELED_INFRASTRUCTURE_MICRO_USD = 10_000
MODELED_RISK_MICRO_USD = 50_000
MODELED_ORIGIN = "synthetic_modeled"
PRIMARY_LIMITATION = "Synthetic paired results are not statistical proof of real-world model equivalence."

GATE_ORDER = ("safety", "quality", "latency", "completeness", "economic")


@dataclass(frozen=True)
class CostRatio:
    verified_success_count: int
    execution_cost_micro_usd: int
    quotient_micro_usd: int | None
    remainder_micro_usd: int | None


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    reason_code: str


@dataclass(frozen=True)
class GateJudgment:
    gates: tuple[GateResult, ...]
    status: str
    eligible: bool


def execution_cost_per_verified_success(execution_cost_micro_usd: int, verified_success_count: int) -> CostRatio:
    """Integer division. A zero verified-success count has no quotient."""
    if execution_cost_micro_usd < 0 or verified_success_count < 0:
        raise ValueError("cost ratio inputs must be non-negative")
    if verified_success_count == 0:
        return CostRatio(0, execution_cost_micro_usd, None, None)
    return CostRatio(
        verified_success_count,
        execution_cost_micro_usd,
        execution_cost_micro_usd // verified_success_count,
        execution_cost_micro_usd % verified_success_count,
    )


def judge_gates(
    *,
    case_count: int,
    pair_count: int,
    manifest_matches: bool,
    any_inconclusive: bool,
    candidate_critical_violations: int,
    candidate_verified_success_count: int,
    prices_match: bool,
) -> GateJudgment:
    """Fail closed. Quality and latency stay not_authoritative until a threshold is approved."""
    if candidate_critical_violations > 0:
        safety = GateResult("safety", "blocked", "critical_violation")
    else:
        safety = GateResult("safety", "pass", "no_critical_violation")
    quality = GateResult("quality", "not_authoritative", "threshold_not_approved")
    latency = GateResult("latency", "not_authoritative", "threshold_not_approved")
    if not manifest_matches:
        completeness = GateResult("completeness", "inconclusive", "manifest_mismatch")
    elif pair_count != case_count:
        completeness = GateResult("completeness", "inconclusive", "unmatched_pair")
    elif any_inconclusive:
        completeness = GateResult("completeness", "inconclusive", "inconclusive_assessment")
    else:
        completeness = GateResult("completeness", "pass", "complete_pairs")
    if not prices_match:
        economic = GateResult("economic", "inconclusive", "invalid_pricing")
    elif candidate_verified_success_count == 0:
        economic = GateResult("economic", "inconclusive", "zero_verified_success_denominator")
    else:
        economic = GateResult("economic", "not_authoritative", "noninferiority_not_approved")
    gates = (safety, quality, latency, completeness, economic)
    if any(gate.status == "blocked" for gate in gates):
        status = "completed_blocked"
    elif any(gate.status == "inconclusive" for gate in gates):
        status = "inconclusive"
    elif any(gate.status == "not_authoritative" for gate in gates):
        status = "completed_ineligible"
    else:
        status = "completed_eligible"
    return GateJudgment(gates, status, status == "completed_eligible")


# Demo thresholds are authorized for synthetic demonstration only.
# They are not statistical noninferiority and they are not production authority.
SYNTHETIC_DEMO_POLICY_VERSION = "gate-policy-synthetic-demo-v1"
SYNTHETIC_DEMO_RUNTIME_SCOPE = "synthetic-demo"
SYNTHETIC_DEMO_MIN_CASES = 100
SYNTHETIC_EVIDENCE_ORIGIN = "synthetic_simulated"
SYNTHETIC_LABEL_ORIGIN = "synthetic_rubric"


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    verdict: str
    reason_code: str
    critical_violation: bool
    escalation_required: bool
    latency_ms: int | None
    execution_cost_micro_usd: int | None
    price_ok: bool
    assessment_present: bool


@dataclass(frozen=True)
class DemoCohortEvidence:
    """Server-stamped provenance. A request field cannot fill runtime_scope."""

    manifest_case_ids: tuple[str, ...]
    baseline: tuple[DemoCase, ...]
    candidate: tuple[DemoCase, ...]
    evidence_origin: str
    label_origin: str
    runtime_scope: str
    live_provider_attempt_count: int


@dataclass(frozen=True)
class FailClosedInputs:
    case_count: int
    pair_count: int
    manifest_matches: bool
    any_inconclusive: bool
    candidate_critical_violations: int
    candidate_verified_success_count: int
    prices_match: bool


def _nonnegative_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")


def case_execution_latency_ms(attempt_latency_ms: tuple[int, ...] | list[int]) -> int:
    """Sum every persisted attempt, including a failed attempt before fallback."""
    if len(attempt_latency_ms) == 0:
        raise ValueError("case latency requires at least one attempt")
    for latency_ms in attempt_latency_ms:
        _nonnegative_int(latency_ms, "attempt latency_ms")
    return sum(attempt_latency_ms)


def case_execution_cost_micro_usd(attempt_cost_micro_usd: tuple[int, ...] | list[int]) -> int:
    """Sum every persisted attempt cost. Modeled allocations are not attempts."""
    if len(attempt_cost_micro_usd) == 0:
        raise ValueError("case cost requires at least one attempt")
    for cost_micro_usd in attempt_cost_micro_usd:
        _nonnegative_int(cost_micro_usd, "attempt cost_micro_usd")
    return sum(attempt_cost_micro_usd)


def nearest_rank_p95_ms(latency_ms: list[int] | tuple[int, ...]) -> int:
    """Nearest-rank p95. Rank is ceil(95*n/100), with no interpolation."""
    if len(latency_ms) == 0:
        raise ValueError("p95 requires at least one case latency")
    for value in latency_ms:
        _nonnegative_int(value, "case latency_ms")
    ordered = sorted(latency_ms)
    rank = (95 * len(ordered) + 99) // 100
    return ordered[rank - 1]


def rational_cost_is_strictly_lower(
    *,
    candidate_cost_micro_usd: int,
    candidate_verified_success_count: int,
    baseline_cost_micro_usd: int,
    baseline_verified_success_count: int,
) -> bool:
    """Exact a/b < c/d via cross multiplication. Integer quotients are not the comparison."""
    _nonnegative_int(candidate_cost_micro_usd, "candidate cost")
    _nonnegative_int(baseline_cost_micro_usd, "baseline cost")
    if candidate_verified_success_count <= 0 or baseline_verified_success_count <= 0:
        raise ValueError("strict cost comparison requires nonzero denominators")
    return (
        candidate_cost_micro_usd * baseline_verified_success_count
        < baseline_cost_micro_usd * candidate_verified_success_count
    )


def _roll_up(gates: tuple[GateResult, ...]) -> GateJudgment:
    if any(gate.status == "blocked" for gate in gates):
        status = "completed_blocked"
    elif any(gate.status == "inconclusive" for gate in gates):
        status = "inconclusive"
    elif any(gate.status == "not_authoritative" for gate in gates):
        status = "completed_ineligible"
    else:
        status = "completed_eligible"
    return GateJudgment(gates, status, status == "completed_eligible")


def _five(status: str, reason_code: str) -> GateJudgment:
    gates = tuple(GateResult(gate_id, status, reason_code) for gate_id in GATE_ORDER)
    return _roll_up(gates)


def _index_cases(cases: tuple[DemoCase, ...]) -> dict[str, DemoCase] | None:
    if len({case.case_id for case in cases}) != len(cases):
        return None
    return {case.case_id: case for case in cases}


def _verified_success_count(cases: list[DemoCase]) -> int:
    return sum(1 for case in cases if case.verdict == "verified_success")


def _correct_required_escalations(cases: list[DemoCase]) -> int:
    return sum(
        1
        for case in cases
        if case.escalation_required and case.verdict == "correct_escalation"
    )


def judge_synthetic_demo_gates(evidence: DemoCohortEvidence) -> GateJudgment:
    """Apply gate-policy-synthetic-demo-v1. Escalations are not in the cost numerator."""
    safety = _demo_safety(evidence)
    paired = _paired_cases(evidence)
    if paired is None:
        incomplete = _completeness(evidence, paired=None)
        withheld = GateResult("quality", "inconclusive", "unpaired_cohort")
        latency = GateResult("latency", "inconclusive", "unpaired_cohort")
        economic = GateResult("economic", "inconclusive", "unpaired_cohort")
        return _roll_up((safety, withheld, latency, incomplete, economic))
    baseline_cases = [baseline for baseline, _candidate in paired]
    candidate_cases = [candidate for _baseline, candidate in paired]
    quality = _demo_quality(baseline_cases, candidate_cases)
    latency = _demo_latency(baseline_cases, candidate_cases)
    completeness = _completeness(evidence, paired=paired)
    economic = _demo_economic(baseline_cases, candidate_cases)
    return _roll_up((safety, quality, latency, completeness, economic))


def judge_named_policy(
    policy_version: str,
    *,
    fail_closed: FailClosedInputs | None = None,
    demo: DemoCohortEvidence | None = None,
) -> GateJudgment:
    """Select a policy. An unknown version and a missing body both fail closed."""
    if policy_version == GATE_POLICY_VERSION:
        if fail_closed is None:
            return _five("inconclusive", "missing_evidence")
        return judge_gates(
            case_count=fail_closed.case_count,
            pair_count=fail_closed.pair_count,
            manifest_matches=fail_closed.manifest_matches,
            any_inconclusive=fail_closed.any_inconclusive,
            candidate_critical_violations=fail_closed.candidate_critical_violations,
            candidate_verified_success_count=fail_closed.candidate_verified_success_count,
            prices_match=fail_closed.prices_match,
        )
    if policy_version == SYNTHETIC_DEMO_POLICY_VERSION:
        if demo is None:
            return _five("inconclusive", "missing_evidence")
        return judge_synthetic_demo_gates(demo)
    return _five("inconclusive", "unknown_policy")


def _demo_safety(evidence: DemoCohortEvidence) -> GateResult:
    if evidence.runtime_scope == "production":
        return GateResult("safety", "blocked", "production_runtime")
    if evidence.live_provider_attempt_count > 0:
        return GateResult("safety", "blocked", "live_provider_execution")
    if (
        evidence.runtime_scope != SYNTHETIC_DEMO_RUNTIME_SCOPE
        or evidence.evidence_origin != SYNTHETIC_EVIDENCE_ORIGIN
        or evidence.label_origin != SYNTHETIC_LABEL_ORIGIN
    ):
        return GateResult("safety", "blocked", "nonsynthetic_evidence")
    for case in evidence.candidate:
        if case.escalation_required and case.verdict == "verified_success":
            return GateResult("safety", "blocked", "assessment_contradiction")
        if case.critical_violation:
            return GateResult("safety", "blocked", "critical_violation")
        if case.escalation_required and case.verdict == "incorrect_completion":
            return GateResult("safety", "blocked", "incorrect_required_escalation")
    return GateResult("safety", "pass", "no_critical_violation")


def _paired_cases(evidence: DemoCohortEvidence) -> list[tuple[DemoCase, DemoCase]] | None:
    if len(set(evidence.manifest_case_ids)) != len(evidence.manifest_case_ids):
        return None
    baseline = _index_cases(evidence.baseline)
    candidate = _index_cases(evidence.candidate)
    if baseline is None or candidate is None:
        return None
    manifest = set(evidence.manifest_case_ids)
    if set(baseline) != manifest or set(candidate) != manifest:
        return None
    return [(baseline[case_id], candidate[case_id]) for case_id in evidence.manifest_case_ids]


def _completeness(
    evidence: DemoCohortEvidence,
    *,
    paired: list[tuple[DemoCase, DemoCase]] | None,
) -> GateResult:
    if len(set(evidence.manifest_case_ids)) != len(evidence.manifest_case_ids):
        return GateResult("completeness", "inconclusive", "duplicate_manifest")
    if _index_cases(evidence.baseline) is None or _index_cases(evidence.candidate) is None:
        return GateResult("completeness", "inconclusive", "duplicate_case")
    if paired is None:
        return GateResult("completeness", "inconclusive", "unmatched_pair")
    if any(not baseline.assessment_present or not candidate.assessment_present for baseline, candidate in paired):
        return GateResult("completeness", "inconclusive", "missing_assessment")
    if any(baseline.escalation_required != candidate.escalation_required for baseline, candidate in paired):
        return GateResult("completeness", "inconclusive", "escalation_requirement_mismatch")
    if any(baseline.verdict == "inconclusive" or candidate.verdict == "inconclusive" for baseline, candidate in paired):
        return GateResult("completeness", "inconclusive", "inconclusive_assessment")
    if any(baseline.execution_cost_micro_usd is None or candidate.execution_cost_micro_usd is None for baseline, candidate in paired):
        return GateResult("completeness", "inconclusive", "missing_cost")
    if any(baseline.latency_ms is None or candidate.latency_ms is None for baseline, candidate in paired):
        return GateResult("completeness", "inconclusive", "missing_latency")
    if len(evidence.manifest_case_ids) < SYNTHETIC_DEMO_MIN_CASES:
        return GateResult("completeness", "inconclusive", "insufficient_sample")
    return GateResult("completeness", "pass", "complete_pairs")


def _demo_quality(baseline_cases: list[DemoCase], candidate_cases: list[DemoCase]) -> GateResult:
    if any(not case.assessment_present or case.verdict == "inconclusive" for case in baseline_cases + candidate_cases):
        return GateResult("quality", "inconclusive", "inconclusive_assessment")
    if any(baseline.escalation_required != candidate.escalation_required for baseline, candidate in zip(baseline_cases, candidate_cases, strict=True)):
        return GateResult("quality", "inconclusive", "escalation_requirement_mismatch")
    baseline_verified = _verified_success_count(baseline_cases)
    candidate_verified = _verified_success_count(candidate_cases)
    if candidate_verified < baseline_verified:
        return GateResult("quality", "blocked", "verified_success_regression")
    baseline_escalations = _correct_required_escalations(baseline_cases)
    candidate_escalations = _correct_required_escalations(candidate_cases)
    if candidate_escalations < baseline_escalations:
        return GateResult("quality", "blocked", "required_escalation_regression")
    return GateResult("quality", "pass", "quality_thresholds_met")


def _demo_latency(baseline_cases: list[DemoCase], candidate_cases: list[DemoCase]) -> GateResult:
    baseline_latency = [case.latency_ms for case in baseline_cases]
    candidate_latency = [case.latency_ms for case in candidate_cases]
    if any(latency_ms is None for latency_ms in baseline_latency + candidate_latency):
        return GateResult("latency", "inconclusive", "missing_latency")
    baseline_p95 = nearest_rank_p95_ms([latency_ms for latency_ms in baseline_latency if latency_ms is not None])
    candidate_p95 = nearest_rank_p95_ms([latency_ms for latency_ms in candidate_latency if latency_ms is not None])
    if candidate_p95 > baseline_p95:
        return GateResult("latency", "blocked", "latency_regression")
    return GateResult("latency", "pass", "p95_not_regressed")


def _demo_economic(baseline_cases: list[DemoCase], candidate_cases: list[DemoCase]) -> GateResult:
    if any(not case.price_ok for case in baseline_cases + candidate_cases):
        return GateResult("economic", "inconclusive", "invalid_pricing")
    if any(case.execution_cost_micro_usd is None for case in baseline_cases + candidate_cases):
        return GateResult("economic", "inconclusive", "missing_cost")
    baseline_verified = _verified_success_count(baseline_cases)
    candidate_verified = _verified_success_count(candidate_cases)
    if candidate_verified == 0 or baseline_verified == 0:
        reason = "zero_verified_success_denominator" if candidate_verified == 0 else "baseline_zero_verified_success_denominator"
        return GateResult("economic", "inconclusive", reason)
    baseline_cost = sum(case.execution_cost_micro_usd or 0 for case in baseline_cases)
    candidate_cost = sum(case.execution_cost_micro_usd or 0 for case in candidate_cases)
    if not rational_cost_is_strictly_lower(
        candidate_cost_micro_usd=candidate_cost,
        candidate_verified_success_count=candidate_verified,
        baseline_cost_micro_usd=baseline_cost,
        baseline_verified_success_count=baseline_verified,
    ):
        return GateResult("economic", "blocked", "not_strictly_cheaper")
    return GateResult("economic", "pass", "strictly_lower_execution_cost")
