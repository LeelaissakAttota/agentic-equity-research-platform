"""Freshness classification policy for market observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from financial_intelligence.domain.market import FreshnessStatus, MarketObservationSeries


@dataclass(frozen=True, slots=True)
class MarketFreshnessPolicy:
    """Deterministic freshness policy keyed on observation as-of time."""

    stale_after: timedelta

    def __post_init__(self) -> None:
        if self.stale_after.total_seconds() <= 0:
            msg = "stale_after must be positive"
            raise ValueError(msg)

    def classify(
        self,
        series: MarketObservationSeries,
        *,
        now: datetime | None = None,
    ) -> FreshnessStatus:
        evaluated = now if now is not None else datetime.now(UTC)
        if evaluated.tzinfo is None:
            msg = "now must be timezone-aware"
            raise ValueError(msg)
        age = evaluated - series.as_of
        if age < timedelta(0):
            # Future as_of is treated as unknown rather than inventing freshness.
            return FreshnessStatus.UNKNOWN
        if age <= self.stale_after:
            return FreshnessStatus.FRESH
        return FreshnessStatus.STALE
