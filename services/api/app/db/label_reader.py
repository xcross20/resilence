from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.assessment import ReferenceExpectation


def fetch_reference_label(session: Session, cohort_id: str, case_id: str) -> ReferenceExpectation | None:
    row = session.execute(
        text(
            """
            SELECT reference_category, expected_disposition, expected_resolution, rubric_version
            FROM reference_label
            WHERE cohort_id = :cohort_id AND case_id = :case_id
            """
        ),
        {"cohort_id": cohort_id, "case_id": case_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    return ReferenceExpectation(
        reference_category=row["reference_category"],
        expected_disposition=row["expected_disposition"],
        expected_resolution=row["expected_resolution"],
        rubric_version=row["rubric_version"],
    )
