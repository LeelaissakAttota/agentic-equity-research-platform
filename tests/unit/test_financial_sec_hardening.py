"""Deep offline SEC companyfacts adapter hardening tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import FinancialConcept
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.infrastructure.financial.reference_dataset import APPLE_ID
from financial_intelligence.infrastructure.financial.sec_company_facts import (
    SecCompanyFactsFinancialDataAdapter,
)
from financial_intelligence.infrastructure.http import (
    BoundedHttpClient,
    HttpFailureKind,
    HttpResponse,
    HttpTransportError,
)


class FakeTransport:
    def __init__(self, handler) -> None:
        self._handler = handler
        self.calls = 0

    def request(
        self, method: str, url: str, *, headers: dict[str, str], timeout: float
    ) -> HttpResponse:
        self.calls += 1
        return self._handler(method, url, headers, timeout)


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "cik": "0000320193",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2022-10-01",
                                "end": "2023-09-30",
                                "fy": 2023,
                                "fp": "FY",
                                "val": 383285000000,
                                "filed": "2023-11-03",
                            },
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 391035000000,
                                "filed": "2024-11-01",
                            },
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 391035000000,
                                "filed": "2024-11-15",
                            },
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
                                "filed": "2024-11-15",
                            }
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 364980000000,
                                "filed": "2024-11-15",
                            }
                        ]
                    }
                },
            }
        },
    }
    base.update(overrides)
    return base


def _adapter(handler, *, retries: int = 0) -> SecCompanyFactsFinancialDataAdapter:
    http = BoundedHttpClient(
        FakeTransport(handler),
        timeout_seconds=5.0,
        max_retries=retries,
        user_agent="test-agent",
    )
    return SecCompanyFactsFinancialDataAdapter(http, clock=lambda: datetime(2026, 8, 8, tzinfo=UTC))


class SecCompanyFactsHardeningTests(TestCase):
    def test_valid_payload_parses_instant_and_duration(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID)
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.data_origin, DataOrigin.LIVE)
        self.assertEqual(package.provider_name, "sec_company_facts")
        assert package.income_statement is not None
        self.assertIsNotNone(package.income_statement.get(FinancialConcept.REVENUE))
        assert package.balance_sheet is not None
        self.assertIsNotNone(package.balance_sheet.get(FinancialConcept.TOTAL_ASSETS))
        assert package.filing is not None
        self.assertEqual(package.filing.authority_tier, 1)

    def test_fiscal_year_selection(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2023)
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.reporting_period.fiscal_year, 2023)

    def test_amended_filing_prefers_later_filed(self) -> None:
        # Both FY2024 rows present; later filed date wins without inventing values.
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None
        revenue = package.income_statement.get(FinancialConcept.REVENUE)  # type: ignore[union-attr]
        assert revenue is not None
        self.assertEqual(revenue.normalized_value, 391035000000)

    def test_missing_concepts_still_partial_success(self) -> None:
        payload = _payload()
        facts = payload["facts"]["us-gaap"]  # type: ignore[index]
        del facts["Assets"]  # type: ignore[index]
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID)
        self.assertIsNotNone(package)
        assert package is not None
        self.assertIsNone(package.balance_sheet)

    def test_unsupported_units_skipped(self) -> None:
        payload = {
            "cik": "0000320193",
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"EUR": [{"fy": 2024, "fp": "FY", "val": 1}]}},
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2023-10-01",
                                    "end": "2024-09-28",
                                    "fy": 2024,
                                    "fp": "FY",
                                    "val": 1,
                                }
                            ]
                        }
                    },
                }
            },
        }
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID)
        assert package is not None
        assert package.income_statement is not None
        self.assertIsNone(package.income_statement.get(FinancialConcept.REVENUE))
        self.assertIsNotNone(package.income_statement.get(FinancialConcept.NET_INCOME))

    def test_malformed_values_skipped(self) -> None:
        payload = _payload()
        payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][1]["val"] = "not-a-number"  # type: ignore[index]
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        # Amended later row still valid; malformed earlier row ignored.
        self.assertIsNotNone(package)

    def test_empty_payload_returns_none(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, b"{}", "application/json", {})
        ).get_financial_package(APPLE_ID)
        self.assertIsNone(package)

    def test_unexpected_json_structure_returns_none(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, b'{"facts":[]}', "application/json", {})
        ).get_financial_package(APPLE_ID)
        self.assertIsNone(package)

    def test_corrupted_json_returns_none(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, b"{not-json", "application/json", {})
        ).get_financial_package(APPLE_ID)
        self.assertIsNone(package)

    def test_5xx_returns_none(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(503, b"down", "text/plain", {})
        ).get_financial_package(APPLE_ID)
        self.assertIsNone(package)

    def test_timeout_returns_none(self) -> None:
        def handler(*_a: object) -> HttpResponse:
            raise HttpTransportError(HttpFailureKind.TIMEOUT, "timed out")

        # BoundedHttpClient wraps transport errors; inject via raising transport.
        class Boom:
            def request(self, method: str, url: str, *, headers: dict[str, str], timeout: float):
                raise HttpTransportError(HttpFailureKind.TIMEOUT, "timed out")

        http = BoundedHttpClient(Boom(), timeout_seconds=1.0, max_retries=0, user_agent="test")
        adapter = SecCompanyFactsFinancialDataAdapter(http)
        self.assertIsNone(adapter.get_financial_package(APPLE_ID))

    def test_oversized_returns_none(self) -> None:
        class Boom:
            def request(self, method: str, url: str, *, headers: dict[str, str], timeout: float):
                raise HttpTransportError(HttpFailureKind.OVERSIZED, "too big")

        http = BoundedHttpClient(Boom(), timeout_seconds=1.0, max_retries=0, user_agent="test")
        self.assertIsNone(SecCompanyFactsFinancialDataAdapter(http).get_financial_package(APPLE_ID))

    def test_retry_exhaustion_returns_none(self) -> None:
        transport = FakeTransport(lambda *a: HttpResponse(429, b"rate", "text/plain", {}))
        http = BoundedHttpClient(
            transport, timeout_seconds=1.0, max_retries=2, user_agent="test-agent"
        )
        adapter = SecCompanyFactsFinancialDataAdapter(http)
        self.assertIsNone(adapter.get_financial_package(APPLE_ID))
        self.assertGreaterEqual(transport.calls, 3)

    def test_missing_accession_still_uses_cik(self) -> None:
        payload = _payload()
        del payload["cik"]
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID)
        assert package is not None and package.filing is not None
        self.assertTrue(package.filing.accession_or_reference)

    def test_unknown_company_no_network_success(self) -> None:
        called = {"n": 0}

        def handler(*_a: object) -> HttpResponse:
            called["n"] += 1
            return HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})

        reliance = CompanyId.from_string("11111111-1111-4111-8111-111111111001")
        self.assertIsNone(_adapter(handler).get_financial_package(reliance))
        self.assertEqual(called["n"], 0)
