"""Bounded in-process market observation cache (no Redis)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock

from financial_intelligence.application.ports import MarketDataPort
from financial_intelligence.domain.identity import CompanyId, ListingIdentity
from financial_intelligence.domain.market import DataOrigin, MarketObservationSeries


@dataclass(slots=True)
class _CacheEntry:
    series: MarketObservationSeries
    expires_at: datetime


class CachingMarketDataAdapter:
    """TTL cache wrapper keyed by listing_id (+ company_id) isolation.

    Cache age is independent of market-observation freshness. Live hits are
    labeled ``cached_live``; fixture hits remain ``fixture``.
    """

    def __init__(
        self,
        inner: MarketDataPort,
        *,
        ttl: timedelta,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl.total_seconds() <= 0:
            msg = "cache ttl must be positive"
            raise ValueError(msg)
        self._inner = inner
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(UTC))
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = RLock()

    def get_ohlcv_series(
        self,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
    ) -> MarketObservationSeries | None:
        key = f"{company_id.as_text()}:{listing.listing_id.as_text()}"
        now = self._clock()
        if now.tzinfo is None:
            msg = "cache clock must return timezone-aware datetime"
            raise ValueError(msg)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None and cached.expires_at > now:
                return self._label_cached(cached.series)
        series = self._inner.get_ohlcv_series(listing, company_id=company_id)
        with self._lock:
            cached = self._entries.get(key)
            now = self._clock()
            if cached is not None and cached.expires_at > now:
                return self._label_cached(cached.series)
            if series is not None:
                self._entries[key] = _CacheEntry(series=series, expires_at=now + self._ttl)
            else:
                self._entries.pop(key, None)
            return series

    @staticmethod
    def _label_cached(series: MarketObservationSeries) -> MarketObservationSeries:
        if series.data_origin is DataOrigin.LIVE:
            return series.with_data_origin(DataOrigin.CACHED_LIVE)
        return series

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
