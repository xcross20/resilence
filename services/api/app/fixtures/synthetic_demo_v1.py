"""Deterministic synthetic-demo cases. These rows are not a statistical sample."""

DEMO_WORKFLOW_ID = "service-desk-synthetic-demo"
DEMO_WORKFLOW_VERSION = "service-desk-synthetic-demo-v1"
FIXTURE_VERSION = "synthetic-demo-fixture-v1"
ACCEPTANCE_COHORT_ID = "synthetic-demo-acceptance"
VERIFICATION_COHORT_ID = "synthetic-demo-verification"
AUTOMATED_RESOLUTION = "synthetic-automation"
ESCALATED_RESOLUTION = "synthetic-escalation"


def _profile(index: int, count: int) -> str:
    if index < count - 20:
        return "routine"
    if index < count - 4:
        return "ambiguous"
    return "privileged"


def build_cases(
    prefix: str,
    count: int,
    *,
    profile_for=None,
    label_overrides: dict[int, dict] | None = None,
    drop_labels: set[int] | None = None,
) -> list[dict]:
    overrides = label_overrides or {}
    omitted = drop_labels or set()
    cases = []
    for index in range(count):
        profile = profile_for(index, count) if profile_for else _profile(index, count)
        case_id = f"{prefix}-{index:03d}"
        if profile == "privileged":
            observed = "privileged"
            label = {
                "reference_category": "privileged",
                "expected_disposition": "escalated",
                "expected_resolution": ESCALATED_RESOLUTION,
            }
        elif profile == "ambiguous":
            observed = "ambiguous"
            label = {
                "reference_category": "ambiguous",
                "expected_disposition": "automated",
                "expected_resolution": AUTOMATED_RESOLUTION,
            }
        else:
            observed = "routine"
            label = {
                "reference_category": "routine",
                "expected_disposition": "automated",
                "expected_resolution": AUTOMATED_RESOLUTION,
            }
        if index in overrides:
            label = overrides[index]
        row = {
            "case_id": case_id,
            "request_text": f"synthetic demo case {case_id}",
            "observation_id": f"obs-{case_id}",
            "observed_category": observed,
            "confidence_bps": 8000,
        }
        if index not in omitted:
            row["label"] = label
        cases.append(row)
    return cases


def acceptance_cases(count: int = 100) -> list[dict]:
    return build_cases("SYN-D", count)


def verification_cases(count: int = 20) -> list[dict]:
    return build_cases("SYN-V", count, profile_for=lambda _index, _count: "routine")


def privileged_only_cases(count: int = 100) -> list[dict]:
    return build_cases("SYN-Z", count, profile_for=lambda _index, _count: "privileged")
