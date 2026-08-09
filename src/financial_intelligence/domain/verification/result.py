"""Verification result domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4


class VerificationStatus(StrEnum):
    """Overall verification status."""

    VERIFIED = "verified"  # Sufficient evidence supports the claim
    PARTIALLY_VERIFIED = "partially_verified"  # Some evidence supports, some missing
    CONTRADICTED = "contradicted"  # Evidence contradicts the claim
    CONFLICTING = "conflicting"  # Evidence both supports and contradicts
    UNVERIFIABLE = "unverifiable"  # Insufficient evidence to conclude
    STALE = "stale"  # Evidence exists but is outdated


class CriticAssessmentStatus(StrEnum):
    """Deterministic stop decision for the bounded critic cycle."""

    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    RESEARCH_REQUIRED = "research_required"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"


class ConfidenceFactor(StrEnum):
    """Factors contributing to confidence score."""

    SOURCE_AUTHORITY = "source_authority"  # Tier-1 > Tier-2 > Tier-3 > Tier-4
    EVIDENCE_RECENCY = "evidence_recency"  # More recent evidence = higher confidence
    EVIDENCE_CONSISTENCY = "evidence_consistency"  # Multiple sources agree
    EVIDENCE_COMPLETENESS = "evidence_completeness"  # All expected fields present
    NO_CONTRADICTIONS = "no_contradictions"  # No contradicting evidence found
    CROSS_SOURCE_AGREEMENT = "cross_source_agreement"  # Tier-1 and Tier-2 agree
    EXPLICIT_PERIOD_MATCH = "explicit_period_match"  # Period matches exactly
    EXPLICIT_UNIT_CURRENCY_MATCH = "explicit_unit_currency_match"  # Unit/currency match


@dataclass(frozen=True, slots=True)
class ContradictionRecord:
    """Record of a contradiction found during verification."""

    claim_id: str  # ClaimId as_text
    supporting_refs: tuple[str, ...]  # EvidenceRef IDs
    contradicting_refs: tuple[str, ...]  # EvidenceRef IDs
    description: str
    detected_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.detected_at is None:
            object.__setattr__(self, "detected_at", datetime.now(UTC))
        elif self.detected_at.tzinfo is None:
            raise ValueError("detected_at must be timezone-aware")
        desc = " ".join(self.description.strip().split())
        if not desc or len(desc) > 1000:
            raise ValueError("contradiction description empty or exceeds bounds")
        object.__setattr__(self, "description", desc)

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "supporting_refs": list(self.supporting_refs),
            "contradicting_refs": list(self.contradicting_refs),
            "description": self.description,
            "detected_at": self.detected_at.isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True, slots=True)
class CriticRequest:
    """Bounded targeted re-research request from critic."""

    request_id: str  # UUID as text
    claim_id: str  # ClaimId as_text
    reason: str
    suggested_capability: str  # e.g., "financials", "market", "news", "regulatory"
    suggested_query: str
    priority: int = 1  # 1=high, 2=medium, 3=low
    max_attempts: int = 2
    created_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(UTC))
        elif self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        reason = " ".join(self.reason.strip().split())
        if not reason or len(reason) > 500:
            raise ValueError("critic reason empty or exceeds bounds")
        object.__setattr__(self, "reason", reason)
        query = " ".join(self.suggested_query.strip().split())
        if not query or len(query) > 500:
            raise ValueError("critic query empty or exceeds bounds")
        object.__setattr__(self, "suggested_query", query)
        capability = " ".join(self.suggested_capability.strip().split())
        if not capability or len(capability) > 128:
            raise ValueError("critic capability empty or exceeds bounds")
        object.__setattr__(self, "suggested_capability", capability)
        if self.priority not in {1, 2, 3}:
            raise ValueError("critic priority must be 1, 2, or 3")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("critic max_attempts must be between 1 and 10")

    @classmethod
    def new(cls, claim_id: str, reason: str, capability: str, query: str) -> CriticRequest:
        return cls(
            request_id=str(uuid4()),
            claim_id=claim_id,
            reason=reason,
            suggested_capability=capability,
            suggested_query=query,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "claim_id": self.claim_id,
            "reason": self.reason,
            "suggested_capability": self.suggested_capability,
            "suggested_query": self.suggested_query,
            "priority": self.priority,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True, slots=True)
class CriticAssessment:
    """Bounded critic decision without executing re-research."""

    claim_id: str
    status: CriticAssessmentStatus
    attempts_used: int
    max_attempts: int
    requests: tuple[CriticRequest, ...] = ()

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ValueError("critic assessment claim_id must not be empty")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("critic assessment max_attempts must be between 1 and 10")
        if not 0 <= self.attempts_used <= self.max_attempts:
            raise ValueError("critic assessment attempts_used is outside the budget")
        if self.status == CriticAssessmentStatus.RESEARCH_REQUIRED:
            if self.attempts_used >= self.max_attempts or not self.requests:
                raise ValueError("research-required assessment needs budget and requests")
        elif self.requests:
            raise ValueError("terminal critic assessment must not contain requests")
        if (
            self.status == CriticAssessmentStatus.ATTEMPTS_EXHAUSTED
            and self.attempts_used != self.max_attempts
        ):
            raise ValueError("exhausted assessment must consume the attempt budget")

    @property
    def remaining_attempts(self) -> int:
        return self.max_attempts - self.attempts_used

    @property
    def should_research(self) -> bool:
        return self.status == CriticAssessmentStatus.RESEARCH_REQUIRED

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "attempts_used": self.attempts_used,
            "max_attempts": self.max_attempts,
            "remaining_attempts": self.remaining_attempts,
            "should_research": self.should_research,
            "requests": [request.to_dict() for request in self.requests],
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of verifying a claim against evidence."""

    claim_id: str  # ClaimId as_text
    status: VerificationStatus
    confidence_score: Decimal  # 0.0 to 1.0
    confidence_factors: tuple[ConfidenceFactor, ...]
    evidence_bundle_id: str  # EvidenceBundle claim_id
    contradictions: tuple[ContradictionRecord, ...]
    critic_requests: tuple[CriticRequest, ...]
    rationale: str
    score_version: str = "phase8-deterministic-v1"
    verified_at: datetime = None  # type: ignore[assignment]
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.verified_at is None:
            object.__setattr__(self, "verified_at", datetime.now(UTC))
        elif self.verified_at.tzinfo is None:
            raise ValueError("verified_at must be timezone-aware")
        if not Decimal("0") <= self.confidence_score <= Decimal("1"):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        rationale = " ".join(self.rationale.strip().split())
        if not rationale or len(rationale) > 2000:
            raise ValueError("rationale empty or exceeds bounds")
        object.__setattr__(self, "rationale", rationale)
        score_version = self.score_version.strip()
        if not score_version or len(score_version) > 128:
            raise ValueError("score_version empty or exceeds bounds")
        object.__setattr__(self, "score_version", score_version)

    @property
    def is_verified(self) -> bool:
        return self.status in {VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED}

    @property
    def has_contradictions(self) -> bool:
        return len(self.contradictions) > 0

    @property
    def needs_critic(self) -> bool:
        return self.status in {
            VerificationStatus.UNVERIFIABLE,
            VerificationStatus.CONFLICTING,
            VerificationStatus.STALE,
            VerificationStatus.CONTRADICTED,
        }

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "confidence_score": float(self.confidence_score),
            "score_version": self.score_version,
            "confidence_factors": [f.value for f in self.confidence_factors],
            "evidence_bundle_id": self.evidence_bundle_id,
            "contradictions": [c.to_dict() for c in self.contradictions],
            "critic_requests": [r.to_dict() for r in self.critic_requests],
            "rationale": self.rationale,
            "verified_at": self.verified_at.isoformat().replace("+00:00", "Z"),
            "is_verified": self.is_verified,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload
