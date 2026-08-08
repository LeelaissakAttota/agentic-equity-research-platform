"""Provider-fallback market adapter (primary then secondary; never fabricates)."""

from __future__ import annotations

from financial_intelligence.application.ports import MarketDataPort
from financial_intelligence.domain.identity import CompanyId, ListingIdentity
from financial_intelligence.domain.market import (
    MarketDataAvailability,
    MarketObservationSeries,
)
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.infrastructure.market.fallback")


class FallbackMarketDataAdapter:
    """Try primary adapter, then secondary, without inventing OHLCV bars.

    Successful primary data is never overridden. Provenance remains whatever
    series is returned (secondary keeps its own provider_name / data_origin).
    """

    def __init__(self, primary: MarketDataPort, secondary: MarketDataPort) -> None:
        self._primary = primary
        self._secondary = secondary

    def get_ohlcv_series(
        self,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
    ) -> MarketObservationSeries | None:
        primary = self._safe_get(self._primary, listing, company_id=company_id, role="primary")
        if self._usable(primary):
            return primary
        secondary = self._safe_get(
            self._secondary,
            listing,
            company_id=company_id,
            role="secondary",
        )
        if self._usable(secondary):
            return secondary
        return primary if primary is not None else secondary

    def _safe_get(
        self,
        adapter: MarketDataPort,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
        role: str,
    ) -> MarketObservationSeries | None:
        try:
            return adapter.get_ohlcv_series(listing, company_id=company_id)
        except Exception as exc:
            logger.warning(
                "market_adapter_failure",
                extra={
                    "provider_role": role,
                    "listing_id": listing.listing_id.as_text(),
                    "error_type": type(exc).__name__,
                },
            )
            return None

    @staticmethod
    def _usable(series: MarketObservationSeries | None) -> bool:
        if series is None:
            return False
        if series.availability is MarketDataAvailability.UNAVAILABLE:
            return False
        return bool(series.bars)
