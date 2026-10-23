from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.db.session import session_for
from app.services.errors import ApiError
from app.services.evaluation import read_evaluation, read_evaluation_cases, read_evaluations, start_evaluation

router = APIRouter()


class EvaluationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str = Field(min_length=1)
    cohort_id: str = Field(min_length=1)
    baseline_revision: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_revision: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_manifest_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_fixture_version: str = Field(min_length=1, max_length=64)
    expected_price_book_version: str = Field(min_length=1, max_length=64)
    expected_evaluator_version: str = Field(min_length=1, max_length=64)
    expected_accounting_version: str = Field(min_length=1, max_length=64)
    expected_gate_policy_version: str = Field(min_length=1, max_length=64)


def _idempotency_key(key: str | None) -> str:
    if key is None or not key.strip() or len(key.strip()) > 200:
        raise ApiError(422, "validation_error", "Idempotency-Key header is required")
    return key.strip()


@router.post("/api/v1/evaluations")
def post_evaluation(
    body: EvaluationBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _idempotency_key(idempotency_key)
    session = session_for(request)
    try:
        status, payload = start_evaluation(session, body.model_dump(), key, request.state.correlation_id)
        return JSONResponse(status_code=status, content=payload)
    finally:
        session.close()


@router.get("/api/v1/evaluations")
def get_evaluations(workflow_id: str, request: Request):
    session = session_for(request)
    try:
        return read_evaluations(session, workflow_id)
    finally:
        session.close()


@router.get("/api/v1/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, request: Request):
    session = session_for(request)
    try:
        return read_evaluation(session, evaluation_id)
    finally:
        session.close()


@router.get("/api/v1/evaluations/{evaluation_id}/cases")
def get_evaluation_cases(evaluation_id: str, request: Request, limit: int = 50, offset: int = 0):
    session = session_for(request)
    try:
        return read_evaluation_cases(session, evaluation_id, limit, offset)
    finally:
        session.close()
