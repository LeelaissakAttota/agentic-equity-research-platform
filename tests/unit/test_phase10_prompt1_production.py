"""Phase 10 Prompt 1 production-readiness foundation tests."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.types import Message, Receive, Scope, Send

from financial_intelligence.api import create_app
from financial_intelligence.api.middleware import RequestSafetyMiddleware
from financial_intelligence.config.settings import Settings
from financial_intelligence.observability.logging import StructuredFormatter


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


def test_safe_production_configuration_is_explicit_and_stable() -> None:
    settings = _production_settings()

    assert settings.app_env == "production"
    assert settings.allowed_host_values() == ("api.example.com", "127.0.0.1")
    assert settings.api_max_request_body_bytes == 1_048_576
    assert settings.allow_paid_models is False
    assert settings.safe_log_context()["allowed_hosts"] == (
        "api.example.com",
        "127.0.0.1",
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"LOG_LEVEL": "DEBUG"}, "LOG_LEVEL=DEBUG"),
        ({"ALLOWED_HOSTS": "*"}, "explicit non-wildcard"),
        ({"ALLOWED_HOSTS": ""}, "explicit non-wildcard"),
        ({"ALLOWED_HOSTS": "https://api.example.com"}, "invalid hostname"),
        (
            {"MARKET_DATA_LIVE_ENABLED": True, "MARKET_DATA_PRIMARY_PROVIDER": "none"},
            "live market data",
        ),
        (
            {"FINANCIAL_DATA_LIVE_ENABLED": True, "FINANCIAL_DATA_PRIMARY_PROVIDER": "none"},
            "live financial data",
        ),
    ],
)
def test_unsafe_production_configuration_fails_closed(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _production_settings(**overrides)


def test_request_body_limit_is_bounded_by_configuration() -> None:
    with pytest.raises(ValidationError):
        _settings(API_MAX_REQUEST_BODY_BYTES=4095)
    with pytest.raises(ValidationError):
        _settings(API_MAX_REQUEST_BODY_BYTES=10_485_761)


def test_production_host_allowlist_rejects_untrusted_host_with_safe_error() -> None:
    with TestClient(create_app(settings=_production_settings())) as client:
        response = client.get(
            "/health",
            headers={"host": "evil.example", "X-Correlation-ID": "host-reject-1"},
        )

    assert response.status_code == 400
    assert response.headers["X-Correlation-ID"] == "host-reject-1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json() == {
        "error": {
            "code": "invalid_host",
            "message": "Request host is not allowed",
            "correlation_id": "host-reject-1",
            "details": [],
        }
    }


def test_production_allowed_host_preserves_health_ready_version_distinction() -> None:
    headers = {"host": "api.example.com", "X-Correlation-ID": "ops-1"}
    with TestClient(create_app(settings=_production_settings())) as client:
        health = client.get("/health", headers=headers)
        ready = client.get("/ready", headers=headers)
        version = client.get("/version", headers=headers)

    assert health.status_code == ready.status_code == version.status_code == 200
    assert "checks" not in health.json()
    checks = {item["name"]: item for item in ready.json()["checks"]}
    assert checks["application"]["ready"] is True
    assert checks["configuration"] == {
        "name": "configuration",
        "ready": True,
        "detail": "production_configuration_validated",
    }
    assert version.json()["environment"] == "production"


def test_oversized_body_fails_before_route_processing_and_retains_correlation() -> None:
    settings = _settings(API_MAX_REQUEST_BODY_BYTES=4096)
    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/research/plans",
            content=b"x" * 4097,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": "body-limit-1",
            },
        )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "request_too_large"
    assert payload["error"]["correlation_id"] == "body-limit-1"
    assert "4097" not in response.text


@pytest.mark.asyncio
async def test_chunked_body_without_content_length_is_still_bounded() -> None:
    called = False
    incoming: list[Message] = [
        {"type": "http.request", "body": b"a" * 3000, "more_body": True},
        {"type": "http.request", "body": b"b" * 2000, "more_body": False},
    ]
    outgoing: list[Message] = []

    async def downstream(_scope: Scope, _receive: Receive, _send: Send) -> None:
        nonlocal called
        called = True

    async def receive() -> Message:
        return incoming.pop(0)

    async def send(message: Message) -> None:
        outgoing.append(message)

    middleware = RequestSafetyMiddleware(
        downstream,
        max_body_bytes=4096,
        allowed_hosts=("localhost",),
        enforce_allowed_hosts=False,
    )
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/research/synthesis",
        "raw_path": b"/research/synthesis",
        "query_string": b"",
        "headers": [(b"x-correlation-id", b"chunked-limit-1")],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 80),
        "root_path": "",
    }

    await middleware(scope, receive, send)

    assert called is False
    start = next(message for message in outgoing if message["type"] == "http.response.start")
    body = next(message for message in outgoing if message["type"] == "http.response.body")
    assert start["status"] == 413
    assert json.loads(body["body"])["error"]["correlation_id"] == "chunked-limit-1"


def test_request_observability_uses_route_template_and_safe_status(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        caplog.at_level(logging.INFO, logger="financial_intelligence.api.requests"),
        TestClient(create_app(settings=_settings(LOG_LEVEL="INFO"))) as client,
    ):
        response = client.get(
            "/health",
            headers={"X-Correlation-ID": "trace-safe-1"},
        )

    assert response.status_code == 200
    record = next(record for record in caplog.records if record.message == "http_request_completed")
    assert record.operation == "/health"
    assert record.method == "GET"
    assert record.status == "success"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, float)


def test_unexpected_exception_content_is_absent_from_response_and_structured_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(settings=_settings())

    @app.get("/_phase10/boom")
    def boom() -> None:
        raise RuntimeError("password=hunter2 C:/private/secrets.env")

    with (
        caplog.at_level(logging.ERROR),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get(
            "/_phase10/boom",
            headers={"X-Correlation-ID": "safe-error-1"},
        )

    combined = response.text + " ".join(record.getMessage() for record in caplog.records)
    assert response.status_code == 500
    assert response.json()["error"]["correlation_id"] == "safe-error-1"
    assert "hunter2" not in combined
    assert "secrets.env" not in combined
    assert "Traceback" not in combined


def test_structured_formatter_never_serializes_exception_message_or_traceback() -> None:
    try:
        raise RuntimeError("token=top-secret")
    except RuntimeError:
        record = logging.getLogger("phase10-test").makeRecord(
            "phase10-test",
            logging.ERROR,
            __file__,
            1,
            "operation_failed",
            (),
            __import__("sys").exc_info(),
        )

    payload = json.loads(StructuredFormatter().format(record))
    assert payload["exception_type"] == "RuntimeError"
    rendered = json.dumps(payload)
    assert "top-secret" not in rendered
    assert "Traceback" not in rendered


def test_identity_isolation_remains_intact_under_request_safety_middleware() -> None:
    with TestClient(create_app(settings=_settings())) as client:
        apple = client.get("/companies/resolve", params={"q": "Apple", "exchange": "NASDAQ"})
        reliance = client.get(
            "/companies/resolve",
            params={"q": "Reliance", "exchange": "NASDAQ"},
        )
        goog = client.get("/companies/resolve", params={"q": "Alphabet", "ticker": "GOOG"})
        googl = client.get("/companies/resolve", params={"q": "Alphabet", "ticker": "GOOGL"})

    assert apple.json()["status"] == "RESOLVED"
    assert reliance.json()["status"] == "NOT_FOUND"
    assert goog.json()["company"]["company_id"] == googl.json()["company"]["company_id"]
    goog_security = goog.json()["candidates"][0]["matched_listings"][0]["security_id"]
    googl_security = googl.json()["candidates"][0]["matched_listings"][0]["security_id"]
    assert goog_security != googl_security


def test_phase9_report_path_injection_remains_rejected_by_api_contract() -> None:
    with TestClient(create_app(settings=_settings())) as client:
        response = client.post(
            "/research/synthesis",
            json={
                "q": "Apple",
                "research_run_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "claims": [],
                "output_path": "../../secrets/report.docx",
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "secrets/report.docx" not in response.text
