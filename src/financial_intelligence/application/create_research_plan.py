"""CreateResearchPlan use case — Phase 6 planning foundation (no execution)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import (
    ResolutionStatus,
)
from financial_intelligence.application.ports import PlannerPort
from financial_intelligence.application.research_plan_contracts import (
    CreateResearchPlanQuery,
    CreateResearchPlanResult,
    ResearchPlanStatus,
)
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.orchestration import (
    PlannerOutcomeStatus,
    RequestId,
    ResearchExecutionBudget,
    ResearchRequest,
)
from financial_intelligence.domain.research_run import ResearchRunId

# Fixed message a ``PlannerPort`` uses to report that a plan exceeded the research
# execution budget. ``PlannerOutcomeStatus`` has no dedicated budget member, so this
# shared constant is how ``CreateResearchPlan`` keeps ``BUDGET_EXCEEDED`` distinct
# from other planner failures.
PLANNER_BUDGET_EXCEEDED_MESSAGE = "plan exceeds the research execution budget"

_PLAN_MISMATCH_MESSAGE = "planner returned a plan that does not match the request"


class CreateResearchPlan:
    """Validate request, resolve company, obtain a plan from the planner — do not execute."""

    def __init__(
        self,
        resolve_company: ResolveCompany,
        planner: PlannerPort,
        *,
        budget: ResearchExecutionBudget | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._resolve_company = resolve_company
        self._planner = planner
        self._budget = budget or ResearchExecutionBudget()
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, query: CreateResearchPlanQuery) -> CreateResearchPlanResult:
        evaluated_at = self._clock()
        if evaluated_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)

        research_run_id = ResearchRunId.new(created_at=evaluated_at)
        try:
            request = ResearchRequest(
                request_id=RequestId.new(),
                research_run_id=research_run_id,
                objective=query.objective,
                raw_query=query.company_query.raw_query,
                created_at=evaluated_at,
                country=query.company_query.country,
                exchange=query.company_query.exchange,
                ticker=query.company_query.ticker,
                objective_text=query.objective_text,
                jurisdiction=query.jurisdiction,
                time_horizon_days=query.time_horizon_days,
            )
        except ValueError as exc:
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.INVALID,
                message=str(exc),
                evaluated_at=evaluated_at,
            )

        resolution = self._resolve_company.execute(query.company_query)
        if resolution.status is ResolutionStatus.INVALID:
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.INVALID,
                message=resolution.message or "invalid company query",
                request=request,
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if resolution.status is not ResolutionStatus.RESOLVED:
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.RESOLUTION_BLOCKED,
                message="research plan withheld until company identity is uniquely resolved",
                request=request,
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        assert resolution.company is not None
        outcome = self._planner.create_plan(request)
        if outcome.status is PlannerOutcomeStatus.INVALID:
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.INVALID,
                message=outcome.message,
                request=request,
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if outcome.status is PlannerOutcomeStatus.FAILED and (
            outcome.message == PLANNER_BUDGET_EXCEEDED_MESSAGE
        ):
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.BUDGET_EXCEEDED,
                message=outcome.message,
                request=request,
                resolution=resolution,
                budget=self._budget,
                evaluated_at=evaluated_at,
            )
        plan = outcome.plan
        if outcome.status is not PlannerOutcomeStatus.OK or plan is None:
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.UNAVAILABLE,
                message=outcome.message,
                request=request,
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        # Fail closed: whatever planner produced it, the plan must belong to the company
        # this use case resolved and to the research run it prepared.
        if (
            plan.company_id != resolution.company.company_id
            or plan.research_run_id != research_run_id
        ):
            return CreateResearchPlanResult(
                query=query,
                status=ResearchPlanStatus.UNAVAILABLE,
                message=_PLAN_MISMATCH_MESSAGE,
                request=request,
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        return CreateResearchPlanResult(
            query=query,
            status=ResearchPlanStatus.OK,
            message="research plan created (not executed)",
            request=request,
            plan=plan,
            resolution=resolution,
            budget=self._budget,
            evaluated_at=evaluated_at,
        )
