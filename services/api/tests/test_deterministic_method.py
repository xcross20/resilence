import json
from pathlib import Path

from app.domain.simulation import CODE_METHOD_VERSION, DETERMINISTIC_RESOLUTION, METHOD_VERSION, simulate_method

PRICE = json.loads(
    (Path(__file__).resolve().parents[1] / "app/fixtures/service_desk_v1/price_book.json").read_text(encoding="utf-8")
)


def test_deterministic_replacement_does_not_use_a_simulated_model_price() -> None:
    result = simulate_method("deterministic", "ambiguous")
    assert result.method_version == CODE_METHOD_VERSION == "synthetic-code-v1"
    assert result.produced_disposition == "automated"
    assert result.produced_resolution == DETERMINISTIC_RESOLUTION == "synthetic-deterministic-template"
    assert result.amount_micro_usd == PRICE["methods"]["deterministic"]["amount_micro_usd"]
    assert result.simulated_latency_ms == PRICE["methods"]["deterministic"]["latency_ms"]
    assert result.amount_micro_usd != PRICE["methods"]["premium"]["amount_micro_usd"]
    assert result.evidence_origin == "synthetic_simulated"
    assert result.price_book_version == PRICE["version"] == "synthetic-price-v2"


def test_deterministic_privileged_observation_escalates_without_a_reference_label() -> None:
    result = simulate_method("deterministic", "privileged")
    assert result.produced_disposition == "escalated"
    assert result.produced_resolution == "synthetic-escalation"
    assert result.method_version == "synthetic-code-v1"


def test_economy_routine_remains_a_simulated_model_call() -> None:
    result = simulate_method("economy", "routine")
    assert result.method_version == METHOD_VERSION == "synthetic-method-v1"
    assert result.produced_disposition == "automated"
    assert result.produced_resolution == "synthetic-automation"
    assert result.amount_micro_usd == PRICE["methods"]["economy"]["amount_micro_usd"]
