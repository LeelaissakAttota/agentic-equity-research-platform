"""Market-data infrastructure adapters for Phase 3."""

from financial_intelligence.infrastructure.market.cache import CachingMarketDataAdapter
from financial_intelligence.infrastructure.market.fallback import FallbackMarketDataAdapter
from financial_intelligence.infrastructure.market.in_memory import InMemoryMarketDataAdapter
from financial_intelligence.infrastructure.market.reference_dataset import (
    build_reference_market_series,
)
from financial_intelligence.infrastructure.market.yahoo_chart import YahooChartMarketDataAdapter

__all__ = [
    "CachingMarketDataAdapter",
    "FallbackMarketDataAdapter",
    "InMemoryMarketDataAdapter",
    "YahooChartMarketDataAdapter",
    "build_reference_market_series",
]
