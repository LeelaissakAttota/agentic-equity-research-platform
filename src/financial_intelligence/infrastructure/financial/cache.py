"""Bounded in-process financial package cache (no Redis)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock

from financial_intelligence.application.ports import FinancialDataPort
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import CompanyFinancialPackage
from financial_intelligence.domain.identity import CompanyId


@dataclass(slots=True)
class _CacheEntry:
    package: CompanyFinancialPackage
    expires_at: datetime


class CachingFinancialDataAdapter:
    """TTL cache keyed by company_id and optional fiscal_year."""

    def __init__(
        self,
        inner: FinancialDataPort,
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

    def get_financial_package(
        self,
        company_id: CompanyId,
        *,
        fiscal_year: int | None = None,
    ) -> CompanyFinancialPackage | None:
        key = f"{company_id.as_text()}:{fiscal_year or 'latest'}"
        now = self._clock()
        if now.tzinfo is None:
            msg = "cache clock must return timezone-aware datetime"
            raise ValueError(msg)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None and cached.expires_at > now:
                return self._label_cached(cached.package)
        package = self._inner.get_financial_package(company_id, fiscal_year=fiscal_year)
        with self._lock:
            now = self._clock()
            cached = self._entries.get(key)
            if cached is not None and cached.expires_at > now:
                return self._label_cached(cached.package)
            if package is not None:
                self._entries[key] = _CacheEntry(package=package, expires_at=now + self._ttl)
            else:
                self._entries.pop(key, None)
            return package

    @staticmethod
    def _label_cached(package: CompanyFinancialPackage) -> CompanyFinancialPackage:
        if package.data_origin is DataOrigin.LIVE:
            return package.with_data_origin(DataOrigin.CACHED_LIVE)
        return package

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
