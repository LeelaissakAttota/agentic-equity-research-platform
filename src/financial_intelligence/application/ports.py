"""Infrastructure-neutral ports owned by the application layer.

Concrete adapters are wired only in the composition root.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from financial_intelligence.domain.financial import CompanyFinancialPackage
from financial_intelligence.domain.identity import (
    CompanyId,
    CompanyIdentity,
    CountryCode,
    ExchangeCode,
    ListingIdentity,
    TickerSymbol,
)
from financial_intelligence.domain.market import MarketObservationSeries


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


@runtime_checkable
class CompanyCatalogPort(Protocol):
    """Application-owned catalog abstraction for company identity records.

    Implementations may be in-memory (Phase 2 foundation) or PostgreSQL later.
    """

    def get_by_id(self, company_id: CompanyId) -> CompanyIdentity | None:
        """Return a company by stable canonical id."""

    def find_by_ticker(
        self,
        ticker: TickerSymbol,
        *,
        exchange: ExchangeCode | None = None,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        """Find companies with a matching listing ticker (exchange/country optional)."""

    def find_by_alias(
        self,
        normalized_alias: str,
        *,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        """Find companies by normalized alias key."""

    def find_by_name(
        self,
        normalized_name: str,
        *,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        """Find companies by normalized legal/display name key."""

    def search_name_candidates(
        self,
        normalized_name: str,
        *,
        country: CountryCode | None = None,
        limit: int = 5,
    ) -> tuple[CompanyIdentity, ...]:
        """Return bounded deterministic fuzzy name candidates (never authoritative alone)."""


@runtime_checkable
class MarketDataPort(Protocol):
    """Application-owned market observation boundary.

    Concrete adapters (fixture / optional live HTTP) are selected in composition.
    Implementations must never invent successful OHLCV when upstream data is missing.
    """

    def get_ohlcv_series(
        self,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
    ) -> MarketObservationSeries | None:
        """Return normalized OHLCV for a listing, or None when unavailable."""


@runtime_checkable
class FinancialDataPort(Protocol):
    """Application-owned financial/filing data boundary.

    Concrete adapters (fixture / optional SEC companyfacts HTTP) are selected
    in composition. Implementations must never invent financial facts when
    upstream data is missing.
    """

    def get_financial_package(
        self,
        company_id: CompanyId,
        *,
        fiscal_year: int | None = None,
    ) -> CompanyFinancialPackage | None:
        """Return normalized financial package for a company, or None when unavailable."""
