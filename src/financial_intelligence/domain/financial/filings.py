"""Filing identity and metadata (provider-neutral)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from financial_intelligence.domain.financial.periods import ReportingPeriod
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceId,
    validate_source_url,
)


class FilingFormType(StrEnum):
    """Supported filing/disclosure form vocabulary.

    US SEC forms and Indian disclosure types are both represented; Indian
    reporting is not assumed to match SEC form semantics.
    """

    US_10K = "10-K"
    US_10Q = "10-Q"
    US_8K = "8-K"
    IN_ANNUAL_RESULTS = "in_annual_results"
    IN_QUARTERLY_RESULTS = "in_quarterly_results"
    IN_ANNUAL_REPORT = "in_annual_report"
    IN_EXCHANGE_DISCLOSURE = "in_exchange_disclosure"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FilingId:
    """Opaque filing identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "filing_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> FilingId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> FilingId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class FilingMetadata:
    """Provider-neutral filing/document metadata with authority linkage."""

    filing_id: FilingId
    company_id: CompanyId
    form_type: FilingFormType
    reporting_period: ReportingPeriod
    source_id: SourceId
    authority_tier: SourceAuthorityTier
    filed_at: date | None = None
    published_at: date | None = None
    retrieved_at: datetime | None = None
    source_url: str | None = None
    accession_or_reference: str | None = None
    provider_name: str = "fixture"

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        cleaned_provider = self.provider_name.strip()
        if len(cleaned_provider) > 64:
            msg = "provider_name exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "provider_name", cleaned_provider)
        if self.retrieved_at is not None and self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        if self.accession_or_reference is not None:
            cleaned = self.accession_or_reference.strip()
            if len(cleaned) > 128:
                msg = "accession_or_reference exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "accession_or_reference", cleaned or None)
        # Validate URL shape only — retrieved filing content remains untrusted data.
        object.__setattr__(self, "source_url", validate_source_url(self.source_url))

    def to_dict(self) -> dict[str, object]:
        return {
            "filing_id": self.filing_id.as_text(),
            "company_id": self.company_id.as_text(),
            "form_type": self.form_type.value,
            "reporting_period": self.reporting_period.to_dict(),
            "source_id": self.source_id.as_text(),
            "authority_tier": int(self.authority_tier),
            "filed_at": self.filed_at.isoformat() if self.filed_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "retrieved_at": (
                self.retrieved_at.isoformat().replace("+00:00", "Z")
                if self.retrieved_at is not None
                else None
            ),
            "source_url": self.source_url,
            "accession_or_reference": self.accession_or_reference,
            "provider_name": self.provider_name,
        }
