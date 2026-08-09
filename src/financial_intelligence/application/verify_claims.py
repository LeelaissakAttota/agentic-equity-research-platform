"""Use case for verifying research claims."""

from __future__ import annotations

from dataclasses import dataclass

from financial_intelligence.application.verification_contracts import (
    VerifyClaimQuery,
    VerifyClaimResult,
)
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.domain.verification.evidence import EvidenceBundle


@dataclass(frozen=True, slots=True)
class VerifyClaimUseCase:
    """Verify a single claim against provided evidence."""

    engine: VerificationEngine

    def execute(self, query: VerifyClaimQuery) -> VerifyClaimResult:
        claim = query.claim
        evidence_refs = query.evidence_refs

        bundle = EvidenceBundle.classify(claim, evidence_refs)
        result = self.engine.verify(claim, bundle)

        return VerifyClaimResult.ok(result)
