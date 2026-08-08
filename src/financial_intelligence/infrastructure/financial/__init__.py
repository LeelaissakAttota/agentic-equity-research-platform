"""Phase 4 financial infrastructure adapters."""

from financial_intelligence.infrastructure.financial.cache import CachingFinancialDataAdapter
from financial_intelligence.infrastructure.financial.fallback import FallbackFinancialDataAdapter
from financial_intelligence.infrastructure.financial.in_memory import InMemoryFinancialDataAdapter
from financial_intelligence.infrastructure.financial.india_filings import (
    INDIA_AUTHORITY_PRECEDENCE,
    IndiaFilingAuthority,
    parse_india_results_fixture,
)
from financial_intelligence.infrastructure.financial.sec_company_facts import (
    SecCompanyFactsFinancialDataAdapter,
)

__all__ = [
    "INDIA_AUTHORITY_PRECEDENCE",
    "CachingFinancialDataAdapter",
    "FallbackFinancialDataAdapter",
    "InMemoryFinancialDataAdapter",
    "IndiaFilingAuthority",
    "SecCompanyFactsFinancialDataAdapter",
    "parse_india_results_fixture",
]
