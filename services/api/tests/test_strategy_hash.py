import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.strategy import StrategyDocument, canonical_json, revision_sha256

FIXTURE = json.loads(Path("app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))


def test_rule_array_order_does_not_change_revision() -> None:
    forward = StrategyDocument.model_validate(FIXTURE)
    reversed_rules = dict(FIXTURE)
    reversed_rules["rules"] = list(reversed(FIXTURE["rules"]))
    backward = StrategyDocument.model_validate(reversed_rules)
    assert canonical_json(forward) == canonical_json(backward)
    assert revision_sha256(forward) == revision_sha256(backward)
    assert revision_sha256(forward).startswith("sha256:")
    assert len(revision_sha256(forward)) == 7 + 64


def test_priority_change_changes_revision() -> None:
    changed = json.loads(json.dumps(FIXTURE))
    changed["rules"][0]["priority"] = 30
    assert revision_sha256(StrategyDocument.model_validate(changed)) != revision_sha256(
        StrategyDocument.model_validate(FIXTURE)
    )


def test_duplicate_priority_is_rejected() -> None:
    broken = json.loads(json.dumps(FIXTURE))
    broken["rules"][1]["priority"] = broken["rules"][0]["priority"]
    with pytest.raises(ValidationError):
        StrategyDocument.model_validate(broken)


def test_predicate_category_outside_the_closed_set_is_rejected() -> None:
    broken = json.loads(json.dumps(FIXTURE))
    broken["rules"][0]["when"]["observed_category_in"] = ["vpn-outage"]
    with pytest.raises(ValidationError):
        StrategyDocument.model_validate(broken)


def test_reference_field_on_strategy_is_rejected() -> None:
    broken = json.loads(json.dumps(FIXTURE))
    broken["reference_category"] = "privileged"
    with pytest.raises(ValidationError):
        StrategyDocument.model_validate(broken)
