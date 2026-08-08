"""Phase 3 Prompt 2 adversarial hardening tests for market intelligence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from unittest import TestCase
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from pydantic import ValidationError

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.market_contracts import (
    MarketSnapshotQuery,
    MarketSnapshotResult,
    MarketSnapshotStatus,
)
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import (
    CompanyId,
    CurrencyCode,
    ExchangeCode,
    ListingId,
    SecurityId,
    TickerSymbol,
)
from financial_intelligence.domain.market import (
    FreshnessStatus,
    MarketDataAvailability,
    MarketObservationSeries,
    OhlcvBar,
    adjusted_last_close,
    exchange_timezone,
    is_weekday_calendar_day,
    last_close,
    simple_moving_average,
    simple_return,
    volume_sum,
)
from financial_intelligence.domain.sources import SourceId
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.market import (
    CachingMarketDataAdapter,
    FallbackMarketDataAdapter,
    InMemoryMarketDataAdapter,
)


def _bar(
    day: date,
    *,
    close: str,
    volume: str = "10",
    currency: str = "USD",
    factor: str = "1",
    open_: str | None = None,
) -> OhlcvBar:
    close_d = Decimal(close)
    open_d = Decimal(open_) if open_ is not None else close_d
    return OhlcvBar(
        session_date=day,
        open=open_d,
        high=max(open_d, close_d),
        low=min(open_d, close_d),
        close=close_d,
        volume=Decimal(volume),
        currency=CurrencyCode(currency),
        adjustment_factor=Decimal(factor),
    )


def _series(
    bars: tuple[OhlcvBar, ...],
    *,
    listing_id: str = "42222222-2222-4222-8222-222222222001",
    company_id: str = "22222222-2222-4222-8222-222222222001",
    security_id: str = "32222222-2222-4222-8222-222222222001",
    exchange: str = "NASDAQ",
    ticker: str = "AAPL",
    currency: str = "USD",
    as_of: datetime | None = None,
    availability: MarketDataAvailability = MarketDataAvailability.AVAILABLE,
    provider_name: str = "fixture",
) -> MarketObservationSeries:
    stamp = as_of or datetime(2026, 8, 7, 20, 0, tzinfo=UTC)
    return MarketObservationSeries(
        company_id=CompanyId.from_string(company_id),
        security_id=SecurityId.from_string(security_id),
        listing_id=ListingId.from_string(listing_id),
        exchange=ExchangeCode(exchange),
        ticker=TickerSymbol(ticker),
        currency=CurrencyCode(currency),
        as_of=stamp,
        retrieved_at=stamp + timedelta(minutes=5),
        source_id=SourceId.new(),
        bars=bars,
        provider_name=provider_name,
        availability=availability,
    )


def _usecase(
    market: object,
    *,
    stale_hours: int = 72,
    now: datetime | None = None,
) -> GetMarketSnapshot:
    evaluated = now or datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    return GetMarketSnapshot(
        resolve_company=ResolveCompany(InMemoryCompanyCatalog()),
        market_data=market,  # type: ignore[arg-type]
        freshness_policy=MarketFreshnessPolicy(stale_after=timedelta(hours=stale_hours)),
        clock=lambda: evaluated,
    )


class OhlcvInvariantTests(TestCase):
    def test_rejects_negative_and_inconsistent_ohlc(self) -> None:
        currency = CurrencyCode("USD")
        with self.assertRaises(ValueError):
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("-1"),
                high=Decimal("1"),
                low=Decimal("0"),
                close=Decimal("1"),
                volume=Decimal("1"),
                currency=currency,
            )
        with self.assertRaises(ValueError):
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("10"),
                high=Decimal("9"),
                low=Decimal("8"),
                close=Decimal("9"),
                volume=Decimal("1"),
                currency=currency,
            )

    def test_rejects_nan_infinity_and_fractional_volume(self) -> None:
        currency = CurrencyCode("USD")
        with self.assertRaises(ValueError):
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("NaN"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1"),
                currency=currency,
            )
        with self.assertRaises(ValueError):
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("1"),
                high=Decimal("Infinity"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1"),
                currency=currency,
            )
        with self.assertRaises(ValueError):
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1.5"),
                currency=currency,
            )

    def test_rejects_zero_or_negative_adjustment_factor(self) -> None:
        with self.assertRaises(ValueError):
            _bar(date(2026, 8, 7), close="10", factor="0")
        with self.assertRaises(ValueError):
            _bar(date(2026, 8, 7), close="10", factor="-1")

    def test_series_rejects_available_without_bars_and_currency_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            _series((), availability=MarketDataAvailability.AVAILABLE)
        with self.assertRaises(ValueError):
            _series((_bar(date(2026, 8, 7), close="10", currency="INR"),), currency="USD")


class CalculationHardeningTests(TestCase):
    def test_simple_return_ratio_goldens(self) -> None:
        bars = (
            _bar(date(2026, 8, 5), close="100"),
            _bar(date(2026, 8, 6), close="105"),
        )
        metric = simple_return(bars)
        self.assertEqual(metric.unit, "ratio")
        self.assertEqual(metric.value, Decimal("0.050000"))
        down = (
            _bar(date(2026, 8, 5), close="100"),
            _bar(date(2026, 8, 6), close="95"),
        )
        self.assertEqual(simple_return(down).value, Decimal("-0.050000"))
        flat = (
            _bar(date(2026, 8, 5), close="100"),
            _bar(date(2026, 8, 6), close="100"),
        )
        self.assertEqual(simple_return(flat).value, Decimal("0.000000"))

    def test_simple_return_rejects_zero_previous_and_single_bar(self) -> None:
        with self.assertRaises(ValueError):
            simple_return((_bar(date(2026, 8, 7), close="10"),))
        zero_prev = (
            _bar(date(2026, 8, 5), close="0"),
            _bar(date(2026, 8, 6), close="10"),
        )
        with self.assertRaises(ValueError):
            simple_return(zero_prev)

    def test_sma_window_boundaries(self) -> None:
        bars = (
            _bar(date(2026, 8, 5), close="10"),
            _bar(date(2026, 8, 6), close="20"),
            _bar(date(2026, 8, 7), close="30"),
        )
        self.assertEqual(simple_moving_average(bars, window=1).value, Decimal("30.0000"))
        self.assertEqual(simple_moving_average(bars, window=3).value, Decimal("20.0000"))
        with self.assertRaises(ValueError):
            simple_moving_average(bars, window=0)
        with self.assertRaises(ValueError):
            simple_moving_average(bars, window=4)

    def test_adjusted_close_and_volume_sum(self) -> None:
        bars = (
            _bar(date(2026, 8, 6), close="200", volume="3", factor="0.5"),
            _bar(date(2026, 8, 7), close="110", volume="7"),
        )
        self.assertEqual(adjusted_last_close(bars).value, Decimal("110.0000"))
        self.assertEqual(last_close(bars).value, Decimal("110.0000"))
        self.assertEqual(volume_sum(bars, window=2).value, Decimal("10"))


class FreshnessHardeningTests(TestCase):
    def test_threshold_boundaries_and_future_as_of(self) -> None:
        policy = MarketFreshnessPolicy(stale_after=timedelta(hours=72))
        as_of = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
        series = _series((_bar(date(2026, 8, 7), close="10"),), as_of=as_of)
        self.assertEqual(
            policy.classify(series, now=as_of + timedelta(hours=72)),
            FreshnessStatus.FRESH,
        )
        self.assertEqual(
            policy.classify(series, now=as_of + timedelta(hours=72, seconds=1)),
            FreshnessStatus.STALE,
        )
        future = _series(
            (_bar(date(2026, 8, 7), close="10"),),
            as_of=datetime(2026, 8, 10, tzinfo=UTC),
        )
        self.assertEqual(
            policy.classify(future, now=datetime(2026, 8, 8, tzinfo=UTC)),
            FreshnessStatus.UNKNOWN,
        )

    def test_future_as_of_snapshot_is_degraded_not_ok(self) -> None:
        listing = "42222222-2222-4222-8222-222222222001"
        future = _series(
            (_bar(date(2026, 8, 7), close="10"),),
            as_of=datetime(2026, 8, 20, tzinfo=UTC),
        )
        adapter = InMemoryMarketDataAdapter(series_by_listing={listing: future})
        result = _usecase(adapter, now=datetime(2026, 8, 8, tzinfo=UTC)).execute(
            MarketSnapshotQuery(company_query=CompanyQuery(raw_query="AAPL"))
        )
        self.assertEqual(result.status, MarketSnapshotStatus.DEGRADED)
        self.assertEqual(result.freshness, FreshnessStatus.UNKNOWN)


class ListingSelectionHardeningTests(TestCase):
    def test_reliance_nse_ok_bse_does_not_reuse_nse(self) -> None:
        use = _usecase(InMemoryMarketDataAdapter())
        nse = use.execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NSE"))
            )
        )
        bse = use.execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("BSE"))
            )
        )
        self.assertEqual(nse.status, MarketSnapshotStatus.OK)
        self.assertEqual(nse.listing.exchange.as_text() if nse.listing else None, "NSE")
        self.assertEqual(bse.status, MarketSnapshotStatus.UNAVAILABLE)
        self.assertIsNone(bse.series)
        self.assertEqual(bse.metrics, ())

    def test_wrong_company_listing_id_does_not_attach(self) -> None:
        apple_listing = "42222222-2222-4222-8222-222222222001"
        result = _usecase(InMemoryMarketDataAdapter()).execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NSE")),
                listing_id=apple_listing,
            )
        )
        self.assertEqual(result.status, MarketSnapshotStatus.UNAVAILABLE)
        self.assertIsNone(result.series)

    def test_identity_mismatch_from_adapter_is_unavailable(self) -> None:
        listing = "42222222-2222-4222-8222-222222222001"
        bad = _series(
            (_bar(date(2026, 8, 7), close="10"),),
            listing_id=listing,
            security_id="32222222-2222-4222-8222-222222222002",  # MSFT security
        )
        result = _usecase(InMemoryMarketDataAdapter(series_by_listing={listing: bad})).execute(
            MarketSnapshotQuery(company_query=CompanyQuery(raw_query="AAPL"))
        )
        self.assertEqual(result.status, MarketSnapshotStatus.UNAVAILABLE)
        self.assertIsNone(result.series)

    def test_alphabet_share_classes_stay_distinct_without_cross_attachment(self) -> None:
        use = _usecase(InMemoryMarketDataAdapter())
        googl = use.execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="GOOGL", exchange=ExchangeCode("NASDAQ"))
            )
        )
        goog = use.execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="GOOG", exchange=ExchangeCode("NASDAQ"))
            )
        )
        self.assertEqual(googl.status, MarketSnapshotStatus.UNAVAILABLE)
        self.assertEqual(goog.status, MarketSnapshotStatus.UNAVAILABLE)
        self.assertNotEqual(
            googl.listing.listing_id if googl.listing else None,
            goog.listing.listing_id if goog.listing else None,
        )

    def test_resolution_blocked_paths(self) -> None:
        use = _usecase(InMemoryMarketDataAdapter())
        blocked = use.execute(
            MarketSnapshotQuery(
                company_query=CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NASDAQ"))
            )
        )
        self.assertEqual(blocked.status, MarketSnapshotStatus.RESOLUTION_BLOCKED)
        self.assertIsNone(blocked.series)
        with self.assertRaises(ValueError):
            MarketSnapshotResult(
                query=MarketSnapshotQuery(company_query=CompanyQuery(raw_query="x")),
                status=MarketSnapshotStatus.RESOLUTION_BLOCKED,
                message="bad",
                series=_series((_bar(date(2026, 8, 7), close="1"),)),
            )


class FallbackAndCacheHardeningTests(TestCase):
    def test_fallback_skips_secondary_on_primary_success_and_keeps_provenance(self) -> None:
        from tests.unit.market_fixtures import APPLE_COMPANY_ID, apple_listing

        listing = apple_listing()
        primary_series = _series((_bar(date(2026, 8, 7), close="11"),), provider_name="primary")
        secondary_series = _series((_bar(date(2026, 8, 7), close="99"),), provider_name="secondary")
        calls: list[str] = []

        class Counting:
            def __init__(self, name: str, series: MarketObservationSeries | None) -> None:
                self.name = name
                self.series = series

            def get_ohlcv_series(
                self,
                listing: object,
                *,
                company_id: CompanyId,
            ) -> MarketObservationSeries | None:
                calls.append(self.name)
                return self.series

        adapter = FallbackMarketDataAdapter(
            Counting("primary", primary_series),
            Counting("secondary", secondary_series),
        )
        got = adapter.get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)
        assert got is not None
        self.assertEqual(got.provider_name, "primary")
        self.assertEqual(calls, ["primary"])

    def test_fallback_uses_secondary_after_primary_exception(self) -> None:
        from tests.unit.market_fixtures import APPLE_COMPANY_ID, apple_listing

        listing = apple_listing()
        secondary_series = _series((_bar(date(2026, 8, 7), close="42"),), provider_name="secondary")

        class Boom:
            def get_ohlcv_series(
                self,
                listing: object,
                *,
                company_id: CompanyId,
            ) -> MarketObservationSeries | None:
                raise RuntimeError("provider down")

        adapter = FallbackMarketDataAdapter(
            Boom(),
            InMemoryMarketDataAdapter(
                series_by_listing={listing.listing_id.as_text(): secondary_series}
            ),
        )
        got = adapter.get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)
        assert got is not None
        self.assertEqual(got.provider_name, "secondary")
        self.assertEqual(got.bars[-1].close, Decimal("42"))

    def test_cache_ttl_boundary_key_isolation_and_clock(self) -> None:
        from tests.unit.market_fixtures import (
            APPLE_COMPANY_ID,
            MSFT_COMPANY_ID,
            apple_listing,
            msft_listing,
        )

        listing_a = apple_listing()
        listing_b = msft_listing()
        calls: list[str] = []
        now = {"t": datetime(2026, 8, 8, 12, 0, tzinfo=UTC)}

        class Counting:
            def get_ohlcv_series(
                self,
                listing: object,
                *,
                company_id: CompanyId,
            ) -> MarketObservationSeries | None:
                listing_id = listing.listing_id.as_text()  # type: ignore[attr-defined]
                calls.append(listing_id)
                return _series((_bar(date(2026, 8, 7), close="10"),), listing_id=listing_id)

        cached = CachingMarketDataAdapter(
            Counting(),
            ttl=timedelta(seconds=10),
            clock=lambda: now["t"],
        )
        cached.get_ohlcv_series(listing_a, company_id=APPLE_COMPANY_ID)
        cached.get_ohlcv_series(listing_a, company_id=APPLE_COMPANY_ID)
        self.assertEqual(calls, [listing_a.listing_id.as_text()])
        now["t"] = now["t"] + timedelta(seconds=10)  # exact expiry → miss
        cached.get_ohlcv_series(listing_a, company_id=APPLE_COMPANY_ID)
        self.assertEqual(
            calls,
            [listing_a.listing_id.as_text(), listing_a.listing_id.as_text()],
        )
        cached.get_ohlcv_series(listing_b, company_id=MSFT_COMPANY_ID)
        self.assertEqual(calls[-1], listing_b.listing_id.as_text())

    def test_cache_hit_does_not_make_old_observation_fresh(self) -> None:
        listing = "42222222-2222-4222-8222-222222222001"
        old = _series(
            (_bar(date(2026, 8, 1), close="10"),),
            as_of=datetime(2026, 8, 1, tzinfo=UTC),
        )
        cached = CachingMarketDataAdapter(
            InMemoryMarketDataAdapter(series_by_listing={listing: old}),
            ttl=timedelta(hours=1),
            clock=lambda: datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        )
        result = _usecase(
            cached, stale_hours=24, now=datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
        ).execute(MarketSnapshotQuery(company_query=CompanyQuery(raw_query="AAPL")))
        self.assertEqual(result.status, MarketSnapshotStatus.DEGRADED)
        self.assertEqual(result.freshness, FreshnessStatus.STALE)

    def test_cache_concurrent_same_key(self) -> None:
        from tests.unit.market_fixtures import APPLE_COMPANY_ID, apple_listing

        listing = apple_listing()
        calls: list[int] = []
        barrier = Barrier(8)

        class Counting:
            def get_ohlcv_series(
                self,
                listing: object,
                *,
                company_id: CompanyId,
            ) -> MarketObservationSeries | None:
                barrier.wait(timeout=5)
                calls.append(1)
                return _series((_bar(date(2026, 8, 7), close="10"),))

        cached = CachingMarketDataAdapter(
            Counting(),
            ttl=timedelta(minutes=5),
            clock=lambda: datetime(2026, 8, 8, tzinfo=UTC),
        )

        def worker() -> MarketObservationSeries | None:
            return cached.get_ohlcv_series(listing, company_id=APPLE_COMPANY_ID)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: worker(), range(8)))
        self.assertTrue(all(item is not None for item in results))
        self.assertGreaterEqual(len(calls), 1)
        self.assertLessEqual(len(calls), 8)


class TimezoneCalendarTests(TestCase):
    def test_exchange_zones_and_dst(self) -> None:
        self.assertEqual(exchange_timezone(ExchangeCode("NSE")), ZoneInfo("Asia/Kolkata"))
        ny = exchange_timezone(ExchangeCode("NASDAQ"))
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=ny)
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=ny)
        self.assertEqual(winter.utcoffset(), timedelta(hours=-5))
        self.assertEqual(summer.utcoffset(), timedelta(hours=-4))
        with self.assertRaises(ValueError):
            exchange_timezone(ExchangeCode("LSE"))

    def test_weekday_helper_does_not_claim_holidays(self) -> None:
        self.assertTrue(is_weekday_calendar_day(date(2026, 8, 7)))
        self.assertFalse(is_weekday_calendar_day(date(2026, 8, 8)))
        self.assertFalse(is_weekday_calendar_day(date(2026, 8, 9)))


class MarketApiHardeningTests(TestCase):
    def test_api_with_frozen_clock_and_safe_failure(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")
        container = build_container(
            settings,
            clock=lambda: datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        )
        with TestClient(create_app(container=container)) as client:
            ok = client.get("/market/snapshot", params={"q": "Apple", "exchange": "NASDAQ"})
            blocked = client.get(
                "/market/snapshot",
                params={"q": "RELIANCE", "exchange": "NASDAQ"},
            )
            bse = client.get("/market/snapshot", params={"q": "RELIANCE", "exchange": "BSE"})
            bad = client.get("/market/snapshot", params={"q": "AAPL", "listing_id": "not-a-uuid"})
            ctrl = client.get("/market/snapshot", params={"q": "AAPL\nInjected"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "ok")
        self.assertEqual(ok.json()["freshness"], "fresh")
        self.assertEqual(ok.json()["data_origin"], "fixture")
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.json()["status"], "resolution_blocked")
        self.assertIsNone(blocked.json()["series"])
        self.assertEqual(bse.status_code, 200)
        self.assertEqual(bse.json()["status"], "unavailable")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(ctrl.status_code, 400)

    def test_settings_reject_invalid_market_knobs(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, MARKET_STALE_AFTER_HOURS=0)
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, MARKET_CACHE_TTL_SECONDS=-1)
