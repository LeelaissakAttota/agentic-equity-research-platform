"""Claim domain models for verification."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class ClaimType(StrEnum):
    """Type of claim being verified."""

    FACTUAL = "factual"  # e.g., "Apple filed 10-K on 2025-11-01"
    NUMERIC = "numeric"  # e.g., "Revenue was $394.3B"
    DATE = "date"  # e.g., "Fiscal year ended 2025-09-27"
    SOURCE_AUTHORITY = "source_authority"  # e.g., "SEC is Tier-1 for Apple filings"


class ClaimStatus(StrEnum):
    """Verification outcome for a claim."""

    VERIFIED = "verified"  # Evidence supports the claim
    CONTRADICTED = "contradicted"  # Evidence contradicts the claim
    UNVERIFIABLE = "unverifiable"  # Insufficient evidence either way
    CONFLICTING = "conflicting"  # Evidence both supports and contradicts
    STALE = "stale"  # Claim may have been true but evidence is outdated


@dataclass(frozen=True, slots=True)
class ClaimId:
    """Opaque claim identity."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            raise ValueError("claim_id must be a UUIDv4")

    @classmethod
    def new(cls) -> ClaimId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> ClaimId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Claim:
    """A verifiable claim extracted from research."""

    claim_id: ClaimId
    claim_type: ClaimType
    text: str
    company_id: str  # CompanyId as_text
    research_run_id: str  # ResearchRunId as_text
    task_id: str | None = None  # TaskId as_text if applicable
    expected_value: str | Decimal | datetime | None = None
    expected_unit: str | None = None
    expected_currency: str | None = None
    expected_period: str | None = None
    expected_as_of: datetime | None = None
    created_at: datetime = None  # type: ignore[assignment]
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(UTC))
        elif self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if isinstance(self.expected_value, datetime) and self.expected_value.tzinfo is None:
            raise ValueError("datetime expected_value must be timezone-aware")
        if self.expected_as_of is not None and self.expected_as_of.tzinfo is None:
            raise ValueError("expected_as_of must be timezone-aware")
        text = " ".join(self.text.strip().split())
        if not text or len(text) > 5000:
            raise ValueError("claim text empty or exceeds bounds")
        object.__setattr__(self, "text", text)

    def with_expected_value(self, value: str | Decimal | datetime) -> Claim:
        return replace(self, expected_value=value)

    def with_expected_context(
        self,
        *,
        unit: str | None = None,
        currency: str | None = None,
        period: str | None = None,
        as_of: datetime | None = None,
    ) -> Claim:
        return replace(
            self,
            expected_unit=unit,
            expected_currency=currency,
            expected_period=period,
            expected_as_of=as_of,
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "claim_id": self.claim_id.as_text(),
            "claim_type": self.claim_type.value,
            "text": self.text,
            "company_id": self.company_id,
            "research_run_id": self.research_run_id,
            "status": "pending",
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
        }
        if self.task_id is not None:
            payload["task_id"] = self.task_id
        if self.expected_value is not None:
            payload["expected_value"] = str(self.expected_value)
        if self.expected_unit is not None:
            payload["expected_unit"] = self.expected_unit
        if self.expected_currency is not None:
            payload["expected_currency"] = self.expected_currency
        if self.expected_period is not None:
            payload["expected_period"] = self.expected_period
        if self.expected_as_of is not None:
            payload["expected_as_of"] = self.expected_as_of.isoformat().replace("+00:00", "Z")
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload
