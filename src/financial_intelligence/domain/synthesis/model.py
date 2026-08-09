"""Structured output models for deterministic research synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.verification import ConfidenceFactor, VerificationStatus

from .contracts import (
    ClaimDisposition,
    ConfidenceLabel,
    FreshnessClassification,
    LanguagePreference,
    MaterialClaimKind,
    MissingDataReason,
    ResearchSectionType,
    SynthesisId,
    SynthesisStatus,
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


@dataclass(frozen=True, slots=True)
class ConfidenceContext:
    claim_id: str
    score: Decimal
    score_version: str
    label: ConfidenceLabel
    factors: tuple[ConfidenceFactor, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "score": float(self.score),
            "score_version": self.score_version,
            "label": self.label.value,
            "factors": [factor.value for factor in self.factors],
        }


@dataclass(frozen=True, slots=True)
class ContradictionContext:
    contradiction_id: str
    claim_id: str
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    description: str
    detected_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "contradiction_id": self.contradiction_id,
            "claim_id": self.claim_id,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "description": self.description,
            "detected_at": _iso(self.detected_at),
        }


@dataclass(frozen=True, slots=True)
class MissingDataContext:
    claim_id: str
    reason: MissingDataReason
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"claim_id": self.claim_id, "reason": self.reason.value, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class FreshnessContext:
    claim_id: str
    classification: FreshnessClassification
    as_of: datetime | None
    assessed_at: datetime
    policy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "classification": self.classification.value,
            "as_of": _iso(self.as_of),
            "assessed_at": _iso(self.assessed_at),
            "policy": self.policy,
        }


@dataclass(frozen=True, slots=True)
class CitationReference:
    citation_id: str
    section: ResearchSectionType
    claim_id: str
    evidence_id: str
    source_id: str
    authority_tier: int
    data_origin: str
    provider: str | None
    source_name: str | None
    url: str | None
    locator: str | None
    published_at: datetime | None
    retrieved_at: datetime
    as_of: datetime | None
    reference_id: str | None
    company_id: str
    security_id: str | None
    listing_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "citation_id": self.citation_id,
            "section": self.section.value,
            "claim_id": self.claim_id,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "authority_tier": self.authority_tier,
            "data_origin": self.data_origin,
            "provider": self.provider,
            "source_name": self.source_name,
            "url": self.url,
            "locator": self.locator,
            "published_at": _iso(self.published_at),
            "retrieved_at": _iso(self.retrieved_at),
            "as_of": _iso(self.as_of),
            "reference_id": self.reference_id,
            "company_id": self.company_id,
            "security_id": self.security_id,
            "listing_id": self.listing_id,
        }


@dataclass(frozen=True, slots=True)
class ResearchClaim:
    claim_id: str
    company_id: str
    research_run_id: str
    section: ResearchSectionType
    rendered_text: str
    disposition: ClaimDisposition
    verification_status: VerificationStatus
    confidence: ConfidenceContext
    citation_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    material_claim_kind: MaterialClaimKind
    freshness: FreshnessContext
    security_id: str | None = None
    listing_id: str | None = None
    expected_value: str | None = None
    unit: str | None = None
    currency: str | None = None
    reporting_period: str | None = None
    as_of: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "company_id": self.company_id,
            "security_id": self.security_id,
            "listing_id": self.listing_id,
            "research_run_id": self.research_run_id,
            "section": self.section.value,
            "text": self.rendered_text,
            "disposition": self.disposition.value,
            "verification_status": self.verification_status.value,
            "confidence": self.confidence.to_dict(),
            "citation_ids": list(self.citation_ids),
            "contradiction_ids": list(self.contradiction_ids),
            "material_claim_kind": self.material_claim_kind.value,
            "freshness": self.freshness.to_dict(),
            "structured_value": {
                "value": self.expected_value,
                "unit": self.unit,
                "currency": self.currency,
                "reporting_period": self.reporting_period,
                "as_of": _iso(self.as_of),
            },
        }


@dataclass(frozen=True, slots=True)
class ResearchSection:
    section_type: ResearchSectionType
    title: str
    claims: tuple[ResearchClaim, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "section_type": self.section_type.value,
            "title": self.title,
            "claims": [claim.to_dict() for claim in self.claims],
        }


@dataclass(frozen=True, slots=True)
class ExecutiveSummaryItem:
    claim_id: str
    text: str
    disposition: ClaimDisposition
    confidence_label: ConfidenceLabel
    citation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "disposition": self.disposition.value,
            "confidence_label": self.confidence_label.value,
            "citation_ids": list(self.citation_ids),
        }


@dataclass(frozen=True, slots=True)
class ExecutiveSummary:
    items: tuple[ExecutiveSummaryItem, ...]
    max_items: int
    method: str = "phase9-deterministic-materiality-v1"

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "max_items": self.max_items,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class ResearchDocument:
    title: str
    sections: tuple[ResearchSection, ...]
    executive_summary: ExecutiveSummary
    confidence_contexts: tuple[ConfidenceContext, ...]
    contradictions: tuple[ContradictionContext, ...]
    missing_data: tuple[MissingDataContext, ...]
    citations: tuple[CitationReference, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "sections": [section.to_dict() for section in self.sections],
            "executive_summary": self.executive_summary.to_dict(),
            "confidence_contexts": [context.to_dict() for context in self.confidence_contexts],
            "contradictions": [context.to_dict() for context in self.contradictions],
            "missing_data": [context.to_dict() for context in self.missing_data],
            "citations": [citation.to_dict() for citation in self.citations],
        }


@dataclass(frozen=True, slots=True)
class ResearchSynthesis:
    synthesis_id: SynthesisId
    research_run_id: str
    status: SynthesisStatus
    company: CompanyIdentity
    document: ResearchDocument
    language: LanguagePreference
    generated_at: datetime

    def to_dict(self) -> dict[str, object]:
        document = self.document.to_dict()
        return {
            "synthesis_id": self.synthesis_id.as_text(),
            "research_run_id": self.research_run_id,
            "status": self.status.value,
            "company": self.company.to_dict(),
            "language": self.language.to_dict(),
            "generated_at": _iso(self.generated_at),
            **document,
            "kind": "research_synthesis",
        }
