import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.api.executions import router as executions_router
from app.db.database_url import create_database_engine
from app.api.revisions import router as revisions_router
from app.api.workflows import router as workflows_router
from app.services.errors import ApiError


def create_app(engine=None) -> FastAPI:
    app = FastAPI(title="Execution Optimizer IMP-001", version="0.1.0")
    app.state.engine = engine or create_database_engine()

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "correlation_id": request.state.correlation_id,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Request failed schema validation",
                "correlation_id": getattr(request.state, "correlation_id", None),
                "details": {"errors": jsonable_encoder(exc.errors())},
            },
        )

    app.include_router(workflows_router)
    app.include_router(revisions_router)
    app.include_router(executions_router)
    return app


