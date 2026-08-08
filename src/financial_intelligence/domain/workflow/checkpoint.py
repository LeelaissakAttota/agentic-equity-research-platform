"""Deterministic workflow checkpoint (not semantic research memory)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from financial_intelligence.domain.orchestration import (
    ResearchPlan,
    TaskEvidenceRef,
    TaskExecutionResult,
)
from financial_intelligence.domain.orchestration.tasks import TaskStatus
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.workflow.ids import WorkflowId


@dataclass(frozen=True, slots=True)
class WorkflowCheckpoint:
    """Snapshot of workflow execution progress for pause/resume continuity.

    Checkpoint state is control/audit data — not vector/semantic Research Memory.
    """

    workflow_id: WorkflowId
    research_run_id: ResearchRunId
    version: int
    plan: ResearchPlan
    created_at: datetime
    total_attempts: int = 0
    external_calls: int = 0
    warnings: tuple[str, ...] = ()
    task_results: tuple[TaskExecutionResult, ...] = ()
    evidence_refs: tuple[TaskEvidenceRef, ...] = ()
    message: str = "checkpoint"

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            msg = "checkpoint created_at must be timezone-aware"
            raise ValueError(msg)
        if self.version < 1:
            msg = "checkpoint version must be >= 1"
            raise ValueError(msg)
        if self.total_attempts < 0 or self.external_calls < 0:
            msg = "attempt counters must be non-negative"
            raise ValueError(msg)
        if self.plan.research_run_id.as_text() != self.research_run_id.as_text():
            msg = "checkpoint research_run_id must match plan"
            raise ValueError(msg)
        text = " ".join(self.message.strip().split())
        if not text or len(text) > 1000:
            msg = "checkpoint message empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "message", text)

    @property
    def completed_task_ids(self) -> tuple[str, ...]:
        return tuple(
            t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.SUCCEEDED
        )

    @property
    def pending_task_ids(self) -> tuple[str, ...]:
        return tuple(
            t.task_id.as_text()
            for t in self.plan.tasks
            if t.status in {TaskStatus.PENDING, TaskStatus.READY}
        )

    @property
    def failed_task_ids(self) -> tuple[str, ...]:
        return tuple(t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.FAILED)

    @property
    def blocked_task_ids(self) -> tuple[str, ...]:
        return tuple(t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.BLOCKED)

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id.as_text(),
            "research_run_id": self.research_run_id.as_text(),
            "version": self.version,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "total_attempts": self.total_attempts,
            "external_calls": self.external_calls,
            "warnings": list(self.warnings),
            "completed_task_ids": list(self.completed_task_ids),
            "pending_task_ids": list(self.pending_task_ids),
            "failed_task_ids": list(self.failed_task_ids),
            "blocked_task_ids": list(self.blocked_task_ids),
            "task_results": [r.to_dict() for r in self.task_results],
            "evidence_refs": [r.to_dict() for r in self.evidence_refs],
            "message": self.message,
            "plan": self.plan.to_dict(),
            "kind": "workflow_checkpoint",
        }
