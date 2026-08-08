"""Phase 4 financial & filing intelligence domain package."""

from financial_intelligence.domain.financial.calculations import (
    CALCULATION_LIBRARY_VERSION,
    FinancialMetric,
    FinancialMetricName,
    FinancialMetricsResult,
    OmittedMetric,
    compute_financial_metrics_result,
    compute_standard_financial_metrics,
    free_cash_flow,
)
from financial_intelligence.domain.financial.concepts import FinancialConcept
from financial_intelligence.domain.financial.conflicts import (
    ConflictResolutionRule,
    FinancialFactConflict,
    detect_fact_conflicts,
    resolve_fact_conflict,
)
from financial_intelligence.domain.financial.facts import FinancialFact, build_fact
from financial_intelligence.domain.financial.filings import (
    FilingFormType,
    FilingId,
    FilingMetadata,
)
from financial_intelligence.domain.financial.missing import MissingDataSemantics
from financial_intelligence.domain.financial.periods import (
    PeriodBasis,
    PeriodIncomparabilityReason,
    ReportingPeriod,
)
from financial_intelligence.domain.financial.statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancialPackage,
    FinancialDataAvailability,
    IncomeStatement,
)
from financial_intelligence.domain.financial.units import FinancialScale, FinancialUnit

__all__ = [
    "CALCULATION_LIBRARY_VERSION",
    "BalanceSheet",
    "CashFlowStatement",
    "CompanyFinancialPackage",
    "ConflictResolutionRule",
    "FilingFormType",
    "FilingId",
    "FilingMetadata",
    "FinancialConcept",
    "FinancialDataAvailability",
    "FinancialFact",
    "FinancialFactConflict",
    "FinancialMetric",
    "FinancialMetricName",
    "FinancialMetricsResult",
    "FinancialScale",
    "FinancialUnit",
    "IncomeStatement",
    "MissingDataSemantics",
    "OmittedMetric",
    "PeriodBasis",
    "PeriodIncomparabilityReason",
    "ReportingPeriod",
    "build_fact",
    "compute_financial_metrics_result",
    "compute_standard_financial_metrics",
    "detect_fact_conflicts",
    "free_cash_flow",
    "resolve_fact_conflict",
]
