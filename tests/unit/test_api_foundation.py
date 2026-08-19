"""FastAPI foundation endpoint and error-contract tests."""

from __future__ import annotations

from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.contracts import ReadinessCheckResult
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class ApplicationFactoryTests(TestCase):
    """Application factory constructs without live external dependencies."""

    def test_create_app_succeeds_offline(self) -> None:
        app = create_app(settings=_settings())
        self.assertEqual(app.title, "Agentic Financial Intelligence & Equity Research Platform")
        self.assertTrue(hasattr(app.state, "container"))


class HealthEndpointTests(TestCase):
    """Liveness endpoint contract."""

    def test_health_returns_stable_contract(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "agentic-financial-intelligence")
        self.assertEqual(payload["version"], "1.0.0")
        self.assertIn("X-Correlation-ID", response.headers)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")


class ReadinessEndpointTests(TestCase):
    """Readiness endpoint and registry extensibility."""

    def test_ready_baseline(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/ready")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["checks"][0]["name"], "application")
        self.assertTrue(payload["checks"][0]["ready"])

    def test_readiness_registry_is_extensible(self) -> None:
        container = build_container(_settings())
        container.readiness.register(
            "future_dependency",
            lambda: ReadinessCheckResult(
                name="future_dependency",
                ready=False,
                detail="not implemented in phase 1",
            ),
        )
        with TestClient(create_app(container=container)) as client:
            response = client.get("/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")
        names = {check["name"] for check in payload["checks"]}
        self.assertIn("future_dependency", names)


class VersionEndpointTests(TestCase):
    """Application metadata endpoint."""

    def test_version_contract(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/version")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["service"], "agentic-financial-intelligence")
        self.assertEqual(payload["version"], "1.0.0")
        self.assertEqual(payload["environment"], "test")


class CorrelationMiddlewareTests(TestCase):
    """HTTP correlation ID middleware behavior."""

    def test_generates_correlation_id_when_absent(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/health")
        correlation_id = response.headers["X-Correlation-ID"]
        self.assertEqual(UUID(correlation_id).version, 4)

    def test_echoes_safe_inbound_correlation_id(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/health", headers={"X-Correlation-ID": "inbound-ok-1"})
        self.assertEqual(response.headers["X-Correlation-ID"], "inbound-ok-1")

    def test_replaces_invalid_inbound_correlation_id(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/health", headers={"X-Correlation-ID": "@@@invalid@@@"})
        correlation_id = response.headers["X-Correlation-ID"]
        self.assertNotEqual(correlation_id, "@@@invalid@@@")
        self.assertEqual(UUID(correlation_id).version, 4)


class ErrorContractTests(TestCase):
    """Stable API error envelope."""

    def test_validation_error_shape_includes_correlation_id(self) -> None:
        app = create_app(settings=_settings())

        @app.get("/_test/validate/{item_id}")
        def validate_item(item_id: int) -> dict[str, int]:
            return {"item_id": item_id}

        with TestClient(app) as client:
            response = client.get(
                "/_test/validate/not-an-int",
                headers={"X-Correlation-ID": "err-corr-1"},
            )
        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "validation_error")
        self.assertEqual(payload["error"]["correlation_id"], "err-corr-1")
        self.assertIsInstance(payload["error"]["details"], list)
        self.assertNotIn("Traceback", response.text)

    def test_unexpected_error_is_normalized(self) -> None:
        app = create_app(settings=_settings())

        @app.get("/_test/boom")
        def boom() -> None:
            raise RuntimeError("secret database password=hunter2")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/boom", headers={"X-Correlation-ID": "boom-1"})
        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "internal_error")
        self.assertEqual(payload["error"]["message"], "An unexpected error occurred")
        self.assertEqual(payload["error"]["correlation_id"], "boom-1")
        self.assertNotIn("hunter2", response.text)
        self.assertNotIn("RuntimeError", response.text)
