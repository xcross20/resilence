import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.db.session import session_for
from app.domain.strategy import StrategyDocument
from app.services.errors import ApiError
from app.services.run_case import store_revision

router = APIRouter()


@router.post("/api/v1/strategies/revisions")
async def post_revision(request: Request):
    try:
        document = StrategyDocument.model_validate(await request.json())
    except ValidationError as exc:
        raise ApiError(
            422,
            "validation_error",
            "Strategy document failed validation",
            {"errors": json.loads(exc.json())},
        ) from exc
    session = session_for(request)
    try:
        status, body = store_revision(session, document)
        return JSONResponse(status_code=status, content=body)
    finally:
        session.close()
