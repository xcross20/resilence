from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.db.session import session_for
from app.services.errors import ApiError
from app.services.release import activate_release, read_events, read_pointer, restore_release, start_verification

router = APIRouter()


class ActivationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    candidate_revision: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_prior_revision: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    expected_generation: int = Field(ge=0)
    confirmation: str | None = None


class VerificationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cohort_id: str = Field(min_length=1)
    expected_manifest_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_fixture_version: str = Field(min_length=1, max_length=64)
    expected_active_revision: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    expected_generation: int = Field(ge=0)


class RestoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_generation: int = Field(ge=0)
    confirmation: str | None = None


def _idempotency_key(key: str | None) -> str:
    if key is None or not key.strip() or len(key.strip()) > 200:
        raise ApiError(422, "validation_error", "Idempotency-Key header is required")
    return key.strip()


def _finish(status: int, payload: dict) -> JSONResponse:
    return JSONResponse(status_code=status, content=payload)


@router.post("/api/v1/releases")
def post_release(
    body: ActivationBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _idempotency_key(idempotency_key)
    session = session_for(request)
    try:
        status, payload = activate_release(session, body.model_dump(), key, request.state.correlation_id)
        return _finish(status, payload)
    finally:
        session.close()


@router.get("/api/v1/releases/{workflow_id}")
def get_release(workflow_id: str, request: Request):
    session = session_for(request)
    try:
        return read_pointer(session, workflow_id)
    finally:
        session.close()


@router.get("/api/v1/releases/{workflow_id}/events")
def get_release_events(workflow_id: str, request: Request):
    session = session_for(request)
    try:
        return read_events(session, workflow_id)
    finally:
        session.close()


@router.post("/api/v1/releases/{workflow_id}/verifications")
def post_verification(
    workflow_id: str,
    body: VerificationBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _idempotency_key(idempotency_key)
    session = session_for(request)
    try:
        status, payload = start_verification(
            session, workflow_id, body.model_dump(), key, request.state.correlation_id
        )
        return _finish(status, payload)
    finally:
        session.close()


@router.post("/api/v1/releases/{workflow_id}/restore")
def post_restore(
    workflow_id: str,
    body: RestoreBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _idempotency_key(idempotency_key)
    session = session_for(request)
    try:
        status, payload = restore_release(session, workflow_id, body.model_dump(), key, request.state.correlation_id)
        return _finish(status, payload)
    finally:
        session.close()
