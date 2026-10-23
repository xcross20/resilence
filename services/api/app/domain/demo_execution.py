"""Server-owned synthetic fixture hook. Request bodies cannot name a method to fail."""

FAIL_FIRST_ECONOMY_CASE_IDS = frozenset({"SYN-D-000"})


def fail_methods_for(case_id: str, selected_method: str) -> frozenset[str]:
    """Fail the first economy attempt on one demo case so fallback cost and latency are persisted."""
    if case_id in FAIL_FIRST_ECONOMY_CASE_IDS and selected_method == "economy":
        return frozenset({"economy"})
    return frozenset()
