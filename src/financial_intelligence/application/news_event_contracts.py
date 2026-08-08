"""Application contracts for news/event snapshot use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.domain.news import CompanyEventPackage, EventType


class NewsEventSnapshotStatus(StrEnum):
    """Outcome of a news/event snapshot request."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class NewsEventSnapshotQuery:
    """News/event snapshot request bound to company resolution inputs."""

    company_query: CompanyQuery
    event_type: EventType | None = None
    limit: int = 20

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 100:
            msg = "limit must be between 1 and 100"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class NewsEventSnapshotResult:
    """Traceable news/event snapshot with provenance."""

    query: NewsEventSnapshotQuery
    status: NewsEventSnapshotStatus
    message: str
    resolution: ResolutionResult | None = None
    package: CompanyEventPackage | None = None
    provider_name: str | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        blocked = {
            NewsEventSnapshotStatus.RESOLUTION_BLOCKED,
            NewsEventSnapshotStatus.INVALID,
        }
        if self.status in blocked and self.package is not None:
            msg = f"{self.status.value} results must not attach event data"
            raise ValueError(msg)
        if self.status is NewsEventSnapshotStatus.UNAVAILABLE and self.package is not None:
            msg = "unavailable results must not include an event package"
            raise ValueError(msg)
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            msg = "evaluated_at must be timezone-aware"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
            "provider_name": self.provider_name,
            "data_origin": (self.package.data_origin.value if self.package is not None else None),
            "query": {
                "raw_query": self.query.company_query.raw_query,
                "country": (
                    self.query.company_query.country.as_text()
                    if self.query.company_query.country
                    else None
                ),
                "exchange": (
                    self.query.company_query.exchange.as_text()
                    if self.query.company_query.exchange
                    else None
                ),
                "ticker": (
                    self.query.company_query.ticker.as_text()
                    if self.query.company_query.ticker
                    else None
                ),
                "event_type": self.query.event_type.value if self.query.event_type else None,
                "limit": self.query.limit,
            },
            "events": (
                [event.to_dict() for event in self.package.events]
                if self.package is not None
                else []
            ),
            "conflicts": (
                [conflict.to_dict() for conflict in self.package.conflicts]
                if self.package is not None
                else []
            ),
        }
        if self.evaluated_at is not None:
            payload["evaluated_at"] = self.evaluated_at.isoformat().replace("+00:00", "Z")
        if self.resolution is not None:
            payload["resolution"] = {
                "status": self.resolution.status.value,
                "matched_by": self.resolution.matched_by.value,
                "confidence": self.resolution.confidence.value,
                "message": self.resolution.message,
                "company_id": (
                    self.resolution.company.company_id.as_text()
                    if self.resolution.company is not None
                    else None
                ),
            }
        if self.package is not None:
            payload["package"] = self.package.to_dict()
        return payload


def resolution_blocks_news_events(status: ResolutionStatus) -> bool:
    """True when news/event data must not be attached to an unresolved company."""

    return status is not ResolutionStatus.RESOLVED
