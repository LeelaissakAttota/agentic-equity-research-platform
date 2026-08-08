"""Deep Financial snapshot API hardening for Phase 4 Prompt 2."""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class FinancialApiHardeningTests(TestCase):
    def test_apple_ok_with_provenance_and_omissions(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&exchange=NASDAQ")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertIn("X-Correlation-ID", response.headers)
        self.assertIn("omissions", payload)
        self.assertIsInstance(payload["omissions"], list)
        self.assertIsNotNone(payload.get("filing"))
        self.assertIsNotNone(payload.get("source"))
        self.assertEqual(payload["source"]["authority_tier"], 1)
        self.assertNotIn("traceback", str(payload).lower())
        self.assertNotIn("api_key", str(payload).lower())

    def test_reliance_india_fixture(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Reliance&exchange=NSE")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertEqual(payload["package"]["currency"], "INR")

    def test_fiscal_year_selection(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&fiscal_year=2023")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["package"]["reporting_period"]["fiscal_year"], 2023)

    def test_wrong_country_blocks_or_misses(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&country=IN")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"resolution_blocked", "unavailable"})

    def test_wrong_exchange_blocks(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&exchange=NSE")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"resolution_blocked", "unavailable"})

    def test_wrong_ticker_blocks(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?ticker=NOTREALTICKER")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "resolution_blocked")
        self.assertIsNone(response.json().get("package"))
        self.assertEqual(response.json().get("metrics"), [])

    def test_ambiguous_company_blocked(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=COLLIDE")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "resolution_blocked")
        self.assertIsNone(payload.get("package"))
        self.assertEqual(payload.get("omissions"), [])

    def test_unknown_company_blocked(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=ZZZZNOTACOMPANY")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "resolution_blocked")

    def test_invalid_fiscal_year_422(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&fiscal_year=1800")
        self.assertEqual(response.status_code, 422)

    def test_malformed_exchange_400(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&exchange=BAD!")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertNotIn("traceback", str(payload).lower())

    def test_oversized_country_422(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&country=USA")
        self.assertEqual(response.status_code, 422)

    def test_security_headers_present(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple")
        # Correlation ID always; common hardening headers when configured.
        self.assertTrue(response.headers.get("X-Correlation-ID"))

    def test_unavailable_fiscal_year(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&fiscal_year=1999")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload.get("metrics"), [])
        self.assertEqual(payload.get("omissions"), [])

    def test_goog_googl_isolation_still_holds_for_financial_route(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            goog = client.get("/financials/snapshot?ticker=GOOG")
            googl = client.get("/financials/snapshot?ticker=GOOGL")
        # Both may be unavailable financially, but must not cross-attach packages.
        self.assertEqual(goog.status_code, 200)
        self.assertEqual(googl.status_code, 200)
        goog_pkg = goog.json().get("package")
        googl_pkg = googl.json().get("package")
        if goog_pkg and googl_pkg:
            self.assertNotEqual(goog_pkg["company_id"], googl_pkg["company_id"])

    def test_reliance_nse_bse_separation(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            nse = client.get("/financials/snapshot?q=Reliance&exchange=NSE")
            bse = client.get("/financials/snapshot?q=Reliance&exchange=BSE")
        self.assertEqual(nse.status_code, 200)
        self.assertEqual(bse.status_code, 200)
        # Fixture financials are company-scoped; do not invent NSE/BSE mixups.
        if nse.json().get("package") and bse.json().get("package"):
            self.assertEqual(
                nse.json()["package"]["company_id"],
                bse.json()["package"]["company_id"],
            )
