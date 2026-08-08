"""Canonical financial concept identifiers (provider-neutral).

Provider-specific tags (US-GAAP, IFRS, vendor fields) map in infrastructure.
"""

from __future__ import annotations

from enum import StrEnum


class FinancialConcept(StrEnum):
    """Internal concept vocabulary for statement facts."""

    REVENUE = "revenue"
    COST_OF_REVENUE = "cost_of_revenue"
    GROSS_PROFIT = "gross_profit"
    OPERATING_INCOME = "operating_income"
    EBIT = "ebit"
    EBITDA = "ebitda"
    NET_INCOME = "net_income"
    EPS_BASIC = "eps_basic"
    EPS_DILUTED = "eps_diluted"
    CASH = "cash"
    TOTAL_ASSETS = "total_assets"
    CURRENT_ASSETS = "current_assets"
    TOTAL_LIABILITIES = "total_liabilities"
    CURRENT_LIABILITIES = "current_liabilities"
    TOTAL_DEBT = "total_debt"
    SHAREHOLDERS_EQUITY = "shareholders_equity"
    OPERATING_CASH_FLOW = "operating_cash_flow"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    FREE_CASH_FLOW = "free_cash_flow"
    SHARES_OUTSTANDING = "shares_outstanding"
