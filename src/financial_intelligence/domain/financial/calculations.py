"""Deterministic financial calculation library (ADR-017).

Formulas are explicit and versioned. LLMs must not perform these calculations.
Missing inputs → omitted metric with explainable reason (never invent zeros).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from financial_intelligence.domain.financial.concepts import FinancialConcept
from financial_intelligence.domain.financial.facts import FinancialFact
from financial_intelligence.domain.financial.missing import MissingDataSemantics
from financial_intelligence.domain.financial.periods import ReportingPeriod
from financial_intelligence.domain.financial.statements import CompanyFinancialPackage
from financial_intelligence.domain.financial.units import FinancialUnit
from financial_intelligence.domain.identity import CurrencyCode

CALCULATION_LIBRARY_VERSION = "financial-calc-1"
_RATIO = Decimal("0.000001")
_MONEY = Decimal("0.01")


class FinancialMetricName(StrEnum):
    """Supported Phase 4 financial metrics."""

    REVENUE_GROWTH = "revenue_growth"
    NET_INCOME_GROWTH = "net_income_growth"
    GROSS_MARGIN = "gross_margin"
    OPERATING_MARGIN = "operating_margin"
    NET_MARGIN = "net_margin"
    CURRENT_RATIO = "current_ratio"
    DEBT_TO_EQUITY = "debt_to_equity"
    OPERATING_CASH_FLOW_MARGIN = "operating_cash_flow_margin"
    FREE_CASH_FLOW = "free_cash_flow"
    FREE_CASH_FLOW_MARGIN = "free_cash_flow_margin"


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    """One reproducible derived financial figure (not a source fact)."""

    name: FinancialMetricName
    value: Decimal
    unit: str
    formula_version: str
    inputs_period: str | None = None
    currency: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "value": str(self.value),
            "unit": self.unit,
            "formula_version": self.formula_version,
            "inputs_period": self.inputs_period,
            "currency": self.currency,
            "kind": "derived_metric",
        }


@dataclass(frozen=True, slots=True)
class OmittedMetric:
    """Explainable absence of a derived metric (never fabricated as zero)."""

    name: FinancialMetricName
    semantics: MissingDataSemantics
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "semantics": self.semantics.value,
            "detail": self.detail,
            "kind": "omitted_metric",
        }


@dataclass(frozen=True, slots=True)
class FinancialMetricsResult:
    """Computed metrics plus explicit omissions for unavailable calculations."""

    metrics: tuple[FinancialMetric, ...]
    omissions: tuple[OmittedMetric, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": [metric.to_dict() for metric in self.metrics],
            "omissions": [omission.to_dict() for omission in self.omissions],
            "calculation_library_version": CALCULATION_LIBRARY_VERSION,
        }


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _currency_fact(
    fact: FinancialFact | None,
    *,
    expected: CurrencyCode,
) -> FinancialFact | None:
    if fact is None:
        return None
    if fact.unit is not FinancialUnit.CURRENCY:
        return None
    if fact.currency != expected:
        return None
    return fact


def _omit(
    name: FinancialMetricName,
    semantics: MissingDataSemantics,
    detail: str,
) -> OmittedMetric:
    return OmittedMetric(name=name, semantics=semantics, detail=detail)


def _growth(
    *,
    name: FinancialMetricName,
    current: FinancialFact | None,
    prior: FinancialFact | None,
    current_period: ReportingPeriod,
    prior_period: ReportingPeriod | None,
) -> FinancialMetric | OmittedMetric:
    if current is None or prior is None or prior_period is None:
        return _omit(
            name,
            MissingDataSemantics.NOT_REPORTED,
            "current or prior period input missing",
        )
    reason = current_period.incomparability_reason(prior_period)
    if reason is not None:
        return _omit(
            name,
            MissingDataSemantics.INCOMPARABLE_PERIOD,
            f"periods not comparable: {reason.value}",
        )
    if current.currency != prior.currency:
        return _omit(
            name,
            MissingDataSemantics.CURRENCY_MISMATCH,
            "current and prior currencies differ",
        )
    if current.unit != prior.unit:
        return _omit(
            name,
            MissingDataSemantics.UNIT_MISMATCH,
            "current and prior units differ",
        )
    if prior.normalized_value == 0:
        return _omit(
            name,
            MissingDataSemantics.ZERO_DENOMINATOR,
            "prior period value is zero",
        )
    value = (current.normalized_value / prior.normalized_value) - Decimal("1")
    return FinancialMetric(
        name=name,
        value=_quantize(value, _RATIO),
        unit="ratio",
        formula_version=f"{CALCULATION_LIBRARY_VERSION}:{name.value}=(current/prior)-1",
        inputs_period=current_period.display_label(),
        currency=current.currency.as_text() if current.currency else None,
    )


def _margin(
    *,
    name: FinancialMetricName,
    numerator: FinancialFact | None,
    denominator: FinancialFact | None,
    period: ReportingPeriod,
    formula: str,
) -> FinancialMetric | OmittedMetric:
    if numerator is None or denominator is None:
        return _omit(
            name,
            MissingDataSemantics.NOT_REPORTED,
            "numerator or denominator concept missing",
        )
    if numerator.currency != denominator.currency:
        return _omit(
            name,
            MissingDataSemantics.CURRENCY_MISMATCH,
            "numerator and denominator currencies differ",
        )
    if numerator.unit is not FinancialUnit.CURRENCY:
        return _omit(
            name,
            MissingDataSemantics.UNIT_MISMATCH,
            "numerator must be currency unit",
        )
    if denominator.unit is not FinancialUnit.CURRENCY:
        return _omit(
            name,
            MissingDataSemantics.UNIT_MISMATCH,
            "denominator must be currency unit",
        )
    if denominator.normalized_value == 0:
        return _omit(
            name,
            MissingDataSemantics.ZERO_DENOMINATOR,
            "denominator is zero",
        )
    value = numerator.normalized_value / denominator.normalized_value
    return FinancialMetric(
        name=name,
        value=_quantize(value, _RATIO),
        unit="ratio",
        formula_version=f"{CALCULATION_LIBRARY_VERSION}:{formula}",
        inputs_period=period.display_label(),
        currency=denominator.currency.as_text() if denominator.currency else None,
    )


def free_cash_flow(
    *,
    operating_cash_flow: FinancialFact | None,
    capital_expenditure: FinancialFact | None,
    period: ReportingPeriod,
) -> FinancialMetric | OmittedMetric:
    """FCF = Operating Cash Flow - Capital Expenditure (CapEx as positive outflow).

    CapEx facts must be stored as non-negative outflow magnitudes. Provider sign
    conventions are normalized in infrastructure before domain facts are built.
    """

    if operating_cash_flow is None or capital_expenditure is None:
        return _omit(
            FinancialMetricName.FREE_CASH_FLOW,
            MissingDataSemantics.NOT_REPORTED,
            "operating cash flow or capital expenditure missing",
        )
    if operating_cash_flow.currency != capital_expenditure.currency:
        return _omit(
            FinancialMetricName.FREE_CASH_FLOW,
            MissingDataSemantics.CURRENCY_MISMATCH,
            "OCF and CapEx currencies differ",
        )
    if operating_cash_flow.unit is not FinancialUnit.CURRENCY:
        return _omit(
            FinancialMetricName.FREE_CASH_FLOW,
            MissingDataSemantics.UNIT_MISMATCH,
            "operating cash flow must be currency unit",
        )
    if capital_expenditure.unit is not FinancialUnit.CURRENCY:
        return _omit(
            FinancialMetricName.FREE_CASH_FLOW,
            MissingDataSemantics.UNIT_MISMATCH,
            "capital expenditure must be currency unit",
        )
    if capital_expenditure.normalized_value < 0:
        return _omit(
            FinancialMetricName.FREE_CASH_FLOW,
            MissingDataSemantics.INVALID_INPUT,
            "CapEx must be a non-negative outflow magnitude",
        )
    value = operating_cash_flow.normalized_value - capital_expenditure.normalized_value
    return FinancialMetric(
        name=FinancialMetricName.FREE_CASH_FLOW,
        value=_quantize(value, _MONEY),
        unit=(
            operating_cash_flow.currency.as_text() if operating_cash_flow.currency else "currency"
        ),
        formula_version=(
            f"{CALCULATION_LIBRARY_VERSION}:free_cash_flow=operating_cash_flow-capital_expenditure"
        ),
        inputs_period=period.display_label(),
        currency=operating_cash_flow.currency.as_text() if operating_cash_flow.currency else None,
    )


def _append_outcome(
    metrics: list[FinancialMetric],
    omissions: list[OmittedMetric],
    outcome: FinancialMetric | OmittedMetric,
) -> None:
    if isinstance(outcome, FinancialMetric):
        metrics.append(outcome)
    else:
        omissions.append(outcome)


def compute_financial_metrics_result(
    package: CompanyFinancialPackage,
) -> FinancialMetricsResult:
    """Compute Prompt metrics where inputs exist; omit with reasons otherwise."""

    metrics: list[FinancialMetric] = []
    omissions: list[OmittedMetric] = []
    currency = package.currency
    period = package.reporting_period
    income = package.income_statement
    balance = package.balance_sheet
    cash = package.cash_flow_statement
    prior = package.prior_period_package

    revenue = _currency_fact(
        income.get(FinancialConcept.REVENUE) if income else None, expected=currency
    )
    gross = _currency_fact(
        income.get(FinancialConcept.GROSS_PROFIT) if income else None, expected=currency
    )
    operating = _currency_fact(
        income.get(FinancialConcept.OPERATING_INCOME) if income else None, expected=currency
    )
    net_income = _currency_fact(
        income.get(FinancialConcept.NET_INCOME) if income else None, expected=currency
    )

    prior_income = prior.income_statement if prior else None
    prior_revenue = _currency_fact(
        prior_income.get(FinancialConcept.REVENUE) if prior_income else None,
        expected=currency,
    )
    prior_net = _currency_fact(
        prior_income.get(FinancialConcept.NET_INCOME) if prior_income else None,
        expected=currency,
    )

    _append_outcome(
        metrics,
        omissions,
        _growth(
            name=FinancialMetricName.REVENUE_GROWTH,
            current=revenue,
            prior=prior_revenue,
            current_period=period,
            prior_period=prior.reporting_period if prior else None,
        ),
    )
    _append_outcome(
        metrics,
        omissions,
        _growth(
            name=FinancialMetricName.NET_INCOME_GROWTH,
            current=net_income,
            prior=prior_net,
            current_period=period,
            prior_period=prior.reporting_period if prior else None,
        ),
    )

    for metric_name, num, formula in (
        (FinancialMetricName.GROSS_MARGIN, gross, "gross_margin=gross_profit/revenue"),
        (
            FinancialMetricName.OPERATING_MARGIN,
            operating,
            "operating_margin=operating_income/revenue",
        ),
        (FinancialMetricName.NET_MARGIN, net_income, "net_margin=net_income/revenue"),
    ):
        _append_outcome(
            metrics,
            omissions,
            _margin(
                name=metric_name,
                numerator=num,
                denominator=revenue,
                period=period,
                formula=formula,
            ),
        )

    current_assets = _currency_fact(
        balance.get(FinancialConcept.CURRENT_ASSETS) if balance else None,
        expected=currency,
    )
    current_liab = _currency_fact(
        balance.get(FinancialConcept.CURRENT_LIABILITIES) if balance else None,
        expected=currency,
    )
    if current_assets is None or current_liab is None:
        omissions.append(
            _omit(
                FinancialMetricName.CURRENT_RATIO,
                MissingDataSemantics.NOT_REPORTED,
                "current assets or current liabilities missing",
            )
        )
    elif current_liab.normalized_value == 0:
        omissions.append(
            _omit(
                FinancialMetricName.CURRENT_RATIO,
                MissingDataSemantics.ZERO_DENOMINATOR,
                "current liabilities are zero",
            )
        )
    else:
        metrics.append(
            FinancialMetric(
                name=FinancialMetricName.CURRENT_RATIO,
                value=_quantize(
                    current_assets.normalized_value / current_liab.normalized_value,
                    _RATIO,
                ),
                unit="ratio",
                formula_version=(
                    f"{CALCULATION_LIBRARY_VERSION}:current_ratio="
                    "current_assets/current_liabilities"
                ),
                inputs_period=period.display_label(),
                currency=currency.as_text(),
            )
        )

    total_debt = _currency_fact(
        balance.get(FinancialConcept.TOTAL_DEBT) if balance else None,
        expected=currency,
    )
    equity = _currency_fact(
        balance.get(FinancialConcept.SHAREHOLDERS_EQUITY) if balance else None,
        expected=currency,
    )
    if total_debt is None or equity is None:
        omissions.append(
            _omit(
                FinancialMetricName.DEBT_TO_EQUITY,
                MissingDataSemantics.NOT_REPORTED,
                "total debt or shareholders equity missing",
            )
        )
    elif equity.normalized_value == 0:
        omissions.append(
            _omit(
                FinancialMetricName.DEBT_TO_EQUITY,
                MissingDataSemantics.ZERO_DENOMINATOR,
                "shareholders equity is zero",
            )
        )
    else:
        # Negative equity is financially possible; ratio remains defined when non-zero.
        metrics.append(
            FinancialMetric(
                name=FinancialMetricName.DEBT_TO_EQUITY,
                value=_quantize(total_debt.normalized_value / equity.normalized_value, _RATIO),
                unit="ratio",
                formula_version=(
                    f"{CALCULATION_LIBRARY_VERSION}:debt_to_equity=total_debt/shareholders_equity"
                ),
                inputs_period=period.display_label(),
                currency=currency.as_text(),
            )
        )

    ocf = _currency_fact(
        cash.get(FinancialConcept.OPERATING_CASH_FLOW) if cash else None,
        expected=currency,
    )
    capex = _currency_fact(
        cash.get(FinancialConcept.CAPITAL_EXPENDITURE) if cash else None,
        expected=currency,
    )
    _append_outcome(
        metrics,
        omissions,
        _margin(
            name=FinancialMetricName.OPERATING_CASH_FLOW_MARGIN,
            numerator=ocf,
            denominator=revenue,
            period=period,
            formula="operating_cash_flow_margin=operating_cash_flow/revenue",
        ),
    )

    fcf_fact = _currency_fact(
        cash.get(FinancialConcept.FREE_CASH_FLOW) if cash else None,
        expected=currency,
    )
    fcf_outcome: FinancialMetric | OmittedMetric
    if fcf_fact is not None:
        fcf_outcome = FinancialMetric(
            name=FinancialMetricName.FREE_CASH_FLOW,
            value=_quantize(fcf_fact.normalized_value, _MONEY),
            unit=currency.as_text(),
            formula_version=f"{CALCULATION_LIBRARY_VERSION}:free_cash_flow=reported_fact",
            inputs_period=period.display_label(),
            currency=currency.as_text(),
        )
    else:
        fcf_outcome = free_cash_flow(
            operating_cash_flow=ocf,
            capital_expenditure=capex,
            period=period,
        )
    _append_outcome(metrics, omissions, fcf_outcome)

    if isinstance(fcf_outcome, FinancialMetric):
        if revenue is None:
            omissions.append(
                _omit(
                    FinancialMetricName.FREE_CASH_FLOW_MARGIN,
                    MissingDataSemantics.NOT_REPORTED,
                    "revenue missing for FCF margin",
                )
            )
        elif revenue.normalized_value == 0:
            omissions.append(
                _omit(
                    FinancialMetricName.FREE_CASH_FLOW_MARGIN,
                    MissingDataSemantics.ZERO_DENOMINATOR,
                    "revenue is zero",
                )
            )
        else:
            metrics.append(
                FinancialMetric(
                    name=FinancialMetricName.FREE_CASH_FLOW_MARGIN,
                    value=_quantize(fcf_outcome.value / revenue.normalized_value, _RATIO),
                    unit="ratio",
                    formula_version=(
                        f"{CALCULATION_LIBRARY_VERSION}:free_cash_flow_margin=fcf/revenue"
                    ),
                    inputs_period=period.display_label(),
                    currency=currency.as_text(),
                )
            )
    else:
        omissions.append(
            _omit(
                FinancialMetricName.FREE_CASH_FLOW_MARGIN,
                MissingDataSemantics.NOT_APPLICABLE,
                "FCF unavailable; FCF margin not computed",
            )
        )

    return FinancialMetricsResult(metrics=tuple(metrics), omissions=tuple(omissions))


def compute_standard_financial_metrics(
    package: CompanyFinancialPackage,
) -> tuple[FinancialMetric, ...]:
    """Backward-compatible helper returning only successfully computed metrics."""

    return compute_financial_metrics_result(package).metrics
