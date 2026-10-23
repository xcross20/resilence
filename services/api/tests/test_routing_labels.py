import ast
import json
from pathlib import Path

from app.domain.execution import execute_observed
from app.domain.routing import route_observed
from app.domain.strategy import StrategyDocument

FIXTURE = json.loads(Path("app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))
ROOT = Path(__file__).resolve().parents[1]
ISOLATED_MODULES = (
    "app/domain/routing.py",
    "app/domain/simulation.py",
    "app/domain/pricing.py",
    "app/domain/execution.py",
    "app/db/runtime_reader.py",
)


def _document() -> StrategyDocument:
    return StrategyDocument.model_validate(FIXTURE)


def test_observed_category_disagrees_with_a_privileged_label_without_correction() -> None:
    decision = route_observed(_document(), "ambiguous")
    assert decision.reason_code == "matched_rule"
    assert decision.matched_rule_id == "R2"
    assert decision.selected_method == "premium"


def test_unknown_observation_uses_safe_default() -> None:
    decision = route_observed(_document(), "vpn-outage")
    assert decision.reason_code == "unknown_observation"
    assert decision.matched_rule_id is None
    assert decision.selected_method == "premium"


def test_known_category_without_a_rule_uses_default_reason() -> None:
    document = StrategyDocument.model_validate(
        {
            "schema_version": "1",
            "workflow_id": "service-desk",
            "rules": [{"rule_id": "R1", "priority": 10, "when": {"observed_category_in": ["routine"]}, "method": "economy"}],
            "default_method": "premium",
            "fallback_method": "premium",
        }
    )
    decision = route_observed(document, "ambiguous")
    assert decision.reason_code == "default"
    assert decision.selected_method == "premium"


def test_failed_attempt_is_kept_and_fallback_is_appended() -> None:
    document = StrategyDocument.model_validate(
        {
            "schema_version": "1",
            "workflow_id": "service-desk",
            "rules": [{"rule_id": "R1", "priority": 10, "when": {"observed_category_in": ["routine"]}, "method": "economy"}],
            "default_method": "premium",
            "fallback_method": "premium",
        }
    )
    trace = execute_observed(document, "routine", fail_methods=frozenset({"economy"}))
    assert [step.attempt.status for step in trace.steps] == ["failed", "succeeded"]
    assert trace.steps[0].decision.reason_code == "matched_rule"
    assert trace.steps[1].decision.reason_code == "fallback"
    assert trace.steps[0].attempt.method_id == "economy"
    assert trace.steps[1].attempt.method_id == "premium"


def test_router_modules_do_not_import_labels_or_assessment() -> None:
    for relative in ISOLATED_MODULES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        joined = " ".join(imported)
        assert "assessment" not in joined
        assert "label_reader" not in joined
        assert "reference_labels" not in joined
