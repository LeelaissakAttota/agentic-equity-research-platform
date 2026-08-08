"""SEC companyfacts adapter tests with fake transport (offline CI)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.infrastructure.financial.reference_dataset import APPLE_ID
from financial_intelligence.infrastructure.financial.sec_company_facts import (
    SecCompanyFactsFinancialDataAdapter,
)
from financial_intelligence.infrastructure.http import BoundedHttpClient, HttpResponse


class FakeTransport:
    def __init__(self, handler) -> None:
        self._handler = handler

    def request(
        self, method: str, url: str, *, headers: dict[str, str], timeout: float
    ) -> HttpResponse:
        return self._handler(method, url, headers, timeout)


def _sample_sec_payload() -> dict[str, object]:
    return {
        "cik": "0000320193",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 391035000000,
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 93736000000,
                            }
                        ]
                    }
                },
            }
        },
    }


class SecCompanyFactsTests(TestCase):
    def test_success_parses_live_package(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            self.assertIn("data.sec.gov", url)
            return HttpResponse(
                200,
                json.dumps(_sample_sec_payload()).encode(),
                "application/json",
                {},
            )

        http = BoundedHttpClient(
            FakeTransport(handler), timeout_seconds=5.0, max_retries=0, user_agent="test-agent"
        )
        adapter = SecCompanyFactsFinancialDataAdapter(
            http,
            clock=lambda: datetime(2026, 8, 7, tzinfo=UTC),
        )
        package = adapter.get_financial_package(APPLE_ID)
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.data_origin, DataOrigin.LIVE)
        self.assertIsNotNone(package.income_statement)

    def test_429_returns_none_from_adapter(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            return HttpResponse(429, b"rate limited", "text/plain", {})

        http = BoundedHttpClient(
            FakeTransport(handler), timeout_seconds=5.0, max_retries=0, user_agent="test-agent"
        )
        adapter = SecCompanyFactsFinancialDataAdapter(http)
        self.assertIsNone(adapter.get_financial_package(APPLE_ID))

    def test_unsupported_company_returns_none(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            return HttpResponse(
                200, json.dumps(_sample_sec_payload()).encode(), "application/json", {}
            )

        http = BoundedHttpClient(
            FakeTransport(handler), timeout_seconds=5.0, max_retries=0, user_agent="test-agent"
        )
        adapter = SecCompanyFactsFinancialDataAdapter(http)
        reliance = CompanyId.from_string("11111111-1111-4111-8111-111111111001")
        self.assertIsNone(adapter.get_financial_package(reliance))
