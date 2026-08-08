"""Adversarial domain hardening for Phase 4 Prompt 2."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    CashFlowStatement,
    CompanyFinancialPackage,
    ConflictResolutionRule,
    FilingFormType,
    FilingId,
    FilingMetadata,
    FinancialConcept,
    FinancialDataAvailability,
    FinancialScale,
    FinancialUnit,
    IncomeStatement,
    PeriodBasis,
    PeriodIncomparabilityReason,
    ReportingPeriod,
    build_fact,
    resolve_fact_conflict,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId


def _company() -> CompanyId:
    return CompanyId.from_string("22222222-2222-4222-8222-222222222001")


def _fy(year: int = 2024) -> ReportingPeriod:
    return ReportingPeriod(
        basis=PeriodBasis.FISCAL_YEAR,
        fiscal_year=year,
        period_start=date(year - 1, 10, 1),
        period_end=date(year, 9, 28),
        label=f"FY{year}",
    )


class FinancialDomainHardeningTests(TestCase):
    def test_rejects_infinity(self) -> None:
        with self.assertRaises(ValueError):
            build_fact(
                company_id=_company(),
                concept=FinancialConcept.REVENUE,
                period=_fy(),
                raw_value=Decimal("Infinity"),
                unit=FinancialUnit.CURRENCY,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                currency=CurrencyCode("USD"),
            )

    def test_rejects_naive_retrieved_at(self) -> None:
        with self.assertRaises(ValueError):
            build_fact(
                company_id=_company(),
                concept=FinancialConcept.REVENUE,
                period=_fy(),
                raw_value=Decimal("1"),
                unit=FinancialUnit.CURRENCY,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8),
                currency=CurrencyCode("USD"),
            )

    def test_rejects_normalized_scale_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            from financial_intelligence.domain.financial.facts import FinancialFact

            FinancialFact(
                company_id=_company(),
                concept=FinancialConcept.REVENUE,
                period=_fy(),
                raw_value=Decimal("10"),
                normalized_value=Decimal("11"),
                unit=FinancialUnit.CURRENCY,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                currency=CurrencyCode("USD"),
            )

    def test_currency_unit_requires_currency(self) -> None:
        with self.assertRaises(ValueError):
            build_fact(
                company_id=_company(),
                concept=FinancialConcept.REVENUE,
                period=_fy(),
                raw_value=Decimal("10"),
                unit=FinancialUnit.CURRENCY,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                currency=None,
            )

    def test_shares_must_not_carry_currency(self) -> None:
        with self.assertRaises(ValueError):
            build_fact(
                company_id=_company(),
                concept=FinancialConcept.SHARES_OUTSTANDING,
                period=_fy(),
                raw_value=Decimal("10"),
                unit=FinancialUnit.SHARES,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                currency=CurrencyCode("USD"),
            )

    def test_negative_values_allowed_where_valid(self) -> None:
        fact = build_fact(
            company_id=_company(),
            concept=FinancialConcept.NET_INCOME,
            period=_fy(),
            raw_value=Decimal("-5"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.MILLIONS,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        self.assertEqual(fact.normalized_value, Decimal("-5000000"))

    def test_duplicate_concepts_rejected_on_statement(self) -> None:
        period = _fy()
        company = _company()
        f1 = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("1"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        f2 = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("2"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        with self.assertRaises(ValueError):
            IncomeStatement(
                company_id=company,
                period=period,
                currency=CurrencyCode("USD"),
                facts=(f1, f2),
            )

    def test_statement_currency_mismatch_rejected(self) -> None:
        period = _fy()
        company = _company()
        fact = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("1"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("INR"),
        )
        with self.assertRaises(ValueError):
            IncomeStatement(
                company_id=company,
                period=period,
                currency=CurrencyCode("USD"),
                facts=(fact,),
            )

    def test_period_duration_mismatch_not_comparable(self) -> None:
        short = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
        )
        full = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2023,
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
        )
        self.assertEqual(
            short.incomparability_reason(full),
            PeriodIncomparabilityReason.DURATION_MISMATCH,
        )
        self.assertFalse(short.is_comparable_to(full))

    def test_fy_vs_ytd_not_comparable(self) -> None:
        fy = _fy()
        ytd = ReportingPeriod(
            basis=PeriodBasis.YEAR_TO_DATE,
            fiscal_year=2024,
            period_start=date(2023, 10, 1),
            period_end=date(2024, 3, 31),
        )
        self.assertEqual(
            fy.incomparability_reason(ytd),
            PeriodIncomparabilityReason.BASIS_MISMATCH,
        )

    def test_instant_not_comparable_for_growth(self) -> None:
        instant = ReportingPeriod(
            basis=PeriodBasis.INSTANT,
            fiscal_year=2024,
            period_end=date(2024, 9, 28),
            as_of=date(2024, 9, 28),
        )
        self.assertEqual(
            instant.incomparability_reason(_fy()),
            PeriodIncomparabilityReason.INSTANT_NOT_COMPARABLE,
        )

    def test_filing_rejects_javascript_url(self) -> None:
        with self.assertRaises(ValueError):
            FilingMetadata(
                filing_id=FilingId.new(),
                company_id=_company(),
                form_type=FilingFormType.US_10K,
                reporting_period=_fy(),
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                source_url="javascript:alert(1)",
            )

    def test_package_rejects_listing_without_security(self) -> None:
        from financial_intelligence.domain.identity import ListingId

        period = _fy()
        company = _company()
        fact = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("1"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        income = IncomeStatement(
            company_id=company,
            period=period,
            currency=CurrencyCode("USD"),
            facts=(fact,),
        )
        with self.assertRaises(ValueError):
            CompanyFinancialPackage(
                company_id=company,
                reporting_period=period,
                currency=CurrencyCode("USD"),
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                income_statement=income,
                listing_id=ListingId(value=UUID("44444444-4444-4444-8444-444444444001")),
            )

    def test_unavailable_origin_cannot_carry_statements(self) -> None:
        period = _fy()
        company = _company()
        fact = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("1"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        income = IncomeStatement(
            company_id=company,
            period=period,
            currency=CurrencyCode("USD"),
            facts=(fact,),
        )
        with self.assertRaises(ValueError):
            CompanyFinancialPackage(
                company_id=company,
                reporting_period=period,
                currency=CurrencyCode("USD"),
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                income_statement=income,
                data_origin=DataOrigin.UNAVAILABLE,
                availability=FinancialDataAvailability.UNAVAILABLE,
            )

    def test_cash_flow_rejects_wrong_concept(self) -> None:
        period = _fy()
        company = _company()
        fact = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("1"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        with self.assertRaises(ValueError):
            CashFlowStatement(
                company_id=company,
                period=period,
                currency=CurrencyCode("USD"),
                facts=(fact,),
            )

    def test_conflict_higher_authority_wins_explicitly(self) -> None:
        period = _fy()
        company = _company()
        low = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("100"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL,
            retrieved_at=datetime(2026, 8, 8, 12, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        high = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("200"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, 11, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        conflict = resolve_fact_conflict((low, high))
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.HIGHER_AUTHORITY_TIER)
        assert conflict.selected is not None
        self.assertEqual(conflict.selected.normalized_value, Decimal("200"))

    def test_conflict_same_tier_disagreement_unresolved(self) -> None:
        period = _fy()
        company = _company()
        a = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("100"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, 12, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        b = build_fact(
            company_id=company,
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("200"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, 13, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        conflict = resolve_fact_conflict((a, b))
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.UNRESOLVED)
        self.assertIsNone(conflict.selected)
        # Later retrieval must not silently win.
        self.assertEqual(len(conflict.candidates), 2)
