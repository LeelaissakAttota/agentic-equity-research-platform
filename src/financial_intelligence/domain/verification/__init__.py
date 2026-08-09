"""Verification domain — Phase 8 Prompt 1 foundation."""

from financial_intelligence.domain.verification.claim import (
    Claim,
    ClaimId,
    ClaimStatus,
    ClaimType,
)
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.domain.verification.evidence import (
    EvidenceBundle,
    EvidenceRef,
)
from financial_intelligence.domain.verification.result import (
    ConfidenceFactor,
    ContradictionRecord,
    CriticAssessment,
    CriticAssessmentStatus,
    CriticRequest,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    "Claim",
    "ClaimId",
    "ClaimStatus",
    "ClaimType",
    "ConfidenceFactor",
    "ContradictionRecord",
    "CriticAssessment",
    "CriticAssessmentStatus",
    "CriticRequest",
    "EvidenceBundle",
    "EvidenceRef",
    "VerificationEngine",
    "VerificationResult",
    "VerificationStatus",
]
