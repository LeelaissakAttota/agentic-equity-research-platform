"""Exchange listing identity independent of issuer and share class."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.identity.codes import (
    CountryCode,
    CurrencyCode,
    ExchangeCode,
    TickerSymbol,
)
from financial_intelligence.domain.identity.ids import ListingId, SecurityId


class ListingStatus(StrEnum):
    """Listing lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELISTED = "delisted"


@dataclass(frozen=True, slots=True)
class ListingIdentity:
    """One exchange listing for a security.

    ``is_primary`` is advisory within a single security. A security may have
    zero or one primary listing (ADR-026). Companies may have multiple primary
    listings across different securities (e.g. share classes). Dual listings of
    the same security (e.g. NSE+BSE) must not mark more than one as primary.
    """

    listing_id: ListingId
    security_id: SecurityId
    exchange: ExchangeCode
    ticker: TickerSymbol
    currency: CurrencyCode
    country: CountryCode
    is_primary: bool = False
    status: ListingStatus = ListingStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        return {
            "listing_id": self.listing_id.as_text(),
            "security_id": self.security_id.as_text(),
            "exchange": self.exchange.as_text(),
            "mic": self.exchange.mic,
            "ticker": self.ticker.as_text(),
            "currency": self.currency.as_text(),
            "country": self.country.as_text(),
            "is_primary": self.is_primary,
            "status": self.status.value,
        }
