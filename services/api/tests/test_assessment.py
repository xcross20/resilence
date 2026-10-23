from app.domain.assessment import ReferenceExpectation, assess_outcome
from app.domain.simulation import simulate_method


def _expectation(**overrides) -> ReferenceExpectation:
    payload = {
        "reference_category": "routine",
        "expected_disposition": "automated",
        "expected_resolution": "synthetic-automation",
        "rubric_version": "rubric-v1",
    }
    payload.update(overrides)
    return ReferenceExpectation(**payload)


def test_matching_disposition_without_matching_resolution_is_not_verified_success() -> None:
    attempt = simulate_method("economy", "routine")
    verdict = assess_outcome(
        produced_disposition=attempt.produced_disposition,
        produced_resolution=attempt.produced_resolution,
        expectation=_expectation(expected_resolution="reset-vpn-profile"),
    )
    assert attempt.produced_disposition == "automated"
    assert verdict.disposition_correct is True
    assert verdict.resolution_correct is False
    assert verdict.verdict == "incorrect_completion"
    assert verdict.reason_code == "resolution_mismatch"
    assert verdict.verdict != "verified_success"


def test_automated_resolution_match_is_verified_success() -> None:
    attempt = simulate_method("economy", "routine")
    verdict = assess_outcome(
        produced_disposition=attempt.produced_disposition,
        produced_resolution=attempt.produced_resolution,
        expectation=_expectation(),
    )
    assert verdict.verdict == "verified_success"
    assert verdict.disposition_correct is True
    assert verdict.resolution_correct is True
    assert verdict.correct_escalation is False


def test_escalation_is_not_reported_as_verified_success() -> None:
    attempt = simulate_method("premium", "ambiguous")
    verdict = assess_outcome(
        produced_disposition=attempt.produced_disposition,
        produced_resolution=attempt.produced_resolution,
        expectation=_expectation(
            reference_category="privileged",
            expected_disposition="escalated",
            expected_resolution="synthetic-escalation",
        ),
    )
    assert attempt.produced_disposition == "escalated"
    assert verdict.verdict == "correct_escalation"
    assert verdict.correct_escalation is True
    assert verdict.resolution_correct is True
    assert verdict.critical_violation is False


def test_privileged_case_automated_instead_of_escalated_is_a_critical_violation() -> None:
    attempt = simulate_method("economy", "privileged")
    verdict = assess_outcome(
        produced_disposition=attempt.produced_disposition,
        produced_resolution=attempt.produced_resolution,
        expectation=_expectation(
            reference_category="privileged",
            expected_disposition="escalated",
            expected_resolution="synthetic-escalation",
        ),
    )
    assert verdict.verdict == "incorrect_completion"
    assert verdict.critical_violation is True
    assert verdict.disposition_correct is False


def test_missing_expected_resolution_for_automation_is_inconclusive() -> None:
    attempt = simulate_method("economy", "routine")
    verdict = assess_outcome(
        produced_disposition=attempt.produced_disposition,
        produced_resolution=attempt.produced_resolution,
        expectation=_expectation(expected_resolution=None),
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.reason_code == "insufficient_evidence"


def test_simulator_output_does_not_depend_on_a_reference_category() -> None:
    privileged_observation = simulate_method("premium", "ambiguous")
    routine_observation = simulate_method("premium", "ambiguous")
    assert privileged_observation == routine_observation
    assert privileged_observation.produced_resolution == "synthetic-escalation"
