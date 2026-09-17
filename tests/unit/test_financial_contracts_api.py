"""F05 regression: API-level serialization must expose the authoritative SEC
filing date, never a period-end fallback (see F05_SEC_FILING_DATE_REMEDIATION_PLAN.md).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.financial_contracts import (
    FinancialSnapshotQuery,
    FinancialSnapshotResult,
    FinancialSnapshotStatus,
)
from financial_intelligence.domain.financial import (
    CompanyFinancialPackage,
    FilingFormType,
    FilingId,
    FilingMetadata,
    FinancialConcept,
    FinancialScale,
    FinancialUnit,
    IncomeStatement,
    PeriodBasis,
    ReportingPeriod,
    build_fact,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId

_COMPANY = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
_RETRIEVED = datetime(2026, 8, 8, tzinfo=UTC)
_PERIOD = ReportingPeriod(
    basis=PeriodBasis.FISCAL_YEAR,
    fiscal_year=2024,
    period_start=date(2023, 10, 1),
    period_end=date(2024, 9, 28),
    label="FY2024",
)
_FILED_AT = date(2024, 11, 15)


def _package_with_filing(*, filed_at: date | None) -> CompanyFinancialPackage:
    source_id = SourceId.new()
    filing_id = FilingId.new()
    fact = build_fact(
        company_id=_COMPANY,
        concept=FinancialConcept.REVENUE,
        period=_PERIOD,
        raw_value=Decimal("391035000000"),
        unit=FinancialUnit.CURRENCY,
        scale=FinancialScale.ONES,
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        retrieved_at=_RETRIEVED,
        currency=CurrencyCode("USD"),
        filing_id=filing_id,
    )
    income = IncomeStatement(
        company_id=_COMPANY,
        period=_PERIOD,
        currency=CurrencyCode("USD"),
        facts=(fact,),
    )
    filing = FilingMetadata(
        filing_id=filing_id,
        company_id=_COMPANY,
        form_type=FilingFormType.US_10K,
        reporting_period=_PERIOD,
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        filed_at=filed_at,
        published_at=filed_at,
        retrieved_at=_RETRIEVED,
    )
    return CompanyFinancialPackage(
        company_id=_COMPANY,
        reporting_period=_PERIOD,
        currency=CurrencyCode("USD"),
        retrieved_at=_RETRIEVED,
        income_statement=income,
        filing=filing,
        provider_name="fixture",
    )


def _result(package: CompanyFinancialPackage) -> FinancialSnapshotResult:
    return FinancialSnapshotResult(
        query=FinancialSnapshotQuery(company_query=CompanyQuery(raw_query="apple")),
        status=FinancialSnapshotStatus.OK,
        message="ok",
        package=package,
    )


class FinancialContractsFilingDateApiTests(TestCase):
    def test_serialized_contract_exposes_authoritative_filed_at(self) -> None:
        result = _result(_package_with_filing(filed_at=_FILED_AT))
        payload = result.to_dict()
        assert payload["filing"] is not None
        assert payload["package"] is not None
        filing_dict = payload["filing"]
        package_filing_dict = payload["package"]["filing"]  # type: ignore[index]
        self.assertEqual(filing_dict["filed_at"], "2024-11-15")  # type: ignore[index]
        self.assertEqual(package_filing_dict["filed_at"], "2024-11-15")  # type: ignore[index]
        self.assertNotEqual(filing_dict["filed_at"], _PERIOD.period_end.isoformat())  # type: ignore[index]

    def test_serialized_contract_leaves_filed_at_none_when_unknown(self) -> None:
        result = _result(_package_with_filing(filed_at=None))
        payload = result.to_dict()
        assert payload["filing"] is not None
        assert payload["package"] is not None
        filing_dict = payload["filing"]
        package_filing_dict = payload["package"]["filing"]  # type: ignore[index]
        self.assertIsNone(filing_dict["filed_at"])  # type: ignore[index]
        self.assertIsNone(package_filing_dict["filed_at"])  # type: ignore[index]
        # No source filing date is available -- period_end must not be substituted.
        self.assertNotEqual(filing_dict["filed_at"], _PERIOD.period_end.isoformat())  # type: ignore[index]
