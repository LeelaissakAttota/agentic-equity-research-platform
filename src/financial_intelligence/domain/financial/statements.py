"""Canonical financial statement containers and company packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial.concepts import FinancialConcept
from financial_intelligence.domain.financial.conflicts import FinancialFactConflict
from financial_intelligence.domain.financial.facts import FinancialFact
from financial_intelligence.domain.financial.filings import FilingMetadata
from financial_intelligence.domain.financial.periods import ReportingPeriod
from financial_intelligence.domain.identity import (
    CompanyId,
    CurrencyCode,
    ListingId,
    SecurityId,
)


class FinancialDataAvailability(StrEnum):
    """Availability of a financial package without fabricating success."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"


_INCOME_CONCEPTS = frozenset(
    {
        FinancialConcept.REVENUE,
        FinancialConcept.COST_OF_REVENUE,
        FinancialConcept.GROSS_PROFIT,
        FinancialConcept.OPERATING_INCOME,
        FinancialConcept.EBIT,
        FinancialConcept.EBITDA,
        FinancialConcept.NET_INCOME,
        FinancialConcept.EPS_BASIC,
        FinancialConcept.EPS_DILUTED,
    }
)
_BALANCE_CONCEPTS = frozenset(
    {
        FinancialConcept.CASH,
        FinancialConcept.TOTAL_ASSETS,
        FinancialConcept.CURRENT_ASSETS,
        FinancialConcept.TOTAL_LIABILITIES,
        FinancialConcept.CURRENT_LIABILITIES,
        FinancialConcept.TOTAL_DEBT,
        FinancialConcept.SHAREHOLDERS_EQUITY,
        FinancialConcept.SHARES_OUTSTANDING,
    }
)
_CASH_FLOW_CONCEPTS = frozenset(
    {
        FinancialConcept.OPERATING_CASH_FLOW,
        FinancialConcept.CAPITAL_EXPENDITURE,
        FinancialConcept.FREE_CASH_FLOW,
    }
)


def _index_facts(
    facts: tuple[FinancialFact, ...],
    *,
    allowed: frozenset[FinancialConcept],
    company_id: CompanyId,
    period: ReportingPeriod,
) -> dict[FinancialConcept, FinancialFact]:
    indexed: dict[FinancialConcept, FinancialFact] = {}
    for fact in facts:
        if fact.concept not in allowed:
            msg = f"concept {fact.concept.value} not allowed on this statement"
            raise ValueError(msg)
        if fact.company_id != company_id:
            msg = "fact company_id must match statement company_id"
            raise ValueError(msg)
        if fact.period != period:
            msg = "fact period must match statement period"
            raise ValueError(msg)
        if fact.concept in indexed:
            msg = f"duplicate concept {fact.concept.value} on statement"
            raise ValueError(msg)
        indexed[fact.concept] = fact
    return indexed


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    """Partial income statement for one reporting period."""

    company_id: CompanyId
    period: ReportingPeriod
    currency: CurrencyCode
    facts: tuple[FinancialFact, ...] = ()

    def __post_init__(self) -> None:
        indexed = _index_facts(
            self.facts,
            allowed=_INCOME_CONCEPTS,
            company_id=self.company_id,
            period=self.period,
        )
        for fact in indexed.values():
            if fact.unit.value in {"currency", "per_share"} and fact.currency != self.currency:
                msg = "income statement fact currency must match statement currency"
                raise ValueError(msg)

    def get(self, concept: FinancialConcept) -> FinancialFact | None:
        for fact in self.facts:
            if fact.concept is concept:
                return fact
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "statement_type": "income_statement",
            "company_id": self.company_id.as_text(),
            "period": self.period.to_dict(),
            "currency": self.currency.as_text(),
            "facts": [fact.to_dict() for fact in self.facts],
        }


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    """Partial balance sheet (instant) for one reporting period."""

    company_id: CompanyId
    period: ReportingPeriod
    currency: CurrencyCode
    facts: tuple[FinancialFact, ...] = ()

    def __post_init__(self) -> None:
        indexed = _index_facts(
            self.facts,
            allowed=_BALANCE_CONCEPTS,
            company_id=self.company_id,
            period=self.period,
        )
        for fact in indexed.values():
            if fact.unit.value == "currency" and fact.currency != self.currency:
                msg = "balance sheet fact currency must match statement currency"
                raise ValueError(msg)

    def get(self, concept: FinancialConcept) -> FinancialFact | None:
        for fact in self.facts:
            if fact.concept is concept:
                return fact
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "statement_type": "balance_sheet",
            "company_id": self.company_id.as_text(),
            "period": self.period.to_dict(),
            "currency": self.currency.as_text(),
            "facts": [fact.to_dict() for fact in self.facts],
        }


@dataclass(frozen=True, slots=True)
class CashFlowStatement:
    """Partial cash-flow statement for one reporting period."""

    company_id: CompanyId
    period: ReportingPeriod
    currency: CurrencyCode
    facts: tuple[FinancialFact, ...] = ()

    def __post_init__(self) -> None:
        indexed = _index_facts(
            self.facts,
            allowed=_CASH_FLOW_CONCEPTS,
            company_id=self.company_id,
            period=self.period,
        )
        for fact in indexed.values():
            if fact.unit.value == "currency" and fact.currency != self.currency:
                msg = "cash flow fact currency must match statement currency"
                raise ValueError(msg)

    def get(self, concept: FinancialConcept) -> FinancialFact | None:
        for fact in self.facts:
            if fact.concept is concept:
                return fact
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "statement_type": "cash_flow_statement",
            "company_id": self.company_id.as_text(),
            "period": self.period.to_dict(),
            "currency": self.currency.as_text(),
            "facts": [fact.to_dict() for fact in self.facts],
        }


@dataclass(frozen=True, slots=True)
class CompanyFinancialPackage:
    """Normalized financial package for one company and primary reporting period.

    Statements in the package share the same duration period for income/cash flow.
    Balance sheet may use an INSTANT period ending on the same ``period_end``.
    Partial availability is explicit: missing statements/facts remain absent.
    """

    company_id: CompanyId
    reporting_period: ReportingPeriod
    currency: CurrencyCode
    retrieved_at: datetime
    income_statement: IncomeStatement | None = None
    balance_sheet: BalanceSheet | None = None
    cash_flow_statement: CashFlowStatement | None = None
    filing: FilingMetadata | None = None
    prior_period_package: CompanyFinancialPackage | None = None
    provider_name: str = "fixture"
    availability: FinancialDataAvailability = FinancialDataAvailability.AVAILABLE
    data_origin: DataOrigin = DataOrigin.FIXTURE
    security_id: SecurityId | None = None
    listing_id: ListingId | None = None
    conflicts: tuple[FinancialFactConflict, ...] = ()

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        if self.listing_id is not None and self.security_id is None:
            msg = "listing_id requires security_id for identity consistency"
            raise ValueError(msg)
        if self.availability is FinancialDataAvailability.AVAILABLE and (
            self.income_statement is None
            and self.balance_sheet is None
            and self.cash_flow_statement is None
        ):
            msg = "AVAILABLE package requires at least one statement"
            raise ValueError(msg)
        if self.data_origin is DataOrigin.UNAVAILABLE and (
            self.income_statement is not None
            or self.balance_sheet is not None
            or self.cash_flow_statement is not None
        ):
            msg = "UNAVAILABLE origin must not include statements"
            raise ValueError(msg)
        for statement in (
            self.income_statement,
            self.balance_sheet,
            self.cash_flow_statement,
        ):
            if statement is None:
                continue
            if statement.company_id != self.company_id:
                msg = "statement company_id must match package"
                raise ValueError(msg)
            if statement.currency != self.currency:
                msg = "statement currency must match package currency"
                raise ValueError(msg)
        if (
            self.income_statement is not None
            and self.income_statement.period != self.reporting_period
        ):
            msg = "income statement period must match package reporting_period"
            raise ValueError(msg)
        if (
            self.cash_flow_statement is not None
            and self.cash_flow_statement.period != self.reporting_period
        ):
            msg = "cash flow period must match package reporting_period"
            raise ValueError(msg)
        if self.balance_sheet is not None:
            bs_period = self.balance_sheet.period
            if bs_period.period_end != self.reporting_period.period_end:
                msg = "balance sheet period_end must match package period_end"
                raise ValueError(msg)
        if self.filing is not None and self.filing.company_id != self.company_id:
            msg = "filing company_id must match package"
            raise ValueError(msg)
        if self.filing is not None:
            filing_id = self.filing.filing_id
            for statement in (
                self.income_statement,
                self.balance_sheet,
                self.cash_flow_statement,
            ):
                if statement is None:
                    continue
                for fact in statement.facts:
                    if fact.filing_id is not None and fact.filing_id != filing_id:
                        msg = "fact filing_id must match package filing when both are set"
                        raise ValueError(msg)
        if self.prior_period_package is not None:
            prior = self.prior_period_package
            if prior.company_id != self.company_id:
                msg = "prior_period_package company_id mismatch"
                raise ValueError(msg)
            if prior.currency != self.currency:
                msg = "prior_period_package currency mismatch"
                raise ValueError(msg)
            if prior.prior_period_package is not None:
                msg = "prior_period_package must not nest further priors"
                raise ValueError(msg)

    def with_data_origin(self, origin: DataOrigin) -> CompanyFinancialPackage:
        return CompanyFinancialPackage(
            company_id=self.company_id,
            reporting_period=self.reporting_period,
            currency=self.currency,
            retrieved_at=self.retrieved_at,
            income_statement=self.income_statement,
            balance_sheet=self.balance_sheet,
            cash_flow_statement=self.cash_flow_statement,
            filing=self.filing,
            prior_period_package=self.prior_period_package,
            provider_name=self.provider_name,
            availability=self.availability,
            data_origin=origin,
            security_id=self.security_id,
            listing_id=self.listing_id,
            conflicts=self.conflicts,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "security_id": self.security_id.as_text() if self.security_id else None,
            "listing_id": self.listing_id.as_text() if self.listing_id else None,
            "reporting_period": self.reporting_period.to_dict(),
            "currency": self.currency.as_text(),
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "income_statement": (
                self.income_statement.to_dict() if self.income_statement else None
            ),
            "balance_sheet": self.balance_sheet.to_dict() if self.balance_sheet else None,
            "cash_flow_statement": (
                self.cash_flow_statement.to_dict() if self.cash_flow_statement else None
            ),
            "filing": self.filing.to_dict() if self.filing else None,
            "prior_reporting_period": (
                self.prior_period_package.reporting_period.to_dict()
                if self.prior_period_package is not None
                else None
            ),
            "provider_name": self.provider_name,
            "availability": self.availability.value,
            "data_origin": self.data_origin.value,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }
