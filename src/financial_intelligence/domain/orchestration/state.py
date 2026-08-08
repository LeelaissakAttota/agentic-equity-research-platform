"""Per-research-run orchestration state (no global mutable state)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from financial_intelligence.domain.orchestration.plan import ResearchPlan
from financial_intelligence.domain.orchestration.results import TaskExecutionResult
from financial_intelligence.domain.orchestration.tasks import TaskStatus
from financial_intelligence.domain.research_run import ResearchRunId


class OrchestrationStatus(StrEnum):
    """High-level orchestration run status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass(frozen=True, slots=True)
class OrchestrationState:
    """Isolated orchestration snapshot for one research run."""

    research_run_id: ResearchRunId
    plan: ResearchPlan
    started_at: datetime
    updated_at: datetime
    results: tuple[TaskExecutionResult, ...] = ()
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    total_attempts: int = 0
    external_calls: int = 0
    warnings: tuple[str, ...] = ()
    terminal_reason: str | None = None

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None or self.updated_at.tzinfo is None:
            msg = "orchestration timestamps must be timezone-aware"
            raise ValueError(msg)
        if self.plan.research_run_id.as_text() != self.research_run_id.as_text():
            msg = "orchestration state research_run_id must match plan"
            raise ValueError(msg)
        if self.total_attempts < 0 or self.external_calls < 0:
            msg = "attempt counters must be non-negative"
            raise ValueError(msg)

    @property
    def completed_task_ids(self) -> tuple[str, ...]:
        return tuple(
            t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.SUCCEEDED
        )

    @property
    def failed_task_ids(self) -> tuple[str, ...]:
        return tuple(t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.FAILED)

    @property
    def blocked_task_ids(self) -> tuple[str, ...]:
        return tuple(t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.BLOCKED)

    @property
    def skipped_task_ids(self) -> tuple[str, ...]:
        return tuple(t.task_id.as_text() for t in self.plan.tasks if t.status is TaskStatus.SKIPPED)

    def with_updated_plan(self, plan: ResearchPlan, *, updated_at: datetime) -> OrchestrationState:
        return replace(self, plan=plan, updated_at=updated_at)

    def with_result(
        self, result: TaskExecutionResult, *, updated_at: datetime
    ) -> OrchestrationState:
        return replace(self, results=(*self.results, result), updated_at=updated_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "research_run_id": self.research_run_id.as_text(),
            "plan_id": self.plan.plan_id.as_text(),
            "status": self.status.value,
            "plan": self.plan.to_dict(),
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z"),
            "completed_tasks": list(self.completed_task_ids),
            "failed_tasks": list(self.failed_task_ids),
            "blocked_tasks": list(self.blocked_task_ids),
            "skipped_tasks": list(self.skipped_task_ids),
            "total_attempts": self.total_attempts,
            "external_calls": self.external_calls,
            "warnings": list(self.warnings),
            "terminal_reason": self.terminal_reason,
            "results": [r.to_dict() for r in self.results],
            "kind": "orchestration_state",
        }
