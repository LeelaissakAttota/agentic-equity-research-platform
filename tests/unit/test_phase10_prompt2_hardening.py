"""Phase 10 Prompt 2 adversarial production-boundary tests."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.types import Message, Receive, Scope, Send

from financial_intelligence.api import create_app
from financial_intelligence.api.middleware import RequestSafetyMiddleware
from financial_intelligence.config.settings import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "test",
        "LOG_LEVEL": "WARNING",
        "ALLOWED_HOSTS": "localhost,127.0.0.1",
        "API_MAX_REQUEST_BODY_BYTES": 1_048_576,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "production",
        "LOG_LEVEL": "INFO",
        "ALLOWED_HOSTS": "api.example.com,127.0.0.1",
    }
    values.update(overrides)
    return _settings(**values)


def _scope(headers: Sequence[tuple[bytes, bytes]], *, path: str = "/probe") -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": list(headers),
        "client": ("127.0.0.1", 12345),
        "server": ("api.example.com", 80),
        "root_path": "",
    }


async def _exercise_boundary(
    *,
    headers: Sequence[tuple[bytes, bytes]],
    messages: Sequence[Message] | None = None,
    max_body_bytes: int = 4096,
    max_body_chunks: int = 1024,
    enforce_hosts: bool = True,
) -> tuple[bool, bytes, list[Message]]:
    called = False
    received = bytearray()
    incoming = list(messages or [{"type": "http.request", "body": b"", "more_body": False}])
    outgoing: list[Message] = []

    async def downstream(_scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal called
        called = True
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            received.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> Message:
        if incoming:
            return incoming.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        outgoing.append(message)

    middleware = RequestSafetyMiddleware(
        downstream,
        max_body_bytes=max_body_bytes,
        allowed_hosts=("api.example.com",),
        enforce_allowed_hosts=enforce_hosts,
        max_body_chunks=max_body_chunks,
    )
    await middleware(_scope(headers), receive, send)
    return called, bytes(received), outgoing


def _response_status(messages: Sequence[Message]) -> int:
    start = next(message for message in messages if message["type"] == "http.response.start")
    return int(start["status"])


def _response_json(messages: Sequence[Message]) -> dict[str, Any]:
    body = next(message for message in messages if message["type"] == "http.response.body")
    return json.loads(body.get("body", b"{}"))


def test_host_configuration_normalizes_whitespace_case_and_duplicates() -> None:
    settings = _production_settings(
        ALLOWED_HOSTS=" API.Example.COM,api.example.com, 127.0.0.1,API.EXAMPLE.COM "
    )
    assert settings.allowed_host_values() == ("api.example.com", "127.0.0.1")


@pytest.mark.parametrize(
    "raw",
    [
        "api.example.com:443",
        "https://api.example.com",
        "api.example.com/path",
        "api.example.com\nmalicious",
        "a" * 254,
        "999.999.999.999",
    ],
)
def test_malformed_production_host_configuration_fails_closed(raw: str) -> None:
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        _production_settings(ALLOWED_HOSTS=raw)


def test_missing_production_host_value_uses_local_only_fail_closed_default() -> None:
    settings = _settings(APP_ENV="production", LOG_LEVEL="INFO")
    assert settings.allowed_host_values() == ("localhost", "127.0.0.1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host_headers", "expected_status"),
    [
        ([(b"host", b"api.example.com")], 204),
        ([(b"host", b"API.EXAMPLE.COM:443")], 204),
        ([(b"host", b"api.example.com.evil")], 400),
        ([(b"host", b"api.example.com:evil")], 400),
        ([(b"host", b"api.example.com:0")], 400),
        ([(b"host", b"api.example.com:65536")], 400),
        ([(b"host", b"api.example.com\x00.evil")], 400),
        ([(b"host", b"a" * 2048)], 400),
        ([], 400),
        ([(b"host", b"api.example.com"), (b"host", b"evil.example")], 400),
        ([(b"host", b"api.example.com"), (b"host", b"api.example.com")], 400),
    ],
)
async def test_trusted_host_boundary_rejects_ambiguous_or_spoofed_values(
    host_headers: list[tuple[bytes, bytes]],
    expected_status: int,
) -> None:
    called, _, outgoing = await _exercise_boundary(headers=host_headers)
    assert _response_status(outgoing) == expected_status
    assert called is (expected_status == 204)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [0, 1, 4095, 4096])
async def test_declared_body_at_or_below_limit_is_replayed_exactly(size: int) -> None:
    body = b"x" * size
    called, received, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com"), (b"content-length", str(size).encode())],
        messages=[{"type": "http.request", "body": body, "more_body": False}],
    )
    assert called is True
    assert received == body
    assert _response_status(outgoing) == 204


@pytest.mark.asyncio
async def test_declared_body_one_byte_above_limit_is_rejected_before_read() -> None:
    called, _, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com"), (b"content-length", b"4097")],
        messages=[{"type": "http.request", "body": b"should-not-be-read", "more_body": False}],
    )
    assert called is False
    assert _response_status(outgoing) == 413
    assert _response_json(outgoing)["error"]["code"] == "request_too_large"


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [b"-1", b"+1", b" 1", b"1 ", b"1.0", b"abc"])
async def test_malformed_content_length_is_rejected(raw: bytes) -> None:
    called, _, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com"), (b"content-length", raw)]
    )
    assert called is False
    assert _response_status(outgoing) == 400
    assert _response_json(outgoing)["error"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_duplicate_content_length_is_rejected_even_when_values_match() -> None:
    called, _, outgoing = await _exercise_boundary(
        headers=[
            (b"host", b"api.example.com"),
            (b"content-length", b"1"),
            (b"content-length", b"1"),
        ],
        messages=[{"type": "http.request", "body": b"x", "more_body": False}],
    )
    assert called is False
    assert _response_status(outgoing) == 400
    assert _response_json(outgoing)["error"]["message"] == "Content-Length is ambiguous"


@pytest.mark.asyncio
async def test_absent_length_chunked_body_is_counted_by_received_bytes() -> None:
    called, received, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com")],
        messages=[
            {"type": "http.request", "body": b"a" * 2048, "more_body": True},
            {"type": "http.request", "body": b"b" * 2048, "more_body": False},
        ],
    )
    assert called is True
    assert received == (b"a" * 2048) + (b"b" * 2048)
    assert _response_status(outgoing) == 204


@pytest.mark.asyncio
async def test_chunked_body_crossing_limit_midstream_fails_without_downstream_call() -> None:
    called, _, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com")],
        messages=[
            {"type": "http.request", "body": b"a" * 4096, "more_body": True},
            {"type": "http.request", "body": b"b", "more_body": False},
        ],
    )
    assert called is False
    assert _response_status(outgoing) == 413


@pytest.mark.asyncio
async def test_multibyte_limit_counts_wire_bytes_not_characters() -> None:
    exact = "é".encode() * 2048
    called, received, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com")],
        messages=[{"type": "http.request", "body": exact, "more_body": False}],
    )
    assert called is True
    assert received == exact
    assert _response_status(outgoing) == 204

    called, _, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com")],
        messages=[{"type": "http.request", "body": exact + b"x", "more_body": False}],
    )
    assert called is False
    assert _response_status(outgoing) == 413


@pytest.mark.asyncio
async def test_excessive_zero_byte_chunks_are_bounded() -> None:
    called, _, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com")],
        messages=[
            {"type": "http.request", "body": b"", "more_body": True},
            {"type": "http.request", "body": b"", "more_body": True},
            {"type": "http.request", "body": b"", "more_body": False},
        ],
        max_body_chunks=2,
    )
    assert called is False
    assert _response_status(outgoing) == 413
    assert _response_json(outgoing)["error"]["code"] == "request_too_complex"


def test_http_exception_detail_is_never_reflected_to_client() -> None:
    app = create_app(settings=_settings())

    @app.get("/_phase10/http-error")
    def fail() -> None:
        raise HTTPException(
            status_code=400,
            detail="token=super-secret C:/private/secrets.env /etc/passwd",
        )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_phase10/http-error")

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Bad request"
    assert "super-secret" not in response.text
    assert "secrets.env" not in response.text
    assert "/etc/passwd" not in response.text


def test_unexpected_error_telemetry_uses_route_template_not_concrete_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(settings=_settings())

    @app.get("/_phase10/boom/{value}")
    def boom(value: str) -> None:
        raise RuntimeError(f"password={value}")

    secret = "token-secret-path"
    with (
        caplog.at_level(logging.ERROR),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get(
            f"/_phase10/boom/{secret}",
            params={"authorization": "Bearer secret-query"},
        )

    rendered = " ".join(str(record.__dict__) for record in caplog.records)
    assert response.status_code == 500
    assert secret not in rendered
    assert "secret-query" not in rendered
    error_record = next(
        record for record in caplog.records if record.message == "unhandled_exception"
    )
    assert error_record.operation == "/_phase10/boom/{value}"
    assert error_record.error_type == "RuntimeError"


def test_success_telemetry_omits_body_query_headers_cookies_and_concrete_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(settings=_settings(LOG_LEVEL="INFO"))

    @app.post("/_phase10/telemetry/{value}")
    def telemetry(value: str) -> dict[str, str]:
        return {"value": value}

    secrets = ("path-secret", "query-secret", "body-secret", "header-secret", "cookie-secret")
    with (
        caplog.at_level(logging.INFO, logger="financial_intelligence.api.requests"),
        TestClient(app) as client,
    ):
        response = client.post(
            f"/_phase10/telemetry/{secrets[0]}",
            params={"token": secrets[1]},
            json={"password": secrets[2]},
            headers={"Authorization": f"Bearer {secrets[3]}", "Cookie": f"session={secrets[4]}"},
        )

    rendered = " ".join(str(record.__dict__) for record in caplog.records)
    assert response.status_code == 200
    assert all(secret not in rendered for secret in secrets)
    record = next(record for record in caplog.records if record.message == "http_request_completed")
    assert record.operation == "/_phase10/telemetry/{value}"


def test_duplicate_correlation_headers_generate_a_fresh_safe_identifier() -> None:
    with TestClient(create_app(settings=_settings())) as client:
        response = client.get(
            "/health",
            headers=[
                ("X-Correlation-ID", "first-caller-id"),
                ("X-Correlation-ID", "second-caller-id"),
            ],
        )

    value = response.headers["X-Correlation-ID"]
    assert value not in {"first-caller-id", "second-caller-id"}
    assert UUID(value).version == 4


def test_rejection_telemetry_contains_only_safe_boundary_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        caplog.at_level(logging.INFO, logger="financial_intelligence.api.requests"),
        TestClient(create_app(settings=_production_settings())) as client,
    ):
        response = client.get(
            "/health",
            headers={
                "host": "token-secret.evil.example",
                "X-Correlation-ID": "boundary-reject-1",
                "Authorization": "Bearer header-secret",
            },
        )

    rendered = " ".join(str(record.__dict__) for record in caplog.records)
    assert response.status_code == 400
    assert "token-secret" not in rendered
    assert "header-secret" not in rendered
    record = next(record for record in caplog.records if record.message == "http_request_rejected")
    assert record.operation == "request_boundary"
    assert record.error_code == "invalid_host"


def test_readiness_exposes_safe_current_checks_only() -> None:
    with TestClient(create_app(settings=_settings())) as client:
        health = client.get("/health").json()
        ready = client.get("/ready").json()
        version = client.get("/version").json()

    assert "checks" not in health
    assert {check["name"] for check in ready["checks"]} == {"application", "configuration"}
    rendered = json.dumps(ready)
    for forbidden in ("allowed_hosts", "api_max_request_body_bytes", "database_url", "redis_url"):
        assert forbidden not in rendered
    assert set(version) == {"service", "version", "environment"}


def test_watchlist_nested_collections_and_unknown_fields_are_bounded() -> None:
    with TestClient(create_app(settings=_settings())) as client:
        too_many_entries = client.post(
            "/watchlists",
            json={
                "name": "oversized",
                "entries": [{"q": f"Company {index}"} for index in range(101)],
                "capabilities": ["market"],
            },
        )
        too_many_capabilities = client.post(
            "/watchlists",
            json={
                "name": "capabilities",
                "entries": [],
                "capabilities": ["market", "financial", "news", "regulatory", "market"],
            },
        )
        unknown_control = client.post(
            "/watchlists",
            json={
                "name": "unknown-control",
                "entries": [],
                "capabilities": ["market"],
                "approve_workflow": True,
            },
        )

    assert too_many_entries.status_code == 422
    assert too_many_capabilities.status_code == 422
    assert unknown_control.status_code == 422
    assert all(
        response.json()["error"]["code"] == "validation_error"
        for response in (too_many_entries, too_many_capabilities, unknown_control)
    )


def test_workflow_list_and_memory_query_limits_are_publicly_bounded() -> None:
    with TestClient(create_app(settings=_settings())) as client:
        too_many_workflows = client.get("/research/workflows", params={"limit": 201})
        negative_offset = client.get("/research/workflows", params={"offset": -1})
        too_many_memory_records = client.get(
            "/research/workflows/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/memory",
            params={"limit": 201},
        )

    assert too_many_workflows.status_code == 400
    assert too_many_workflows.json()["error"]["code"] == "invalid_workflow_list_query"
    assert negative_offset.status_code == 400
    assert negative_offset.json()["error"]["code"] == "invalid_workflow_list_query"
    assert too_many_memory_records.status_code == 400
    assert too_many_memory_records.json()["error"]["code"] == "invalid_memory_list_query"
