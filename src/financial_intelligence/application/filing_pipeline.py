"""Deterministic filing document processing pipeline foundation.

Acquisition → validation → metadata → normalization → concept mapping →
facts → statements → derived metrics → provenance.

Raw source facts stay separate from derived calculations. No RAG / LLM.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.financial import (
    CompanyFinancialPackage,
    FinancialFact,
    FinancialFactConflict,
    FinancialMetricsResult,
    PeriodBasis,
    ReportingPeriod,
    build_fact,
    compute_financial_metrics_result,
    detect_fact_conflicts,
)
from financial_intelligence.domain.financial.concepts import FinancialConcept
from financial_intelligence.domain.financial.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)


class FilingPipelineStage(StrEnum):
    """Ordered pipeline stages for financial filing processing."""

    ACQUISITION = "acquisition"
    VALIDATION = "validation"
    METADATA_EXTRACTION = "metadata_extraction"
    NORMALIZATION = "normalization"
    CONCEPT_MAPPING = "concept_mapping"
    FINANCIAL_FACTS = "financial_facts"
    STATEMENTS = "statements"
    DERIVED_METRICS = "derived_metrics"
    PROVENANCE = "provenance"


_INCOME = frozenset(
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
_BALANCE = frozenset(
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
_CASH = frozenset(
    {
        FinancialConcept.OPERATING_CASH_FLOW,
        FinancialConcept.CAPITAL_EXPENDITURE,
        FinancialConcept.FREE_CASH_FLOW,
    }
)


@dataclass(frozen=True, slots=True)
class FilingPipelineResult:
    """Pipeline output with stage completion, conflicts, and derived metrics."""

    stages_completed: tuple[FilingPipelineStage, ...]
    package: CompanyFinancialPackage | None
    raw_facts: tuple[FinancialFact, ...]
    conflicts: tuple[FinancialFactConflict, ...]
    metrics_result: FinancialMetricsResult | None
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "stages_completed": [stage.value for stage in self.stages_completed],
            "detail": self.detail,
            "raw_fact_count": len(self.raw_facts),
            "conflict_count": len(self.conflicts),
            "package": self.package.to_dict() if self.package is not None else None,
            "metrics_result": (
                self.metrics_result.to_dict() if self.metrics_result is not None else None
            ),
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "kind": "filing_pipeline_result",
        }


def assemble_package_from_facts(
    base: CompanyFinancialPackage,
    facts: Sequence[FinancialFact],
) -> FilingPipelineResult:
    """Validate/normalize facts into statements, then compute derived metrics.

    ``base`` supplies company/period/currency/filing/provenance context.
    Input facts are treated as raw acquired facts; derived metrics are separate.
    """

    stages: list[FilingPipelineStage] = [
        FilingPipelineStage.ACQUISITION,
        FilingPipelineStage.VALIDATION,
        FilingPipelineStage.METADATA_EXTRACTION,
        FilingPipelineStage.NORMALIZATION,
        FilingPipelineStage.CONCEPT_MAPPING,
        FilingPipelineStage.FINANCIAL_FACTS,
    ]
    raw = tuple(facts)
    for fact in raw:
        if fact.company_id != base.company_id:
            return FilingPipelineResult(
                stages_completed=tuple(stages[:2]),
                package=None,
                raw_facts=raw,
                conflicts=(),
                metrics_result=None,
                detail="fact company_id does not match package company_id",
            )

    survivors, conflicts = detect_fact_conflicts(raw)
    stages.append(FilingPipelineStage.STATEMENTS)

    income_facts = tuple(
        f for f in survivors if f.concept in _INCOME and f.period == base.reporting_period
    )
    cash_facts = tuple(
        f for f in survivors if f.concept in _CASH and f.period == base.reporting_period
    )

    balance_period = ReportingPeriod(
        basis=PeriodBasis.INSTANT,
        fiscal_year=base.reporting_period.fiscal_year,
        period_end=base.reporting_period.period_end,
        as_of=base.reporting_period.period_end,
        label=f"BS{base.reporting_period.fiscal_year}",
    )
    if base.balance_sheet is not None:
        balance_period = base.balance_sheet.period

    balance_facts = tuple(
        build_fact(
            company_id=f.company_id,
            concept=f.concept,
            period=balance_period,
            raw_value=f.raw_value,
            unit=f.unit,
            scale=f.scale,
            source_id=f.source_id,
            authority_tier=f.authority_tier,
            retrieved_at=f.retrieved_at,
            currency=f.currency,
            filing_id=f.filing_id,
            provider_concept=f.provider_concept,
        )
        for f in survivors
        if f.concept in _BALANCE and f.period.period_end == balance_period.period_end
    )

    try:
        income = (
            IncomeStatement(
                company_id=base.company_id,
                period=base.reporting_period,
                currency=base.currency,
                facts=income_facts,
            )
            if income_facts
            else None
        )
        balance = (
            BalanceSheet(
                company_id=base.company_id,
                period=balance_period,
                currency=base.currency,
                facts=balance_facts,
            )
            if balance_facts
            else None
        )
        cash = (
            CashFlowStatement(
                company_id=base.company_id,
                period=base.reporting_period,
                currency=base.currency,
                facts=cash_facts,
            )
            if cash_facts
            else None
        )
        package = CompanyFinancialPackage(
            company_id=base.company_id,
            reporting_period=base.reporting_period,
            currency=base.currency,
            retrieved_at=base.retrieved_at,
            income_statement=income,
            balance_sheet=balance,
            cash_flow_statement=cash,
            filing=base.filing,
            prior_period_package=base.prior_period_package,
            provider_name=base.provider_name,
            availability=base.availability,
            data_origin=base.data_origin,
            security_id=base.security_id,
            listing_id=base.listing_id,
            conflicts=conflicts,
        )
    except ValueError as exc:
        return FilingPipelineResult(
            stages_completed=tuple(stages),
            package=None,
            raw_facts=raw,
            conflicts=conflicts,
            metrics_result=None,
            detail=f"statement assembly failed: {exc}",
        )

    stages.append(FilingPipelineStage.DERIVED_METRICS)
    metrics_result = compute_financial_metrics_result(package)
    stages.append(FilingPipelineStage.PROVENANCE)
    return FilingPipelineResult(
        stages_completed=tuple(stages),
        package=package,
        raw_facts=raw,
        conflicts=conflicts,
        metrics_result=metrics_result,
        detail="filing pipeline completed",
    )
