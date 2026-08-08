"""Watchlist domain foundation — configuration only (no schedulers)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from financial_intelligence.domain.identity import CompanyId, ExchangeCode


class WatchlistId:
    """Opaque watchlist identity (UUIDv4)."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        if value.version != 4:
            msg = "watchlist_id must be a UUIDv4"
            raise ValueError(msg)
        self._value = value

    @classmethod
    def new(cls) -> WatchlistId:
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> WatchlistId:
        return cls(UUID(raw))

    def as_text(self) -> str:
        return str(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, WatchlistId) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class MonitoringCapability(StrEnum):
    MARKET = "market"
    FINANCIAL = "financial"
    NEWS = "news"
    REGULATORY = "regulatory"


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Bounded monitoring configuration — DATA only; no automatic polling."""

    capabilities: tuple[MonitoringCapability, ...]
    interval_hours: int = 24
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.capabilities:
            msg = "monitoring policy requires at least one capability"
            raise ValueError(msg)
        if len(self.capabilities) != len(set(self.capabilities)):
            msg = "monitoring capabilities must be unique"
            raise ValueError(msg)
        if self.interval_hours < 1 or self.interval_hours > 24 * 30:
            msg = "interval_hours out of bounds"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "capabilities": [c.value for c in self.capabilities],
            "interval_hours": self.interval_hours,
            "enabled": self.enabled,
            "kind": "monitoring_policy",
        }


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    """Watchlist membership referencing canonical CompanyId."""

    company_id: CompanyId
    raw_query: str
    exchange: ExchangeCode | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        query = " ".join(self.raw_query.strip().split())
        if not query or len(query) > 200:
            msg = "watchlist entry raw_query empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "raw_query", query)
        if self.note is not None:
            note = " ".join(self.note.strip().split())
            if len(note) > 256:
                msg = "watchlist entry note exceeds bounds"
                raise ValueError(msg)
            if any(ord(ch) < 32 for ch in note):
                msg = "watchlist entry note must not contain control characters"
                raise ValueError(msg)
            object.__setattr__(self, "note", note or None)

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "raw_query": self.raw_query,
            "exchange": self.exchange.as_text() if self.exchange else None,
            "note": self.note,
            "kind": "watchlist_entry",
        }


@dataclass(frozen=True, slots=True)
class Watchlist:
    """Named set of companies with optional monitoring policy."""

    watchlist_id: WatchlistId
    name: str
    created_at: datetime
    updated_at: datetime
    entries: tuple[WatchlistEntry, ...] = ()
    policy: MonitoringPolicy | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            msg = "watchlist timestamps must be timezone-aware"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in self.name):
            msg = "watchlist name must not contain control characters"
            raise ValueError(msg)
        name = " ".join(self.name.strip().split())
        if not name or len(name) > 128:
            msg = "watchlist name empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "name", name)
        ids = [e.company_id.as_text() for e in self.entries]
        if len(ids) != len(set(ids)):
            msg = "duplicate company on watchlist"
            raise ValueError(msg)

    def with_entries(self, entries: tuple[WatchlistEntry, ...], *, at: datetime) -> Watchlist:
        return Watchlist(
            watchlist_id=self.watchlist_id,
            name=self.name,
            created_at=self.created_at,
            updated_at=at,
            entries=entries,
            policy=self.policy,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "watchlist_id": self.watchlist_id.as_text(),
            "name": self.name,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z"),
            "entries": [e.to_dict() for e in self.entries],
            "policy": self.policy.to_dict() if self.policy else None,
            "entry_count": len(self.entries),
            "kind": "watchlist",
        }
