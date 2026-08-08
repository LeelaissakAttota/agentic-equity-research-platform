"""Company / security / listing identity domain package."""

from financial_intelligence.domain.identity.aliases import AliasType, CompanyAlias
from financial_intelligence.domain.identity.codes import (
    CountryCode,
    CurrencyCode,
    ExchangeCode,
    TickerSymbol,
)
from financial_intelligence.domain.identity.company import CompanyIdentity
from financial_intelligence.domain.identity.ids import CompanyId, ListingId, SecurityId
from financial_intelligence.domain.identity.listing import ListingIdentity, ListingStatus
from financial_intelligence.domain.identity.normalization import (
    MAX_COMPANY_NAME_LENGTH,
    MAX_QUERY_LENGTH,
    company_match_key,
    normalize_company_display_name,
    normalize_ticker,
)
from financial_intelligence.domain.identity.providers import ProviderIdentifier, ProviderKind
from financial_intelligence.domain.identity.security import SecurityIdentity, SecurityType

__all__ = [
    "MAX_COMPANY_NAME_LENGTH",
    "MAX_QUERY_LENGTH",
    "AliasType",
    "CompanyAlias",
    "CompanyId",
    "CompanyIdentity",
    "CountryCode",
    "CurrencyCode",
    "ExchangeCode",
    "ListingId",
    "ListingIdentity",
    "ListingStatus",
    "ProviderIdentifier",
    "ProviderKind",
    "SecurityId",
    "SecurityIdentity",
    "SecurityType",
    "TickerSymbol",
    "company_match_key",
    "normalize_company_display_name",
    "normalize_ticker",
]
