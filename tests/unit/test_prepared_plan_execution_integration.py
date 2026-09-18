"""Integration regression: prepared-plan origin does not break execution.

Closes MEDIUM finding #1 from the Phase 5 audit: a workflow created through
``ResearchOrchestrator``'s prepared-plan path (a ``PlannerPort`` supplying a
``ResearchPlan`` directly, bypassing ``CreateResearchPlan``/
``DeterministicPlanner``) had no test proving it can then be handed to the
existing ``ManageResearchWorkflow.execute`` lifecycle/execution path and
actually run to completion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.research_orchestrator import ResearchOrchestrator
from financial_intelligence.application.workflow_contracts import (
    CreateResearchWorkflowQuery,
    WorkflowOperationStatus,
)
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import ExchangeCode
from financial_intelligence.domain.orchestration import (
    PLANNER_VERSION,
    PlanId,
    PlannerOutcome,
    PlannerOutcomeStatus,
    PlanStatus,
    ResearchObjective,
    ResearchPlan,
    ResearchTask,
    TaskId,
    TaskType,
)
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.workflow import WorkflowStatus


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _clock() -> datetime:
    # Matches the known-fresh fixture timestamp used by the existing golden
    # workflow tests (tests/unit/test_research_workflows.py) so market-data
    # freshness checks succeed and the workflow can reach COMPLETED.
    return datetime(2026, 8, 8, 17, 0, tzinfo=UTC)


class _FakePlanner:
    """Test-only PlannerPort implementation — not production intelligence."""

    def __init__(self, outcome: PlannerOutcome) -> None:
        self._outcome = outcome

    def create_plan(self, request: object) -> PlannerOutcome:
        del request
        return self._outcome


class PreparedPlanReachesExecutionPathTests(TestCase):
    def test_prepared_plan_workflow_executes_through_manage_research_workflow(self) -> None:
        """A prepared-plan workflow runs through the unmodified execution engine.

        The plan is supplied by a fake ``PlannerPort`` (never by
        ``CreateResearchPlan``/``DeterministicPlanner``) with a distinctive
        description marker, carries the resolved company's real identity, and
        uses the ``market_intelligence`` capability that
        ``Phase6CapabilityExecutor`` can dispatch successfully. If the
        prepared-plan origin broke anything downstream (a missing field, an
        identity mismatch against company resolution, an incompatible task
        shape), this would surface as a non-OK/non-COMPLETED result below
        rather than as a construction-time error.
        """

        container = build_container(settings=_settings(), clock=_clock)
        company_query = CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ"))

        resolution = container.resolve_company.execute(company_query)
        assert resolution.company is not None
        company = resolution.company

        distinctive_task = ResearchTask(
            task_id=TaskId.new(),
            task_type=TaskType.MARKET_INTELLIGENCE,
            capability_id="market_intelligence",
            description="prepared-plan-integration-marker",
            created_at=_clock(),
        )
        prepared_plan = ResearchPlan(
            plan_id=PlanId.new(),
            research_run_id=ResearchRunId.new(created_at=_clock()),
            objective=ResearchObjective.MARKET_ANALYSIS,
            company_id=company.company_id,
            tasks=(distinctive_task,),
            created_at=_clock(),
            planner_version=PLANNER_VERSION,
            status=PlanStatus.READY,
        )
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=prepared_plan)
        )
        orchestrator = ResearchOrchestrator(
            planner, container.create_research_workflow, clock=_clock
        )

        created = orchestrator.execute(
            CreateResearchWorkflowQuery(
                company_query=company_query,
                objective=ResearchObjective.MARKET_ANALYSIS,
            )
        )

        assert created.workflow_result is not None
        self.assertEqual(created.workflow_result.status, WorkflowOperationStatus.OK)
        assert created.workflow_result.workflow is not None
        workflow = created.workflow_result.workflow
        self.assertEqual(workflow.plan.tasks[0].description, "prepared-plan-integration-marker")
        self.assertEqual(workflow.status, WorkflowStatus.READY)

        executed = container.manage_research_workflow.execute(workflow.workflow_id)

        self.assertEqual(executed.status, WorkflowOperationStatus.OK)
        assert executed.workflow is not None
        self.assertEqual(executed.workflow.status, WorkflowStatus.COMPLETED)
        self.assertGreaterEqual(executed.workflow.checkpoint_version, 1)
        self.assertGreaterEqual(executed.workflow.evidence_count, 1)
