"""Infrastructure-neutral ports owned by the application layer.

Concrete adapters are wired only in the composition root. Phase 1 does not
provide working database or cache adapters.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PersistencePort(Protocol):
    """Future durable persistence boundary (PostgreSQL in later phases)."""

    def ping(self) -> bool:
        """Return True when the persistence dependency can accept work."""


@runtime_checkable
class CachePort(Protocol):
    """Future cache/coordination boundary (Redis in later phases)."""

    def ping(self) -> bool:
        """Return True when the cache dependency can accept work."""
