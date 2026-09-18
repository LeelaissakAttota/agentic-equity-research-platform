"""ResearchOrchestrator — thin Manager/Orchestrator seam (incremental orchestration integration).

Establishes the boundary::

    ResearchRequest -> Manager/Orchestrator -> PlannerPort -> ResearchPlan
        -> existing workflow creation/execution mechanisms (same plan)

without reimplementing any part of the already-complete, production-wired
workflow engine (``CreateResearchWorkflow`` / ``ManageResearchWorkflow`` /
``ExecuteResearchPlan``). This class never touches ``ResearchWorkflowStorePort``
or any task/plan/workflow lifecycle transition directly — it only decides
whether to call the existing ``CreateResearchWorkflow`` use case, based on
whether ``PlannerPort`` produced a plan.

The ``ResearchPlan`` returned by ``PlannerPort`` is the plan that gets
persisted and executed: it is handed to ``CreateResearchWorkflow`` as a
``PreparedResearchPlan``, which short-circuits that use case's own
``CreateResearchPlan``/``DeterministicPlanner`` call. There is no second,
silently-discarding plan generation on this path. In this phase ``PlannerPort``
has no working implementation (see
``infrastructure.orchestration.UnavailablePlannerAdapter``), so the "planner
succeeded" branch is only exercised by tests using a fake planner.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from financial_intelligence.application.create_research_workflow import CreateResearchWorkflow
from financial_intelligence.application.orchestrator_contracts import (
    OrchestrateResearchRequestResult,
    OrchestrationOutcomeStatus,
)
from financial_intelligence.application.ports import PlannerPort
from financial_intelligence.application.workflow_contracts import (
    CreateResearchWorkflowQuery,
    PreparedResearchPlan,
    WorkflowOperationStatus,
)
from financial_intelligence.domain.orchestration import (
    PlannerOutcomeStatus,
    RequestId,
    ResearchRequest,
)
from financial_intelligence.domain.research_run import ResearchRunId


class ResearchOrchestrator:
    """Route a research request through PlannerPort before delegating to CreateResearchWorkflow."""

    def __init__(
        self,
        planner: PlannerPort,
        create_research_workflow: CreateResearchWorkflow,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._planner = planner
        self._create_workflow = create_research_workflow
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        query: CreateResearchWorkflowQuery,
        *,
        correlation_id: str | None = None,
    ) -> OrchestrateResearchRequestResult:
        now = self._clock()
        if now.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)

        try:
            request = ResearchRequest(
                request_id=RequestId.new(),
                research_run_id=ResearchRunId.new(created_at=now),
                objective=query.objective,
                raw_query=query.company_query.raw_query,
                created_at=now,
                country=query.company_query.country,
                exchange=query.company_query.exchange,
                ticker=query.company_query.ticker,
                objective_text=query.objective_text,
                jurisdiction=query.jurisdiction,
                time_horizon_days=query.time_horizon_days,
            )
        except ValueError as exc:
            return OrchestrateResearchRequestResult(
                status=OrchestrationOutcomeStatus.INVALID,
                message=str(exc),
                correlation_id=correlation_id,
                evaluated_at=now,
            )

        outcome = self._planner.create_plan(request)
        if outcome.status is PlannerOutcomeStatus.UNAVAILABLE:
            return OrchestrateResearchRequestResult(
                status=OrchestrationOutcomeStatus.PLANNER_UNAVAILABLE,
                message=outcome.message,
                planner_outcome=outcome,
                correlation_id=correlation_id,
                evaluated_at=now,
            )
        if outcome.status is not PlannerOutcomeStatus.OK:
            return OrchestrateResearchRequestResult(
                status=OrchestrationOutcomeStatus.PLANNER_FAILED,
                message=outcome.message,
                planner_outcome=outcome,
                correlation_id=correlation_id,
                evaluated_at=now,
            )

        assert outcome.plan is not None
        prepared_plan = PreparedResearchPlan(plan=outcome.plan, request=request)
        workflow_result = self._create_workflow.execute(query, prepared_plan=prepared_plan)
        if workflow_result.status is not WorkflowOperationStatus.OK:
            return OrchestrateResearchRequestResult(
                status=OrchestrationOutcomeStatus.WORKFLOW_FAILED,
                message=workflow_result.message,
                planner_outcome=outcome,
                workflow_result=workflow_result,
                correlation_id=correlation_id,
                evaluated_at=now,
            )
        return OrchestrateResearchRequestResult(
            status=OrchestrationOutcomeStatus.OK,
            message="workflow created after planner-approved request",
            planner_outcome=outcome,
            workflow_result=workflow_result,
            correlation_id=correlation_id,
            evaluated_at=now,
        )
