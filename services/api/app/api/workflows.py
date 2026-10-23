from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db.session import session_for
from app.services.errors import ApiError

router = APIRouter()


@router.get("/api/v1/workflows/{workflow_id}")
def get_workflow(workflow_id: str, request: Request):
    session = session_for(request)
    try:
        workflow = session.execute(
            text("SELECT workflow_id, version, graph_json FROM workflow_definition WHERE workflow_id = :workflow_id"),
            {"workflow_id": workflow_id},
        ).mappings().one_or_none()
        if workflow is None:
            raise ApiError(404, "workflow_not_found", "Workflow does not exist")
        cohorts = session.execute(
            text(
                """
                SELECT cohort_id, version, purpose, fixture_version, manifest_sha256, case_ids
                FROM cohort_manifest WHERE workflow_id = :workflow_id ORDER BY cohort_id
                """
            ),
            {"workflow_id": workflow_id},
        ).mappings().all()
        pointer = session.execute(
            text(
                """
                SELECT generation, revision_sha256
                FROM active_policy_pointer
                WHERE workflow_id = :workflow_id
                """
            ),
            {"workflow_id": workflow_id},
        ).mappings().one_or_none()
        active_policy = None
        if pointer is not None and pointer["generation"] > 0 and pointer["revision_sha256"] is not None:
            active_policy = {
                "revision_sha256": pointer["revision_sha256"],
                "generation": pointer["generation"],
            }
        return {
            "workflow_id": workflow["workflow_id"],
            "version": workflow["version"],
            "graph": workflow["graph_json"],
            "cohorts": [dict(row) for row in cohorts],
            "active_policy": active_policy,
        }
    finally:
        session.close()
