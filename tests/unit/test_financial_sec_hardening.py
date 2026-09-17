"""Deep offline SEC companyfacts adapter hardening tests."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
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
                                "accn": "0000320193-23-000106",
                            },
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 391035000000,
                                "filed": "2024-11-01",
                                "accn": "0000320193-24-000106",
                            },
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "fy": 2024,
                                "fp": "FY",
                                "val": 391035000000,
                                "filed": "2024-11-15",
                                "accn": "0000320193-24-000123",
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
                                "accn": "0000320193-24-000123",
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
                                "accn": "0000320193-24-000123",
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

    def test_filed_at_reflects_source_filed_date_not_period_end(self) -> None:
        # Fixture's Revenues FY2024 rows carry filed=2024-11-01 and filed=2024-11-15,
        # distinct from end=2024-09-28 (period end). F05 regression: filed_at must be
        # the authoritative SEC filing date, never the period end.
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertEqual(package.reporting_period.period_end, date(2024, 9, 28))
        self.assertEqual(package.filing.filed_at, date(2024, 11, 15))
        self.assertNotEqual(package.filing.filed_at, package.reporting_period.period_end)

    def test_filed_at_uses_latest_amendment_consistently_with_value_selection(self) -> None:
        # Two FY2024 Revenues rows share the same value but different filed dates
        # (2024-11-01 vs 2024-11-15 -- an amendment). The later filed date must win,
        # matching the amendment-selection semantics already proven for fact values.
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertEqual(package.filing.filed_at, date(2024, 11, 15))

    def test_filed_at_none_when_source_omits_filed_date(self) -> None:
        payload = _payload()
        for tag_entry in payload["facts"]["us-gaap"].values():  # type: ignore[union-attr]
            for row in tag_entry["units"]["USD"]:  # type: ignore[index]
                row.pop("filed", None)
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertIsNone(package.filing.filed_at)
        self.assertIsNone(package.filing.published_at)
        # The defect under regression: removing the source's filing date must not
        # cause period_end to silently become the reported filed_at.
        self.assertNotEqual(package.filing.filed_at, package.reporting_period.period_end)

    def test_malformed_filed_date_does_not_fall_back_to_period_end(self) -> None:
        # Corrupt 'filed' on every FY2024 duration-tag row (Revenues and
        # NetIncomeLoss) so no valid filing date can be recovered from any of
        # them -- the resulting filed_at must be None, not a guess.
        payload = _payload()
        for tag in ("Revenues", "NetIncomeLoss"):
            rows = payload["facts"]["us-gaap"][tag]["units"]["USD"]  # type: ignore[index]
            for row in rows:  # type: ignore[union-attr]
                if row.get("fy") == 2024:  # type: ignore[union-attr]
                    row["filed"] = "not-a-date"  # type: ignore[index]
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        # Fact values remain valid despite the malformed filing date on their row.
        revenue = package.income_statement.get(FinancialConcept.REVENUE)  # type: ignore[union-attr]
        assert revenue is not None
        self.assertEqual(revenue.normalized_value, 391035000000)
        # A malformed source date must surface as None, never as a coerced/guessed
        # date and never as the period end.
        self.assertIsNone(package.filing.filed_at)
        self.assertNotEqual(package.filing.filed_at, package.reporting_period.period_end)

    def test_published_at_mirrors_filed_at_not_period_end(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertEqual(package.filing.published_at, package.filing.filed_at)
        self.assertNotEqual(package.filing.published_at, package.reporting_period.period_end)

    def test_filing_contract_serializes_authoritative_filed_at(self) -> None:
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        serialized = package.filing.to_dict()
        self.assertEqual(serialized["filed_at"], "2024-11-15")
        self.assertNotEqual(serialized["filed_at"], package.reporting_period.period_end.isoformat())

    def test_accession_or_reference_reflects_real_filing_not_cik(self) -> None:
        # F12 regression: accession_or_reference must be the filing-specific SEC
        # accession number ('accn'), never the company-level CIK. The fixture's
        # winning FY2024 row (filed=2024-11-15) carries accn=0000320193-24-000123,
        # distinct in shape and value from the payload's cik=0000320193.
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertEqual(package.filing.accession_or_reference, "0000320193-24-000123")
        self.assertNotEqual(package.filing.accession_or_reference, "0000320193")

    def test_accession_or_reference_none_when_source_omits_accession(self) -> None:
        # The defect under regression: removing the source's accession number must
        # not cause the company CIK to silently become the reported accession.
        payload = _payload()
        for tag_entry in payload["facts"]["us-gaap"].values():  # type: ignore[union-attr]
            for row in tag_entry["units"]["USD"]:  # type: ignore[index]
                row.pop("accn", None)
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertIsNone(package.filing.accession_or_reference)
        self.assertNotEqual(package.filing.accession_or_reference, payload["cik"])

    def test_malformed_accession_does_not_fall_back_to_cik(self) -> None:
        payload = _payload()
        for tag in ("Revenues", "NetIncomeLoss"):
            rows = payload["facts"]["us-gaap"][tag]["units"]["USD"]  # type: ignore[index]
            for row in rows:  # type: ignore[union-attr]
                if row.get("fy") == 2024:  # type: ignore[union-attr]
                    row["accn"] = 12345  # type: ignore[index]  # not a string
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertIsNone(package.filing.accession_or_reference)
        self.assertNotEqual(package.filing.accession_or_reference, payload["cik"])

    def test_accession_or_reference_matches_the_same_fact_as_filed_at(self) -> None:
        # F12 selection-consistency requirement: accession_or_reference must come
        # from the SAME selected fact as filed_at, never a different fact's
        # accession. NetIncomeLoss here has an earlier filed date and a distinct,
        # deliberately "wrong" accession; Revenues has the later (winning) filed
        # date. The winning accession must match Revenues', not NetIncomeLoss'.
        payload = _payload()
        payload["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["filed"] = (  # type: ignore[index]
            "2024-10-01"
        )
        payload["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["accn"] = (  # type: ignore[index]
            "0000320193-24-000999"
        )
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID, fiscal_year=2024)
        assert package is not None and package.filing is not None
        self.assertEqual(package.filing.filed_at, date(2024, 11, 15))
        self.assertEqual(package.filing.accession_or_reference, "0000320193-24-000123")
        self.assertNotEqual(package.filing.accession_or_reference, "0000320193-24-000999")

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

    def test_missing_cik_does_not_affect_accession_or_reference(self) -> None:
        # F12: accession_or_reference is derived solely from the per-fact 'accn'
        # field, never from 'cik' -- removing the top-level cik key must not
        # change the (correct) accession value at all.
        payload = _payload()
        del payload["cik"]
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID)
        assert package is not None and package.filing is not None
        self.assertEqual(package.filing.accession_or_reference, "0000320193-24-000123")

    def test_missing_cik_and_accession_yields_none_not_cik(self) -> None:
        # The historical defect: with no accession data anywhere in the source and
        # no top-level cik, accession_or_reference must be None -- never fabricated
        # from the adapter's resolved cik lookup value (F12).
        payload = _payload()
        del payload["cik"]
        for tag_entry in payload["facts"]["us-gaap"].values():  # type: ignore[union-attr]
            for row in tag_entry["units"]["USD"]:  # type: ignore[index]
                row.pop("accn", None)
        package = _adapter(
            lambda *a: HttpResponse(200, json.dumps(payload).encode(), "application/json", {})
        ).get_financial_package(APPLE_ID)
        assert package is not None and package.filing is not None
        self.assertIsNone(package.filing.accession_or_reference)

    def test_unknown_company_no_network_success(self) -> None:
        called = {"n": 0}

        def handler(*_a: object) -> HttpResponse:
            called["n"] += 1
            return HttpResponse(200, json.dumps(_payload()).encode(), "application/json", {})

        reliance = CompanyId.from_string("11111111-1111-4111-8111-111111111001")
        self.assertIsNone(_adapter(handler).get_financial_package(reliance))
        self.assertEqual(called["n"], 0)
