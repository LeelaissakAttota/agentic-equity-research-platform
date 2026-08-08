"""Industry & competitor intelligence domain models (Phase 5 foundation).

Competitor peers must link to canonical CompanyIdentity when resolved.
Unresolved peers remain explicit — never silently guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.news.events import EventEvidenceRef, InformationClass
from financial_intelligence.domain.sources import SourceAuthorityTier

_LABEL_MAX = 128
_CODE_MAX = 64
_NAME_MAX = 256


class IndustryTaxonomySource(StrEnum):
    """Where an industry label came from — never invent free-form LLM industries."""

    REFERENCE = "reference"
    PROVIDER = "provider"
    UNMAPPED = "unmapped"


class PeerResolutionState(StrEnum):
    """Whether a competitor peer maps to canonical CompanyIdentity."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class RelationshipDirection(StrEnum):
    BIDIRECTIONAL = "bidirectional"
    DIRECTIONAL = "directional"


class IndustryAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class IndustryClassification:
    """Reference-backed industry classification for one company."""

    company_id: CompanyId
    canonical_code: str | None
    canonical_label: str | None
    provider_label: str | None
    taxonomy_source: IndustryTaxonomySource
    evidence: EventEvidenceRef
    information_class: InformationClass = InformationClass.FACT

    def __post_init__(self) -> None:
        if self.taxonomy_source is IndustryTaxonomySource.UNMAPPED:
            if self.canonical_code is not None or self.canonical_label is not None:
                msg = "UNMAPPED classification must not invent canonical industry fields"
                raise ValueError(msg)
        else:
            if not self.canonical_code or not self.canonical_label:
                msg = "mapped industry classification requires canonical_code and label"
                raise ValueError(msg)
            code = self.canonical_code.strip().lower()
            label = self.canonical_label.strip()
            if not code or len(code) > _CODE_MAX or " " in code:
                msg = "canonical_code empty, has spaces, or exceeds bounds"
                raise ValueError(msg)
            if not label or len(label) > _LABEL_MAX:
                msg = "canonical_label empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "canonical_code", code)
            object.__setattr__(self, "canonical_label", label)
        if self.provider_label is not None:
            raw = self.provider_label.strip()
            if not raw or len(raw) > _LABEL_MAX:
                msg = "provider_label empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "provider_label", raw)
        if (
            self.evidence.authority_tier is SourceAuthorityTier.TIER_4_GENERAL_WEB
            and self.information_class is InformationClass.FACT
        ):
            msg = "Tier-4 general web cannot classify industry as FACT"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "canonical_code": self.canonical_code,
            "canonical_label": self.canonical_label,
            "provider_label": self.provider_label,
            "taxonomy_source": self.taxonomy_source.value,
            "information_class": self.information_class.value,
            "evidence": self.evidence.to_dict(),
            "kind": "industry_classification",
        }


@dataclass(frozen=True, slots=True)
class CompetitorRelationship:
    """Evidence-backed competitor/peer relationship (canonical identity when known)."""

    subject_company_id: CompanyId
    peer_display_name: str
    peer_resolution: PeerResolutionState
    evidence: EventEvidenceRef
    as_of: date
    peer_company_id: CompanyId | None = None
    direction: RelationshipDirection = RelationshipDirection.BIDIRECTIONAL
    information_class: InformationClass = InformationClass.RESEARCH_FINDING

    def __post_init__(self) -> None:
        name = " ".join(self.peer_display_name.strip().split())
        if not name or len(name) > _NAME_MAX:
            msg = "peer_display_name empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "peer_display_name", name)
        if self.peer_resolution is PeerResolutionState.RESOLVED:
            if self.peer_company_id is None:
                msg = "RESOLVED peer requires peer_company_id"
                raise ValueError(msg)
            if self.peer_company_id == self.subject_company_id:
                msg = "company cannot compete with itself"
                raise ValueError(msg)
        else:
            if self.peer_company_id is not None:
                msg = "unresolved/ambiguous peer must not attach a canonical peer_company_id"
                raise ValueError(msg)
        if self.information_class is InformationClass.FACT and (
            self.evidence.authority_tier is SourceAuthorityTier.TIER_4_GENERAL_WEB
        ):
            msg = "Tier-4 cannot support FACT competitor relationships"
            raise ValueError(msg)

    def relationship_key(self) -> tuple[str, str]:
        """Deterministic identity for duplicate peer collapse."""

        peer = (
            self.peer_company_id.as_text()
            if self.peer_company_id is not None
            else f"name:{self.peer_display_name.casefold()}"
        )
        return (self.subject_company_id.as_text(), peer)

    def to_dict(self) -> dict[str, object]:
        return {
            "subject_company_id": self.subject_company_id.as_text(),
            "peer_company_id": (
                self.peer_company_id.as_text() if self.peer_company_id is not None else None
            ),
            "peer_display_name": self.peer_display_name,
            "peer_resolution": self.peer_resolution.value,
            "direction": self.direction.value,
            "as_of": self.as_of.isoformat(),
            "information_class": self.information_class.value,
            "evidence": self.evidence.to_dict(),
            "kind": "competitor_relationship",
        }


def deduplicate_competitor_relationships(
    relationships: tuple[CompetitorRelationship, ...],
) -> tuple[CompetitorRelationship, ...]:
    """Collapse duplicate peer keys; prefer higher authority then earlier retrieval."""

    winners: dict[tuple[str, str], CompetitorRelationship] = {}
    for rel in relationships:
        key = rel.relationship_key()
        existing = winners.get(key)
        if existing is None:
            winners[key] = rel
            continue
        if int(rel.evidence.authority_tier) < int(existing.evidence.authority_tier):
            winners[key] = rel
            continue
        if int(rel.evidence.authority_tier) > int(existing.evidence.authority_tier):
            continue
        if rel.evidence.retrieved_at < existing.evidence.retrieved_at:
            winners[key] = rel
    ordered = sorted(
        winners.values(),
        key=lambda r: (r.peer_display_name.casefold(), r.as_of.isoformat()),
    )
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class CompanyIndustryPackage:
    """Industry context + competitor relationships for one company."""

    company_id: CompanyId
    retrieved_at: datetime
    industry: IndustryClassification | None = None
    competitors: tuple[CompetitorRelationship, ...] = ()
    provider_name: str = "fixture"
    availability: IndustryAvailability = IndustryAvailability.AVAILABLE
    data_origin: DataOrigin = DataOrigin.FIXTURE

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        if not self.provider_name.strip():
            msg = "provider_name is required"
            raise ValueError(msg)
        object.__setattr__(self, "provider_name", self.provider_name.strip())
        if self.industry is not None and self.industry.company_id != self.company_id:
            msg = "industry classification company_id must match package"
            raise ValueError(msg)
        for rel in self.competitors:
            if rel.subject_company_id != self.company_id:
                msg = "competitor subject_company_id must match package"
                raise ValueError(msg)
        if self.availability is IndustryAvailability.AVAILABLE and (
            self.industry is None and not self.competitors
        ):
            msg = "AVAILABLE industry package requires industry or competitors"
            raise ValueError(msg)
        if self.data_origin is DataOrigin.UNAVAILABLE and (
            self.industry is not None or self.competitors
        ):
            msg = "UNAVAILABLE origin must not include industry payload"
            raise ValueError(msg)
        object.__setattr__(
            self,
            "competitors",
            deduplicate_competitor_relationships(self.competitors),
        )

    def with_data_origin(self, origin: DataOrigin) -> CompanyIndustryPackage:
        return CompanyIndustryPackage(
            company_id=self.company_id,
            retrieved_at=self.retrieved_at,
            industry=self.industry,
            competitors=self.competitors,
            provider_name=self.provider_name,
            availability=self.availability,
            data_origin=origin,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "industry": self.industry.to_dict() if self.industry is not None else None,
            "competitors": [c.to_dict() for c in self.competitors],
            "provider_name": self.provider_name,
            "availability": self.availability.value,
            "data_origin": self.data_origin.value,
            "competitor_count": len(self.competitors),
            "kind": "company_industry_package",
        }
