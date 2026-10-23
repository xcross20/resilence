from dataclasses import dataclass

from app.domain.strategy import StrategyDocument

KNOWN_CATEGORIES = frozenset({"routine", "ambiguous", "privileged"})
STEP_ID = "draft_resolution"


@dataclass(frozen=True)
class RouteDecision:
    matched_rule_id: str | None
    selected_method: str
    reason_code: str


def route_observed(document: StrategyDocument, observed_category: str) -> RouteDecision:
    """Select a method from the observed category. Reference labels are not a parameter."""
    if observed_category not in KNOWN_CATEGORIES:
        return RouteDecision(None, document.default_method, "unknown_observation")
    for rule in sorted(document.rules, key=lambda item: item.priority):
        if observed_category in rule.when.observed_category_in:
            return RouteDecision(rule.rule_id, rule.method, "matched_rule")
    return RouteDecision(None, document.default_method, "default")


def fallback_decision(document: StrategyDocument) -> RouteDecision:
    return RouteDecision(None, document.fallback_method, "fallback")
