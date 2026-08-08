"""Phase 5 news/event infrastructure adapters."""

from financial_intelligence.infrastructure.news.cache import CachingNewsEventAdapter
from financial_intelligence.infrastructure.news.in_memory import InMemoryNewsEventAdapter

__all__ = [
    "CachingNewsEventAdapter",
    "InMemoryNewsEventAdapter",
]
