"""Deterministic financial reference fixtures for Phase 4 Prompt 1.

REFERENCE / DEMO financial data only — never live authoritative filings.

Coverage is intentionally small: Apple (US) and Reliance Industries (India NSE).
Values are fixed Decimals chosen for reproducible calculation goldens.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancialPackage,
    FilingFormType,
    FilingId,
    FilingMetadata,
    FinancialConcept,
    FinancialDataAvailability,
    FinancialFact,
    FinancialScale,
    FinancialUnit,
    IncomeStatement,
    PeriodBasis,
    ReportingPeriod,
    build_fact,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId

_RETRIEVED = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)
_APPLE_SOURCE = SourceId(value=UUID("63333333-3333-4333-8333-333333333001"))
_RELIANCE_SOURCE = SourceId(value=UUID("63333333-3333-4333-8333-333333333002"))
_APPLE_FILING = FilingId(value=UUID("73333333-3333-4333-8333-333333333001"))
_RELIANCE_FILING = FilingId(value=UUID("73333333-3333-4333-8333-333333333002"))
_APPLE_PRIOR_FILING = FilingId(value=UUID("73333333-3333-4333-8333-333333333011"))
_RELIANCE_PRIOR_FILING = FilingId(value=UUID("73333333-3333-4333-8333-333333333012"))

APPLE_ID = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
RELIANCE_ID = CompanyId.from_string("11111111-1111-4111-8111-111111111001")


def _fy(year: int, *, start: date, end: date) -> ReportingPeriod:
    return ReportingPeriod(
        basis=PeriodBasis.FISCAL_YEAR,
        fiscal_year=year,
        period_start=start,
        period_end=end,
        label=f"FY{year}",
    )


def _instant(year: int, as_of: date) -> ReportingPeriod:
    return ReportingPeriod(
        basis=PeriodBasis.INSTANT,
        fiscal_year=year,
        period_end=as_of,
        as_of=as_of,
        label=f"BS{year}",
    )


def _money(
    company_id: CompanyId,
    concept: FinancialConcept,
    period: ReportingPeriod,
    raw: str,
    *,
    currency: str,
    source_id: SourceId,
    filing_id: FilingId,
    scale: FinancialScale = FinancialScale.MILLIONS,
    provider_concept: str | None = None,
) -> FinancialFact:
    return build_fact(
        company_id=company_id,
        concept=concept,
        period=period,
        raw_value=Decimal(raw),
        unit=FinancialUnit.CURRENCY,
        scale=scale,
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        retrieved_at=_RETRIEVED,
        currency=CurrencyCode(currency),
        filing_id=filing_id,
        provider_concept=provider_concept,
    )


def _shares(
    company_id: CompanyId,
    period: ReportingPeriod,
    raw: str,
    *,
    source_id: SourceId,
    filing_id: FilingId,
) -> FinancialFact:
    return build_fact(
        company_id=company_id,
        concept=FinancialConcept.SHARES_OUTSTANDING,
        period=period,
        raw_value=Decimal(raw),
        unit=FinancialUnit.SHARES,
        scale=FinancialScale.ONES,
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        retrieved_at=_RETRIEVED,
        filing_id=filing_id,
        provider_concept="CommonStockSharesOutstanding",
    )


def _eps(
    company_id: CompanyId,
    concept: FinancialConcept,
    period: ReportingPeriod,
    raw: str,
    *,
    currency: str,
    source_id: SourceId,
    filing_id: FilingId,
) -> FinancialFact:
    return build_fact(
        company_id=company_id,
        concept=concept,
        period=period,
        raw_value=Decimal(raw),
        unit=FinancialUnit.PER_SHARE,
        scale=FinancialScale.ONES,
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        retrieved_at=_RETRIEVED,
        currency=CurrencyCode(currency),
        filing_id=filing_id,
    )


def _apple_package(*, year: int, prior: CompanyFinancialPackage | None) -> CompanyFinancialPackage:
    if year == 2024:
        period = _fy(2024, start=date(2023, 10, 1), end=date(2024, 9, 28))
        bs_period = _instant(2024, date(2024, 9, 28))
        filing_id = _APPLE_FILING
        revenue, cogs, gross, op_inc, net_inc = "391035", "210352", "180683", "123216", "93736"
        cash, assets, ca, liab, cl, debt, equity = (
            "29943",
            "364980",
            "152987",
            "308030",
            "176392",
            "106600",
            "56950",
        )
        ocf, capex = "118254", "9447"
        shares, eps_b, eps_d = "15116786000", "6.11", "6.08"
    elif year == 2023:
        period = _fy(2023, start=date(2022, 10, 1), end=date(2023, 9, 30))
        bs_period = _instant(2023, date(2023, 9, 30))
        filing_id = _APPLE_PRIOR_FILING
        revenue, cogs, gross, op_inc, net_inc = "383285", "214137", "169148", "114301", "96995"
        cash, assets, ca, liab, cl, debt, equity = (
            "29965",
            "352583",
            "143566",
            "290437",
            "145308",
            "111088",
            "62146",
        )
        ocf, capex = "110543", "10959"
        shares, eps_b, eps_d = "15550061000", "6.16", "6.13"
    else:
        msg = f"unsupported apple fixture year {year}"
        raise ValueError(msg)

    currency = CurrencyCode("USD")
    income = IncomeStatement(
        company_id=APPLE_ID,
        period=period,
        currency=currency,
        facts=(
            _money(
                APPLE_ID,
                FinancialConcept.REVENUE,
                period,
                revenue,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
                provider_concept="Revenues",
            ),
            _money(
                APPLE_ID,
                FinancialConcept.COST_OF_REVENUE,
                period,
                cogs,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.GROSS_PROFIT,
                period,
                gross,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.OPERATING_INCOME,
                period,
                op_inc,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.NET_INCOME,
                period,
                net_inc,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _eps(
                APPLE_ID,
                FinancialConcept.EPS_BASIC,
                period,
                eps_b,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _eps(
                APPLE_ID,
                FinancialConcept.EPS_DILUTED,
                period,
                eps_d,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
        ),
    )
    balance = BalanceSheet(
        company_id=APPLE_ID,
        period=bs_period,
        currency=currency,
        facts=(
            _money(
                APPLE_ID,
                FinancialConcept.CASH,
                bs_period,
                cash,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.TOTAL_ASSETS,
                bs_period,
                assets,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.CURRENT_ASSETS,
                bs_period,
                ca,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.TOTAL_LIABILITIES,
                bs_period,
                liab,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.CURRENT_LIABILITIES,
                bs_period,
                cl,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.TOTAL_DEBT,
                bs_period,
                debt,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.SHAREHOLDERS_EQUITY,
                bs_period,
                equity,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _shares(
                APPLE_ID,
                bs_period,
                shares,
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
        ),
    )
    cash_flow = CashFlowStatement(
        company_id=APPLE_ID,
        period=period,
        currency=currency,
        facts=(
            _money(
                APPLE_ID,
                FinancialConcept.OPERATING_CASH_FLOW,
                period,
                ocf,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                APPLE_ID,
                FinancialConcept.CAPITAL_EXPENDITURE,
                period,
                capex,
                currency="USD",
                source_id=_APPLE_SOURCE,
                filing_id=filing_id,
            ),
        ),
    )
    filing = FilingMetadata(
        filing_id=filing_id,
        company_id=APPLE_ID,
        form_type=FilingFormType.US_10K,
        reporting_period=period,
        source_id=_APPLE_SOURCE,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        filed_at=period.period_end,
        published_at=period.period_end,
        retrieved_at=_RETRIEVED,
        accession_or_reference=f"fixture-aapl-10k-{year}",
        provider_name="fixture",
    )
    return CompanyFinancialPackage(
        company_id=APPLE_ID,
        reporting_period=period,
        currency=currency,
        retrieved_at=_RETRIEVED,
        income_statement=income,
        balance_sheet=balance,
        cash_flow_statement=cash_flow,
        filing=filing,
        prior_period_package=prior,
        provider_name="fixture",
        availability=FinancialDataAvailability.AVAILABLE,
        data_origin=DataOrigin.FIXTURE,
    )


def _reliance_package(
    *, year: int, prior: CompanyFinancialPackage | None
) -> CompanyFinancialPackage:
    if year == 2025:
        period = _fy(2025, start=date(2024, 4, 1), end=date(2025, 3, 31))
        bs_period = _instant(2025, date(2025, 3, 31))
        filing_id = _RELIANCE_FILING
        revenue, gross, op_inc, net_inc = "964690", "301200", "112400", "69620"
        cash, assets, ca, liab, cl, debt, equity = (
            "185000",
            "1785000",
            "420000",
            "980000",
            "310000",
            "340000",
            "805000",
        )
        ocf, capex = "158000", "92000"
    elif year == 2024:
        period = _fy(2024, start=date(2023, 4, 1), end=date(2024, 3, 31))
        bs_period = _instant(2024, date(2024, 3, 31))
        filing_id = _RELIANCE_PRIOR_FILING
        revenue, gross, op_inc, net_inc = "901060", "280100", "104200", "69620"
        cash, assets, ca, liab, cl, debt, equity = (
            "170000",
            "1650000",
            "390000",
            "920000",
            "290000",
            "320000",
            "730000",
        )
        ocf, capex = "145000", "88000"
    else:
        msg = f"unsupported reliance fixture year {year}"
        raise ValueError(msg)

    currency = CurrencyCode("INR")
    income = IncomeStatement(
        company_id=RELIANCE_ID,
        period=period,
        currency=currency,
        facts=(
            _money(
                RELIANCE_ID,
                FinancialConcept.REVENUE,
                period,
                revenue,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
                provider_concept="Revenue from Operations",
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.GROSS_PROFIT,
                period,
                gross,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.OPERATING_INCOME,
                period,
                op_inc,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.NET_INCOME,
                period,
                net_inc,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
        ),
    )
    balance = BalanceSheet(
        company_id=RELIANCE_ID,
        period=bs_period,
        currency=currency,
        facts=(
            _money(
                RELIANCE_ID,
                FinancialConcept.CASH,
                bs_period,
                cash,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.TOTAL_ASSETS,
                bs_period,
                assets,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.CURRENT_ASSETS,
                bs_period,
                ca,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.TOTAL_LIABILITIES,
                bs_period,
                liab,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.CURRENT_LIABILITIES,
                bs_period,
                cl,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.TOTAL_DEBT,
                bs_period,
                debt,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.SHAREHOLDERS_EQUITY,
                bs_period,
                equity,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
        ),
    )
    cash_flow = CashFlowStatement(
        company_id=RELIANCE_ID,
        period=period,
        currency=currency,
        facts=(
            _money(
                RELIANCE_ID,
                FinancialConcept.OPERATING_CASH_FLOW,
                period,
                ocf,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
            _money(
                RELIANCE_ID,
                FinancialConcept.CAPITAL_EXPENDITURE,
                period,
                capex,
                currency="INR",
                source_id=_RELIANCE_SOURCE,
                filing_id=filing_id,
            ),
        ),
    )
    filing = FilingMetadata(
        filing_id=filing_id,
        company_id=RELIANCE_ID,
        form_type=FilingFormType.IN_ANNUAL_RESULTS,
        reporting_period=period,
        source_id=_RELIANCE_SOURCE,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        filed_at=period.period_end,
        published_at=period.period_end,
        retrieved_at=_RETRIEVED,
        accession_or_reference=f"fixture-reliance-annual-{year}",
        provider_name="fixture",
    )
    return CompanyFinancialPackage(
        company_id=RELIANCE_ID,
        reporting_period=period,
        currency=currency,
        retrieved_at=_RETRIEVED,
        income_statement=income,
        balance_sheet=balance,
        cash_flow_statement=cash_flow,
        filing=filing,
        prior_period_package=prior,
        provider_name="fixture",
        availability=FinancialDataAvailability.AVAILABLE,
        data_origin=DataOrigin.FIXTURE,
    )


def build_reference_financial_packages() -> dict[str, CompanyFinancialPackage]:
    """Return company_id → latest financial package (with prior linked)."""

    apple_2023 = _apple_package(year=2023, prior=None)
    apple_2024 = _apple_package(year=2024, prior=apple_2023)
    reliance_2024 = _reliance_package(year=2024, prior=None)
    reliance_2025 = _reliance_package(year=2025, prior=reliance_2024)
    return {
        APPLE_ID.as_text(): apple_2024,
        RELIANCE_ID.as_text(): reliance_2025,
    }
