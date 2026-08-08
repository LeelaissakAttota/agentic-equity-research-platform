"""Regulatory intelligence domain models (Phase 5 foundation).

Official regulatory facts prefer Tier-1 sources. Secondary news may reference
regulatory activity but must not be silently upgraded to official evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.news.events import EventEvidenceRef, InformationClass
from financial_intelligence.domain.sources import SourceAuthorityTier

_TITLE_MAX = 256
_SUMMARY_MAX = 2000
_CASE_MAX = 128


class RegulatorCode(StrEnum):
    """Known regulator vocabulary (fixture-scale; not full coverage)."""

    SEC = "SEC"
    SEBI = "SEBI"
    NSE = "NSE"
    BSE = "BSE"
    OTHER = "OTHER"


class RegulatoryActionType(StrEnum):
    INQUIRY = "inquiry"
    ORDER = "order"
    PENALTY = "penalty"
    GUIDANCE = "guidance"
    NOTICE = "notice"
    AMENDMENT = "amendment"
    WITHDRAWAL = "withdrawal"
    OTHER = "other"


class RegulatoryStatus(StrEnum):
    """Lifecycle / certainty of a regulatory item."""

    ALLEGED = "alleged"
    ACTIVE = "active"
    AMENDED = "amended"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class RegulatoryAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class RegulatoryEvent:
    """One time-aware, source-grounded regulatory development for a company."""

    event_id: str
    company_id: CompanyId
    regulator: RegulatorCode
    jurisdiction: str
    action_type: RegulatoryActionType
    status: RegulatoryStatus
    title: str
    summary: str
    event_date: date
    information_class: InformationClass
    evidence: EventEvidenceRef
    case_reference: str | None = None
    published_at: date | None = None

    def __post_init__(self) -> None:
        title = " ".join(self.title.strip().split())
        if not title or len(title) > _TITLE_MAX:
            msg = "regulatory title empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "title", title)
        summary = self.summary.strip()
        if not summary or len(summary) > _SUMMARY_MAX:
            msg = "regulatory summary empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "summary", summary)
        jur = self.jurisdiction.strip().upper()
        if len(jur) != 2:
            msg = "jurisdiction must be ISO alpha-2"
            raise ValueError(msg)
        object.__setattr__(self, "jurisdiction", jur)
        if self.case_reference is not None:
            ref = self.case_reference.strip()
            if not ref or len(ref) > _CASE_MAX:
                msg = "case_reference empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "case_reference", ref)
        if not self.event_id.strip() or len(self.event_id) > 64:
            msg = "event_id empty or exceeds bounds"
            raise ValueError(msg)
        # Secondary-only allegations cannot be FACT / ACTIVE official records.
        if self.evidence.authority_tier in {
            SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            SourceAuthorityTier.TIER_4_GENERAL_WEB,
        }:
            if self.information_class is InformationClass.FACT:
                msg = "secondary regulatory coverage cannot be classified as FACT"
                raise ValueError(msg)
            if self.status not in {
                RegulatoryStatus.ALLEGED,
                RegulatoryStatus.UNKNOWN,
            }:
                msg = "secondary regulatory coverage must be ALLEGED or UNKNOWN status"
                raise ValueError(msg)
        if (
            self.evidence.authority_tier is SourceAuthorityTier.TIER_1_AUTHORITATIVE
            and self.status is RegulatoryStatus.ALLEGED
            and self.information_class is InformationClass.FACT
        ):
            msg = "Tier-1 official FACT must not use ALLEGED status"
            raise ValueError(msg)
        published = self.published_at or self.evidence.published_at
        if published is not None and self.event_date > published:
            msg = "event_date must not be after published_at"
            raise ValueError(msg)
        if published is not None and published > self.evidence.retrieved_at.date():
            msg = "published_at must not be after retrieved_at date"
            raise ValueError(msg)

    def dedupe_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.company_id.as_text(),
            self.regulator.value,
            self.action_type.value,
            (self.case_reference or "").casefold(),
            self.event_date.isoformat(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "company_id": self.company_id.as_text(),
            "regulator": self.regulator.value,
            "jurisdiction": self.jurisdiction,
            "action_type": self.action_type.value,
            "status": self.status.value,
            "title": self.title,
            "summary": self.summary,
            "event_date": self.event_date.isoformat(),
            "published_at": (
                self.published_at.isoformat()
                if self.published_at is not None
                else (
                    self.evidence.published_at.isoformat()
                    if self.evidence.published_at is not None
                    else None
                )
            ),
            "case_reference": self.case_reference,
            "information_class": self.information_class.value,
            "evidence": self.evidence.to_dict(),
            "kind": "regulatory_event",
        }


def deduplicate_regulatory_events(
    events: tuple[RegulatoryEvent, ...],
) -> tuple[RegulatoryEvent, ...]:
    """Collapse exact regulatory keys; prefer higher authority then earlier retrieval.

    WITHDRAWN / AMENDED items sharing a case remain distinct when status differs.
    """

    winners: dict[tuple[str, str, str, str, str, str], RegulatoryEvent] = {}
    for event in events:
        key = (*event.dedupe_key(), event.status.value)
        existing = winners.get(key)
        if existing is None:
            winners[key] = event
            continue
        if int(event.evidence.authority_tier) < int(existing.evidence.authority_tier):
            winners[key] = event
            continue
        if int(event.evidence.authority_tier) > int(existing.evidence.authority_tier):
            continue
        if event.evidence.retrieved_at < existing.evidence.retrieved_at:
            winners[key] = event
    ordered = sorted(
        winners.values(),
        key=lambda e: (e.event_date.isoformat(), e.title.casefold(), e.event_id),
        reverse=True,
    )
    # Re-sort within date ascending title
    by_date: dict[str, list[RegulatoryEvent]] = {}
    for event in ordered:
        by_date.setdefault(event.event_date.isoformat(), []).append(event)
    result: list[RegulatoryEvent] = []
    for day in sorted(by_date.keys(), reverse=True):
        result.extend(sorted(by_date[day], key=lambda e: (e.title.casefold(), e.event_id)))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class CompanyRegulatoryPackage:
    """Normalized regulatory package for one company."""

    company_id: CompanyId
    retrieved_at: datetime
    events: tuple[RegulatoryEvent, ...] = ()
    provider_name: str = "fixture"
    availability: RegulatoryAvailability = RegulatoryAvailability.AVAILABLE
    data_origin: DataOrigin = DataOrigin.FIXTURE

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        object.__setattr__(self, "provider_name", self.provider_name.strip())
        for event in self.events:
            if event.company_id != self.company_id:
                msg = "regulatory event company_id must match package"
                raise ValueError(msg)
        object.__setattr__(self, "events", deduplicate_regulatory_events(self.events))
        if self.availability is RegulatoryAvailability.AVAILABLE and not self.events:
            msg = "AVAILABLE regulatory package requires at least one event"
            raise ValueError(msg)
        if self.data_origin is DataOrigin.UNAVAILABLE and self.events:
            msg = "UNAVAILABLE origin must not include events"
            raise ValueError(msg)

    def with_data_origin(self, origin: DataOrigin) -> CompanyRegulatoryPackage:
        return CompanyRegulatoryPackage(
            company_id=self.company_id,
            retrieved_at=self.retrieved_at,
            events=self.events,
            provider_name=self.provider_name,
            availability=self.availability,
            data_origin=origin,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "events": [event.to_dict() for event in self.events],
            "provider_name": self.provider_name,
            "availability": self.availability.value,
            "data_origin": self.data_origin.value,
            "event_count": len(self.events),
            "kind": "company_regulatory_package",
        }
