"""Adversarial and golden tests for deterministic financial calculations."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    BalanceSheet,
    CompanyFinancialPackage,
    FinancialConcept,
    FinancialDataAvailability,
    FinancialMetricName,
    FinancialScale,
    FinancialUnit,
    IncomeStatement,
    MissingDataSemantics,
    PeriodBasis,
    ReportingPeriod,
    build_fact,
    compute_financial_metrics_result,
    free_cash_flow,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId
from financial_intelligence.infrastructure.financial.reference_dataset import (
    APPLE_ID,
    build_reference_financial_packages,
)


def _cid() -> CompanyId:
    return CompanyId.from_string("22222222-2222-4222-8222-222222222001")


def _period(year: int = 2024) -> ReportingPeriod:
    return ReportingPeriod(
        basis=PeriodBasis.FISCAL_YEAR,
        fiscal_year=year,
        period_start=date(year - 1, 10, 1),
        period_end=date(year, 9, 28),
        label=f"FY{year}",
    )


def _money(concept: FinancialConcept, raw: str, period: ReportingPeriod) -> object:
    return build_fact(
        company_id=_cid(),
        concept=concept,
        period=period,
        raw_value=Decimal(raw),
        unit=FinancialUnit.CURRENCY,
        scale=FinancialScale.ONES,
        source_id=SourceId.new(),
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
        currency=CurrencyCode("USD"),
    )


class FinancialCalculationHardeningTests(TestCase):
    def test_apple_golden_revenue_growth_precise(self) -> None:
        package = build_reference_financial_packages()[APPLE_ID.as_text()]
        result = compute_financial_metrics_result(package)
        growth = next(m for m in result.metrics if m.name is FinancialMetricName.REVENUE_GROWTH)
        # 391035 / 383285 - 1
        expected = (Decimal("391035") / Decimal("383285")) - Decimal("1")
        self.assertEqual(growth.value, expected.quantize(Decimal("0.000001")))

    def test_zero_denominator_omits_margin(self) -> None:
        period = _period()
        income = IncomeStatement(
            company_id=_cid(),
            period=period,
            currency=CurrencyCode("USD"),
            facts=(
                _money(FinancialConcept.REVENUE, "0", period),  # type: ignore[arg-type]
                _money(FinancialConcept.NET_INCOME, "10", period),  # type: ignore[arg-type]
            ),
        )
        package = CompanyFinancialPackage(
            company_id=_cid(),
            reporting_period=period,
            currency=CurrencyCode("USD"),
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            income_statement=income,
            data_origin=DataOrigin.FIXTURE,
            availability=FinancialDataAvailability.PARTIAL,
        )
        result = compute_financial_metrics_result(package)
        net_margin = next(o for o in result.omissions if o.name is FinancialMetricName.NET_MARGIN)
        self.assertEqual(net_margin.semantics, MissingDataSemantics.ZERO_DENOMINATOR)

    def test_negative_equity_debt_ratio_computed(self) -> None:
        period = _period()
        bs_period = ReportingPeriod(
            basis=PeriodBasis.INSTANT,
            fiscal_year=2024,
            period_end=period.period_end,
            as_of=period.period_end,
        )
        balance = BalanceSheet(
            company_id=_cid(),
            period=bs_period,
            currency=CurrencyCode("USD"),
            facts=(
                build_fact(
                    company_id=_cid(),
                    concept=FinancialConcept.TOTAL_DEBT,
                    period=bs_period,
                    raw_value=Decimal("50"),
                    unit=FinancialUnit.CURRENCY,
                    scale=FinancialScale.ONES,
                    source_id=SourceId.new(),
                    authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                    retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                    currency=CurrencyCode("USD"),
                ),
                build_fact(
                    company_id=_cid(),
                    concept=FinancialConcept.SHAREHOLDERS_EQUITY,
                    period=bs_period,
                    raw_value=Decimal("-25"),
                    unit=FinancialUnit.CURRENCY,
                    scale=FinancialScale.ONES,
                    source_id=SourceId.new(),
                    authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                    retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                    currency=CurrencyCode("USD"),
                ),
            ),
        )
        package = CompanyFinancialPackage(
            company_id=_cid(),
            reporting_period=period,
            currency=CurrencyCode("USD"),
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            balance_sheet=balance,
            availability=FinancialDataAvailability.PARTIAL,
        )
        result = compute_financial_metrics_result(package)
        dte = next(m for m in result.metrics if m.name is FinancialMetricName.DEBT_TO_EQUITY)
        self.assertEqual(dte.value, Decimal("-2.000000"))

    def test_mismatched_periods_omit_growth(self) -> None:
        current = _period(2024)
        prior = ReportingPeriod(
            basis=PeriodBasis.FISCAL_QUARTER,
            fiscal_year=2023,
            fiscal_quarter=4,
            period_start=date(2023, 7, 1),
            period_end=date(2023, 9, 30),
        )
        current_income = IncomeStatement(
            company_id=_cid(),
            period=current,
            currency=CurrencyCode("USD"),
            facts=(_money(FinancialConcept.REVENUE, "200", current),),  # type: ignore[arg-type]
        )
        prior_income = IncomeStatement(
            company_id=_cid(),
            period=prior,
            currency=CurrencyCode("USD"),
            facts=(_money(FinancialConcept.REVENUE, "100", prior),),  # type: ignore[arg-type]
        )
        prior_pkg = CompanyFinancialPackage(
            company_id=_cid(),
            reporting_period=prior,
            currency=CurrencyCode("USD"),
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            income_statement=prior_income,
            availability=FinancialDataAvailability.PARTIAL,
        )
        package = CompanyFinancialPackage(
            company_id=_cid(),
            reporting_period=current,
            currency=CurrencyCode("USD"),
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            income_statement=current_income,
            prior_period_package=prior_pkg,
            availability=FinancialDataAvailability.PARTIAL,
        )
        result = compute_financial_metrics_result(package)
        omission = next(o for o in result.omissions if o.name is FinancialMetricName.REVENUE_GROWTH)
        self.assertEqual(omission.semantics, MissingDataSemantics.INCOMPARABLE_PERIOD)

    def test_currency_mismatch_omits_margin(self) -> None:
        period = _period()
        revenue = build_fact(
            company_id=_cid(),
            concept=FinancialConcept.REVENUE,
            period=period,
            raw_value=Decimal("100"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        # Force net income with mismatched currency by building statement bypass:
        # statements reject mismatch, so exercise free_cash_flow helper directly.
        ocf = build_fact(
            company_id=_cid(),
            concept=FinancialConcept.OPERATING_CASH_FLOW,
            period=period,
            raw_value=Decimal("40"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("USD"),
        )
        capex = build_fact(
            company_id=_cid(),
            concept=FinancialConcept.CAPITAL_EXPENDITURE,
            period=period,
            raw_value=Decimal("10"),
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            currency=CurrencyCode("INR"),
        )
        outcome = free_cash_flow(
            operating_cash_flow=ocf,
            capital_expenditure=capex,
            period=period,
        )
        self.assertEqual(
            getattr(outcome, "semantics", None), MissingDataSemantics.CURRENCY_MISMATCH
        )
        self.assertIsNotNone(revenue)

    def test_negative_capex_omits_fcf(self) -> None:
        period = _period()
        ocf = _money(FinancialConcept.OPERATING_CASH_FLOW, "40", period)
        capex = _money(FinancialConcept.CAPITAL_EXPENDITURE, "-10", period)
        outcome = free_cash_flow(
            operating_cash_flow=ocf,  # type: ignore[arg-type]
            capital_expenditure=capex,  # type: ignore[arg-type]
            period=period,
        )
        self.assertEqual(getattr(outcome, "semantics", None), MissingDataSemantics.INVALID_INPUT)

    def test_extreme_decimal_precision(self) -> None:
        period = _period()
        income = IncomeStatement(
            company_id=_cid(),
            period=period,
            currency=CurrencyCode("USD"),
            facts=(
                _money(FinancialConcept.REVENUE, "1000000000000", period),  # type: ignore[arg-type]
                _money(FinancialConcept.NET_INCOME, "1", period),  # type: ignore[arg-type]
            ),
        )
        package = CompanyFinancialPackage(
            company_id=_cid(),
            reporting_period=period,
            currency=CurrencyCode("USD"),
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            income_statement=income,
            availability=FinancialDataAvailability.PARTIAL,
        )
        result = compute_financial_metrics_result(package)
        net_margin = next(m for m in result.metrics if m.name is FinancialMetricName.NET_MARGIN)
        self.assertEqual(net_margin.value, Decimal("0.000000"))

    def test_missing_concepts_produce_omissions_not_zeros(self) -> None:
        period = _period()
        income = IncomeStatement(
            company_id=_cid(),
            period=period,
            currency=CurrencyCode("USD"),
            facts=(_money(FinancialConcept.REVENUE, "100", period),),  # type: ignore[arg-type]
        )
        package = CompanyFinancialPackage(
            company_id=_cid(),
            reporting_period=period,
            currency=CurrencyCode("USD"),
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            income_statement=income,
            availability=FinancialDataAvailability.PARTIAL,
        )
        result = compute_financial_metrics_result(package)
        self.assertTrue(result.omissions)
        for omission in result.omissions:
            self.assertNotEqual(omission.semantics.value, "0")
        self.assertFalse(
            any(m.value == 0 and m.name is FinancialMetricName.NET_MARGIN for m in result.metrics)
        )
