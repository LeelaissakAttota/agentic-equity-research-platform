"""Phase 6 orchestration domain — research objectives."""

from __future__ import annotations

from enum import StrEnum


class ResearchObjective(StrEnum):
    """Explicit research objectives (deterministic planner input)."""

    COMPANY_OVERVIEW = "company_overview"
    MARKET_ANALYSIS = "market_analysis"
    FINANCIAL_ANALYSIS = "financial_analysis"
    NEWS_AND_EVENTS = "news_and_events"
    INDUSTRY_ANALYSIS = "industry_analysis"
    REGULATORY_ANALYSIS = "regulatory_analysis"
    COMPREHENSIVE_EQUITY_RESEARCH = "comprehensive_equity_research"
