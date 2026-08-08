"""Infrastructure-only concept mapping for provider tags → canonical concepts.

Domain/application code must never scatter US-GAAP / IFRS / vendor field names.

Unknown or ambiguous labels return None — never silently map to the wrong concept.
"""

from __future__ import annotations

from financial_intelligence.domain.financial import FinancialConcept

# Representative US-GAAP tags used by SEC company-facts style payloads.
US_GAAP_CONCEPT_MAP: dict[str, FinancialConcept] = {
    "Revenues": FinancialConcept.REVENUE,
    "RevenueFromContractWithCustomerExcludingAssessedTax": FinancialConcept.REVENUE,
    "SalesRevenueNet": FinancialConcept.REVENUE,
    "CostOfGoodsAndServicesSold": FinancialConcept.COST_OF_REVENUE,
    "GrossProfit": FinancialConcept.GROSS_PROFIT,
    "OperatingIncomeLoss": FinancialConcept.OPERATING_INCOME,
    "NetIncomeLoss": FinancialConcept.NET_INCOME,
    "EarningsPerShareBasic": FinancialConcept.EPS_BASIC,
    "EarningsPerShareDiluted": FinancialConcept.EPS_DILUTED,
    "CashAndCashEquivalentsAtCarryingValue": FinancialConcept.CASH,
    "Assets": FinancialConcept.TOTAL_ASSETS,
    "AssetsCurrent": FinancialConcept.CURRENT_ASSETS,
    "Liabilities": FinancialConcept.TOTAL_LIABILITIES,
    "LiabilitiesCurrent": FinancialConcept.CURRENT_LIABILITIES,
    "LongTermDebt": FinancialConcept.TOTAL_DEBT,
    "LongTermDebtNoncurrent": FinancialConcept.TOTAL_DEBT,
    "StockholdersEquity": FinancialConcept.SHAREHOLDERS_EQUITY,
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": (
        FinancialConcept.SHAREHOLDERS_EQUITY
    ),
    "NetCashProvidedByUsedInOperatingActivities": FinancialConcept.OPERATING_CASH_FLOW,
    "PaymentsToAcquirePropertyPlantAndEquipment": FinancialConcept.CAPITAL_EXPENDITURE,
    "CommonStockSharesOutstanding": FinancialConcept.SHARES_OUTSTANDING,
}

# Representative Indian results labels (fixture / future adapters).
INDIA_RESULTS_CONCEPT_MAP: dict[str, FinancialConcept] = {
    "Total Income from Operations": FinancialConcept.REVENUE,
    "Revenue from Operations": FinancialConcept.REVENUE,
    "Profit / (Loss) for the period": FinancialConcept.NET_INCOME,
    "Net Profit": FinancialConcept.NET_INCOME,
    "Equity Share Capital": FinancialConcept.SHAREHOLDERS_EQUITY,
    "Total Assets": FinancialConcept.TOTAL_ASSETS,
    "Total Equity": FinancialConcept.SHAREHOLDERS_EQUITY,
    "Cash and Cash Equivalents": FinancialConcept.CASH,
}

# Labels that look mappable but are intentionally ambiguous / unsafe.
_AMBIGUOUS_LABELS = frozenset(
    {
        "income",
        "profit",
        "revenue",
        "sales",
        "equity",
        "assets",
        "earnings",
        "total",
        "operations",
    }
)


def normalize_concept_label(label: str) -> str:
    """Collapse whitespace; preserve case for primary exact matching."""

    return " ".join(label.strip().split())


def _casefold_index(mapping: dict[str, FinancialConcept]) -> dict[str, FinancialConcept]:
    indexed: dict[str, FinancialConcept] = {}
    collisions: set[str] = set()
    for key, concept in mapping.items():
        folded = normalize_concept_label(key).casefold()
        if folded in indexed and indexed[folded] is not concept:
            collisions.add(folded)
        indexed[folded] = concept
    for key in collisions:
        indexed.pop(key, None)
    return indexed


_US_GAAP_CASEFOLD = _casefold_index(US_GAAP_CONCEPT_MAP)
_INDIA_CASEFOLD = _casefold_index(INDIA_RESULTS_CONCEPT_MAP)


def map_us_gaap(tag: str) -> FinancialConcept | None:
    """Map a US-GAAP tag. Unknown/ambiguous → None (no substring overmatching)."""

    cleaned = normalize_concept_label(tag)
    if not cleaned:
        return None
    if cleaned.casefold() in _AMBIGUOUS_LABELS:
        return None
    exact = US_GAAP_CONCEPT_MAP.get(cleaned)
    if exact is not None:
        return exact
    return _US_GAAP_CASEFOLD.get(cleaned.casefold())


def map_india_results_label(label: str) -> FinancialConcept | None:
    """Map an India results label. Prefer UNKNOWN over false certainty."""

    cleaned = normalize_concept_label(label)
    if not cleaned:
        return None
    if cleaned.casefold() in _AMBIGUOUS_LABELS:
        return None
    exact = INDIA_RESULTS_CONCEPT_MAP.get(cleaned)
    if exact is not None:
        return exact
    # Whitespace/case normalized exact match only — never fuzzy/substring.
    return _INDIA_CASEFOLD.get(cleaned.casefold())
