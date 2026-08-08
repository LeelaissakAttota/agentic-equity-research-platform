"""Canonical issuer / company identity aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field

from financial_intelligence.domain.identity.aliases import CompanyAlias
from financial_intelligence.domain.identity.codes import CountryCode
from financial_intelligence.domain.identity.ids import CompanyId
from financial_intelligence.domain.identity.listing import ListingIdentity
from financial_intelligence.domain.identity.normalization import (
    company_match_key,
    normalize_company_display_name,
)
from financial_intelligence.domain.identity.providers import ProviderIdentifier
from financial_intelligence.domain.identity.security import SecurityIdentity


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    """Provider-neutral issuer identity with nested securities and listings.

    ``company_id`` is stable. Legal/display names, tickers, aliases, and provider
    symbols may change without redefining the company itself.
    """

    company_id: CompanyId
    legal_name: str
    display_name: str
    country: CountryCode
    aliases: tuple[CompanyAlias, ...] = ()
    securities: tuple[SecurityIdentity, ...] = ()
    provider_identifiers: tuple[ProviderIdentifier, ...] = ()
    sector: str | None = None
    industry: str | None = None
    legal_name_key: str = field(init=False)
    display_name_key: str = field(init=False)

    def __post_init__(self) -> None:
        legal = normalize_company_display_name(self.legal_name)
        display = normalize_company_display_name(self.display_name)
        object.__setattr__(self, "legal_name", legal)
        object.__setattr__(self, "display_name", display)
        object.__setattr__(self, "legal_name_key", company_match_key(legal))
        object.__setattr__(self, "display_name_key", company_match_key(display))
        for security in self.securities:
            if security.company_id != self.company_id:
                msg = "security company_id must match parent company"
                raise ValueError(msg)

    def all_listings(self) -> tuple[ListingIdentity, ...]:
        return tuple(listing for security in self.securities for listing in security.listings)

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "legal_name": self.legal_name,
            "display_name": self.display_name,
            "country": self.country.as_text(),
            "sector": self.sector,
            "industry": self.industry,
            "aliases": [
                {"value": alias.value, "alias_type": alias.alias_type.value}
                for alias in self.aliases
            ],
            "securities": [security.to_dict() for security in self.securities],
            "provider_identifiers": [
                {"provider": item.provider.value, "value": item.value}
                for item in self.provider_identifiers
            ],
        }
