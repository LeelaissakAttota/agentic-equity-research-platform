"""Phase 10 Prompt 3 production-boundary contract freeze tests."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings
from financial_intelligence.observability.correlation import resolve_correlation_id
from tests.unit.test_phase10_prompt2_hardening import (
    _exercise_boundary,
    _production_settings,
    _response_json,
    _response_status,
    _settings,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_host",
    [
        b" api.example.com",
        b"api.example.com ",
        b"\tapi.example.com",
        b"api.example.com\x7f",
        b"api.example.com:" + (b"9" * 5000),
    ],
)
async def test_trusted_host_rejects_outer_whitespace_control_and_extreme_port(
    raw_host: bytes,
) -> None:
    called, _, outgoing = await _exercise_boundary(headers=[(b"host", raw_host)])

    assert called is False
    assert _response_status(outgoing) == 400
    assert _response_json(outgoing)["error"]["code"] == "invalid_host"


@pytest.mark.asyncio
async def test_extreme_numeric_content_length_fails_closed_without_integer_conversion() -> None:
    called, _, outgoing = await _exercise_boundary(
        headers=[
            (b"host", b"api.example.com"),
            (b"content-length", b"9" * 5000),
        ]
    )

    assert called is False
    assert _response_status(outgoing) == 413
    assert _response_json(outgoing)["error"]["code"] == "request_too_large"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("size", "expected_status"),
    [(4095, 204), (4096, 204), (4097, 413)],
)
async def test_actual_body_byte_boundary_without_content_length(
    size: int,
    expected_status: int,
) -> None:
    called, received, outgoing = await _exercise_boundary(
        headers=[(b"host", b"api.example.com")],
        messages=[{"type": "http.request", "body": b"x" * size, "more_body": False}],
    )

    assert _response_status(outgoing) == expected_status
    assert called is (expected_status == 204)
    assert received == (b"x" * size if expected_status == 204 else b"")


@pytest.mark.parametrize("raw", [" safe-id", "safe-id ", "\tsafe-id", "safe-id\n"])
def test_correlation_id_rejects_outer_whitespace_and_control(raw: str) -> None:
    resolved = resolve_correlation_id(raw).value

    assert resolved != raw.strip()
    assert UUID(resolved).version == 4


def test_malformed_json_uses_safe_correlated_error_contract() -> None:
    sentinel = "token=phase10-secret"
    with TestClient(create_app(settings=_settings())) as client:
        response = client.post(
            "/research/plans",
            content=f'{{"q":"Apple","objective":"{sentinel}"',
            headers={
                "Content-Type": "application/json",
                "X-Correlation-ID": "phase10-malformed-json",
            },
        )

    assert response.status_code == 422
    assert response.headers["X-Correlation-ID"] == "phase10-malformed-json"
    assert response.json()["error"]["code"] == "validation_error"
    assert sentinel not in response.text


def test_health_ready_version_freeze_under_explicit_production_host() -> None:
    with TestClient(create_app(settings=_production_settings())) as client:
        responses = {
            path: client.get(path, headers={"host": "api.example.com"})
            for path in ("/health", "/ready", "/version")
        }

    assert all(response.status_code == 200 for response in responses.values())
    assert "checks" not in responses["/health"].json()
    assert {item["name"] for item in responses["/ready"].json()["checks"]} == {
        "application",
        "configuration",
    }
    assert set(responses["/version"].json()) == {"service", "version", "environment"}


def test_development_test_and_production_configuration_contracts_are_distinct() -> None:
    development = Settings(_env_file=None, APP_ENV="development", ALLOWED_HOSTS="*")
    test = Settings(_env_file=None, APP_ENV="test", ALLOWED_HOSTS="localhost")
    production = _production_settings()

    assert development.allowed_host_values() == ("*",)
    assert test.allowed_host_values() == ("localhost",)
    assert production.allowed_host_values() == ("api.example.com", "127.0.0.1")
    assert production.allow_paid_models is False
