"""GetMarketSnapshot use case — Phase 3 Market Intelligence vertical slice."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import ResolutionStatus
from financial_intelligence.application.market_contracts import (
    MarketSnapshotQuery,
    MarketSnapshotResult,
    MarketSnapshotStatus,
    resolution_blocks_market,
)
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.ports import MarketDataPort
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.identity import ListingId, ListingIdentity
from financial_intelligence.domain.market import (
    FreshnessStatus,
    MarketDataAvailability,
    MarketObservationSeries,
    compute_standard_metrics,
)
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceMetadata,
    SourceType,
)


class GetMarketSnapshot:
    """Resolve company identity safely, then load traceable market observations.

    Never attaches market data to AMBIGUOUS / NOT_FOUND / INVALID companies.
    Never fabricates OHLCV or metrics when the market adapter has no series.
    """

    def __init__(
        self,
        resolve_company: ResolveCompany,
        market_data: MarketDataPort,
        freshness_policy: MarketFreshnessPolicy,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._resolve_company = resolve_company
        self._market_data = market_data
        self._freshness_policy = freshness_policy
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, query: MarketSnapshotQuery) -> MarketSnapshotResult:
        evaluated_at = self._clock()
        if evaluated_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        resolution = self._resolve_company.execute(query.company_query)

        if resolution.status is ResolutionStatus.INVALID:
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.INVALID,
                message=resolution.message or "invalid company query",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        if resolution_blocks_market(resolution.status):
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.RESOLUTION_BLOCKED,
                message=("market data is withheld until company identity is uniquely resolved"),
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        assert resolution.company is not None
        try:
            listing = self._select_listing(resolution.candidates[0].matched_listings, query)
        except ValueError as exc:
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.INVALID,
                message=str(exc),
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if listing is None:
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.UNAVAILABLE,
                message="no listing matched the requested constraints",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        series = self._market_data.get_ohlcv_series(
            listing,
            company_id=resolution.company.company_id,
        )
        if series is None:
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.UNAVAILABLE,
                message="market observations are unavailable for the selected listing",
                resolution=resolution,
                listing=listing,
                freshness=FreshnessStatus.UNKNOWN,
                provider_name=None,
                evaluated_at=evaluated_at,
            )

        if not self._series_matches_listing(series, listing):
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.UNAVAILABLE,
                message=(
                    "market adapter returned observations that do not match the selected listing"
                ),
                resolution=resolution,
                listing=listing,
                freshness=FreshnessStatus.UNKNOWN,
                provider_name=series.provider_name,
                evaluated_at=evaluated_at,
            )
        if series.company_id != resolution.company.company_id:
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.UNAVAILABLE,
                message="market adapter returned observations for a different company",
                resolution=resolution,
                listing=listing,
                freshness=FreshnessStatus.UNKNOWN,
                provider_name=series.provider_name,
                evaluated_at=evaluated_at,
            )

        availability = series.availability
        if availability is MarketDataAvailability.UNAVAILABLE or not series.bars:
            return MarketSnapshotResult(
                query=query,
                status=MarketSnapshotStatus.UNAVAILABLE,
                message="market observations are unavailable for the selected listing",
                resolution=resolution,
                listing=listing,
                series=None,
                freshness=FreshnessStatus.UNKNOWN,
                provider_name=series.provider_name,
                evaluated_at=evaluated_at,
            )

        metrics = compute_standard_metrics(series.bars, sma_window=query.sma_window)
        freshness = self._freshness_policy.classify(series, now=evaluated_at)
        source = SourceMetadata(
            source_id=series.source_id,
            name=f"{series.provider_name} market observations",
            source_type=SourceType.MARKET_DATA,
            authority_tier=SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL,
            published_at=series.as_of,
            retrieved_at=series.retrieved_at,
            company_id=series.company_id,
            security_id=series.security_id,
            listing_id=series.listing_id,
            content_type="application/vnd.financial-intelligence.ohlcv+json",
        )

        if availability is MarketDataAvailability.PARTIAL:
            status = MarketSnapshotStatus.PARTIAL
            message = "market observations are partial"
        elif (
            availability is MarketDataAvailability.DEGRADED
            or freshness is FreshnessStatus.STALE
            or freshness is FreshnessStatus.UNKNOWN
        ):
            status = MarketSnapshotStatus.DEGRADED
            if availability is MarketDataAvailability.DEGRADED:
                message = "market observations returned in degraded mode"
            elif freshness is FreshnessStatus.STALE:
                message = "market observations are stale"
            else:
                message = "market observation freshness cannot be confirmed"
        else:
            status = MarketSnapshotStatus.OK
            message = "market snapshot computed"

        return MarketSnapshotResult(
            query=query,
            status=status,
            message=message,
            resolution=resolution,
            listing=listing,
            series=series,
            metrics=metrics,
            freshness=freshness,
            source=source,
            provider_name=series.provider_name,
            evaluated_at=evaluated_at,
        )

    @staticmethod
    def _series_matches_listing(
        series: MarketObservationSeries,
        listing: ListingIdentity,
    ) -> bool:
        return (
            series.listing_id == listing.listing_id
            and series.security_id == listing.security_id
            and series.exchange == listing.exchange
            and series.ticker == listing.ticker
            and series.currency == listing.currency
        )

    @staticmethod
    def _select_listing(
        matched_listings: tuple[ListingIdentity, ...],
        query: MarketSnapshotQuery,
    ) -> ListingIdentity | None:
        if not matched_listings:
            return None
        if query.listing_id:
            wanted = ListingId.from_string(query.listing_id)
            for listing in matched_listings:
                if listing.listing_id == wanted:
                    return listing
            return None
        # Prefer primary listing when present; otherwise first matched listing.
        for listing in matched_listings:
            if listing.is_primary:
                return listing
        return matched_listings[0]
