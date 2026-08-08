"""Evidence-aware task execution results (orchestration contracts)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId, ListingId, SecurityId
from financial_intelligence.domain.orchestration.tasks import TaskId
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId


class TaskResultStatus(StrEnum):
    """Outcome of executing one research task."""

    SUCCESS = "success"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class TaskEvidenceRef:
    """Lightweight evidence/provenance pointer for a task result."""

    company_id: CompanyId
    source_id: SourceId | None = None
    authority_tier: SourceAuthorityTier | None = None
    data_origin: DataOrigin | None = None
    security_id: SecurityId | None = None
    listing_id: ListingId | None = None
    as_of: datetime | None = None
    retrieved_at: datetime | None = None
    locator: str | None = None

    def __post_init__(self) -> None:
        for ts in (self.as_of, self.retrieved_at):
            if ts is not None and ts.tzinfo is None:
                msg = "evidence timestamps must be timezone-aware when set"
                raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "source_id": self.source_id.as_text() if self.source_id else None,
            "authority_tier": int(self.authority_tier) if self.authority_tier else None,
            "data_origin": self.data_origin.value if self.data_origin else None,
            "security_id": self.security_id.as_text() if self.security_id else None,
            "listing_id": self.listing_id.as_text() if self.listing_id else None,
            "as_of": self.as_of.isoformat().replace("+00:00", "Z") if self.as_of else None,
            "retrieved_at": (
                self.retrieved_at.isoformat().replace("+00:00", "Z") if self.retrieved_at else None
            ),
            "locator": self.locator,
            "kind": "task_evidence_ref",
        }


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    """Typed result of a capability execution attempt."""

    task_id: TaskId
    status: TaskResultStatus
    message: str
    evidence_refs: tuple[TaskEvidenceRef, ...] = ()
    output_summary: str | None = None
    retryable: bool = False
    error_code: str | None = None

    def __post_init__(self) -> None:
        msg = self.message.strip()
        if not msg or len(msg) > 1000:
            msg_err = "result message empty or exceeds bounds"
            raise ValueError(msg_err)
        object.__setattr__(self, "message", msg)
        if self.output_summary is not None:
            summary = self.output_summary.strip()
            if len(summary) > 2000:
                err = "output_summary exceeds bounds"
                raise ValueError(err)
            object.__setattr__(self, "output_summary", summary or None)
        if self.error_code is not None:
            code = self.error_code.strip().lower().replace(" ", "_")
            if not code or len(code) > 64:
                err = "error_code empty or exceeds bounds"
                raise ValueError(err)
            object.__setattr__(self, "error_code", code)
        if self.status in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL} and self.retryable:
            err = "successful/partial results must not be retryable"
            raise ValueError(err)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id.as_text(),
            "status": self.status.value,
            "message": self.message,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "output_summary": self.output_summary,
            "retryable": self.retryable,
            "error_code": self.error_code,
            "kind": "task_execution_result",
        }
