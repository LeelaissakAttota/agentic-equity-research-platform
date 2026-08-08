"""Offline tests for optional Yahoo chart live market adapter + HTTP client."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.market import DataOrigin
from financial_intelligence.infrastructure.http import (
    BoundedHttpClient,
    HttpFailureKind,
    HttpResponse,
    HttpTransportError,
)
from financial_intelligence.infrastructure.market.symbol_mapping import yahoo_chart_symbol
from financial_intelligence.infrastructure.market.yahoo_chart import YahooChartMarketDataAdapter
from tests.unit.market_fixtures import (
    APPLE_COMPANY_ID,
    apple_listing,
    reliance_bse_listing,
    reliance_nse_listing,
)


def _yahoo_payload() -> dict[str, object]:
    return {
        "chart": {
            "result": [
                {
                    "meta": {"regularMarketTime": 1754582400},
                    "timestamp": [1754323200, 1754409600, 1754496000],
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 11.0, 12.0],
                                "high": [10.5, 11.5, 12.5],
                                "low": [9.5, 10.5, 11.5],
                                "close": [10.2, 11.2, 12.2],
                                "volume": [1000, 1100, 1200],
                            }
                        ],
                        "adjclose": [{"adjclose": [10.2, 11.2, 12.2]}],
                    },
                }
            ]
        }
    }


class FakeTransport:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls = 0

    def request(
        self, method: str, url: str, *, headers: dict[str, str], timeout: float
    ) -> HttpResponse:
        self.calls += 1
        return self.handler(method, url, headers, timeout)


class SymbolMappingTests(TestCase):
    def test_india_and_us_suffixes(self) -> None:
        self.assertEqual(yahoo_chart_symbol(apple_listing()), "AAPL")
        self.assertEqual(yahoo_chart_symbol(reliance_nse_listing()), "RELIANCE.NS")
        self.assertEqual(yahoo_chart_symbol(reliance_bse_listing()), "RELIANCE.BO")


class BoundedHttpClientTests(TestCase):
    def test_retries_429_then_succeeds(self) -> None:
        payloads = [
            HttpResponse(429, b"{}", "application/json", {"retry-after": "0"}),
            HttpResponse(200, json.dumps({"ok": True}).encode(), "application/json", {}),
        ]

        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            return payloads.pop(0)

        transport = FakeTransport(handler)
        client = BoundedHttpClient(transport, timeout_seconds=1, max_retries=2, user_agent="test")
        self.assertEqual(client.get_json("https://query1.finance.yahoo.com/x"), {"ok": True})
        self.assertEqual(transport.calls, 2)

    def test_does_not_retry_400(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            return HttpResponse(400, b"{}", "application/json", {})

        transport = FakeTransport(handler)
        client = BoundedHttpClient(transport, timeout_seconds=1, max_retries=3, user_agent="test")
        with self.assertRaises(HttpTransportError) as ctx:
            client.get_json("https://query1.finance.yahoo.com/x")
        self.assertEqual(ctx.exception.kind, HttpFailureKind.INVALID_RESPONSE)
        self.assertEqual(transport.calls, 1)

    def test_oversized_response(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            raise HttpTransportError(HttpFailureKind.OVERSIZED, "too big")

        client = BoundedHttpClient(
            FakeTransport(handler), timeout_seconds=1, max_retries=0, user_agent="test"
        )
        with self.assertRaises(HttpTransportError) as ctx:
            client.get_json("https://query1.finance.yahoo.com/x")
        self.assertEqual(ctx.exception.kind, HttpFailureKind.OVERSIZED)


class YahooChartAdapterTests(TestCase):
    def test_normalizes_live_series_with_live_origin(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            self.assertIn("AAPL", url)
            self.assertIn("User-Agent", headers)
            return HttpResponse(
                200,
                json.dumps(_yahoo_payload()).encode(),
                "application/json",
                {},
            )

        adapter = YahooChartMarketDataAdapter(
            BoundedHttpClient(
                FakeTransport(handler), timeout_seconds=1, max_retries=0, user_agent="test"
            ),
            history_days=5,
            clock=lambda: datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        )
        series = adapter.get_ohlcv_series(apple_listing(), company_id=APPLE_COMPANY_ID)
        assert series is not None
        self.assertEqual(series.data_origin, DataOrigin.LIVE)
        self.assertEqual(series.provider_name, "yahoo_finance_chart")
        self.assertEqual(series.bars[-1].close, Decimal("12.2"))
        self.assertEqual(series.listing_id, apple_listing().listing_id)

    def test_provider_outage_returns_none(self) -> None:
        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            return HttpResponse(503, b"down", "text/plain", {})

        adapter = YahooChartMarketDataAdapter(
            BoundedHttpClient(
                FakeTransport(handler), timeout_seconds=1, max_retries=0, user_agent="test"
            ),
        )
        self.assertIsNone(adapter.get_ohlcv_series(apple_listing(), company_id=APPLE_COMPANY_ID))

    def test_malformed_ohlc_rejected(self) -> None:
        bad = _yahoo_payload()
        bad["chart"]["result"][0]["indicators"]["quote"][0]["high"] = [1.0, 1.0, 1.0]
        bad["chart"]["result"][0]["indicators"]["quote"][0]["low"] = [2.0, 2.0, 2.0]

        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            return HttpResponse(200, json.dumps(bad).encode(), "application/json", {})

        adapter = YahooChartMarketDataAdapter(
            BoundedHttpClient(
                FakeTransport(handler), timeout_seconds=1, max_retries=0, user_agent="test"
            ),
        )
        self.assertIsNone(adapter.get_ohlcv_series(apple_listing(), company_id=APPLE_COMPANY_ID))

    def test_nse_symbol_used_in_url(self) -> None:
        seen: list[str] = []

        def handler(method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
            seen.append(url)
            return HttpResponse(404, b"{}", "application/json", {})

        adapter = YahooChartMarketDataAdapter(
            BoundedHttpClient(
                FakeTransport(handler), timeout_seconds=1, max_retries=0, user_agent="test"
            ),
        )
        from financial_intelligence.domain.identity import CompanyId

        company = CompanyId.from_string("11111111-1111-4111-8111-111111111001")
        self.assertIsNone(adapter.get_ohlcv_series(reliance_nse_listing(), company_id=company))
        self.assertTrue(any("RELIANCE.NS" in url for url in seen))
