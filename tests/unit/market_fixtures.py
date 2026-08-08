"""Shared listing fixtures for Phase 3 market adapter tests."""

from __future__ import annotations

from financial_intelligence.domain.identity import (
    CompanyId,
    CountryCode,
    CurrencyCode,
    ExchangeCode,
    ListingId,
    ListingIdentity,
    ListingStatus,
    SecurityId,
    TickerSymbol,
)

APPLE_COMPANY_ID = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
MSFT_COMPANY_ID = CompanyId.from_string("22222222-2222-4222-8222-222222222002")


def apple_listing() -> ListingIdentity:
    return ListingIdentity(
        listing_id=ListingId.from_string("42222222-2222-4222-8222-222222222001"),
        security_id=SecurityId.from_string("32222222-2222-4222-8222-222222222001"),
        exchange=ExchangeCode("NASDAQ"),
        ticker=TickerSymbol("AAPL"),
        currency=CurrencyCode("USD"),
        country=CountryCode("US"),
        is_primary=True,
        status=ListingStatus.ACTIVE,
    )


def msft_listing() -> ListingIdentity:
    return ListingIdentity(
        listing_id=ListingId.from_string("42222222-2222-4222-8222-222222222002"),
        security_id=SecurityId.from_string("32222222-2222-4222-8222-222222222002"),
        exchange=ExchangeCode("NASDAQ"),
        ticker=TickerSymbol("MSFT"),
        currency=CurrencyCode("USD"),
        country=CountryCode("US"),
        is_primary=True,
        status=ListingStatus.ACTIVE,
    )


def reliance_nse_listing() -> ListingIdentity:
    return ListingIdentity(
        listing_id=ListingId.from_string("41111111-1111-4111-8111-111111111001"),
        security_id=SecurityId.from_string("31111111-1111-4111-8111-111111111001"),
        exchange=ExchangeCode("NSE"),
        ticker=TickerSymbol("RELIANCE"),
        currency=CurrencyCode("INR"),
        country=CountryCode("IN"),
        is_primary=True,
        status=ListingStatus.ACTIVE,
    )


def reliance_bse_listing() -> ListingIdentity:
    return ListingIdentity(
        listing_id=ListingId.from_string("41111111-1111-4111-8111-111111111011"),
        security_id=SecurityId.from_string("31111111-1111-4111-8111-111111111001"),
        exchange=ExchangeCode("BSE"),
        ticker=TickerSymbol("RELIANCE"),
        currency=CurrencyCode("INR"),
        country=CountryCode("IN"),
        is_primary=False,
        status=ListingStatus.ACTIVE,
    )
