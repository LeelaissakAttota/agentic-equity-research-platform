"""Optional Yahoo Finance chart HTTP adapter (Tier-2 structured market data).

No API key is required. Requests use an allowlisted Yahoo chart base URL only.
Automated tests must inject a fake transport — CI never depends on live Yahoo.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

from financial_intelligence.domain.identity import CompanyId, ListingIdentity
from financial_intelligence.domain.market import (
    DataOrigin,
    MarketDataAvailability,
    MarketObservationSeries,
    OhlcvBar,
)
from financial_intelligence.domain.sources import SourceId
from financial_intelligence.infrastructure.http import (
    BoundedHttpClient,
    HttpTransportError,
)
from financial_intelligence.infrastructure.market.symbol_mapping import yahoo_chart_symbol
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.infrastructure.market.yahoo_chart")

_YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
_MAX_BARS = 120


class YahooChartMarketDataAdapter:
    """Live MarketDataPort adapter for Yahoo chart daily OHLCV."""

    provider_name = "yahoo_finance_chart"

    def __init__(
        self,
        http: BoundedHttpClient,
        *,
        history_days: int = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if history_days < 1 or history_days > 365:
            msg = "history_days must be between 1 and 365"
            raise ValueError(msg)
        self._http = http
        self._history_days = history_days
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_ohlcv_series(
        self,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
    ) -> MarketObservationSeries | None:
        symbol = yahoo_chart_symbol(listing)
        url = self._build_url(symbol)
        retrieved_at = self._clock()
        if retrieved_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        try:
            payload = self._http.get_json(url)
            bars, as_of = self._normalize(payload, listing=listing)
        except HttpTransportError as exc:
            logger.info(
                "yahoo_chart_unavailable",
                extra={
                    "provider_name": self.provider_name,
                    "listing_id": listing.listing_id.as_text(),
                    "failure_kind": exc.kind.value,
                    "status_code": exc.status_code,
                },
            )
            return None
        except (TypeError, ValueError, KeyError) as exc:
            logger.info(
                "yahoo_chart_invalid_payload",
                extra={
                    "provider_name": self.provider_name,
                    "listing_id": listing.listing_id.as_text(),
                    "error_type": type(exc).__name__,
                },
            )
            return None
        if not bars:
            return None
        return MarketObservationSeries(
            company_id=company_id,
            security_id=listing.security_id,
            listing_id=listing.listing_id,
            exchange=listing.exchange,
            ticker=listing.ticker,
            currency=listing.currency,
            as_of=as_of,
            retrieved_at=retrieved_at,
            source_id=SourceId.new(),
            bars=bars,
            provider_name=self.provider_name,
            availability=MarketDataAvailability.AVAILABLE,
            data_origin=DataOrigin.LIVE,
        )

    def _build_url(self, symbol: str) -> str:
        query = urlencode({"interval": "1d", "range": f"{self._history_days}d"})
        return f"{_YAHOO_CHART_BASE}{quote(symbol, safe='.')}?{query}"

    def _normalize(
        self,
        payload: dict[str, object],
        *,
        listing: ListingIdentity,
    ) -> tuple[tuple[OhlcvBar, ...], datetime]:
        chart = payload.get("chart")
        if not isinstance(chart, dict):
            msg = "missing chart object"
            raise ValueError(msg)
        results = chart.get("result")
        if not isinstance(results, list) or not results:
            msg = "missing chart result"
            raise ValueError(msg)
        result = results[0]
        if not isinstance(result, dict):
            msg = "invalid chart result"
            raise ValueError(msg)
        timestamps = result.get("timestamp")
        indicators = result.get("indicators")
        if not isinstance(timestamps, list) or not isinstance(indicators, dict):
            msg = "missing timestamp/indicators"
            raise ValueError(msg)
        quote_list = indicators.get("quote")
        adj_list = indicators.get("adjclose")
        if not isinstance(quote_list, list) or not quote_list:
            msg = "missing quote indicators"
            raise ValueError(msg)
        quote = quote_list[0]
        if not isinstance(quote, dict):
            msg = "invalid quote block"
            raise ValueError(msg)
        opens = quote.get("open")
        highs = quote.get("high")
        lows = quote.get("low")
        closes = quote.get("close")
        volumes = quote.get("volume")
        if not all(isinstance(item, list) for item in (opens, highs, lows, closes, volumes)):
            msg = "OHLCV arrays missing"
            raise ValueError(msg)
        adj_closes: list[Any] | None = None
        if isinstance(adj_list, list) and adj_list and isinstance(adj_list[0], dict):
            maybe = adj_list[0].get("adjclose")
            if isinstance(maybe, list):
                adj_closes = maybe

        bars: list[OhlcvBar] = []
        for index, raw_ts in enumerate(timestamps):
            if index >= _MAX_BARS:
                break
            if not isinstance(raw_ts, (int, float)):
                continue
            open_v = opens[index]  # type: ignore[index]
            high_v = highs[index]  # type: ignore[index]
            low_v = lows[index]  # type: ignore[index]
            close_v = closes[index]  # type: ignore[index]
            volume_v = volumes[index]  # type: ignore[index]
            if None in (open_v, high_v, low_v, close_v, volume_v):
                continue
            close_dec = Decimal(str(close_v))
            factor = Decimal("1")
            if adj_closes is not None and index < len(adj_closes) and adj_closes[index] is not None:
                adj = Decimal(str(adj_closes[index]))
                if close_dec != 0:
                    factor = adj / close_dec
            session = datetime.fromtimestamp(int(raw_ts), tz=UTC).date()
            volume_dec = Decimal(str(volume_v)).to_integral_value()
            bars.append(
                OhlcvBar(
                    session_date=session,
                    open=Decimal(str(open_v)),
                    high=Decimal(str(high_v)),
                    low=Decimal(str(low_v)),
                    close=close_dec,
                    volume=volume_dec,
                    currency=listing.currency,
                    adjustment_factor=factor if factor > 0 else Decimal("1"),
                )
            )
        unique: dict[date, OhlcvBar] = {bar.session_date: bar for bar in bars}
        ordered = tuple(unique[key] for key in sorted(unique))
        if not ordered:
            msg = "no usable bars"
            raise ValueError(msg)
        as_of = datetime.combine(ordered[-1].session_date, datetime.min.time(), tzinfo=UTC)
        meta = result.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("regularMarketTime"), (int, float)):
            as_of = datetime.fromtimestamp(int(meta["regularMarketTime"]), tz=UTC)
        return ordered, as_of
