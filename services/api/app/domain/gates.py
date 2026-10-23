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
