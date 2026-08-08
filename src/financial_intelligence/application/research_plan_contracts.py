"""Application contracts for CreateResearchPlan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionResult,
)
from financial_intelligence.domain.orchestration import (
    ResearchExecutionBudget,
    ResearchObjective,
    ResearchPlan,
    ResearchRequest,
)


class ResearchPlanStatus(StrEnum):
    """Outcome of a plan-creation request."""

    OK = "ok"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"
    BUDGET_EXCEEDED = "budget_exceeded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CreateResearchPlanQuery:
    """HTTP/application input for plan creation."""

    company_query: CompanyQuery
    objective: ResearchObjective
    objective_text: str | None = None
    jurisdiction: str | None = None
    time_horizon_days: int | None = None


@dataclass(frozen=True, slots=True)
class CreateResearchPlanResult:
    """Traceable plan-creation result (does not execute the plan)."""

    query: CreateResearchPlanQuery
    status: ResearchPlanStatus
    message: str
    request: ResearchRequest | None = None
    plan: ResearchPlan | None = None
    resolution: ResolutionResult | None = None
    budget: ResearchExecutionBudget | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        blocked = {
            ResearchPlanStatus.RESOLUTION_BLOCKED,
            ResearchPlanStatus.INVALID,
            ResearchPlanStatus.BUDGET_EXCEEDED,
            ResearchPlanStatus.UNAVAILABLE,
        }
        if self.status in blocked and self.plan is not None:
            msg = f"{self.status.value} results must not attach a plan"
            raise ValueError(msg)
        if self.status is ResearchPlanStatus.OK and self.plan is None:
            msg = "ok results require a research plan"
            raise ValueError(msg)
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            msg = "evaluated_at must be timezone-aware"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
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
            "research_run_id": (
                self.plan.research_run_id.as_text() if self.plan is not None else None
            ),
            "plan_id": self.plan.plan_id.as_text() if self.plan is not None else None,
            "planner_version": (self.plan.planner_version if self.plan is not None else None),
            "objective": self.query.objective.value,
            "tasks": (
                [task.to_dict() for task in self.plan.tasks] if self.plan is not None else []
            ),
            "dependencies": (
                [{"depends_on": a, "task_id": b} for a, b in self.plan.dependencies]
                if self.plan is not None
                else []
            ),
        }
        if self.evaluated_at is not None:
            payload["evaluated_at"] = self.evaluated_at.isoformat().replace("+00:00", "Z")
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
        if self.plan is not None:
            payload["plan"] = self.plan.to_dict()
        if self.request is not None:
            payload["request"] = self.request.to_dict()
        if self.budget is not None:
            payload["budget"] = self.budget.to_dict()
        return payload
