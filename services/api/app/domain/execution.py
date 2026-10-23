from dataclasses import dataclass

from app.domain.routing import RouteDecision, fallback_decision, route_observed
from app.domain.simulation import SimulatedAttempt, simulate_method
from app.domain.strategy import StrategyDocument


@dataclass(frozen=True)
class ExecutedStep:
    decision: RouteDecision
    attempt: SimulatedAttempt


@dataclass(frozen=True)
class ExecutionTrace:
    steps: tuple[ExecutedStep, ...]

    @property
    def final_attempt(self) -> SimulatedAttempt:
        return self.steps[-1].attempt


def execute_observed(
    document: StrategyDocument,
    observed_category: str,
    *,
    fail_methods: frozenset[str] = frozenset(),
) -> ExecutionTrace:
    """Run the selected method. A failed attempt is kept, then the fallback method runs once."""
    decision = route_observed(document, observed_category)
    first = simulate_method(decision.selected_method, observed_category, force_failure=decision.selected_method in fail_methods)
    steps = [ExecutedStep(decision, first)]
    if first.status == "failed":
        fallback = fallback_decision(document)
        second = simulate_method(
            fallback.selected_method,
            observed_category,
            force_failure=fallback.selected_method in fail_methods,
        )
        steps.append(ExecutedStep(fallback, second))
    return ExecutionTrace(tuple(steps))
