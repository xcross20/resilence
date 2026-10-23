import hashlib
import json
from dataclasses import dataclass

from app.domain.pricing import price_method

METHOD_VERSION = "synthetic-method-v1"
CODE_METHOD_VERSION = "synthetic-code-v1"
DETERMINISTIC_RESOLUTION = "synthetic-deterministic-template"
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


def _method_version(method: str) -> str:
    if method == "deterministic":
        return CODE_METHOD_VERSION
    return METHOD_VERSION


def _successful_output(method: str, observed_category: str) -> tuple[str, str]:
    """Code replacement never prices a simulated model call. It does not read a reference label."""
    if method == "deterministic":
        if observed_category == "privileged":
            return "escalated", "synthetic-escalation"
        return "automated", DETERMINISTIC_RESOLUTION
    if method == "economy" or observed_category == "routine":
        return "automated", "synthetic-automation"
    return "escalated", "synthetic-escalation"


def simulate_method(method: str, observed_category: str, *, force_failure: bool = False) -> SimulatedAttempt:
    """Synthetic method output depends on the method and the observed category only."""
    price = price_method(method)
    method_version = _method_version(method)
    input_digest = _digest({"method": method, "observed_category": observed_category, "method_version": method_version})
    if force_failure:
        disposition, resolution, status = "none", "", "failed"
    else:
        disposition, resolution = _successful_output(method, observed_category)
        status = "succeeded"
    output = {"disposition": disposition, "resolution": resolution, "status": status}
    return SimulatedAttempt(
        method_id=method,
        method_version=method_version,
        status=status,
        produced_disposition=disposition,
        produced_resolution=resolution,
        simulated_latency_ms=price.latency_ms,
        amount_micro_usd=price.amount_micro_usd,
        price_book_version=price.price_book_version,
        input_digest=input_digest,
        output_digest=_digest(output),
        evidence_origin=EVIDENCE_ORIGIN,
    )
