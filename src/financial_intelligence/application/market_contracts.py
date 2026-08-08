"""Application contracts for market snapshot use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.domain.identity import ListingIdentity
from financial_intelligence.domain.market import (
    FreshnessStatus,
    MarketMetric,
    MarketObservationSeries,
)
from financial_intelligence.domain.sources import SourceMetadata


class MarketSnapshotStatus(StrEnum):
    """Outcome of a market snapshot request."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class MarketSnapshotQuery:
    """Market snapshot request bound to company resolution inputs."""

    company_query: CompanyQuery
    listing_id: str | None = None
    sma_window: int = 3

    def __post_init__(self) -> None:
        if self.sma_window < 1 or self.sma_window > 60:
            msg = "sma_window must be between 1 and 60"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MarketSnapshotResult:
    """Traceable market snapshot with identity, observations, and metrics."""

    query: MarketSnapshotQuery
    status: MarketSnapshotStatus
    message: str
    resolution: ResolutionResult | None = None
    listing: ListingIdentity | None = None
    series: MarketObservationSeries | None = None
    metrics: tuple[MarketMetric, ...] = ()
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    source: SourceMetadata | None = None
    provider_name: str | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        blocked = {
            MarketSnapshotStatus.RESOLUTION_BLOCKED,
            MarketSnapshotStatus.INVALID,
        }
        if self.status in blocked and (self.series is not None or self.metrics):
            msg = f"{self.status.value} results must not attach market observations or metrics"
            raise ValueError(msg)
        if self.status is MarketSnapshotStatus.UNAVAILABLE and self.metrics:
            msg = "unavailable results must not include derived metrics"
            raise ValueError(msg)
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            msg = "evaluated_at must be timezone-aware"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
            "freshness": self.freshness.value,
            "provider_name": self.provider_name,
            "data_origin": (self.series.data_origin.value if self.series is not None else None),
            "metrics": [metric.to_dict() for metric in self.metrics],
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
                "listing_id": self.query.listing_id,
                "sma_window": self.query.sma_window,
            },
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
        if self.listing is not None:
            payload["listing"] = self.listing.to_dict()
        if self.series is not None:
            payload["series"] = self.series.to_dict()
        if self.source is not None:
            payload["source"] = self.source.to_dict()
        return payload


def resolution_blocks_market(status: ResolutionStatus) -> bool:
    """True when market data must not be attached to an unresolved company."""

    return status is not ResolutionStatus.RESOLVED
