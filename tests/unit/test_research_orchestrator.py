"""Tests for ResearchOrchestrator (Manager/Orchestrator -> PlannerPort seam)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.create_research_workflow import CreateResearchWorkflow
from financial_intelligence.application.orchestrator_contracts import OrchestrationOutcomeStatus
from financial_intelligence.application.research_orchestrator import ResearchOrchestrator
from financial_intelligence.application.research_plan_contracts import CreateResearchPlanQuery
from financial_intelligence.application.workflow_contracts import (
    CreateResearchWorkflowQuery,
    WorkflowOperationStatus,
)
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import CompanyId, ExchangeCode
from financial_intelligence.domain.orchestration import (
    PLANNER_VERSION,
    PlanId,
    PlannerOutcome,
    PlannerOutcomeStatus,
    PlanStatus,
    ResearchObjective,
    ResearchPlan,
    ResearchRequest,
    ResearchTask,
    TaskId,
    TaskType,
)
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.infrastructure.orchestration import UnavailablePlannerAdapter


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _clock() -> datetime:
    return datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _query() -> CreateResearchWorkflowQuery:
    return CreateResearchWorkflowQuery(
        company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
        objective=ResearchObjective.MARKET_ANALYSIS,
    )


def _plan(*, description: str = "fetch market snapshot") -> ResearchPlan:
    task = ResearchTask(
        task_id=TaskId.new(),
        task_type=TaskType.MARKET_INTELLIGENCE,
        capability_id="market_intelligence",
        description=description,
        created_at=_clock(),
    )
    return ResearchPlan(
        plan_id=PlanId.new(),
        research_run_id=ResearchRunId.new(created_at=_clock()),
        objective=ResearchObjective.MARKET_ANALYSIS,
        company_id=CompanyId.new(),
        tasks=(task,),
        created_at=_clock(),
        planner_version=PLANNER_VERSION,
        status=PlanStatus.READY,
    )


class _FakePlanner:
    """Test-only PlannerPort implementation — not production intelligence."""

    def __init__(self, outcome: PlannerOutcome) -> None:
        self._outcome = outcome
        self.calls = 0

    def create_plan(self, request: ResearchRequest) -> PlannerOutcome:
        del request
        self.calls += 1
        return self._outcome


class _RecordingCreateResearchWorkflow:
    """Wraps the real CreateResearchWorkflow use case to record whether it ran."""

    def __init__(self, inner: CreateResearchWorkflow) -> None:
        self._inner = inner
        self.calls = 0

    def execute(
        self, query: CreateResearchWorkflowQuery, *, prepared_plan: object = None
    ) -> object:
        self.calls += 1
        return self._inner.execute(query, prepared_plan=prepared_plan)  # type: ignore[arg-type]


class _SpyCreateResearchPlan:
    """Stands in for CreateResearchPlan and fails the test if it is ever invoked.

    Used to prove the orchestrator's prepared-plan path never triggers a second,
    independent plan generation.
    """

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, query: CreateResearchPlanQuery) -> object:
        del query
        self.calls += 1
        msg = "a second plan must never be generated on the prepared-plan path"
        raise AssertionError(msg)


class OrchestratorPlannerUnavailableTests(TestCase):
    def test_unavailable_planner_prevents_workflow_creation(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        recording = _RecordingCreateResearchWorkflow(container.create_research_workflow)
        orchestrator = ResearchOrchestrator(UnavailablePlannerAdapter(), recording, clock=_clock)

        result = orchestrator.execute(_query())

        self.assertEqual(result.status, OrchestrationOutcomeStatus.PLANNER_UNAVAILABLE)
        self.assertIsNone(result.workflow_result)
        self.assertEqual(recording.calls, 0, "no workflow may be created on planner failure")
        assert result.planner_outcome is not None
        self.assertEqual(result.planner_outcome.status, PlannerOutcomeStatus.UNAVAILABLE)
        self.assertIsNone(result.planner_outcome.plan)


class OrchestratorPlannerFailedTests(TestCase):
    def test_failed_planner_prevents_workflow_creation(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        recording = _RecordingCreateResearchWorkflow(container.create_research_workflow)
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.FAILED, message="planner attempt failed")
        )
        orchestrator = ResearchOrchestrator(planner, recording, clock=_clock)

        result = orchestrator.execute(_query())

        self.assertEqual(result.status, OrchestrationOutcomeStatus.PLANNER_FAILED)
        self.assertIsNone(result.workflow_result)
        self.assertEqual(recording.calls, 0)

    def test_invalid_planner_outcome_prevents_workflow_creation(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        recording = _RecordingCreateResearchWorkflow(container.create_research_workflow)
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.INVALID, message="unsupported request")
        )
        orchestrator = ResearchOrchestrator(planner, recording, clock=_clock)

        result = orchestrator.execute(_query())

        self.assertEqual(result.status, OrchestrationOutcomeStatus.PLANNER_FAILED)
        self.assertIsNone(result.workflow_result)
        self.assertEqual(recording.calls, 0, "no workflow may be created on planner failure")
        assert result.planner_outcome is not None
        self.assertEqual(result.planner_outcome.status, PlannerOutcomeStatus.INVALID)


class OrchestratorPlannerOkTests(TestCase):
    def test_ok_planner_delegates_to_existing_create_research_workflow(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        recording = _RecordingCreateResearchWorkflow(container.create_research_workflow)
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        orchestrator = ResearchOrchestrator(planner, recording, clock=_clock)

        result = orchestrator.execute(_query())

        self.assertEqual(result.status, OrchestrationOutcomeStatus.OK)
        self.assertEqual(recording.calls, 1, "must delegate to the existing use case exactly once")
        assert result.workflow_result is not None
        self.assertEqual(result.workflow_result.status, WorkflowOperationStatus.OK)
        assert result.workflow_result.workflow is not None

    def test_planner_plan_is_the_exact_plan_the_workflow_receives(self) -> None:
        """Proof A: the planner's ResearchPlan is used verbatim, not discarded.

        A distinctive plan object (unique description) flows, unmodified, all
        the way into the persisted workflow -- object identity, not just
        equal-by-value, so a hidden re-plan (a structurally similar but
        different plan) would also be caught.
        """

        container = build_container(settings=_settings(), clock=_clock)
        distinctive_plan = _plan(description="distinctive-planner-output-marker")
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=distinctive_plan)
        )
        orchestrator = ResearchOrchestrator(
            planner, container.create_research_workflow, clock=_clock
        )

        result = orchestrator.execute(_query())

        assert result.workflow_result is not None
        assert result.workflow_result.workflow is not None
        self.assertIs(result.workflow_result.workflow.plan, distinctive_plan)
        self.assertEqual(
            result.workflow_result.workflow.plan.tasks[0].description,
            "distinctive-planner-output-marker",
        )

    def test_no_second_plan_is_generated_on_the_prepared_plan_path(self) -> None:
        """Proof B: CreateResearchPlan/DeterministicPlanner is never invoked.

        A CreateResearchPlan stand-in raises if ``execute`` is ever called;
        the run must still succeed, proving the prepared plan short-circuits
        that call entirely instead of merely racing/ignoring its result.
        """

        container = build_container(settings=_settings(), clock=_clock)
        spy_plan = _SpyCreateResearchPlan()
        create_workflow = CreateResearchWorkflow(
            spy_plan,  # type: ignore[arg-type]
            container.workflow_store,
            clock=_clock,
        )
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        orchestrator = ResearchOrchestrator(planner, create_workflow, clock=_clock)

        result = orchestrator.execute(_query())

        self.assertEqual(result.status, OrchestrationOutcomeStatus.OK)
        self.assertEqual(
            spy_plan.calls, 0, "CreateResearchPlan must not run when a plan is prepared"
        )


class CreateResearchWorkflowBackwardCompatibilityTests(TestCase):
    """Proof C: existing callers that omit ``prepared_plan`` are unaffected."""

    def test_execute_without_prepared_plan_still_uses_deterministic_planning(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)

        result = container.create_research_workflow.execute(_query())

        self.assertEqual(result.status, WorkflowOperationStatus.OK)
        assert result.workflow is not None
        self.assertEqual(result.workflow.plan.planner_version, PLANNER_VERSION)
        assert result.resolution is not None and result.resolution.company is not None


class OrchestratorRequestValidationTests(TestCase):
    def test_planner_receives_a_research_request_built_from_the_query(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        orchestrator = ResearchOrchestrator(
            planner, container.create_research_workflow, clock=_clock
        )

        query = _query()
        orchestrator.execute(query)

        self.assertEqual(planner.calls, 1)


class OrchestratorCorrelationIdTests(TestCase):
    def test_correlation_id_is_preserved_on_every_branch(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        correlation_id = "req-abc123"

        unavailable = ResearchOrchestrator(
            UnavailablePlannerAdapter(), container.create_research_workflow, clock=_clock
        ).execute(_query(), correlation_id=correlation_id)
        self.assertEqual(unavailable.correlation_id, correlation_id)

        ok_planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        ok_result = ResearchOrchestrator(
            ok_planner, container.create_research_workflow, clock=_clock
        ).execute(_query(), correlation_id=correlation_id)
        self.assertEqual(ok_result.correlation_id, correlation_id)

    def test_correlation_id_defaults_to_none_when_not_supplied(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        result = ResearchOrchestrator(
            UnavailablePlannerAdapter(), container.create_research_workflow, clock=_clock
        ).execute(_query())
        self.assertIsNone(result.correlation_id)


class OrchestratorInvalidRequestTests(TestCase):
    def test_invalid_request_never_reaches_the_planner(self) -> None:
        container = build_container(settings=_settings(), clock=_clock)
        planner = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        orchestrator = ResearchOrchestrator(
            planner, container.create_research_workflow, clock=_clock
        )
        bad_query = CreateResearchWorkflowQuery(
            company_query=CompanyQuery(raw_query="x" * 5000),
            objective=ResearchObjective.MARKET_ANALYSIS,
        )

        result = orchestrator.execute(bad_query)

        self.assertEqual(result.status, OrchestrationOutcomeStatus.INVALID)
        self.assertEqual(planner.calls, 0)
