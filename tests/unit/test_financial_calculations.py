"""Golden tests for Phase 4 deterministic financial metrics."""

from __future__ import annotations

from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.financial import (
    FinancialMetricName,
    compute_standard_financial_metrics,
)
from financial_intelligence.infrastructure.financial.reference_dataset import (
    APPLE_ID,
    build_reference_financial_packages,
)


class FinancialCalculationTests(TestCase):
    def test_apple_fixture_golden_metrics(self) -> None:
        package = build_reference_financial_packages()[APPLE_ID.as_text()]
        metrics = compute_standard_financial_metrics(package)
        names = {metric.name for metric in metrics}
        self.assertIn(FinancialMetricName.REVENUE_GROWTH, names)
        self.assertIn(FinancialMetricName.GROSS_MARGIN, names)
        self.assertIn(FinancialMetricName.FREE_CASH_FLOW, names)
        revenue_growth = next(m for m in metrics if m.name is FinancialMetricName.REVENUE_GROWTH)
        # FY2024 revenue 391035m vs FY2023 383285m → ~2.02%
        self.assertEqual(revenue_growth.unit, "ratio")
        self.assertGreater(revenue_growth.value, Decimal("0.01"))
        self.assertLess(revenue_growth.value, Decimal("0.03"))

    def test_missing_prior_skips_growth(self) -> None:
        package = build_reference_financial_packages()[APPLE_ID.as_text()]
        package_no_prior = type(package)(
            company_id=package.company_id,
            reporting_period=package.reporting_period,
            currency=package.currency,
            retrieved_at=package.retrieved_at,
            income_statement=package.income_statement,
            balance_sheet=package.balance_sheet,
            cash_flow_statement=package.cash_flow_statement,
            filing=package.filing,
            prior_period_package=None,
            provider_name=package.provider_name,
            availability=package.availability,
            data_origin=package.data_origin,
        )
        metrics = compute_standard_financial_metrics(package_no_prior)
        names = {metric.name for metric in metrics}
        self.assertNotIn(FinancialMetricName.REVENUE_GROWTH, names)
