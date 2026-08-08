"""Phase 6 orchestration domain — research plan."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.orchestration.graph import (
    dependency_edges,
    topological_order,
    validate_task_graph,
)
from financial_intelligence.domain.orchestration.objectives import ResearchObjective
from financial_intelligence.domain.orchestration.tasks import ResearchTask
from financial_intelligence.domain.research_run import ResearchRunId

PLANNER_VERSION = "phase6-deterministic-v1"


class PlanStatus(StrEnum):
    """Plan lifecycle (Prompt 1 creates plans; execution is later)."""

    DRAFT = "draft"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PlanId:
    """Opaque research-plan identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "plan_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> PlanId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> PlanId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    """Immutable dependency-ordered research plan."""

    plan_id: PlanId
    research_run_id: ResearchRunId
    objective: ResearchObjective
    company_id: CompanyId
    tasks: tuple[ResearchTask, ...]
    created_at: datetime
    planner_version: str = PLANNER_VERSION
    status: PlanStatus = PlanStatus.READY

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            msg = "created_at must be timezone-aware"
            raise ValueError(msg)
        if not self.planner_version.strip():
            msg = "planner_version is required"
            raise ValueError(msg)
        if not self.tasks:
            msg = "research plan requires at least one task"
            raise ValueError(msg)
        validate_task_graph(self.tasks)
        ordered = topological_order(self.tasks)
        object.__setattr__(self, "tasks", ordered)

    @property
    def dependencies(self) -> tuple[tuple[str, str], ...]:
        return dependency_edges(self.tasks)

    def with_tasks(
        self,
        tasks: tuple[ResearchTask, ...],
        *,
        status: PlanStatus | None = None,
    ) -> ResearchPlan:
        """Return a plan copy with replaced tasks (revalidated/topo-ordered)."""

        return replace(self, tasks=tasks, status=status if status is not None else self.status)

    def with_status(self, status: PlanStatus) -> ResearchPlan:
        return replace(self, status=status)

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id.as_text(),
            "research_run_id": self.research_run_id.as_text(),
            "objective": self.objective.value,
            "company_id": self.company_id.as_text(),
            "tasks": [task.to_dict() for task in self.tasks],
            "dependencies": [{"depends_on": a, "task_id": b} for a, b in self.dependencies],
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "planner_version": self.planner_version,
            "status": self.status.value,
            "task_count": len(self.tasks),
            "kind": "research_plan",
        }
