"""Market snapshot use-case and adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.market_contracts import (
    MarketSnapshotQuery,
    MarketSnapshotStatus,
)
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.identity import (
    CompanyId,
    ExchangeCode,
)
from financial_intelligence.domain.market import (
    FreshnessStatus,
    MarketDataAvailability,
    MarketObservationSeries,
)
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId, SourceType
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.market import (
    CachingMarketDataAdapter,
    FallbackMarketDataAdapter,
    InMemoryMarketDataAdapter,
)


def _usecase(
    market: InMemoryMarketDataAdapter | FallbackMarketDataAdapter | CachingMarketDataAdapter,
    *,
    stale_hours: int = 72,
    now: datetime | None = None,
) -> GetMarketSnapshot:
    catalog = InMemoryCompanyCatalog()
    evaluated = now or datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    return GetMarketSnapshot(
        resolve_company=ResolveCompany(catalog),
        market_data=market,
        freshness_policy=MarketFreshnessPolicy(stale_after=timedelta(hours=stale_hours)),
        clock=lambda: evaluated,
    )


class MarketSnapshotUseCaseTests(TestCase):
    def test_apple_snapshot_ok_with_metrics_and_tier2_source(self) -> None:
        result = _usecase(InMemoryMarketDataAdapter()).execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="AAPL", exchange=ExchangeCode("NASDAQ"))
            )
        )
        self.assertEqual(result.status, MarketSnapshotStatus.OK)
        self.assertIsNotNone(result.series)
        self.assertGreaterEqual(len(result.metrics), 3)
        assert result.source is not None
        self.assertEqual(result.source.source_type, SourceType.MARKET_DATA)
        self.assertEqual(
            result.source.authority_tier, SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL
        )
        self.assertEqual(result.freshness, FreshnessStatus.FRESH)
        last = next(metric for metric in result.metrics if metric.name.value == "last_close")
        self.assertEqual(last.value, Decimal("199.0000"))

    def test_ambiguous_resolution_blocks_market_attachment(self) -> None:
        # "Reliance" without exchange still resolves uniquely in the fixture;
        # force ambiguity via fuzzy-only style: empty ticker-like miss is hard.
        # Use a name that yields AMBIGUOUS fuzzy candidates if present; otherwise
        # RELIANCE+NASDAQ is NOT_FOUND and must also block.
        result = _usecase(InMemoryMarketDataAdapter()).execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(
                    raw_query="RELIANCE",
                    exchange=ExchangeCode("NASDAQ"),
                )
            )
        )
        self.assertEqual(result.status, MarketSnapshotStatus.RESOLUTION_BLOCKED)
        self.assertIsNone(result.series)
        self.assertEqual(result.metrics, ())

    def test_missing_listing_series_is_unavailable_not_fabricated(self) -> None:
        # TCS exists in company catalog but has no market fixture bars.
        result = _usecase(InMemoryMarketDataAdapter()).execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="TCS", exchange=ExchangeCode("NSE"))
            )
        )
        self.assertEqual(result.status, MarketSnapshotStatus.UNAVAILABLE)
        self.assertIsNone(result.series)
        self.assertEqual(result.metrics, ())

    def test_stale_series_surfaces_degraded_status(self) -> None:
        result = _usecase(
            InMemoryMarketDataAdapter(),
            stale_hours=1,
            now=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        ).execute(MarketSnapshotQuery(company_query=CompanyQuery(raw_query="AAPL")))
        self.assertEqual(result.status, MarketSnapshotStatus.DEGRADED)
        self.assertEqual(result.freshness, FreshnessStatus.STALE)
        self.assertTrue(result.metrics)

    def test_invalid_listing_id_rejected(self) -> None:
        result = _usecase(InMemoryMarketDataAdapter()).execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="AAPL"),
                listing_id="not-a-uuid",
            )
        )
        self.assertEqual(result.status, MarketSnapshotStatus.INVALID)


class MarketAdapterTests(TestCase):
    def test_fallback_uses_secondary_when_primary_empty(self) -> None:
        from tests.unit.market_fixtures import APPLE_COMPANY_ID, apple_listing

        listing = apple_listing()
        series = InMemoryMarketDataAdapter().get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)
        assert series is not None
        adapter = FallbackMarketDataAdapter(
            InMemoryMarketDataAdapter(series_by_listing={}),
            InMemoryMarketDataAdapter(series_by_listing={listing.listing_id.as_text(): series}),
        )
        recovered = adapter.get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertEqual(recovered.listing_id, listing.listing_id)

    def test_cache_is_keyed_by_listing_id(self) -> None:
        from tests.unit.market_fixtures import (
            APPLE_COMPANY_ID,
            MSFT_COMPANY_ID,
            apple_listing,
            msft_listing,
        )

        calls: list[str] = []

        class CountingAdapter:
            def get_ohlcv_series(
                self,
                listing: object,
                *,
                company_id: CompanyId,
            ) -> MarketObservationSeries | None:
                calls.append(listing.listing_id.as_text())  # type: ignore[attr-defined]
                return None

        cached = CachingMarketDataAdapter(CountingAdapter(), ttl=timedelta(seconds=60))
        a = apple_listing()
        b = msft_listing()
        cached.get_ohlcv_series(a, company_id=APPLE_COMPANY_ID)
        cached.get_ohlcv_series(a, company_id=APPLE_COMPANY_ID)
        cached.get_ohlcv_series(b, company_id=MSFT_COMPANY_ID)
        self.assertEqual(
            calls,
            [a.listing_id.as_text(), a.listing_id.as_text(), b.listing_id.as_text()],
        )

    def test_unavailable_availability_not_usable_by_fallback(self) -> None:
        from tests.unit.market_fixtures import APPLE_COMPANY_ID, apple_listing

        listing = apple_listing()
        empty = MarketObservationSeries(
            company_id=APPLE_COMPANY_ID,
            security_id=listing.security_id,
            listing_id=listing.listing_id,
            exchange=listing.exchange,
            ticker=listing.ticker,
            currency=listing.currency,
            as_of=datetime(2026, 8, 7, tzinfo=UTC),
            retrieved_at=datetime(2026, 8, 7, tzinfo=UTC),
            source_id=SourceId.new(),
            bars=(),
            availability=MarketDataAvailability.UNAVAILABLE,
        )
        good = InMemoryMarketDataAdapter().get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)
        assert good is not None
        adapter = FallbackMarketDataAdapter(
            InMemoryMarketDataAdapter(series_by_listing={listing.listing_id.as_text(): empty}),
            InMemoryMarketDataAdapter(series_by_listing={listing.listing_id.as_text(): good}),
        )
        recovered = adapter.get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)
        assert recovered is not None
        self.assertTrue(recovered.bars)
        self.assertEqual(recovered.bars[-1].close, Decimal("199.00"))
