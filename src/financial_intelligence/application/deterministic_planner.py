"""Deterministic research planner (no LLM)."""

from __future__ import annotations

from datetime import datetime

from financial_intelligence.application.capability_registry import CapabilityRegistry
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.orchestration import (
    PLANNER_VERSION,
    PlanId,
    PlanStatus,
    ResearchExecutionBudget,
    ResearchObjective,
    ResearchPlan,
    ResearchTask,
    TaskId,
    TaskStatus,
    TaskType,
)
from financial_intelligence.domain.research_run import ResearchRunId

# Objective -> ordered capability ids (company_resolution is performed before planning).
_OBJECTIVE_CAPABILITIES: dict[ResearchObjective, tuple[str, ...]] = {
    ResearchObjective.COMPANY_OVERVIEW: (
        "market_intelligence",
        "financial_intelligence",
        "news_event_intelligence",
    ),
    ResearchObjective.MARKET_ANALYSIS: ("market_intelligence",),
    ResearchObjective.FINANCIAL_ANALYSIS: ("financial_intelligence",),
    ResearchObjective.NEWS_AND_EVENTS: ("news_event_intelligence",),
    ResearchObjective.INDUSTRY_ANALYSIS: ("industry_intelligence",),
    ResearchObjective.REGULATORY_ANALYSIS: ("regulatory_intelligence",),
    ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH: (
        "market_intelligence",
        "financial_intelligence",
        "news_event_intelligence",
        "industry_intelligence",
        "regulatory_intelligence",
    ),
}


class DeterministicPlanner:
    """Build a dependency-aware ResearchPlan without model calls.

    Same inputs produce structurally equivalent plans (stable task types,
    priorities, and dependency topology). Task UUIDs are fresh per plan.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        budget: ResearchExecutionBudget | None = None,
    ) -> None:
        self._registry = registry
        self._budget = budget or ResearchExecutionBudget()

    @property
    def planner_version(self) -> str:
        return PLANNER_VERSION

    def build_plan(
        self,
        *,
        research_run_id: ResearchRunId,
        objective: ResearchObjective,
        company_id: CompanyId,
        created_at: datetime,
    ) -> ResearchPlan:
        capability_ids = _OBJECTIVE_CAPABILITIES[objective]
        tasks: list[ResearchTask] = []
        for index, capability_id in enumerate(capability_ids):
            cap = self._registry.require(capability_id)
            if cap.availability.value == "unavailable":
                continue
            # Comprehensive: financial depends on market (diamond-friendly chain).
            deps: tuple[TaskId, ...] = ()
            if (
                objective is ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH
                and capability_id == "financial_intelligence"
                and tasks
            ):
                market = next(
                    (t for t in tasks if t.task_type is TaskType.MARKET_INTELLIGENCE),
                    None,
                )
                if market is not None:
                    deps = (market.task_id,)
            tasks.append(
                ResearchTask(
                    task_id=TaskId.new(),
                    task_type=cap.task_type,
                    capability_id=cap.capability_id,
                    description=cap.description,
                    dependencies=deps,
                    status=TaskStatus.PENDING,
                    priority=10 + index * 10,
                    required=True,
                    attempt_count=0,
                    max_attempts=1,
                    created_at=created_at,
                )
            )
        task_tuple = tuple(tasks)
        self._budget.validate_tasks(task_tuple)
        return ResearchPlan(
            plan_id=PlanId.new(),
            research_run_id=research_run_id,
            objective=objective,
            company_id=company_id,
            tasks=task_tuple,
            created_at=created_at,
            planner_version=self.planner_version,
            status=PlanStatus.READY,
        )
