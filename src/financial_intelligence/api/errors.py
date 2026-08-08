"""Typed API error contract and exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

from financial_intelligence.observability.correlation import (
    get_correlation_id,
    resolve_correlation_id,
)
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.api.errors")


class ApiErrorBody(BaseModel):
    """Stable client-facing error payload."""

    code: str
    message: str
    correlation_id: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    """Envelope for all normalized API errors."""

    error: ApiErrorBody


def _correlation_id_from_request(request: Request) -> str:
    bound = get_correlation_id()
    if bound:
        return bound
    state_value = getattr(request.state, "correlation_id", None)
    if isinstance(state_value, str) and state_value:
        return state_value
    return resolve_correlation_id(request.headers.get("X-Correlation-ID")).value


def build_error_response(
    *,
    code: str,
    message: str,
    correlation_id: str,
    details: list[dict[str, Any]] | None = None,
    status_code: int,
) -> JSONResponse:
    """Build a predictable JSON error response without leaking internals."""

    payload = ApiErrorResponse(
        error=ApiErrorBody(
            code=code,
            message=message,
            correlation_id=correlation_id,
            details=details or [],
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Register validation, HTTP, and unexpected-error handlers."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        correlation_id = _correlation_id_from_request(request)
        safe_details = [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "invalid")),
                "type": str(error.get("type", "validation_error")),
            }
            for error in exc.errors()
        ]
        logger.info(
            "request_validation_failed",
            extra={"correlation_id": correlation_id, "error_count": len(safe_details)},
        )
        return build_error_response(
            code="validation_error",
            message="Request validation failed",
            correlation_id=correlation_id,
            details=safe_details,
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        correlation_id = _correlation_id_from_request(request)
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return build_error_response(
            code="http_error",
            message=message,
            correlation_id=correlation_id,
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        correlation_id = _correlation_id_from_request(request)
        logger.exception(
            "unhandled_exception",
            extra={
                "correlation_id": correlation_id,
                "path": str(request.url.path),
                "error_type": type(exc).__name__,
            },
        )
        return build_error_response(
            code="internal_error",
            message="An unexpected error occurred",
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
