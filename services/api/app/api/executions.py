from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.db.session import session_for
from app.services.errors import ApiError
from app.services.run_case import execute_case, read_evidence

router = APIRouter()


class ExecuteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str = Field(min_length=1)
    cohort_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    revision_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _idempotency_key(key: str | None) -> str:
    if key is None or not key.strip() or len(key.strip()) > 200:
        raise ApiError(422, "validation_error", "Idempotency-Key header is required")
    return key.strip()


@router.post("/api/v1/executions")
def post_execution(
    body: ExecuteBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _idempotency_key(idempotency_key)
    session = session_for(request)
    try:
        status, evidence = execute_case(session, body.model_dump(), key, request.state.correlation_id)
        return JSONResponse(status_code=status, content=evidence)
    finally:
        session.close()


@router.get("/api/v1/executions/{run_id}/evidence")
def get_evidence(run_id: str, request: Request):
    session = session_for(request)
    try:
        return read_evidence(session, run_id)
    finally:
        session.close()
