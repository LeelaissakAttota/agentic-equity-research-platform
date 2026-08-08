"""Structured Research Memory — not vector/RAG/LLM memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.orchestration import TaskEvidenceRef
from financial_intelligence.domain.orchestration.tasks import TaskId
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.workflow.ids import WorkflowId


class MemoryRecordId:
    """Opaque memory record identity (UUIDv4)."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        if value.version != 4:
            msg = "memory record_id must be a UUIDv4"
            raise ValueError(msg)
        self._value = value

    @classmethod
    def new(cls) -> MemoryRecordId:
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> MemoryRecordId:
        return cls(UUID(raw))

    def as_text(self) -> str:
        return str(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MemoryRecordId) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class MemoryRecordStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ResearchMemoryRecord:
    """Deterministic structured memory of a completed workflow task outcome.

    Does not upgrade evidence authority or data_origin. Not semantic RAG memory.
    """

    record_id: MemoryRecordId
    workflow_id: WorkflowId
    research_run_id: ResearchRunId
    company_id: CompanyId
    capability: str
    task_id: TaskId
    status: MemoryRecordStatus
    summary: str
    created_at: datetime
    evidence_refs: tuple[TaskEvidenceRef, ...] = ()
    as_of: datetime | None = None
    data_origin: DataOrigin | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            msg = "memory created_at must be timezone-aware"
            raise ValueError(msg)
        if self.as_of is not None and self.as_of.tzinfo is None:
            msg = "memory as_of must be timezone-aware"
            raise ValueError(msg)
        cap = " ".join(self.capability.strip().split())
        if not cap or len(cap) > 128:
            msg = "capability empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "capability", cap)
        summary = " ".join(self.summary.strip().split())
        if not summary or len(summary) > 1000:
            msg = "summary empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "summary", summary)
        for ref in self.evidence_refs:
            if ref.company_id != self.company_id:
                msg = "memory evidence company_id mismatch"
                raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id.as_text(),
            "workflow_id": self.workflow_id.as_text(),
            "research_run_id": self.research_run_id.as_text(),
            "company_id": self.company_id.as_text(),
            "capability": self.capability,
            "task_id": self.task_id.as_text(),
            "status": self.status.value,
            "summary": self.summary,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "as_of": self.as_of.isoformat().replace("+00:00", "Z") if self.as_of else None,
            "data_origin": self.data_origin.value if self.data_origin else None,
            "evidence_refs": [r.to_dict() for r in self.evidence_refs],
            "kind": "research_memory_record",
        }
