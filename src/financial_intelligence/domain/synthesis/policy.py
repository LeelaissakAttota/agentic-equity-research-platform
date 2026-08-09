"""Deterministic verified-claim gate, section assembler, and summary policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.verification import (
    EvidenceBundle,
    EvidenceRef,
    VerificationStatus,
)

from .contracts import (
    SECTION_ORDER,
    ClaimDisposition,
    ConfidenceLabel,
    FreshnessClassification,
    LanguagePreference,
    MaterialClaimKind,
    MissingDataReason,
    ResearchSectionType,
    SynthesisId,
    SynthesisStatus,
    VerifiedClaimInput,
)
from .model import (
    CitationReference,
    ConfidenceContext,
    ContradictionContext,
    ExecutiveSummary,
    ExecutiveSummaryItem,
    FreshnessContext,
    MissingDataContext,
    ResearchClaim,
    ResearchDocument,
    ResearchSection,
    ResearchSynthesis,
)

_ADVICE_PATTERN = re.compile(
    r"\b(?:buy|sell|hold)\b|price\s+target|portfolio\s+allocation|investment\s+instruction|"
    r"guaranteed\s+returns?|\bwill\s+(?:rise|fall|go\s+up|go\s+down)\b",
    re.IGNORECASE,
)
_SECTION_TITLES: dict[ResearchSectionType, str] = {
    ResearchSectionType.COMPANY_OVERVIEW: "Company Overview",
    ResearchSectionType.MARKET_CONTEXT: "Market Intelligence",
    ResearchSectionType.FINANCIAL_PERFORMANCE: "Financial Performance and Health",
    ResearchSectionType.NEWS_AND_EVENTS: "News and Events",
    ResearchSectionType.INDUSTRY_CONTEXT: "Industry Context",
    ResearchSectionType.COMPETITIVE_CONTEXT: "Competitive Context",
    ResearchSectionType.REGULATORY_CONTEXT: "Regulatory Context",
    ResearchSectionType.RISKS_AND_UNCERTAINTIES: "Risks and Uncertainties",
}


@dataclass(frozen=True, slots=True)
class GatedClaim:
    claim: ResearchClaim
    citations: tuple[CitationReference, ...]
    contradictions: tuple[ContradictionContext, ...]
    missing: MissingDataContext | None
    materiality: int


@dataclass(frozen=True, slots=True)
class VerifiedClaimGate:
    """Convert a Phase 8 result into presentation-safe structured output."""

    high_confidence_threshold: Decimal = Decimal("0.8")
    moderate_confidence_threshold: Decimal = Decimal("0.6")

    def evaluate(
        self,
        item: VerifiedClaimInput,
        company: CompanyIdentity,
        *,
        generated_at: datetime | None = None,
    ) -> GatedClaim:
        if generated_at is None:
            generated_at = item.verification.verified_at
        self._validate_identity(item, company)
        status = item.verification.status
        freshness = self._freshness(item, generated_at)
        label = self.confidence_label(status, item.verification.confidence_score)
        disposition, rendered_text = self._render(item, freshness)
        if freshness.classification is FreshnessClassification.STALE:
            label = ConfidenceLabel.STALE
        contexts = {context.evidence_id: context for context in item.source_contexts}
        citation_refs = self._citation_evidence(item)
        citations = tuple(
            CitationReference(
                citation_id=f"CIT-{item.claim.claim_id.as_text()}-{ref.evidence_id}",
                section=item.section,
                claim_id=item.claim.claim_id.as_text(),
                evidence_id=ref.evidence_id,
                source_id=ref.source_id,
                authority_tier=int(ref.authority_tier),
                data_origin=ref.data_origin.value,
                provider=(
                    contexts[ref.evidence_id].provider if ref.evidence_id in contexts else None
                ),
                source_name=(
                    contexts[ref.evidence_id].source_name if ref.evidence_id in contexts else None
                ),
                url=(
                    contexts[ref.evidence_id].url
                    if ref.evidence_id in contexts and contexts[ref.evidence_id].url is not None
                    else ref.url
                ),
                locator=(
                    contexts[ref.evidence_id].locator if ref.evidence_id in contexts else None
                ),
                published_at=(
                    contexts[ref.evidence_id].published_at if ref.evidence_id in contexts else None
                ),
                retrieved_at=ref.retrieved_at,
                as_of=ref.as_of,
                reference_id=(
                    contexts[ref.evidence_id].reference_id if ref.evidence_id in contexts else None
                ),
                company_id=item.claim.company_id,
                security_id=item.security_id,
                listing_id=item.listing_id,
            )
            for ref in citation_refs
        )
        evidence_ids = {ref.evidence_id for ref in item.evidence_bundle.evidence_refs}
        contradictions = tuple(
            ContradictionContext(
                contradiction_id=f"CON-{record.claim_id}-{index}",
                claim_id=record.claim_id,
                supporting_evidence_ids=record.supporting_refs,
                contradicting_evidence_ids=record.contradicting_refs,
                description=record.description,
                detected_at=record.detected_at,
            )
            for index, record in enumerate(item.verification.contradictions, 1)
        )
        for context in contradictions:
            if not set(context.supporting_evidence_ids + context.contradicting_evidence_ids) <= (
                evidence_ids
            ):
                raise ValueError("contradiction references evidence outside the bundle")
        confidence = ConfidenceContext(
            claim_id=item.claim.claim_id.as_text(),
            score=item.verification.confidence_score,
            score_version=item.verification.score_version,
            label=label,
            factors=item.verification.confidence_factors,
        )
        missing = self._missing_context(item, disposition)
        research_claim = ResearchClaim(
            claim_id=item.claim.claim_id.as_text(),
            company_id=item.claim.company_id,
            security_id=item.security_id,
            listing_id=item.listing_id,
            research_run_id=item.claim.research_run_id,
            section=item.section,
            rendered_text=rendered_text,
            disposition=disposition,
            verification_status=status,
            confidence=confidence,
            citation_ids=tuple(citation.citation_id for citation in citations),
            contradiction_ids=tuple(context.contradiction_id for context in contradictions),
            material_claim_kind=item.material_claim_kind,
            freshness=freshness,
            expected_value=(
                str(item.claim.expected_value) if item.claim.expected_value is not None else None
            ),
            unit=item.claim.expected_unit,
            currency=item.claim.expected_currency,
            reporting_period=item.claim.expected_period,
            as_of=item.claim.expected_as_of,
        )
        return GatedClaim(
            claim=research_claim,
            citations=citations,
            contradictions=contradictions,
            missing=missing,
            materiality=item.materiality,
        )

    def _validate_identity(self, item: VerifiedClaimInput, company: CompanyIdentity) -> None:
        if item.claim.company_id != company.company_id.as_text():
            raise ValueError("claim company_id does not match resolved company")
        securities = {security.security_id.as_text(): security for security in company.securities}
        if item.security_id is not None and item.security_id not in securities:
            raise ValueError("claim security_id does not belong to resolved company")
        if item.listing_id is not None:
            security = securities[item.security_id or ""]
            listing_ids = {listing.listing_id.as_text() for listing in security.listings}
            if item.listing_id not in listing_ids:
                raise ValueError("claim listing_id does not belong to claim security")

    def confidence_label(self, status: VerificationStatus, score: Decimal) -> ConfidenceLabel:
        """Return a label from Phase 8 status/score without aggregating confidence."""
        if status is VerificationStatus.CONFLICTING:
            return ConfidenceLabel.CONFLICTING
        if status is VerificationStatus.CONTRADICTED:
            return ConfidenceLabel.CONTRADICTED
        if status is VerificationStatus.STALE:
            return ConfidenceLabel.STALE
        if status is VerificationStatus.UNVERIFIABLE:
            return ConfidenceLabel.INSUFFICIENT
        if score >= self.high_confidence_threshold:
            return ConfidenceLabel.HIGH
        if score >= self.moderate_confidence_threshold:
            return ConfidenceLabel.MODERATE
        return ConfidenceLabel.LOW

    def _render(
        self,
        item: VerifiedClaimInput,
        freshness: FreshnessContext,
    ) -> tuple[ClaimDisposition, str]:
        claim_id = item.claim.claim_id.as_text()
        if _ADVICE_PATTERN.search(item.claim.text):
            return (
                ClaimDisposition.POLICY_EXCLUDED,
                f"Claim {claim_id} was excluded by the research-only, no-advice policy.",
            )
        if item.is_material and not self._material_authority_is_sufficient(item):
            return (
                ClaimDisposition.INSUFFICIENT,
                f"Insufficient authoritative evidence for material claim: {item.claim.text}",
            )
        status = item.verification.status
        if freshness.classification is FreshnessClassification.STALE:
            as_of = item.claim.expected_as_of
            qualifier = f" as of {as_of.date().isoformat()}" if as_of is not None else ""
            return ClaimDisposition.STALE, f"Evidence is stale{qualifier}: {item.claim.text}"
        if status is VerificationStatus.VERIFIED:
            return ClaimDisposition.FACTUAL, item.claim.text
        if status is VerificationStatus.PARTIALLY_VERIFIED:
            return ClaimDisposition.QUALIFIED, f"Partially verified: {item.claim.text}"
        if status is VerificationStatus.CONFLICTING:
            return ClaimDisposition.CONFLICT, f"Sources disagree regarding: {item.claim.text}"
        if status is VerificationStatus.CONTRADICTED:
            return (
                ClaimDisposition.CONTRADICTED,
                f"Available evidence contradicts: {item.claim.text}",
            )
        if status is VerificationStatus.STALE:
            as_of = item.claim.expected_as_of
            qualifier = f" as of {as_of.date().isoformat()}" if as_of is not None else ""
            return ClaimDisposition.STALE, f"Evidence is stale{qualifier}: {item.claim.text}"
        return (
            ClaimDisposition.INSUFFICIENT,
            f"Insufficient evidence to verify: {item.claim.text}",
        )

    @staticmethod
    def _material_authority_is_sufficient(item: VerifiedClaimInput) -> bool:
        classified = EvidenceBundle.classify(item.claim, item.evidence_bundle.evidence_refs)
        if not classified.supporting:
            return False
        maximum_tier = (
            SourceAuthorityTier.TIER_3_REPUTABLE_NEWS
            if item.material_claim_kind
            in {
                MaterialClaimKind.MATERIAL_EVENT,
                MaterialClaimKind.INDUSTRY_CLAIM,
                MaterialClaimKind.COMPETITOR_CLAIM,
            }
            else SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL
        )
        return any(ref.authority_tier <= maximum_tier for ref in classified.supporting)

    def _freshness(self, item: VerifiedClaimInput, generated_at: datetime) -> FreshnessContext:
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        as_of = item.claim.expected_as_of
        kind = item.material_claim_kind
        if as_of is not None and as_of > generated_at:
            raise ValueError("claim as_of cannot be after synthesis generation time")
        if item.verification.status is VerificationStatus.STALE:
            classification = FreshnessClassification.STALE
            policy = "phase8-verification-status"
        elif kind in {MaterialClaimKind.MARKET_PRICE, MaterialClaimKind.MARKET_CHANGE}:
            if as_of is None:
                classification = FreshnessClassification.STALE
                policy = "market-currentness-as-of-required"
            elif generated_at - as_of > timedelta(days=1):
                classification = FreshnessClassification.STALE
                policy = "market-currentness-24h"
            else:
                classification = FreshnessClassification.CURRENT
                policy = "market-currentness-24h"
        elif kind in {
            MaterialClaimKind.REVENUE,
            MaterialClaimKind.EARNINGS,
            MaterialClaimKind.MARGIN,
            MaterialClaimKind.VALUATION,
        } and (item.claim.expected_period is not None or as_of is not None):
            classification = FreshnessClassification.HISTORICAL
            policy = "historical-financial-period"
        else:
            classification = FreshnessClassification.UNSPECIFIED
            policy = "phase8-status-only"
        return FreshnessContext(
            claim_id=item.claim.claim_id.as_text(),
            classification=classification,
            as_of=as_of,
            assessed_at=generated_at,
            policy=policy,
        )

    def _citation_evidence(self, item: VerifiedClaimInput) -> tuple[EvidenceRef, ...]:
        bundle = item.evidence_bundle
        status = item.verification.status
        if status in {
            VerificationStatus.VERIFIED,
            VerificationStatus.PARTIALLY_VERIFIED,
            VerificationStatus.STALE,
        }:
            return bundle.supporting
        if status is VerificationStatus.CONFLICTING:
            return bundle.supporting + bundle.contradicting
        if status is VerificationStatus.CONTRADICTED:
            return bundle.contradicting
        return bundle.evidence_refs

    def _missing_context(
        self, item: VerifiedClaimInput, disposition: ClaimDisposition
    ) -> MissingDataContext | None:
        reason = item.missing_reason
        if reason is None:
            reason = {
                ClaimDisposition.CONFLICT: MissingDataReason.CONFLICTING,
                ClaimDisposition.INSUFFICIENT: MissingDataReason.INSUFFICIENT_EVIDENCE,
                ClaimDisposition.CONTRADICTED: MissingDataReason.UNRESOLVED,
                ClaimDisposition.STALE: MissingDataReason.STALE,
                ClaimDisposition.POLICY_EXCLUDED: MissingDataReason.NOT_APPLICABLE,
            }.get(disposition)
        if reason is None:
            return None
        return MissingDataContext(
            claim_id=item.claim.claim_id.as_text(),
            reason=reason,
            detail=f"Claim retained with {reason.value} semantics; no value was fabricated.",
        )


@dataclass(frozen=True, slots=True)
class DeterministicSynthesisAssembler:
    """Create stable sections and a bounded traceable summary without an LLM."""

    gate: VerifiedClaimGate = VerifiedClaimGate()
    max_summary_items: int = 5

    def __post_init__(self) -> None:
        if not 1 <= self.max_summary_items <= 10:
            raise ValueError("max_summary_items must be between 1 and 10")

    def assemble(
        self,
        *,
        company: CompanyIdentity,
        verified_claims: tuple[VerifiedClaimInput, ...],
        language: LanguagePreference,
        generated_at: datetime,
    ) -> ResearchSynthesis:
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not verified_claims or len(verified_claims) > 100:
            raise ValueError("synthesis requires between 1 and 100 verified claims")
        run_ids = {item.research_run_id for item in verified_claims}
        if len(run_ids) != 1:
            raise ValueError("all synthesis claims must share one research_run_id")
        claim_ids = tuple(item.claim.claim_id.as_text() for item in verified_claims)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("duplicate claim_id in synthesis request")
        order = {section: index for index, section in enumerate(SECTION_ORDER)}
        ordered_inputs = sorted(
            verified_claims,
            key=lambda item: (order[item.section], item.materiality, item.claim.claim_id.as_text()),
        )
        gated = tuple(
            self.gate.evaluate(item, company, generated_at=generated_at) for item in ordered_inputs
        )
        sections = tuple(
            ResearchSection(
                section_type=section_type,
                title=_SECTION_TITLES[section_type],
                claims=tuple(item.claim for item in gated if item.claim.section is section_type),
            )
            for section_type in SECTION_ORDER
            if any(item.claim.section is section_type for item in gated)
        )
        summary_candidates = sorted(
            (
                item
                for item in gated
                if item.claim.disposition is not ClaimDisposition.POLICY_EXCLUDED
            ),
            key=self._summary_sort_key,
        )
        summary = ExecutiveSummary(
            items=tuple(
                ExecutiveSummaryItem(
                    claim_id=item.claim.claim_id,
                    text=item.claim.rendered_text,
                    disposition=item.claim.disposition,
                    confidence_label=item.claim.confidence.label,
                    citation_ids=item.claim.citation_ids,
                )
                for item in summary_candidates[: self.max_summary_items]
            ),
            max_items=self.max_summary_items,
        )
        confidence_contexts = tuple(item.claim.confidence for item in gated)
        contradictions = tuple(context for item in gated for context in item.contradictions)
        missing_data = tuple(item.missing for item in gated if item.missing is not None)
        citations = tuple(
            sorted(
                (citation for item in gated for citation in item.citations),
                key=lambda citation: citation.citation_id,
            )
        )
        status = self._status(gated)
        research_run_id = next(iter(run_ids))
        synthesis_id = SynthesisId.from_components(
            research_run_id=research_run_id,
            company_id=company.company_id.as_text(),
            claim_ids=claim_ids,
        )
        document = ResearchDocument(
            title=f"Research Synthesis — {company.display_name}",
            sections=sections,
            executive_summary=summary,
            confidence_contexts=confidence_contexts,
            contradictions=contradictions,
            missing_data=missing_data,
            citations=citations,
        )
        return ResearchSynthesis(
            synthesis_id=synthesis_id,
            research_run_id=research_run_id,
            status=status,
            company=company,
            document=document,
            language=language,
            generated_at=generated_at,
        )

    @staticmethod
    def _summary_sort_key(item: GatedClaim) -> tuple[int, int, Decimal, str]:
        disposition_group = {
            ClaimDisposition.FACTUAL: 0,
            ClaimDisposition.CONFLICT: 1,
            ClaimDisposition.CONTRADICTED: 1,
            ClaimDisposition.STALE: 2,
            ClaimDisposition.INSUFFICIENT: 2,
            ClaimDisposition.QUALIFIED: 3,
            ClaimDisposition.POLICY_EXCLUDED: 4,
        }[item.claim.disposition]
        return (
            disposition_group,
            item.materiality,
            -item.claim.confidence.score,
            item.claim.claim_id,
        )

    @staticmethod
    def _status(gated: tuple[GatedClaim, ...]) -> SynthesisStatus:
        dispositions = {item.claim.disposition for item in gated}
        factual = {ClaimDisposition.FACTUAL, ClaimDisposition.QUALIFIED}
        if dispositions <= factual:
            return SynthesisStatus.COMPLETE
        if dispositions & factual:
            return SynthesisStatus.PARTIAL
        return SynthesisStatus.INSUFFICIENT
