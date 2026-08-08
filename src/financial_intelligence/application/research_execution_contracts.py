"""Application contracts for ExecuteResearchPlan (Phase 6 Prompt 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import CompanyQuery, ResolutionResult
from financial_intelligence.application.research_plan_contracts import CreateResearchPlanQuery
from financial_intelligence.domain.orchestration import (
    OrchestrationState,
    ResearchExecutionBudget,
    ResearchObjective,
    ResearchPlan,
    TaskEvidenceRef,
    TaskExecutionResult,
)


class ResearchExecutionStatus(StrEnum):
    """Outcome of a bounded research-plan execution."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ExecuteResearchPlanQuery:
    """Create-and-execute request (plans are not persisted).

    Semantics: resolve company → build deterministic plan → execute synchronously
    within budget. There is no plan-id lookup; each call creates a fresh plan.
    """

    company_query: CompanyQuery
    objective: ResearchObjective
    objective_text: str | None = None
    jurisdiction: str | None = None
    time_horizon_days: int | None = None
    budget: ResearchExecutionBudget | None = None

    def as_plan_query(self) -> CreateResearchPlanQuery:
        return CreateResearchPlanQuery(
            company_query=self.company_query,
            objective=self.objective,
            objective_text=self.objective_text,
            jurisdiction=self.jurisdiction,
            time_horizon_days=self.time_horizon_days,
        )


@dataclass(frozen=True, slots=True)
class ResearchExecutionResult:
    """Stable whole-run execution result (no investment conclusion)."""

    query: ExecuteResearchPlanQuery
    status: ResearchExecutionStatus
    message: str
    research_run_id: str | None = None
    plan_id: str | None = None
    plan: ResearchPlan | None = None
    orchestration: OrchestrationState | None = None
    task_results: tuple[TaskExecutionResult, ...] = ()
    evidence_refs: tuple[TaskEvidenceRef, ...] = ()
    warnings: tuple[str, ...] = ()
    completed_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    partial_count: int = 0
    skipped_count: int = 0
    resolution: ResolutionResult | None = None
    budget: ResearchExecutionBudget | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        for ts in (self.started_at, self.completed_at):
            if ts is not None and ts.tzinfo is None:
                msg = "execution timestamps must be timezone-aware"
                raise ValueError(msg)
        blocked = {
            ResearchExecutionStatus.RESOLUTION_BLOCKED,
            ResearchExecutionStatus.INVALID,
            ResearchExecutionStatus.UNAVAILABLE,
        }
        if self.status in blocked and self.plan is not None:
            msg = f"{self.status.value} results must not attach an executed plan"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
            "research_run_id": self.research_run_id,
            "plan_id": self.plan_id,
            "objective": self.query.objective.value,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "blocked_count": self.blocked_count,
            "partial_count": self.partial_count,
            "skipped_count": self.skipped_count,
            "warnings": list(self.warnings),
            "task_results": [r.to_dict() for r in self.task_results],
            "evidence_refs": [r.to_dict() for r in self.evidence_refs],
            "query": {
                "raw_query": self.query.company_query.raw_query,
                "country": (
                    self.query.company_query.country.as_text()
                    if self.query.company_query.country
                    else None
                ),
                "exchange": (
                    self.query.company_query.exchange.as_text()
                    if self.query.company_query.exchange
                    else None
                ),
                "ticker": (
                    self.query.company_query.ticker.as_text()
                    if self.query.company_query.ticker
                    else None
                ),
                "objective": self.query.objective.value,
                "objective_text": self.query.objective_text,
                "jurisdiction": self.query.jurisdiction,
                "time_horizon_days": self.query.time_horizon_days,
            },
            "kind": "research_execution_result",
            "idempotency_note": (
                "Within one execution state, a task is not re-executed unless an "
                "authorized retry transitions FAILED→READY. Distributed/API "
                "idempotency is not implemented; plans are not persisted."
            ),
        }
        if self.started_at is not None:
            payload["started_at"] = self.started_at.isoformat().replace("+00:00", "Z")
        if self.completed_at is not None:
            payload["completed_at"] = self.completed_at.isoformat().replace("+00:00", "Z")
        if self.plan is not None:
            payload["plan"] = self.plan.to_dict()
        if self.orchestration is not None:
            payload["orchestration"] = self.orchestration.to_dict()
        if self.resolution is not None:
            payload["resolution"] = {
                "status": self.resolution.status.value,
                "matched_by": self.resolution.matched_by.value,
                "confidence": self.resolution.confidence.value,
                "message": self.resolution.message,
                "company_id": (
                    self.resolution.company.company_id.as_text()
                    if self.resolution.company is not None
                    else None
                ),
            }
            if self.resolution.company is not None:
                payload["company"] = self.resolution.company.to_dict()
        if self.budget is not None:
            payload["budget"] = self.budget.to_dict()
        return payload
