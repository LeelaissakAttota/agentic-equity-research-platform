"""GetFinancialSnapshot use case tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.financial_contracts import (
    FinancialSnapshotQuery,
    FinancialSnapshotStatus,
)
from financial_intelligence.application.financial_snapshot import GetFinancialSnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.financial import InMemoryFinancialDataAdapter


class FinancialSnapshotTests(TestCase):
    def _use_case(self) -> GetFinancialSnapshot:
        catalog = InMemoryCompanyCatalog()
        return GetFinancialSnapshot(
            resolve_company=ResolveCompany(catalog),
            financial_data=InMemoryFinancialDataAdapter(),
            clock=lambda: datetime(2026, 8, 7, 20, 0, tzinfo=UTC),
        )

    def test_apple_resolved_returns_fixture_origin(self) -> None:
        result = self._use_case().execute(
            FinancialSnapshotQuery(company_query=CompanyQuery(raw_query="Apple"))
        )
        self.assertEqual(result.status, FinancialSnapshotStatus.OK)
        self.assertIsNotNone(result.package)
        assert result.package is not None
        self.assertEqual(result.package.data_origin, DataOrigin.FIXTURE)
        self.assertGreater(len(result.metrics), 0)

    def test_ambiguous_blocks_financials(self) -> None:
        result = self._use_case().execute(
            FinancialSnapshotQuery(company_query=CompanyQuery(raw_query="COLLIDE"))
        )
        self.assertEqual(result.status, FinancialSnapshotStatus.RESOLUTION_BLOCKED)
        self.assertIsNone(result.package)

    def test_not_found_blocks_financials(self) -> None:
        result = self._use_case().execute(
            FinancialSnapshotQuery(company_query=CompanyQuery(raw_query="ZZZZNOTACOMPANY"))
        )
        self.assertEqual(result.status, FinancialSnapshotStatus.RESOLUTION_BLOCKED)
        self.assertIsNone(result.package)

    def test_fiscal_year_selection(self) -> None:
        result = self._use_case().execute(
            FinancialSnapshotQuery(
                company_query=CompanyQuery(raw_query="Apple"),
                fiscal_year=2023,
            )
        )
        self.assertEqual(result.status, FinancialSnapshotStatus.OK)
        assert result.package is not None
        self.assertEqual(result.package.reporting_period.fiscal_year, 2023)
