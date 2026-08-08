"""Human approval contracts for research workflows (research-only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ApprovalStatus(StrEnum):
    """Explicit approval state — never inferred from absence of rejection."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ApprovalRequirement:
    """Whether a workflow must wait for human approval before execution."""

    required: bool
    reason: str

    def __post_init__(self) -> None:
        text = " ".join(self.reason.strip().split())
        if not text or len(text) > 512:
            msg = "approval reason empty or exceeds bounds"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in text):
            msg = "approval reason must not contain control characters"
            raise ValueError(msg)
        object.__setattr__(self, "reason", text)

    def to_dict(self) -> dict[str, object]:
        return {
            "required": self.required,
            "reason": self.reason,
            "kind": "approval_requirement",
        }


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """Recorded human approval decision."""

    status: ApprovalStatus
    decided_at: datetime
    note: str | None = None
    decision_source: str = "trusted_api"

    def __post_init__(self) -> None:
        if self.decided_at.tzinfo is None:
            msg = "decided_at must be timezone-aware"
            raise ValueError(msg)
        if self.status not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            msg = "decision status must be approved or rejected"
            raise ValueError(msg)
        source = " ".join(self.decision_source.strip().split())
        if not source or len(source) > 64:
            msg = "decision_source empty or exceeds bounds"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in source):
            msg = "decision_source must not contain control characters"
            raise ValueError(msg)
        object.__setattr__(self, "decision_source", source)
        if self.note is not None:
            note = " ".join(self.note.strip().split())
            if len(note) > 512:
                msg = "approval note exceeds bounds"
                raise ValueError(msg)
            if any(ord(ch) < 32 for ch in note):
                msg = "approval note must not contain control characters"
                raise ValueError(msg)
            object.__setattr__(self, "note", note or None)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "decided_at": self.decided_at.isoformat().replace("+00:00", "Z"),
            "note": self.note,
            "decision_source": self.decision_source,
            "kind": "approval_decision",
        }
