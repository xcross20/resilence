from dataclasses import dataclass

EVALUATOR_VERSION = "rubric-assessor-v1"


@dataclass(frozen=True)
class ReferenceExpectation:
    reference_category: str
    expected_disposition: str
    expected_resolution: str | None
    rubric_version: str


@dataclass(frozen=True)
class OutcomeVerdict:
    disposition_correct: bool | None
    resolution_correct: bool | None
    verdict: str
    reason_code: str
    correct_escalation: bool
    critical_violation: bool
    rubric_version: str
    evaluator_version: str


def _inconclusive(rubric_version: str) -> OutcomeVerdict:
    return OutcomeVerdict(None, None, "inconclusive", "insufficient_evidence", False, False, rubric_version, EVALUATOR_VERSION)


def assess_outcome(
    *,
    produced_disposition: str | None,
    produced_resolution: str | None,
    expectation: ReferenceExpectation | None,
) -> OutcomeVerdict:
    """Judge a finished attempt. Disposition match alone is not verified_success."""
    if expectation is None or not produced_disposition or produced_resolution is None:
        return _inconclusive(expectation.rubric_version if expectation else "rubric-v1")
    if produced_disposition == "none":
        return _inconclusive(expectation.rubric_version)
    disposition_correct = produced_disposition == expectation.expected_disposition
    if expectation.expected_disposition == "automated" and expectation.expected_resolution is None:
        return OutcomeVerdict(
            disposition_correct, None, "inconclusive", "insufficient_evidence", False, False,
            expectation.rubric_version, EVALUATOR_VERSION,
        )
    resolution_correct = None
    if expectation.expected_resolution is not None:
        resolution_correct = produced_resolution == expectation.expected_resolution
    if expectation.expected_disposition == "escalated" and produced_disposition == "escalated":
        return OutcomeVerdict(
            True, resolution_correct, "correct_escalation", "correct_escalation", True, False,
            expectation.rubric_version, EVALUATOR_VERSION,
        )
    if produced_disposition == "automated" and expectation.expected_disposition == "escalated":
        critical = expectation.reference_category == "privileged"
        return OutcomeVerdict(
            False, resolution_correct, "incorrect_completion", "automated_when_escalation_required",
            False, critical, expectation.rubric_version, EVALUATOR_VERSION,
        )
    if expectation.expected_disposition == "automated" and produced_disposition == "automated" and resolution_correct:
        return OutcomeVerdict(
            True, True, "verified_success", "verified_resolution", False, False,
            expectation.rubric_version, EVALUATOR_VERSION,
        )
    if expectation.expected_disposition == "automated" and produced_disposition == "automated":
        return OutcomeVerdict(
            True, False, "incorrect_completion", "resolution_mismatch", False, False,
            expectation.rubric_version, EVALUATOR_VERSION,
        )
    return OutcomeVerdict(
        disposition_correct, resolution_correct, "incorrect_completion", "escalated_when_automation_expected",
        False, False, expectation.rubric_version, EVALUATOR_VERSION,
    )
