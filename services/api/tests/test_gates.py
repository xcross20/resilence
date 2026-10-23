import pytest

from app.domain.gates import execution_cost_per_verified_success, judge_gates


def test_zero_verified_success_has_no_quotient() -> None:
    ratio = execution_cost_per_verified_success(19800, 0)
    assert ratio.quotient_micro_usd is None
    assert ratio.remainder_micro_usd is None
    assert ratio.execution_cost_micro_usd == 19800


def test_quotient_is_integer_division_of_execution_cost() -> None:
    ratio = execution_cost_per_verified_success(10, 3)
    assert ratio.quotient_micro_usd == 3
    assert ratio.remainder_micro_usd == 1
    assert ratio.quotient_micro_usd * 3 + ratio.remainder_micro_usd == 10


def test_negative_cost_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        execution_cost_per_verified_success(-1, 1)


def _judgment(**overrides):
    payload = {
        "case_count": 1,
        "pair_count": 1,
        "manifest_matches": True,
        "any_inconclusive": False,
        "candidate_critical_violations": 0,
        "candidate_verified_success_count": 1,
        "prices_match": True,
    }
    payload.update(overrides)
    return judge_gates(**payload)


def test_unapproved_thresholds_keep_a_complete_evaluation_ineligible() -> None:
    judgment = _judgment()
    assert judgment.eligible is False
    assert judgment.status == "completed_ineligible"
    by_id = {gate.gate_id: gate for gate in judgment.gates}
    assert by_id["safety"].status == "pass"
    assert by_id["completeness"].status == "pass"
    assert by_id["quality"].status == "not_authoritative"
    assert by_id["quality"].reason_code == "threshold_not_approved"
    assert by_id["latency"].reason_code == "threshold_not_approved"
    assert by_id["economic"].status == "not_authoritative"
    assert by_id["economic"].reason_code == "noninferiority_not_approved"


def test_critical_violation_blocks_even_when_the_denominator_is_zero() -> None:
    judgment = _judgment(candidate_critical_violations=1, candidate_verified_success_count=0)
    assert judgment.status == "completed_blocked"
    assert judgment.eligible is False
    assert judgment.gates[0].reason_code == "critical_violation"


def test_zero_success_denominator_is_inconclusive() -> None:
    judgment = _judgment(candidate_verified_success_count=0)
    assert judgment.status == "inconclusive"
    assert judgment.eligible is False
    economic = judgment.gates[-1]
    assert economic.gate_id == "economic"
    assert economic.reason_code == "zero_verified_success_denominator"


def test_invalid_pricing_fails_closed_before_the_zero_denominator() -> None:
    judgment = _judgment(prices_match=False, candidate_verified_success_count=0)
    assert judgment.gates[-1].reason_code == "invalid_pricing"
    assert judgment.status == "inconclusive"


def test_missing_pair_or_inconclusive_assessment_fails_closed() -> None:
    unmatched = _judgment(pair_count=0)
    assert unmatched.gates[3].reason_code == "unmatched_pair"
    missing_label = _judgment(any_inconclusive=True)
    assert missing_label.gates[3].reason_code == "inconclusive_assessment"
    mismatch = _judgment(manifest_matches=False)
    assert mismatch.gates[3].reason_code == "manifest_mismatch"
    assert unmatched.eligible is False
    assert missing_label.eligible is False
    assert mismatch.eligible is False
