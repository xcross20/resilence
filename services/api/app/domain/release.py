from dataclasses import dataclass

# Empty until a human approves a gate policy that may set eligible.
APPROVED_ACTIVATION_POLICIES: frozenset[str] = frozenset()
HOLDOUT_CLAIMS_APPROVED = False
ACTIVATE_CONFIRMATION = "activate_synthetic_revision"
RESTORE_CONFIRMATION = "restore_prior_revision"
REQUIRED_GATES = ("safety", "quality", "latency", "completeness", "economic")


@dataclass(frozen=True)
class ReleaseDecision:
    status_code: int
    reason_code: str
    commit_transition: bool
    event_type: str


def judge_activation(
    *,
    confirmation: str | None,
    expected_generation: int,
    actual_generation: int,
    expected_prior_revision: str | None,
    actual_prior_revision: str | None,
    evaluation_found: bool,
    evaluation_workflow_matches: bool,
    requested_revision: str | None,
    evaluation_candidate_revision: str | None,
    evaluation_status: str | None,
    evaluation_eligible: bool,
    gate_policy_version: str | None,
    gate_statuses: dict[str, str],
    approved_policies: frozenset[str] = APPROVED_ACTIVATION_POLICIES,
) -> ReleaseDecision:
    """Deny unless an approved policy stored a fully passing eligible evaluation."""
    if confirmation != ACTIVATE_CONFIRMATION:
        return ReleaseDecision(409, "missing_approval", False, "activation_denied")
    if expected_generation != actual_generation:
        return ReleaseDecision(409, "stale_generation", False, "activation_denied")
    if expected_prior_revision != actual_prior_revision:
        return ReleaseDecision(409, "prior_revision_mismatch", False, "activation_denied")
    if not evaluation_found:
        return ReleaseDecision(404, "evaluation_not_found", False, "activation_denied")
    if requested_revision != evaluation_candidate_revision:
        return ReleaseDecision(409, "wrong_revision", False, "activation_denied")
    if not evaluation_workflow_matches:
        return ReleaseDecision(409, "evaluation_workflow_mismatch", False, "activation_denied")
    gates_pass = all(gate_statuses.get(gate_id) == "pass" for gate_id in REQUIRED_GATES)
    policy_approved = gate_policy_version in approved_policies
    if (
        evaluation_eligible
        and evaluation_status == "completed_eligible"
        and policy_approved
        and gates_pass
    ):
        return ReleaseDecision(200, "activation_committed", True, "activation_committed")
    if len(gate_statuses) != len(REQUIRED_GATES):
        return ReleaseDecision(409, "missing_evidence", False, "activation_denied")
    return ReleaseDecision(409, "evaluation_not_eligible", False, "activation_denied")


def judge_restore(
    *,
    confirmation: str | None,
    expected_generation: int,
    actual_generation: int,
    actual_revision: str | None,
    recorded_prior_revision: str | None,
) -> ReleaseDecision:
    if confirmation != RESTORE_CONFIRMATION:
        return ReleaseDecision(409, "missing_approval", False, "restoration_denied")
    if expected_generation != actual_generation:
        return ReleaseDecision(409, "stale_generation", False, "restoration_denied")
    if actual_generation == 0 or actual_revision is None or recorded_prior_revision is None:
        return ReleaseDecision(409, "nothing_to_restore", False, "restoration_denied")
    return ReleaseDecision(200, "restoration_committed", True, "restoration_committed")


def classify_verification(assessments: list[dict], overlap_case_ids: list[str]) -> str:
    if overlap_case_ids:
        return "denied_overlap"
    if not assessments:
        return "inconclusive"
    if any(item["critical_violation"] or item["verdict"] == "incorrect_completion" for item in assessments):
        return "regressed"
    if any(item["verdict"] == "inconclusive" for item in assessments):
        return "inconclusive"
    if all(item["verdict"] in {"verified_success", "correct_escalation"} for item in assessments):
        return "recorded"
    return "inconclusive"


def claims_independent_holdout(
    *,
    status: str,
    overlap_case_ids: list[str],
    approved: bool = HOLDOUT_CLAIMS_APPROVED,
) -> bool:
    """A synthetic recording is not an approved independent holdout."""
    return bool(approved and status == "recorded" and not overlap_case_ids)
