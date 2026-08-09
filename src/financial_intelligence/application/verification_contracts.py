"""Application contracts for verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from financial_intelligence.domain.verification.claim import Claim
from financial_intelligence.domain.verification.evidence import EvidenceRef
from financial_intelligence.domain.verification.result import VerificationResult


@dataclass(frozen=True, slots=True)
class VerifyClaimQuery:
    """Query to verify a single claim."""

    claim: Claim
    evidence_refs: tuple[EvidenceRef, ...]


@dataclass(frozen=True, slots=True)
class VerificationOperationStatus:
    """Status of a verification operation."""

    OK = "ok"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class VerifyClaimResult:
    """Result of verifying a claim."""

    status: str
    verification: VerificationResult | None = None
    error_message: str | None = None

    @classmethod
    def ok(cls, verification: VerificationResult) -> VerifyClaimResult:
        return cls(status=VerificationOperationStatus.OK, verification=verification)

    @classmethod
    def not_found(cls, message: str) -> VerifyClaimResult:
        return cls(status=VerificationOperationStatus.NOT_FOUND, error_message=message)

    @classmethod
    def invalid(cls, message: str) -> VerifyClaimResult:
        return cls(status=VerificationOperationStatus.INVALID, error_message=message)

    @classmethod
    def conflict(cls, message: str) -> VerifyClaimResult:
        return cls(status=VerificationOperationStatus.CONFLICT, error_message=message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status}
        if self.verification is not None:
            payload["verification"] = self.verification.to_dict()
        if self.error_message is not None:
            payload["error"] = self.error_message
        return payload
