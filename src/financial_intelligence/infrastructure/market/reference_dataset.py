"""Deterministic OHLCV reference fixture for Phase 3 Prompt 1.

This is REFERENCE / TEST market data only:

- not live exchange quotes
- not complete India/US market coverage
- not an investment-grade market feed

Live Yahoo/Alpha Vantage/Finnhub adapters remain deferred until separately
authorized. Values are fixed Decimals chosen for reproducible calculations.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from financial_intelligence.domain.identity import (
    CompanyId,
    CurrencyCode,
    ExchangeCode,
    ListingId,
    SecurityId,
    TickerSymbol,
)
from financial_intelligence.domain.market import MarketObservationSeries, OhlcvBar
from financial_intelligence.domain.sources import SourceId

# Fixed source IDs keep golden tests stable across runs.
_AAPL_SOURCE = SourceId(value=UUID("53333333-3333-4333-8333-333333333001"))
_RELIANCE_NSE_SOURCE = SourceId(value=UUID("53333333-3333-4333-8333-333333333002"))
_MSFT_SOURCE = SourceId(value=UUID("53333333-3333-4333-8333-333333333003"))

# Intentionally recent as-of for default freshness tests (2026-08-07 UTC).
_AS_OF = datetime(2026, 8, 7, 20, 0, tzinfo=UTC)
_RETRIEVED = datetime(2026, 8, 7, 20, 5, tzinfo=UTC)


def _bar(
    session: date,
    *,
    open_: str,
    high: str,
    low: str,
    close: str,
    volume: str,
    currency: str,
    adjustment_factor: str = "1",
) -> OhlcvBar:
    return OhlcvBar(
        session_date=session,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        currency=CurrencyCode(currency),
        adjustment_factor=Decimal(adjustment_factor),
    )


def build_reference_market_series() -> dict[str, MarketObservationSeries]:
    """Return listing_id → OHLCV series for a subset of Phase 2 fixture listings."""

    apple = MarketObservationSeries(
        company_id=CompanyId.from_string("22222222-2222-4222-8222-222222222001"),
        security_id=SecurityId.from_string("32222222-2222-4222-8222-222222222001"),
        listing_id=ListingId.from_string("42222222-2222-4222-8222-222222222001"),
        exchange=ExchangeCode("NASDAQ"),
        ticker=TickerSymbol("AAPL"),
        currency=CurrencyCode("USD"),
        as_of=_AS_OF,
        retrieved_at=_RETRIEVED,
        source_id=_AAPL_SOURCE,
        provider_name="fixture",
        bars=(
            _bar(
                date(2026, 8, 3),
                open_="190.00",
                high="192.00",
                low="189.00",
                close="191.00",
                volume="1000",
                currency="USD",
            ),
            _bar(
                date(2026, 8, 4),
                open_="191.00",
                high="194.00",
                low="190.50",
                close="193.00",
                volume="1100",
                currency="USD",
            ),
            _bar(
                date(2026, 8, 5),
                open_="193.00",
                high="196.00",
                low="192.00",
                close="195.00",
                volume="1200",
                currency="USD",
                # Simulated post-split residual factor for corporate-action awareness.
                adjustment_factor="1",
            ),
            _bar(
                date(2026, 8, 6),
                open_="195.00",
                high="198.00",
                low="194.00",
                close="197.00",
                volume="1300",
                currency="USD",
            ),
            _bar(
                date(2026, 8, 7),
                open_="197.00",
                high="200.00",
                low="196.00",
                close="199.00",
                volume="1400",
                currency="USD",
            ),
        ),
    )

    # Pre-split bar + post-split adjusted series for RELIANCE NSE (adjustment demo).
    reliance = MarketObservationSeries(
        company_id=CompanyId.from_string("11111111-1111-4111-8111-111111111001"),
        security_id=SecurityId.from_string("31111111-1111-4111-8111-111111111001"),
        listing_id=ListingId.from_string("41111111-1111-4111-8111-111111111001"),
        exchange=ExchangeCode("NSE"),
        ticker=TickerSymbol("RELIANCE"),
        currency=CurrencyCode("INR"),
        as_of=_AS_OF,
        retrieved_at=_RETRIEVED,
        source_id=_RELIANCE_NSE_SOURCE,
        provider_name="fixture",
        bars=(
            _bar(
                date(2026, 8, 4),
                open_="2800.00",
                high="2820.00",
                low="2780.00",
                close="2810.00",
                volume="50000",
                currency="INR",
                adjustment_factor="0.5",
            ),
            _bar(
                date(2026, 8, 5),
                open_="1400.00",
                high="1420.00",
                low="1390.00",
                close="1410.00",
                volume="90000",
                currency="INR",
            ),
            _bar(
                date(2026, 8, 6),
                open_="1410.00",
                high="1435.00",
                low="1405.00",
                close="1430.00",
                volume="85000",
                currency="INR",
            ),
            _bar(
                date(2026, 8, 7),
                open_="1430.00",
                high="1450.00",
                low="1425.00",
                close="1445.00",
                volume="88000",
                currency="INR",
            ),
        ),
    )

    microsoft = MarketObservationSeries(
        company_id=CompanyId.from_string("22222222-2222-4222-8222-222222222002"),
        security_id=SecurityId.from_string("32222222-2222-4222-8222-222222222002"),
        listing_id=ListingId.from_string("42222222-2222-4222-8222-222222222002"),
        exchange=ExchangeCode("NASDAQ"),
        ticker=TickerSymbol("MSFT"),
        currency=CurrencyCode("USD"),
        as_of=_AS_OF,
        retrieved_at=_RETRIEVED,
        source_id=_MSFT_SOURCE,
        provider_name="fixture",
        bars=(
            _bar(
                date(2026, 8, 5),
                open_="420.00",
                high="425.00",
                low="418.00",
                close="422.00",
                volume="2000",
                currency="USD",
            ),
            _bar(
                date(2026, 8, 6),
                open_="422.00",
                high="428.00",
                low="421.00",
                close="426.00",
                volume="2100",
                currency="USD",
            ),
            _bar(
                date(2026, 8, 7),
                open_="426.00",
                high="430.00",
                low="424.00",
                close="429.00",
                volume="2200",
                currency="USD",
            ),
        ),
    )

    return {
        apple.listing_id.as_text(): apple,
        reliance.listing_id.as_text(): reliance,
        microsoft.listing_id.as_text(): microsoft,
    }
