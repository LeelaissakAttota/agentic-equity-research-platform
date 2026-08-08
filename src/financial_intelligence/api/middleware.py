"""HTTP middleware for correlation identifiers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from financial_intelligence.observability.correlation import (
    CORRELATION_HEADER,
    bind_correlation_id,
    reset_correlation_id,
    resolve_correlation_id,
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a validated correlation ID."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        inbound = request.headers.get(CORRELATION_HEADER)
        correlation = resolve_correlation_id(inbound)
        token = bind_correlation_id(correlation.value)
        request.state.correlation_id = correlation.value
        try:
            response = await call_next(request)
        except Exception:
            reset_correlation_id(token)
            raise
        reset_correlation_id(token)
        response.headers[CORRELATION_HEADER] = correlation.value
        return response
