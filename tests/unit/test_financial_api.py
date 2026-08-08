"""Financial snapshot API contract tests."""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class FinancialApiTests(TestCase):
    def test_financial_snapshot_apple_ok(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&exchange=NASDAQ")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertIn("metrics", payload)
        self.assertTrue(payload["metrics"])
        self.assertEqual(payload["metrics"][0]["kind"], "derived_metric")

    def test_financial_snapshot_ambiguous_returns_blocked(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=COLLIDE")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "resolution_blocked")

    def test_invalid_fiscal_year_returns_422(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&fiscal_year=1800")
        self.assertEqual(response.status_code, 422)
