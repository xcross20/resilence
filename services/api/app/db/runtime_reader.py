from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

# Application allowlist. The view is not a hardened database privilege boundary.
RUNTIME_VIEW_COLUMNS = (
    "case_id",
    "cohort_id",
    "request_text",
    "observation_id",
    "observed_category",
    "confidence_bps",
    "classifier_version",
    "observation_origin",
    "fixture_version",
    "workflow_id",
    "workflow_version",
)

_RUNTIME_SQL = """
SELECT
    case_id,
    cohort_id,
    request_text,
    observation_id,
    observed_category,
    confidence_bps,
    classifier_version,
    observation_origin,
    fixture_version,
    workflow_id,
    workflow_version
FROM runtime_case_v
WHERE cohort_id = :cohort_id AND case_id = :case_id
"""


@dataclass(frozen=True)
class RuntimeCase:
    case_id: str
    cohort_id: str
    request_text: str
    observation_id: str
    observed_category: str
    confidence_bps: int | None
    classifier_version: str
    observation_origin: str
    fixture_version: str
    workflow_id: str
    workflow_version: str


def fetch_runtime_case(session: Session, cohort_id: str, case_id: str) -> RuntimeCase | None:
    if "reference_label" in _RUNTIME_SQL or "expected_disposition" in _RUNTIME_SQL:
        raise RuntimeError("runtime reader query must not name reference fields")
    row = session.execute(text(_RUNTIME_SQL), {"cohort_id": cohort_id, "case_id": case_id}).mappings().one_or_none()
    if row is None:
        return None
    return RuntimeCase(**{column: row[column] for column in RUNTIME_VIEW_COLUMNS})
