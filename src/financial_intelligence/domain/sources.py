"""Source metadata foundation aligned with EVIDENCE_MODEL.md and DATA_SOURCES.md.

This package models source contracts only. Live acquisition/fetchers are out of scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum
from urllib.parse import urlparse
from uuid import UUID, uuid4

from financial_intelligence.domain.identity.ids import CompanyId, ListingId, SecurityId

_SOURCE_NAME_RE = re.compile(r"^[\w .,&/+()-]{1,128}$", re.UNICODE)
_MAX_URL_LENGTH = 2048
_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


class SourceAuthorityTier(IntEnum):
    """Frozen authority hierarchy from DATA_SOURCES.md / ADR-019."""

    TIER_1_AUTHORITATIVE = 1
    TIER_2_STRUCTURED_FINANCIAL = 2
    TIER_3_REPUTABLE_NEWS = 3
    TIER_4_GENERAL_WEB = 4


class SourceType(StrEnum):
    """Extensible normalized source-type vocabulary."""

    REGULATORY_FILING = "regulatory_filing"
    EXCHANGE_DISCLOSURE = "exchange_disclosure"
    COMPANY_INVESTOR_RELATIONS = "company_investor_relations"
    FINANCIAL_STATEMENT = "financial_statement"
    MARKET_DATA = "market_data"
    NEWS = "news"
    REGULATORY_ANNOUNCEMENT = "regulatory_announcement"
    INDUSTRY_SOURCE = "industry_source"
    GENERAL_WEB = "general_web"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SourceId:
    """Opaque source identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "source_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> SourceId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> SourceId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


def validate_source_url(url: str | None) -> str | None:
    """Validate and bound an optional http(s) URL without fetching it."""

    if url is None:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    if len(candidate) > _MAX_URL_LENGTH:
        msg = "source URL exceeds length bounds"
        raise ValueError(msg)
    if any(ord(ch) < 32 for ch in candidate):
        msg = "source URL contains control characters"
        raise ValueError(msg)
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        msg = "source URL scheme must be http or https"
        raise ValueError(msg)
    if not parsed.netloc:
        msg = "source URL must include a network location"
        raise ValueError(msg)
    if candidate.lower().startswith(("javascript:", "data:", "file:")):
        msg = "source URL scheme is not allowed"
        raise ValueError(msg)
    return candidate


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Source reference/metadata contract for future evidence linkage.

    URLs are validated but never fetched here. Retrieved content remains untrusted
    (ADR-021) and belongs to later acquisition phases.
    """

    source_id: SourceId
    name: str
    source_type: SourceType
    authority_tier: SourceAuthorityTier
    url: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    company_id: CompanyId | None = None
    security_id: SecurityId | None = None
    listing_id: ListingId | None = None
    content_type: str | None = None
    integrity_hash: str | None = None

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name or not _SOURCE_NAME_RE.fullmatch(name):
            msg = "source name is empty, invalid, or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "url", validate_source_url(self.url))
        for stamp in (self.published_at, self.retrieved_at):
            if stamp is not None and stamp.tzinfo is None:
                msg = "source timestamps must be timezone-aware"
                raise ValueError(msg)
        # Minimum linkage consistency without requiring a database:
        # listing → security → company.
        if self.listing_id is not None and self.security_id is None:
            msg = "listing_id requires security_id"
            raise ValueError(msg)
        if self.security_id is not None and self.company_id is None:
            msg = "security_id requires company_id"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id.as_text(),
            "name": self.name,
            "source_type": self.source_type.value,
            "authority_tier": int(self.authority_tier),
            "url": self.url,
            "publisher": self.publisher,
            "published_at": (
                self.published_at.isoformat().replace("+00:00", "Z")
                if self.published_at is not None
                else None
            ),
            "retrieved_at": (
                self.retrieved_at.isoformat().replace("+00:00", "Z")
                if self.retrieved_at is not None
                else None
            ),
            "company_id": self.company_id.as_text() if self.company_id else None,
            "security_id": self.security_id.as_text() if self.security_id else None,
            "listing_id": self.listing_id.as_text() if self.listing_id else None,
            "content_type": self.content_type,
            "integrity_hash": self.integrity_hash,
        }
