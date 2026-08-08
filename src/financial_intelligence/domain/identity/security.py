"""Security / share-class identity distinct from issuers and listings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.identity.ids import CompanyId, SecurityId
from financial_intelligence.domain.identity.listing import ListingIdentity
from financial_intelligence.domain.identity.normalization import (
    normalize_company_display_name,
)


class SecurityType(StrEnum):
    """High-level security classification."""

    COMMON_SHARE = "common_share"
    PREFERRED_SHARE = "preferred_share"
    ADR = "adr"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SecurityIdentity:
    """One tradable security / share class belonging to an issuer."""

    security_id: SecurityId
    company_id: CompanyId
    security_type: SecurityType
    display_name: str
    share_class: str | None = None
    listings: tuple[ListingIdentity, ...] = ()

    def __post_init__(self) -> None:
        display = normalize_company_display_name(self.display_name)
        object.__setattr__(self, "display_name", display)
        if self.share_class is not None:
            share_class = self.share_class.strip().upper()
            if not share_class or len(share_class) > 16:
                msg = "share_class is empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "share_class", share_class)
        for listing in self.listings:
            if listing.security_id != self.security_id:
                msg = "listing security_id must match parent security"
                raise ValueError(msg)
        primary_count = sum(1 for listing in self.listings if listing.is_primary)
        if primary_count > 1:
            msg = "a security may have at most one primary listing"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "security_id": self.security_id.as_text(),
            "company_id": self.company_id.as_text(),
            "security_type": self.security_type.value,
            "display_name": self.display_name,
            "share_class": self.share_class,
            "listings": [listing.to_dict() for listing in self.listings],
        }
