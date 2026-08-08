"""Prompt 2 deep validation for readiness registry robustness."""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
)
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings


class ReadinessRegistryTests(TestCase):
    """Verify readiness evaluation is stable and failure-safe."""

    def setUp(self) -> None:
        self.metadata = ApplicationMetadata(
            service="agentic-financial-intelligence",
            version="0.1.0",
            environment="test",
        )

    def test_checks_are_evaluated_in_sorted_name_order(self) -> None:
        registry = ReadinessRegistry()
        registry.register("zulu", lambda: ReadinessCheckResult(name="zulu", ready=True))
        registry.register("alpha", lambda: ReadinessCheckResult(name="alpha", ready=True))
        result = registry.evaluate(self.metadata)
        self.assertEqual([check.name for check in result.checks], ["alpha", "zulu"])

    def test_probe_exception_becomes_not_ready(self) -> None:
        registry = ReadinessRegistry()
        registry.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = registry.evaluate(self.metadata)
        self.assertFalse(result.ready)
        self.assertEqual(result.status, "not_ready")
        self.assertEqual(result.checks[0].detail, "probe_error:RuntimeError")

    def test_empty_name_rejected(self) -> None:
        registry = ReadinessRegistry()
        with self.assertRaises(ValueError):
            registry.register("  ", lambda: ReadinessCheckResult(name="x", ready=True))

    def test_name_mismatch_becomes_not_ready(self) -> None:
        registry = ReadinessRegistry()
        registry.register(
            "expected",
            lambda: ReadinessCheckResult(name="other", ready=True),
        )
        result = registry.evaluate(self.metadata)
        self.assertFalse(result.ready)
        self.assertEqual(result.checks[0].detail, "probe_error:name_mismatch")

    def test_http_ready_returns_503_when_probe_fails(self) -> None:
        container = build_container(Settings(_env_file=None, APP_ENV="test"))
        container.readiness.register(
            "future_dependency",
            lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
        )
        with TestClient(create_app(container=container)) as client:
            response = client.get("/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertTrue(any(check["name"] == "future_dependency" for check in payload["checks"]))
