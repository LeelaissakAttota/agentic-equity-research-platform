"""API and composition tests for company resolution."""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.ports import CompanyCatalogPort
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class CompanyResolutionApiTests(TestCase):
    def test_resolve_apple(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get(
                "/companies/resolve",
                params={"q": "Apple"},
                headers={"X-Correlation-ID": "company-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Correlation-ID"], "company-1")
        payload = response.json()
        self.assertEqual(payload["status"], "RESOLVED")
        self.assertEqual(payload["company"]["legal_name"], "Apple Inc.")
        self.assertEqual(payload["company"]["country"], "US")

    def test_resolve_not_found_and_invalid(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            missing = client.get("/companies/resolve", params={"q": "NoSuchIssuerZZZ"})
            invalid = client.get("/companies/resolve", params={"q": "   "})
            bad_country = client.get(
                "/companies/resolve",
                params={"q": "Apple", "country": "U1"},
            )
            oversized_country = client.get(
                "/companies/resolve",
                params={"q": "Apple", "country": "USA"},
            )
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json()["status"], "NOT_FOUND")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "invalid_company_query")
        self.assertEqual(bad_country.status_code, 400)
        self.assertEqual(oversized_country.status_code, 422)

    def test_resolve_india_ticker(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get(
                "/companies/resolve",
                params={"q": "RELIANCE", "exchange": "NSE"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "RESOLVED")
        self.assertEqual(payload["company"]["legal_name"], "Reliance Industries Limited")


class CompositionWiringTests(TestCase):
    def test_container_wires_port_and_use_case(self) -> None:
        container = build_container(_settings())
        self.assertIsInstance(container.company_catalog, InMemoryCompanyCatalog)
        self.assertIsInstance(container.resolve_company, ResolveCompany)
        self.assertIsInstance(container.company_catalog, CompanyCatalogPort)
