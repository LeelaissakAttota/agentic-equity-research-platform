"""Canonical news/event domain models for Phase 5.

Events are source-grounded qualitative items. Opinion/sentiment labels are
explicit information classes — never promoted to facts without evidence links.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceId,
    validate_source_url,
)

if TYPE_CHECKING:
    from financial_intelligence.domain.news.conflicts import EventConflict

_TITLE_MAX = 256
_SUMMARY_MAX = 2000
_LOCATOR_MAX = 256


def _reject_control_chars(value: str, field: str) -> str:
    if any(ord(ch) < 32 for ch in value):
        msg = f"{field} must not contain control characters"
        raise ValueError(msg)
    return value


class EventType(StrEnum):
    """Deterministic event taxonomy (Phase 5 foundation)."""

    EARNINGS = "earnings"
    PRODUCT = "product"
    MERGER_ACQUISITION = "merger_acquisition"
    INVESTMENT = "investment"
    MANAGEMENT = "management"
    REGULATORY = "regulatory"
    LITIGATION = "litigation"
    INDUSTRY = "industry"
    OTHER = "other"


class InformationClass(StrEnum):
    """EVIDENCE_MODEL information classes for qualitative content."""

    FACT = "fact"
    MODEL_INTERPRETATION = "model_interpretation"
    RESEARCH_FINDING = "research_finding"
    OPINION = "opinion"


class NewsEventAvailability(StrEnum):
    """Availability of a company event package without fabricating success."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class EventId:
    """Opaque event identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "event_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> EventId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> EventId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class EventEvidenceRef:
    """Minimal evidence pointer for a qualitative event (EVIDENCE_MODEL-aligned)."""

    source_id: SourceId
    authority_tier: SourceAuthorityTier
    locator: str
    retrieved_at: datetime
    source_url: str | None = None
    published_at: date | None = None
    provider_name: str = "fixture"

    def __post_init__(self) -> None:
        cleaned = _reject_control_chars(self.locator.strip(), "evidence locator")
        if not cleaned or len(cleaned) > _LOCATOR_MAX:
            msg = "evidence locator empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "locator", cleaned)
        if self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        object.__setattr__(
            self,
            "provider_name",
            _reject_control_chars(self.provider_name.strip(), "provider_name"),
        )
        object.__setattr__(self, "source_url", validate_source_url(self.source_url))
        if self.published_at is not None and self.published_at > self.retrieved_at.date():
            msg = "published_at must not be after retrieved_at date"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id.as_text(),
            "authority_tier": int(self.authority_tier),
            "locator": self.locator,
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "provider_name": self.provider_name,
            "kind": "event_evidence_ref",
        }


@dataclass(frozen=True, slots=True)
class EventAgeMetadata:
    """Explicit age dimensions — never conflated with cache TTL."""

    days_since_event: int | None
    days_since_publication: int | None
    days_since_retrieval: int

    def to_dict(self) -> dict[str, object]:
        return {
            "days_since_event": self.days_since_event,
            "days_since_publication": self.days_since_publication,
            "days_since_retrieval": self.days_since_retrieval,
            "kind": "event_age_metadata",
        }


def compute_event_age(
    event: QualitativeEvent,
    *,
    as_of: datetime,
) -> EventAgeMetadata:
    """Compute explicit age metadata without inventing freshness thresholds."""

    if as_of.tzinfo is None:
        msg = "as_of must be timezone-aware"
        raise ValueError(msg)
    as_of_date = as_of.date()
    retrieval = event.evidence.retrieved_at
    days_retrieval = (as_of_date - retrieval.date()).days
    days_event = (as_of_date - event.event_date).days
    days_pub = (
        (as_of_date - event.evidence.published_at).days
        if event.evidence.published_at is not None
        else None
    )
    return EventAgeMetadata(
        days_since_event=days_event,
        days_since_publication=days_pub,
        days_since_retrieval=days_retrieval,
    )


@dataclass(frozen=True, slots=True)
class QualitativeEvent:
    """One deduplicable, time-aware, source-grounded company event."""

    event_id: EventId
    company_id: CompanyId
    event_type: EventType
    title: str
    summary: str
    event_date: date
    information_class: InformationClass
    evidence: EventEvidenceRef
    sentiment_label: str | None = None
    jurisdiction: str | None = None

    def __post_init__(self) -> None:
        title = " ".join(_reject_control_chars(self.title, "event title").strip().split())
        if not title or len(title) > _TITLE_MAX:
            msg = "event title empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "title", title)
        summary = _reject_control_chars(self.summary, "event summary").strip()
        if not summary or len(summary) > _SUMMARY_MAX:
            msg = "event summary empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "summary", summary)
        if self.sentiment_label is not None:
            cleaned = self.sentiment_label.strip().lower()
            if cleaned not in {"positive", "negative", "neutral", "mixed"}:
                msg = "sentiment_label must be positive|negative|neutral|mixed when set"
                raise ValueError(msg)
            if (
                cleaned in {"positive", "negative", "mixed"}
                and self.information_class is InformationClass.FACT
            ):
                msg = "directional sentiment cannot be labeled as FACT without analysis class"
                raise ValueError(msg)
            object.__setattr__(self, "sentiment_label", cleaned)
        if self.jurisdiction is not None:
            jur = self.jurisdiction.strip().upper()
            if len(jur) != 2:
                msg = "jurisdiction must be ISO alpha-2 when set"
                raise ValueError(msg)
            object.__setattr__(self, "jurisdiction", jur)
        if (
            self.evidence.authority_tier is SourceAuthorityTier.TIER_4_GENERAL_WEB
            and self.information_class is InformationClass.FACT
        ):
            msg = "Tier-4 general web content cannot be classified as FACT"
            raise ValueError(msg)
        if self.evidence.published_at is not None and self.event_date > self.evidence.published_at:
            # Event occurrence after publication is not meaningful for this model.
            msg = "event_date must not be after published_at"
            raise ValueError(msg)

    def dedupe_key(self) -> tuple[str, str, str, str]:
        """Deterministic identity for near-duplicate collapse."""

        return (
            self.company_id.as_text(),
            self.event_type.value,
            self.event_date.isoformat(),
            self.title.casefold(),
        )

    def age_metadata(self, *, as_of: datetime) -> EventAgeMetadata:
        return compute_event_age(self, as_of=as_of)

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id.as_text(),
            "company_id": self.company_id.as_text(),
            "event_type": self.event_type.value,
            "title": self.title,
            "summary": self.summary,
            "event_date": self.event_date.isoformat(),
            "information_class": self.information_class.value,
            "sentiment_label": self.sentiment_label,
            "jurisdiction": self.jurisdiction,
            "evidence": self.evidence.to_dict(),
            "kind": "qualitative_event",
        }


@dataclass(frozen=True, slots=True)
class CompanyEventPackage:
    """Normalized event package for one company after deterministic processing."""

    company_id: CompanyId
    retrieved_at: datetime
    events: tuple[QualitativeEvent, ...] = ()
    conflicts: tuple[EventConflict, ...] = ()
    provider_name: str = "fixture"
    availability: NewsEventAvailability = NewsEventAvailability.AVAILABLE
    data_origin: DataOrigin = DataOrigin.FIXTURE

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        object.__setattr__(self, "provider_name", self.provider_name.strip())
        if self.availability is NewsEventAvailability.AVAILABLE and not self.events:
            msg = "AVAILABLE package requires at least one event"
            raise ValueError(msg)
        if self.data_origin is DataOrigin.UNAVAILABLE and self.events:
            msg = "UNAVAILABLE origin must not include events"
            raise ValueError(msg)
        for event in self.events:
            if event.company_id != self.company_id:
                msg = "event company_id must match package"
                raise ValueError(msg)

    def with_data_origin(self, origin: DataOrigin) -> CompanyEventPackage:
        return CompanyEventPackage(
            company_id=self.company_id,
            retrieved_at=self.retrieved_at,
            events=self.events,
            conflicts=self.conflicts,
            provider_name=self.provider_name,
            availability=self.availability,
            data_origin=origin,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "events": [event.to_dict() for event in self.events],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "provider_name": self.provider_name,
            "availability": self.availability.value,
            "data_origin": self.data_origin.value,
            "event_count": len(self.events),
            "conflict_count": len(self.conflicts),
        }
