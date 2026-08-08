"""HTTP contract tests for GET /market/snapshot."""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings


def _settings() -> Settings:
    # Keep fixture as_of (2026-08-07) fresh under long-window policy for API goldens.
    return Settings(
        _env_file=None,
        APP_ENV="test",
        LOG_LEVEL="WARNING",
        MARKET_STALE_AFTER_HOURS=8760,
    )


class MarketSnapshotApiTests(TestCase):
    def test_snapshot_for_apple_returns_metrics(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/market/snapshot", params={"q": "Apple", "exchange": "NASDAQ"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["listing"]["ticker"], "AAPL")
        self.assertTrue(payload["metrics"])
        self.assertEqual(payload["source"]["authority_tier"], 2)
        self.assertEqual(payload["source"]["source_type"], "market_data")
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertIn("X-Correlation-ID", response.headers)

    def test_false_positive_company_does_not_attach_market_data(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get(
                "/market/snapshot",
                params={"q": "RELIANCE", "exchange": "NASDAQ"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "resolution_blocked")
        self.assertIsNone(payload["series"])
        self.assertEqual(payload["metrics"], [])

    def test_missing_market_fixture_is_unavailable(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/market/snapshot", params={"q": "TCS", "exchange": "NSE"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unavailable")

    def test_invalid_query_returns_400(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/market/snapshot", params={"q": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_market_query")
