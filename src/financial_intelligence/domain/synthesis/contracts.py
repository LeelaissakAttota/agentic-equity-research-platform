"""Input contracts and vocabularies for deterministic research synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from financial_intelligence.domain.sources import validate_source_url
from financial_intelligence.domain.verification import (
    Claim,
    EvidenceBundle,
    EvidenceRef,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
)

_LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


class SynthesisStatus(StrEnum):
    """Overall completeness of a synthesis document."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class ResearchSectionType(StrEnum):
    """Stable research-section taxonomy for the Phase 9 foundation."""

    COMPANY_OVERVIEW = "company_overview"
    MARKET_CONTEXT = "market_context"
    FINANCIAL_PERFORMANCE = "financial_performance"
    NEWS_AND_EVENTS = "news_and_events"
    INDUSTRY_CONTEXT = "industry_context"
    COMPETITIVE_CONTEXT = "competitive_context"
    REGULATORY_CONTEXT = "regulatory_context"
    RISKS_AND_UNCERTAINTIES = "risks_and_uncertainties"


SECTION_ORDER: tuple[ResearchSectionType, ...] = tuple(ResearchSectionType)


class ClaimDisposition(StrEnum):
    """Presentation decision made by the verified-claim gate."""

    FACTUAL = "factual"
    QUALIFIED = "qualified"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"
    STALE = "stale"
    POLICY_EXCLUDED = "policy_excluded"


class ConfidenceLabel(StrEnum):
    """Presentation labels derived from the Phase 8 score and status."""

    HIGH = "high_confidence"
    MODERATE = "moderate_confidence"
    LOW = "low_confidence"
    CONFLICTING = "conflicting_evidence"
    INSUFFICIENT = "insufficient_evidence"
    CONTRADICTED = "contradicted"
    STALE = "stale"


class MissingDataReason(StrEnum):
    """Missing/uncertain states that must remain distinct."""

    UNAVAILABLE = "unavailable"
    NOT_REPORTED = "not_reported"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"
    UNRESOLVED = "unresolved"


class MaterialClaimKind(StrEnum):
    """Bounded material-claim taxonomy used by synthesis policy."""

    OTHER = "other"
    REVENUE = "revenue"
    EARNINGS = "earnings"
    MARGIN = "margin"
    VALUATION = "valuation"
    MARKET_PRICE = "market_price"
    MARKET_CHANGE = "market_change"
    REGULATORY_ACTION = "regulatory_action"
    MATERIAL_EVENT = "material_event"
    INDUSTRY_CLAIM = "industry_claim"
    COMPETITOR_CLAIM = "competitor_claim"


class FreshnessClassification(StrEnum):
    """Presentation freshness without rewriting Phase 8 verification state."""

    CURRENT = "current"
    HISTORICAL = "historical"
    STALE = "stale"
    UNSPECIFIED = "unspecified"


class OutputLanguage(StrEnum):
    """Languages supported by the presentation contract, not a translator."""

    ENGLISH = "en"
    TELUGU = "te"
    HINDI = "hi"


@dataclass(frozen=True, slots=True)
class LanguagePreference:
    """Bounded output-language and locale preference."""

    language_code: OutputLanguage = OutputLanguage.ENGLISH
    rendering_locale: str = "en-US"

    def __post_init__(self) -> None:
        locale = self.rendering_locale.strip()
        if not _LOCALE_RE.fullmatch(locale):
            raise ValueError("rendering_locale must use ll or ll-CC format")
        if not locale.startswith(self.language_code.value):
            raise ValueError("rendering_locale must match language_code")
        object.__setattr__(self, "rendering_locale", locale)

    def to_dict(self) -> dict[str, str]:
        return {
            "language_code": self.language_code.value,
            "rendering_locale": self.rendering_locale,
            "translation_status": "not_applied",
        }


@dataclass(frozen=True, slots=True)
class SynthesisId:
    """Deterministic synthesis identity derived from canonical inputs."""

    value: UUID

    @classmethod
    def from_components(
        cls,
        *,
        research_run_id: str,
        company_id: str,
        claim_ids: tuple[str, ...],
    ) -> SynthesisId:
        stable_key = "|".join((research_run_id, company_id, *sorted(claim_ids)))
        return cls(uuid5(NAMESPACE_URL, f"financial-intelligence/synthesis/{stable_key}"))

    def as_text(self) -> str:
        return str(self.value)


def _bounded_optional(value: str | None, *, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{label} empty or exceeds bounds")
    return normalized


@dataclass(frozen=True, slots=True)
class CitationSourceContext:
    """Optional source metadata not present in the Phase 8 evidence reference."""

    evidence_id: str
    source_id: str
    provider: str | None = None
    source_name: str | None = None
    url: str | None = None
    locator: str | None = None
    published_at: datetime | None = None
    reference_id: str | None = None
    company_id: str | None = None
    security_id: str | None = None
    listing_id: str | None = None

    def __post_init__(self) -> None:
        evidence_id = _bounded_optional(self.evidence_id, label="evidence_id", maximum=128)
        source_id = _bounded_optional(self.source_id, label="source_id", maximum=128)
        assert evidence_id is not None
        assert source_id is not None
        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(
            self, "provider", _bounded_optional(self.provider, label="provider", maximum=128)
        )
        object.__setattr__(
            self,
            "source_name",
            _bounded_optional(self.source_name, label="source_name", maximum=128),
        )
        object.__setattr__(self, "url", validate_source_url(self.url))
        object.__setattr__(
            self, "locator", _bounded_optional(self.locator, label="locator", maximum=512)
        )
        object.__setattr__(
            self,
            "reference_id",
            _bounded_optional(self.reference_id, label="reference_id", maximum=128),
        )
        object.__setattr__(
            self, "company_id", _bounded_optional(self.company_id, label="company_id", maximum=128)
        )
        object.__setattr__(
            self,
            "security_id",
            _bounded_optional(self.security_id, label="security_id", maximum=128),
        )
        object.__setattr__(
            self, "listing_id", _bounded_optional(self.listing_id, label="listing_id", maximum=128)
        )
        if self.listing_id is not None and self.security_id is None:
            raise ValueError("citation listing_id requires security_id")
        if self.security_id is not None and self.company_id is None:
            raise ValueError("citation security_id requires company_id")
        if self.published_at is not None and self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class VerifiedClaimInput:
    """A Phase 8 verified claim plus presentation and identity context."""

    claim: Claim
    evidence_bundle: EvidenceBundle
    verification: VerificationResult
    section: ResearchSectionType
    materiality: int = 2
    material_claim_kind: MaterialClaimKind = MaterialClaimKind.OTHER
    security_id: str | None = None
    listing_id: str | None = None
    missing_reason: MissingDataReason | None = None
    source_contexts: tuple[CitationSourceContext, ...] = ()

    def __post_init__(self) -> None:
        claim_id = self.claim.claim_id.as_text()
        if self.evidence_bundle.claim_id != claim_id:
            raise ValueError("evidence bundle does not belong to claim")
        if self.verification.claim_id != claim_id:
            raise ValueError("verification result does not belong to claim")
        if self.verification.evidence_bundle_id != self.evidence_bundle.claim_id:
            raise ValueError("verification result does not reference evidence bundle")
        classified = EvidenceBundle.classify(self.claim, self.evidence_bundle.evidence_refs)
        status = self.verification.status
        if (
            status
            in {
                VerificationStatus.VERIFIED,
                VerificationStatus.PARTIALLY_VERIFIED,
                VerificationStatus.STALE,
            }
            and not classified.supporting
        ):
            raise ValueError("verified or stale result requires supporting evidence")
        if status is VerificationStatus.CONTRADICTED and not classified.contradicting:
            raise ValueError("contradicted result requires contradicting evidence")
        if status is VerificationStatus.CONFLICTING and (
            not classified.supporting or not classified.contradicting
        ):
            raise ValueError("conflicting result requires supporting and contradicting evidence")
        recomputed = VerificationEngine().verify(
            self.claim,
            self.evidence_bundle,
            now=self.verification.verified_at,
        )
        if (
            recomputed.status is not self.verification.status
            or recomputed.confidence_score != self.verification.confidence_score
            or recomputed.confidence_factors != self.verification.confidence_factors
            or recomputed.score_version != self.verification.score_version
        ):
            raise ValueError("verification result does not match deterministic Phase 8 policy")
        if not 1 <= self.materiality <= 3:
            raise ValueError("materiality must be between 1 and 3")
        if self.listing_id is not None and self.security_id is None:
            raise ValueError("listing_id requires security_id")
        fingerprints = [
            self._evidence_fingerprint(ref) for ref in self.evidence_bundle.evidence_refs
        ]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("duplicate semantic evidence in evidence bundle")
        evidence_by_id = {ref.evidence_id: ref for ref in self.evidence_bundle.evidence_refs}
        for contradiction in self.verification.contradictions:
            referenced = contradiction.supporting_refs + contradiction.contradicting_refs
            if not set(referenced) <= set(evidence_by_id):
                raise ValueError("contradiction references evidence outside the bundle")
        context_ids = [context.evidence_id for context in self.source_contexts]
        if len(context_ids) != len(set(context_ids)):
            raise ValueError("duplicate citation source context")
        for context in self.source_contexts:
            evidence = evidence_by_id.get(context.evidence_id)
            if evidence is None:
                raise ValueError("citation source context references unknown evidence")
            if context.source_id != evidence.source_id:
                raise ValueError("citation source context source_id mismatch")
            if context.url is not None and evidence.url is not None and context.url != evidence.url:
                raise ValueError("citation source context URL mismatch")
            if context.company_id is not None and context.company_id != self.claim.company_id:
                raise ValueError("citation source context company_id mismatch")
            if context.security_id is not None and context.security_id != self.security_id:
                raise ValueError("citation source context security_id mismatch")
            if context.listing_id is not None and context.listing_id != self.listing_id:
                raise ValueError("citation source context listing_id mismatch")
        self._validate_material_claim()

    @staticmethod
    def _evidence_fingerprint(evidence: EvidenceRef) -> tuple[object, ...]:
        return (
            evidence.source_id,
            evidence.claim_type,
            str(evidence.extracted_value),
            evidence.extracted_unit,
            evidence.extracted_currency,
            evidence.extracted_period,
            evidence.as_of,
            evidence.url,
            evidence.raw_snippet,
        )

    def _validate_material_claim(self) -> None:
        if self.material_claim_kind is MaterialClaimKind.OTHER:
            return
        accepted = self.verification.status in {
            VerificationStatus.VERIFIED,
            VerificationStatus.PARTIALLY_VERIFIED,
            VerificationStatus.STALE,
        }
        if accepted and not self.evidence_bundle.evidence_refs:
            raise ValueError("accepted material claim requires evidence")
        if not accepted:
            return
        kind = self.material_claim_kind
        if kind in {MaterialClaimKind.REVENUE, MaterialClaimKind.EARNINGS} and (
            self.claim.expected_value is None
            or self.claim.expected_unit is None
            or self.claim.expected_currency is None
            or self.claim.expected_period is None
        ):
            raise ValueError(
                "accepted revenue or earnings claim requires value, unit, currency, period"
            )
        if kind in {MaterialClaimKind.MARGIN, MaterialClaimKind.VALUATION} and (
            self.claim.expected_value is None or self.claim.expected_unit is None
        ):
            raise ValueError("accepted margin or valuation claim requires value and unit")
        if kind is MaterialClaimKind.MARKET_PRICE and (
            self.claim.expected_value is None
            or self.claim.expected_currency is None
            or self.claim.expected_as_of is None
        ):
            raise ValueError("accepted market price claim requires value, currency, and as_of")
        if kind is MaterialClaimKind.MARKET_CHANGE and (
            self.claim.expected_value is None
            or self.claim.expected_unit is None
            or self.claim.expected_as_of is None
        ):
            raise ValueError("accepted market change claim requires value, unit, and as_of")

    @property
    def is_material(self) -> bool:
        return self.material_claim_kind is not MaterialClaimKind.OTHER

    @property
    def research_run_id(self) -> str:
        return self.claim.research_run_id
