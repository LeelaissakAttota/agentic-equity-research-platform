"""Bounded HTTP GET client for optional market-data acquisition.

Uses the standard library only. Never follows arbitrary user-supplied URLs:
callers must construct allowlisted provider URLs.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpFailureKind(StrEnum):
    """Normalized HTTP failure categories for provider adapters."""

    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    INVALID_RESPONSE = "invalid_response"
    UPSTREAM_ERROR = "upstream_error"
    NETWORK_ERROR = "network_error"
    OVERSIZED = "oversized"


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Bounded successful HTTP response body."""

    status_code: int
    body: bytes
    content_type: str | None
    headers: dict[str, str]


class HttpTransportError(Exception):
    """Normalized transport/provider HTTP failure."""

    def __init__(
        self, kind: HttpFailureKind, message: str, *, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


class HttpTransport(Protocol):
    """Injectable transport for tests (no live network in CI)."""

    def request(
        self, method: str, url: str, *, headers: dict[str, str], timeout: float
    ) -> HttpResponse:
        """Perform one HTTP request and return a bounded response."""


class UrlLibHttpTransport:
    """stdlib urllib transport with response-size enforcement."""

    def __init__(self, *, max_response_bytes: int) -> None:
        if max_response_bytes < 1:
            msg = "max_response_bytes must be positive"
            raise ValueError(msg)
        self._max_response_bytes = max_response_bytes

    def request(
        self, method: str, url: str, *, headers: dict[str, str], timeout: float
    ) -> HttpResponse:
        if method.upper() != "GET":
            msg = "only GET is supported"
            raise ValueError(msg)
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                content_type = response.headers.get("Content-Type")
                body = self._read_bounded(response)
                header_map = {k.lower(): v for k, v in response.headers.items()}
        except HTTPError as exc:
            body = self._read_bounded(exc)
            header_map = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            return HttpResponse(
                status_code=int(exc.code),
                body=body,
                content_type=header_map.get("content-type"),
                headers=header_map,
            )
        except TimeoutError as exc:
            raise HttpTransportError(HttpFailureKind.TIMEOUT, "http request timed out") from exc
        except URLError as exc:
            reason = str(exc.reason)
            if "timed out" in reason.lower():
                raise HttpTransportError(HttpFailureKind.TIMEOUT, "http request timed out") from exc
            raise HttpTransportError(
                HttpFailureKind.NETWORK_ERROR, f"network error: {reason}"
            ) from exc
        return HttpResponse(
            status_code=status,
            body=body,
            content_type=content_type,
            headers=header_map,
        )

    def _read_bounded(self, response: object) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)  # type: ignore[attr-defined]
            if not chunk:
                break
            total += len(chunk)
            if total > self._max_response_bytes:
                raise HttpTransportError(
                    HttpFailureKind.OVERSIZED,
                    f"response exceeded {self._max_response_bytes} bytes",
                )
            chunks.append(chunk)
        return b"".join(chunks)


class BoundedHttpClient:
    """GET client with timeout, size limits, bounded retries, and normalization."""

    def __init__(
        self,
        transport: HttpTransport,
        *,
        timeout_seconds: float,
        max_retries: int,
        user_agent: str,
        retryable_statuses: frozenset[int] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        if max_retries < 0:
            msg = "max_retries must be non-negative"
            raise ValueError(msg)
        if not user_agent.strip():
            msg = "user_agent is required"
            raise ValueError(msg)
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._user_agent = user_agent.strip()
        self._retryable_statuses = retryable_statuses or frozenset({429, 500, 502, 503, 504})

    def get_json(self, url: str) -> dict[str, object]:
        """GET JSON with bounded retries. Raises HttpTransportError on failure."""

        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
        }
        attempts = self._max_retries + 1
        last_error: HttpTransportError | None = None
        for attempt in range(attempts):
            try:
                response = self._transport.request(
                    "GET",
                    url,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            except HttpTransportError as exc:
                last_error = exc
                if (
                    exc.kind in {HttpFailureKind.TIMEOUT, HttpFailureKind.NETWORK_ERROR}
                    and attempt + 1 < attempts
                ):
                    time.sleep(min(2**attempt * 0.05, 1.0))
                    continue
                raise
            if response.status_code == 200:
                return self._parse_json(response)
            kind = self._classify_status(response.status_code)
            last_error = HttpTransportError(
                kind,
                f"http status {response.status_code}",
                status_code=response.status_code,
            )
            if response.status_code in self._retryable_statuses and attempt + 1 < attempts:
                delay = min(2**attempt * 0.05, 1.0)
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    delay = min(float(retry_after), 2.0)
                time.sleep(delay)
                continue
            raise last_error
        assert last_error is not None
        raise last_error

    def _parse_json(self, response: HttpResponse) -> dict[str, object]:
        content_type = (response.content_type or "").lower()
        if content_type and "json" not in content_type and "text/plain" not in content_type:
            raise HttpTransportError(
                HttpFailureKind.INVALID_RESPONSE,
                f"unexpected content-type: {response.content_type}",
                status_code=response.status_code,
            )
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpTransportError(
                HttpFailureKind.INVALID_RESPONSE,
                "response body is not valid JSON",
                status_code=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise HttpTransportError(
                HttpFailureKind.INVALID_RESPONSE,
                "JSON root must be an object",
                status_code=response.status_code,
            )
        return payload

    @staticmethod
    def _classify_status(status_code: int) -> HttpFailureKind:
        if status_code == 401 or status_code == 403:
            return HttpFailureKind.UNAUTHORIZED
        if status_code == 404:
            return HttpFailureKind.NOT_FOUND
        if status_code == 429:
            return HttpFailureKind.RATE_LIMITED
        if 500 <= status_code <= 599:
            return HttpFailureKind.UPSTREAM_ERROR
        if 400 <= status_code <= 499:
            return HttpFailureKind.INVALID_RESPONSE
        return HttpFailureKind.UPSTREAM_ERROR
