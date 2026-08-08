"""In-memory watchlist store."""

from __future__ import annotations

from threading import RLock

from financial_intelligence.domain.watchlist import Watchlist, WatchlistId


class WatchlistStoreError(ValueError):
    """Watchlist store conflict."""


class InMemoryWatchlistStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, Watchlist] = {}

    def save(self, watchlist: Watchlist) -> None:
        key = watchlist.watchlist_id.as_text()
        with self._lock:
            self._items[key] = watchlist

    def get(self, watchlist_id: WatchlistId) -> Watchlist | None:
        with self._lock:
            return self._items.get(watchlist_id.as_text())

    def list_all(self, *, limit: int = 50, offset: int = 0) -> tuple[Watchlist, ...]:
        if limit < 1 or limit > 200:
            msg = "limit must be between 1 and 200"
            raise WatchlistStoreError(msg)
        if offset < 0:
            msg = "offset must be non-negative"
            raise WatchlistStoreError(msg)
        with self._lock:
            items = list(self._items.values())
        items.sort(key=lambda w: (w.created_at.isoformat(), w.watchlist_id.as_text()))
        return tuple(items[offset : offset + limit])
