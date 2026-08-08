"""Domain tests for Phase 4 financial facts, periods, and statements."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.financial import (
    BalanceSheet,
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


class FinancialDomainTests(TestCase):
    def test_financial_fact_rejects_nan(self) -> None:
        company_id = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
        period = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2023, 10, 1),
            period_end=date(2024, 9, 28),
        )
        with self.assertRaises(ValueError):
            build_fact(
                company_id=company_id,
                concept=FinancialConcept.REVENUE,
                period=period,
                raw_value=Decimal("NaN"),
                unit=FinancialUnit.CURRENCY,
                scale=FinancialScale.MILLIONS,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 7, tzinfo=UTC),
                currency=CurrencyCode("USD"),
            )

    def test_period_comparability_blocks_mixed_basis(self) -> None:
        fy = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2023, 10, 1),
            period_end=date(2024, 9, 28),
        )
        q = ReportingPeriod(
            basis=PeriodBasis.FISCAL_QUARTER,
            fiscal_year=2024,
            fiscal_quarter=1,
            period_start=date(2023, 10, 1),
            period_end=date(2023, 12, 31),
        )
        self.assertFalse(fy.is_comparable_to(q))

    def test_income_statement_partial_facts_allowed(self) -> None:
        company_id = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
        period = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2023, 10, 1),
            period_end=date(2024, 9, 28),
        )
        fact = build_fact(
            company_id=company_id,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("100"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.MILLIONS,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 7, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        statement = IncomeStatement(
            company_id=company_id,
            period=period,
            currency=CurrencyCode("USD"),
            facts=(fact,),
        )
        self.assertIsNone(statement.get(FinancialConcept.NET_INCOME))
        payload = statement.to_dict()
        self.assertEqual(payload["statement_type"], "income_statement")
        self.assertEqual(len(payload["facts"]), 1)

    def test_balance_sheet_rejects_wrong_concept(self) -> None:
        company_id = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
        period = ReportingPeriod(
            basis=PeriodBasis.INSTANT,
            fiscal_year=2024,
            period_end=date(2024, 9, 28),
            as_of=date(2024, 9, 28),
        )
        bad_fact = build_fact(
            company_id=company_id,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("1"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.MILLIONS,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 7, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        with self.assertRaises(ValueError):
            BalanceSheet(
                company_id=company_id,
                period=period,
                currency=CurrencyCode("USD"),
                facts=(bad_fact,),
            )
