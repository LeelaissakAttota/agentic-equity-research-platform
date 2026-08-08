"""In-memory market-data adapter backed by the Phase 3 reference fixture."""

from __future__ import annotations

from financial_intelligence.domain.identity import CompanyId, ListingIdentity
from financial_intelligence.domain.market import DataOrigin, MarketObservationSeries
from financial_intelligence.infrastructure.market.reference_dataset import (
    build_reference_market_series,
)


class InMemoryMarketDataAdapter:
    """Fixture-backed MarketDataPort implementation (no network)."""

    def __init__(
        self,
        series_by_listing: dict[str, MarketObservationSeries] | None = None,
        *,
        provider_name: str = "fixture",
    ) -> None:
        data = (
            series_by_listing if series_by_listing is not None else build_reference_market_series()
        )
        # Shallow copy isolates the adapter from later mutations of the input map.
        self._series = dict(data)
        self.provider_name = provider_name

    def get_ohlcv_series(
        self,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
    ) -> MarketObservationSeries | None:
        series = self._series.get(listing.listing_id.as_text())
        if series is None:
            return None
        # Re-bind to requested identity fields when fixture matches listing id.
        if series.listing_id != listing.listing_id or series.company_id != company_id:
            return None
        if series.data_origin is not DataOrigin.FIXTURE:
            return series.with_data_origin(DataOrigin.FIXTURE)
        return series
