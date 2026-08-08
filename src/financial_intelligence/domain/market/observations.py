"""Normalized market observations for Phase 3 Market Intelligence.

Prices and volumes use Decimal. Timestamps are timezone-aware. Observations
always retain company/security/listing identity and source provenance.

``adjustment_factor`` is a per-bar multiplier applied as
``adjusted_close = close * adjustment_factor``. This is corporate-action
*awareness*, not a full split/dividend adjustment engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import (
    CompanyId,
    CurrencyCode,
    ExchangeCode,
    ListingId,
    SecurityId,
    TickerSymbol,
)
from financial_intelligence.domain.sources import SourceId


class FreshnessStatus(StrEnum):
    """Deterministic freshness classification for market figures."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class MarketDataAvailability(StrEnum):
    """Provider/adapter availability without fabricating success."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"


def _require_finite_non_negative(label: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        msg = f"{label} must be Decimal"
        raise TypeError(msg)
    if value.is_nan() or value.is_infinite():
        msg = f"{label} must be a finite Decimal"
        raise ValueError(msg)
    if value < 0:
        msg = f"{label} must be non-negative"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class OhlcvBar:
    """One OHLCV market bar for a listing.

    ``volume`` is expressed in share units and must be a non-negative integer
    Decimal (provider semantics for what a share unit means remain provider-
    defined; fractional share volumes are rejected at this boundary).
    """

    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    currency: CurrencyCode
    adjustment_factor: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for label, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            _require_finite_non_negative(label, value)
        _require_finite_non_negative("adjustment_factor", self.adjustment_factor)
        if self.volume != self.volume.to_integral_value():
            msg = "volume must be an integer number of shares"
            raise ValueError(msg)
        if self.high < self.low:
            msg = "high must be >= low"
            raise ValueError(msg)
        if self.high < self.open or self.high < self.close:
            msg = "high must cover open/close"
            raise ValueError(msg)
        if self.low > self.open or self.low > self.close:
            msg = "low must cover open/close"
            raise ValueError(msg)
        if self.adjustment_factor <= 0:
            msg = "adjustment_factor must be positive"
            raise ValueError(msg)

    @property
    def adjusted_close(self) -> Decimal:
        """Close adjusted by optional corporate-action factor."""

        return self.close * self.adjustment_factor

    def to_dict(self) -> dict[str, object]:
        return {
            "session_date": self.session_date.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "adjusted_close": str(self.adjusted_close),
            "volume": str(self.volume),
            "currency": self.currency.as_text(),
            "adjustment_factor": str(self.adjustment_factor),
        }


@dataclass(frozen=True, slots=True)
class MarketObservationSeries:
    """Traceable OHLCV series bound to canonical listing identity."""

    company_id: CompanyId
    security_id: SecurityId
    listing_id: ListingId
    exchange: ExchangeCode
    ticker: TickerSymbol
    currency: CurrencyCode
    as_of: datetime
    retrieved_at: datetime
    source_id: SourceId
    bars: tuple[OhlcvBar, ...]
    provider_name: str = "fixture"
    availability: MarketDataAvailability = MarketDataAvailability.AVAILABLE
    data_origin: DataOrigin = DataOrigin.FIXTURE

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.retrieved_at.tzinfo is None:
            msg = "market observation timestamps must be timezone-aware"
            raise ValueError(msg)
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        if self.availability is MarketDataAvailability.AVAILABLE and not self.bars:
            msg = "AVAILABLE series must include at least one bar"
            raise ValueError(msg)
        if self.data_origin is DataOrigin.UNAVAILABLE and self.bars:
            msg = "UNAVAILABLE origin must not include bars"
            raise ValueError(msg)
        dates = [bar.session_date for bar in self.bars]
        if dates != sorted(dates):
            msg = "bars must be ordered by ascending session_date"
            raise ValueError(msg)
        if len(dates) != len(set(dates)):
            msg = "duplicate session_date in bars"
            raise ValueError(msg)
        for bar in self.bars:
            if bar.currency != self.currency:
                msg = "bar currency must match series currency"
                raise ValueError(msg)

    def with_data_origin(self, origin: DataOrigin) -> MarketObservationSeries:
        """Return a copy with an updated data-origin label."""

        return MarketObservationSeries(
            company_id=self.company_id,
            security_id=self.security_id,
            listing_id=self.listing_id,
            exchange=self.exchange,
            ticker=self.ticker,
            currency=self.currency,
            as_of=self.as_of,
            retrieved_at=self.retrieved_at,
            source_id=self.source_id,
            bars=self.bars,
            provider_name=self.provider_name,
            availability=self.availability,
            data_origin=origin,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "security_id": self.security_id.as_text(),
            "listing_id": self.listing_id.as_text(),
            "exchange": self.exchange.as_text(),
            "ticker": self.ticker.as_text(),
            "currency": self.currency.as_text(),
            "as_of": self.as_of.isoformat().replace("+00:00", "Z"),
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "source_id": self.source_id.as_text(),
            "provider_name": self.provider_name,
            "availability": self.availability.value,
            "data_origin": self.data_origin.value,
            "bars": [bar.to_dict() for bar in self.bars],
        }
