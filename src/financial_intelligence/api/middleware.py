"""HTTP middleware for correlation, safety, and operational traceability."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Awaitable, Callable
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from financial_intelligence.observability.correlation import (
    CORRELATION_HEADER,
    bind_correlation_id,
    reset_correlation_id,
    resolve_correlation_id,
)
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.api.requests")
MAX_REQUEST_BODY_CHUNKS = 1024
_CONTENT_LENGTH_PATTERN = re.compile(r"^[0-9]+$")


def _header_values(scope: Scope, name: bytes) -> tuple[str, ...]:
    return tuple(
        value.decode("latin-1") for key, value in scope.get("headers", ()) if key.lower() == name
    )


def _correlation_from_scope(scope: Scope) -> str:
    values = _header_values(scope, CORRELATION_HEADER.lower().encode("ascii"))
    raw = values[0] if len(values) == 1 else None
    return resolve_correlation_id(raw).value


def _request_operation(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if isinstance(route_path, str) else "unmatched"


def _status_category(status_code: int) -> str:
    if status_code >= 500:
        return "server_error"
    if status_code >= 400:
        return "client_error"
    return "success"


def _host_without_port(raw: str) -> str | None:
    if len(raw) > 259 or raw != raw.strip():
        return None
    candidate = raw.lower()
    if not candidate or candidate.startswith("[") or candidate.count(":") > 1:
        return None
    if ":" not in candidate:
        return candidate
    host, port = candidate.split(":", maxsplit=1)
    if not host or not _CONTENT_LENGTH_PATTERN.fullmatch(port):
        return None
    if not 1 <= int(port) <= 65535:
        return None
    return host


class RequestSafetyMiddleware:
    """Reject untrusted hosts and oversized bodies before route processing."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        allowed_hosts: tuple[str, ...],
        enforce_allowed_hosts: bool,
        max_body_chunks: int = MAX_REQUEST_BODY_CHUNKS,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.enforce_allowed_hosts = enforce_allowed_hosts
        self.max_body_chunks = max_body_chunks

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = _correlation_from_scope(scope)
        if self.enforce_allowed_hosts:
            host_values = _header_values(scope, b"host")
            host = _host_without_port(host_values[0]) if len(host_values) == 1 else None
            if not host or host not in self.allowed_hosts:
                await self._reject(
                    send,
                    status_code=400,
                    code="invalid_host",
                    message="Request host is not allowed",
                    correlation_id=correlation_id,
                )
                return

        content_length_values = _header_values(scope, b"content-length")
        if len(content_length_values) > 1:
            await self._reject(
                send,
                status_code=400,
                code="invalid_request",
                message="Content-Length is ambiguous",
                correlation_id=correlation_id,
            )
            return
        if content_length_values:
            content_length = content_length_values[0]
            if not _CONTENT_LENGTH_PATTERN.fullmatch(content_length):
                await self._reject(
                    send,
                    status_code=400,
                    code="invalid_request",
                    message="Content-Length is invalid",
                    correlation_id=correlation_id,
                )
                return
            normalized_length = content_length.lstrip("0") or "0"
            maximum = str(self.max_body_bytes)
            if len(normalized_length) > len(maximum) or (
                len(normalized_length) == len(maximum) and normalized_length > maximum
            ):
                await self._reject_too_large(send, correlation_id)
                return

        messages: deque[Message] = deque()
        total = 0
        body_chunks = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            body_chunks += 1
            if body_chunks > self.max_body_chunks:
                await self._reject(
                    send,
                    status_code=413,
                    code="request_too_complex",
                    message="Request body contains too many chunks",
                    correlation_id=correlation_id,
                )
                return
            total += len(message.get("body", b""))
            if total > self.max_body_bytes:
                await self._reject_too_large(send, correlation_id)
                return
            if not message.get("more_body", False):
                break

        async def replay_receive() -> Message:
            if messages:
                return messages.popleft()
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

    async def _reject_too_large(self, send: Send, correlation_id: str) -> None:
        await self._reject(
            send,
            status_code=413,
            code="request_too_large",
            message="Request body exceeds the configured limit",
            correlation_id=correlation_id,
        )

    async def _reject(
        self,
        send: Send,
        *,
        status_code: int,
        code: str,
        message: str,
        correlation_id: str,
    ) -> None:
        logger.info(
            "http_request_rejected",
            extra={
                "correlation_id": correlation_id,
                "operation": "request_boundary",
                "status": "client_error",
                "status_code": status_code,
                "error_code": code,
            },
        )
        response = JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "correlation_id": correlation_id,
                    "details": [],
                }
            },
            headers={
                CORRELATION_HEADER: correlation_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
            },
        )
        await response({"type": "http"}, self._empty_receive, send)

    @staticmethod
    async def _empty_receive() -> Message:
        return {"type": "http.disconnect"}


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a validated correlation ID."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation = resolve_correlation_id(_correlation_from_scope(request.scope))
        token = bind_correlation_id(correlation.value)
        request.state.correlation_id = correlation.value
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "http_request_failed",
                extra={
                    "operation": _request_operation(request),
                    "method": request.method,
                    "status": "server_error",
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            reset_correlation_id(token)
            raise
        logger.info(
            "http_request_completed",
            extra={
                "operation": _request_operation(request),
                "method": request.method,
                "status": _status_category(response.status_code),
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
        reset_correlation_id(token)
        response.headers[CORRELATION_HEADER] = correlation.value
        return response
