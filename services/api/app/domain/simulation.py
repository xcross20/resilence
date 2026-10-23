import hashlib
import json
from dataclasses import dataclass

from app.domain.pricing import price_method

METHOD_VERSION = "synthetic-method-v1"
EVIDENCE_ORIGIN = "synthetic_simulated"


@dataclass(frozen=True)
class SimulatedAttempt:
    method_id: str
    method_version: str
    status: str
    produced_disposition: str
    produced_resolution: str
    simulated_latency_ms: int
    amount_micro_usd: int
    price_book_version: str
    input_digest: str
    output_digest: str
    evidence_origin: str


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def simulate_method(method: str, observed_category: str, *, force_failure: bool = False) -> SimulatedAttempt:
    """Synthetic method output depends on the method and the observed category only."""
    price = price_method(method)
    input_digest = _digest({"method": method, "observed_category": observed_category, "method_version": METHOD_VERSION})
    if force_failure:
        output = {"disposition": "none", "resolution": "", "status": "failed"}
        return SimulatedAttempt(
            method_id=method,
            method_version=METHOD_VERSION,
            status="failed",
            produced_disposition="none",
            produced_resolution="",
            simulated_latency_ms=price.latency_ms,
            amount_micro_usd=price.amount_micro_usd,
            price_book_version=price.price_book_version,
            input_digest=input_digest,
            output_digest=_digest(output),
            evidence_origin=EVIDENCE_ORIGIN,
        )
    if method == "economy" or observed_category == "routine":
        disposition = "automated"
        resolution = "synthetic-automation"
    else:
        disposition = "escalated"
        resolution = "synthetic-escalation"
    output = {"disposition": disposition, "resolution": resolution, "status": "succeeded"}
    return SimulatedAttempt(
        method_id=method,
        method_version=METHOD_VERSION,
        status="succeeded",
        produced_disposition=disposition,
        produced_resolution=resolution,
        simulated_latency_ms=price.latency_ms,
        amount_micro_usd=price.amount_micro_usd,
        price_book_version=price.price_book_version,
        input_digest=input_digest,
        output_digest=_digest(output),
        evidence_origin=EVIDENCE_ORIGIN,
    )
