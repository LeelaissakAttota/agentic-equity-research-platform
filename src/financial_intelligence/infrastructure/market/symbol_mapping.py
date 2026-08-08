"""Provider-specific market symbol mapping (never becomes canonical identity)."""

from __future__ import annotations

from financial_intelligence.domain.identity import ListingIdentity, ProviderIdentifier, ProviderKind


def yahoo_chart_symbol(listing: ListingIdentity) -> str:
    """Map a canonical listing to a Yahoo Finance chart symbol.

    Exchange suffixes are infrastructure conventions, not CompanyId/ListingId.
    """

    ticker = listing.ticker.as_text()
    exchange = listing.exchange.as_text()
    if exchange == "NSE":
        return f"{ticker}.NS"
    if exchange == "BSE":
        return f"{ticker}.BO"
    # NASDAQ / NYSE commonly use the bare ticker on Yahoo chart endpoints.
    return ticker


def prefer_yahoo_provider_identifier(
    identifiers: tuple[ProviderIdentifier, ...],
    listing: ListingIdentity,
) -> str:
    """Prefer an explicit Yahoo provider id when present; else map from listing."""

    for item in identifiers:
        if item.provider is ProviderKind.YAHOO_FINANCE:
            return item.value
    return yahoo_chart_symbol(listing)
