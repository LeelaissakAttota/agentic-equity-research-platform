"""Unit tests for DeterministicPlannerAdapter (Step 4C) and the PlannerPort migration.

Covers the adapter itself, ``CreateResearchPlan`` now depending on ``PlannerPort``,
and the composition root wiring the deterministic adapter as the default planner.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from financial_intelligence.application.capability_registry import CapabilityRegistry
from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ConfidenceBand,
    MatchMethod,
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.application.create_research_plan import (
    PLANNER_BUDGET_EXCEEDED_MESSAGE,
    CreateResearchPlan,
)
from financial_intelligence.application.deterministic_planner import DeterministicPlanner
from financial_intelligence.application.ports import LlmRouterPort, PlannerPort
from financial_intelligence.application.research_plan_contracts import (
    CreateResearchPlanQuery,
    ResearchPlanStatus,
)
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import CompanyId, ExchangeCode
from financial_intelligence.domain.llm import ModelRequest, ModelResponse
from financial_intelligence.domain.orchestration import (
    PLANNER_VERSION,
    BudgetExceededError,
    PlannerOutcome,
    PlannerOutcomeStatus,
    RequestId,
    ResearchExecutionBudget,
    ResearchObjective,
    ResearchRequest,
    TaskType,
)
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.orchestration import (
    DeterministicPlannerAdapter,
    deterministic_planner_adapter,
)

NOW = datetime(2026, 9, 19, 9, 30, tzinfo=UTC)
SECRET = "sk-or-v1-SUPERSECRET /etc/internal/path Traceback"
LOGGER_NAME = "financial_intelligence.infrastructure.orchestration.deterministic_planner_adapter"


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _clock() -> datetime:
    return NOW


def _request(raw_query: str = "Apple", **overrides: Any) -> ResearchRequest:
    values: dict[str, Any] = {
        "request_id": RequestId.new(),
        "research_run_id": ResearchRunId.new(created_at=NOW),
        "objective": ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH,
        "raw_query": raw_query,
        "created_at": NOW,
        "exchange": ExchangeCode("NASDAQ"),
    }
    values.update(overrides)
    return ResearchRequest(**values)


def _resolver() -> ResolveCompany:
    return ResolveCompany(InMemoryCompanyCatalog())


def _real_planner(
    registry: CapabilityRegistry | None = None,
    budget: ResearchExecutionBudget | None = None,
) -> DeterministicPlanner:
    return DeterministicPlanner(registry or CapabilityRegistry(), budget=budget)


def _adapter(planner: DeterministicPlanner | None = None) -> DeterministicPlannerAdapter:
    return DeterministicPlannerAdapter(planner or _real_planner(), _resolver())


def _apple_company_id() -> CompanyId:
    resolution = _resolver().execute(
        CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ"))
    )
    assert resolution.company is not None
    return resolution.company.company_id


class _RaisingPlanner(DeterministicPlanner):
    """Test-only planner whose build_plan raises a scripted exception."""

    def __init__(self, exc: BaseException) -> None:
        super().__init__(CapabilityRegistry())
        self._exc = exc

    def build_plan(self, **kwargs: Any) -> Any:
        raise self._exc


class _InvalidResolver(ResolveCompany):
    """Test-only resolver that always reports an invalid query."""

    def __init__(self) -> None:
        super().__init__(InMemoryCompanyCatalog())

    def execute(self, query: CompanyQuery) -> ResolutionResult:
        return ResolutionResult(
            query=query,
            status=ResolutionStatus.INVALID,
            matched_by=MatchMethod.INVALID_INPUT,
            confidence=ConfidenceBand.NONE,
            message=f"detail {SECRET}",
        )


class AdapterSuccessTests(TestCase):
    def test_implements_planner_port(self) -> None:
        self.assertIsInstance(_adapter(), PlannerPort)

    def test_successful_plan_creation(self) -> None:
        outcome = _adapter().create_plan(_request())
        self.assertIs(outcome.status, PlannerOutcomeStatus.OK)
        self.assertIsNotNone(outcome.plan)
        assert outcome.plan is not None
        self.assertEqual(len(outcome.plan.tasks), 5)

    def test_company_is_resolved_and_used(self) -> None:
        outcome = _adapter().create_plan(_request())
        assert outcome.plan is not None
        self.assertEqual(outcome.plan.company_id, _apple_company_id())

    def test_delegates_once_to_deterministic_planner_with_request_values(self) -> None:
        planner = _real_planner()
        request = _request(objective=ResearchObjective.MARKET_ANALYSIS)
        with patch.object(planner, "build_plan", wraps=planner.build_plan) as spy:
            outcome = _adapter(planner).create_plan(request)
        spy.assert_called_once_with(
            research_run_id=request.research_run_id,
            objective=request.objective,
            company_id=_apple_company_id(),
            created_at=request.created_at,
        )
        assert outcome.plan is not None
        self.assertEqual(outcome.plan.research_run_id, request.research_run_id)
        self.assertIs(outcome.plan.objective, ResearchObjective.MARKET_ANALYSIS)
        self.assertEqual(outcome.plan.created_at, request.created_at)

    def test_planner_version_is_propagated(self) -> None:
        adapter = _adapter()
        outcome = adapter.create_plan(_request())
        assert outcome.plan is not None
        self.assertEqual(outcome.planner_version, PLANNER_VERSION)
        self.assertEqual(outcome.plan.planner_version, PLANNER_VERSION)
        self.assertEqual(adapter.planner_version, _real_planner().planner_version)

    def test_task_ids_are_server_generated_per_plan(self) -> None:
        adapter = _adapter()
        first = adapter.create_plan(_request())
        second = adapter.create_plan(_request())
        assert first.plan is not None and second.plan is not None
        first_ids = {t.task_id for t in first.plan.tasks}
        second_ids = {t.task_id for t in second.plan.tasks}
        self.assertEqual(len(first_ids), len(first.plan.tasks))
        self.assertTrue(first_ids.isdisjoint(second_ids))
        self.assertNotEqual(first.plan.plan_id, second.plan.plan_id)

    def test_task_types_are_registry_derived(self) -> None:
        registry = CapabilityRegistry()
        outcome = _adapter(_real_planner(registry)).create_plan(_request())
        assert outcome.plan is not None
        for task in outcome.plan.tasks:
            self.assertIs(task.task_type, registry.require(task.capability_id).task_type)
        self.assertNotIn(TaskType.COMPANY_RESOLUTION, {t.task_type for t in outcome.plan.tasks})

    def test_same_output_as_direct_deterministic_planner(self) -> None:
        planner = _real_planner()
        request = _request()
        outcome = _adapter(planner).create_plan(request)
        direct = planner.build_plan(
            research_run_id=request.research_run_id,
            objective=request.objective,
            company_id=_apple_company_id(),
            created_at=request.created_at,
        )
        assert outcome.plan is not None
        self.assertEqual(
            [(t.task_type, t.priority, t.capability_id) for t in outcome.plan.tasks],
            [(t.task_type, t.priority, t.capability_id) for t in direct.tasks],
        )

    def test_makes_no_network_or_llm_calls(self) -> None:
        def _blocked(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("network access attempted")

        with (
            patch.object(socket.socket, "connect", _blocked),
            patch.object(socket, "getaddrinfo", _blocked),
        ):
            outcome = _adapter().create_plan(_request())
        self.assertIs(outcome.status, PlannerOutcomeStatus.OK)
        # Constructor takes only a planner and a resolver: no router/provider seam exists.
        self.assertFalse(hasattr(_adapter(), "_router"))


class AdapterFailureTests(TestCase):
    def assertSafeFailure(
        self,
        outcome: PlannerOutcome,
        status: PlannerOutcomeStatus,
    ) -> None:
        self.assertIs(outcome.status, status)
        self.assertIsNone(outcome.plan)
        self.assertEqual(outcome.planner_version, PLANNER_VERSION)
        self.assertLessEqual(len(outcome.message), 512)
        self.assertNotIn("SUPERSECRET", outcome.message)
        self.assertNotIn("sk-", outcome.message)
        self.assertNotIn("/etc", outcome.message)
        self.assertNotIn("Traceback", outcome.message)

    def test_invalid_company_query_maps_to_invalid(self) -> None:
        adapter = DeterministicPlannerAdapter(_real_planner(), _InvalidResolver())
        outcome = adapter.create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.INVALID)

    def test_unknown_company_maps_to_invalid(self) -> None:
        outcome = _adapter().create_plan(_request("ZZZZNOTACOMPANY"))
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.INVALID)

    def test_ambiguous_company_maps_to_invalid(self) -> None:
        outcome = _adapter().create_plan(_request("COLLIDE", exchange=None))
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.INVALID)

    def test_planner_is_not_called_when_company_unresolved(self) -> None:
        planner = _real_planner()
        with patch.object(planner, "build_plan") as spy:
            _adapter(planner).create_plan(_request("ZZZZNOTACOMPANY"))
        spy.assert_not_called()

    def test_budget_exceeded_maps_to_failed(self) -> None:
        planner = _RaisingPlanner(BudgetExceededError(SECRET))
        outcome = _adapter(planner).create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.FAILED)
        self.assertEqual(outcome.message, PLANNER_BUDGET_EXCEEDED_MESSAGE)

    def test_real_budget_overflow_maps_to_failed(self) -> None:
        planner = _real_planner(budget=ResearchExecutionBudget(max_tasks=1))
        outcome = _adapter(planner).create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.FAILED)
        self.assertEqual(outcome.message, PLANNER_BUDGET_EXCEEDED_MESSAGE)

    def test_registry_lookup_failure_maps_to_unavailable(self) -> None:
        planner = _real_planner(registry=CapabilityRegistry(()))
        outcome = _adapter(planner).create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.UNAVAILABLE)

    def test_key_error_message_is_not_echoed(self) -> None:
        outcome = _adapter(_RaisingPlanner(KeyError(SECRET))).create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.UNAVAILABLE)

    def test_value_error_maps_to_failed(self) -> None:
        outcome = _adapter(_RaisingPlanner(ValueError(SECRET))).create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.FAILED)
        self.assertNotEqual(outcome.message, PLANNER_BUDGET_EXCEEDED_MESSAGE)

    def test_unexpected_exception_maps_to_failed_and_logs_only_type(self) -> None:
        planner = _RaisingPlanner(RuntimeError(SECRET))
        with self.assertLogs(LOGGER_NAME, level="WARNING") as captured:
            outcome = _adapter(planner).create_plan(_request())
        self.assertSafeFailure(outcome, PlannerOutcomeStatus.FAILED)
        record = captured.records[0]
        self.assertEqual(getattr(record, "error_type", None), "RuntimeError")
        self.assertNotIn("SUPERSECRET", "\n".join(captured.output))
        self.assertNotIn("SUPERSECRET", str(record.__dict__))
        self.assertIsNone(record.exc_info)


class _ScriptedPlanner:
    """Test-only PlannerPort: returns a scripted outcome and records calls."""

    def __init__(self, build: Any) -> None:
        self._build = build
        self.requests: list[ResearchRequest] = []

    def create_plan(self, request: ResearchRequest) -> PlannerOutcome:
        self.requests.append(request)
        return self._build(request)  # type: ignore[no-any-return]


def _ok_for(company_id: CompanyId, *, run_id_override: ResearchRunId | None = None) -> Any:
    def build(request: ResearchRequest) -> PlannerOutcome:
        plan = _real_planner().build_plan(
            research_run_id=run_id_override or request.research_run_id,
            objective=request.objective,
            company_id=company_id,
            created_at=request.created_at,
        )
        return PlannerOutcome(
            status=PlannerOutcomeStatus.OK,
            message="scripted plan",
            plan=plan,
            planner_version="scripted-v1",
        )

    return build


def _status_only(status: PlannerOutcomeStatus, message: str) -> Any:
    def build(request: ResearchRequest) -> PlannerOutcome:
        del request
        return PlannerOutcome(status=status, message=message)

    return build


def _use_case(planner: PlannerPort) -> CreateResearchPlan:
    return CreateResearchPlan(_resolver(), planner, clock=_clock)


def _query(raw: str = "Apple", **overrides: Any) -> CreateResearchPlanQuery:
    values: dict[str, Any] = {
        "company_query": CompanyQuery(raw_query=raw, exchange=ExchangeCode("NASDAQ")),
        "objective": ResearchObjective.MARKET_ANALYSIS,
    }
    values.update(overrides)
    return CreateResearchPlanQuery(**values)


class CreateResearchPlanPlannerPortTests(TestCase):
    def test_accepts_planner_port_and_invokes_it_exactly_once(self) -> None:
        planner = _ScriptedPlanner(_ok_for(_apple_company_id()))
        self.assertIsInstance(planner, PlannerPort)
        result = _use_case(planner).execute(_query())
        self.assertIs(result.status, ResearchPlanStatus.OK)
        self.assertEqual(len(planner.requests), 1)

    def test_returned_plan_is_used_and_relationships_preserved(self) -> None:
        captured: list[PlannerOutcome] = []

        def build(request: ResearchRequest) -> PlannerOutcome:
            outcome = _ok_for(_apple_company_id())(request)
            captured.append(outcome)
            return outcome  # type: ignore[no-any-return]

        result = _use_case(_ScriptedPlanner(build)).execute(_query())
        assert result.plan is not None and result.request is not None
        self.assertIs(result.plan, captured[0].plan)
        self.assertEqual(result.plan.research_run_id, result.request.research_run_id)
        self.assertEqual(result.plan.created_at, NOW)
        assert result.resolution is not None and result.resolution.company is not None
        self.assertEqual(result.plan.company_id, result.resolution.company.company_id)

    def test_planner_receives_the_prepared_request(self) -> None:
        planner = _ScriptedPlanner(_ok_for(_apple_company_id()))
        result = _use_case(planner).execute(_query())
        self.assertIs(planner.requests[0], result.request)

    def test_company_id_mismatch_fails_closed(self) -> None:
        planner = _ScriptedPlanner(_ok_for(CompanyId.new()))
        result = _use_case(planner).execute(_query())
        self.assertIsNot(result.status, ResearchPlanStatus.OK)
        self.assertIs(result.status, ResearchPlanStatus.UNAVAILABLE)
        self.assertIsNone(result.plan)
        self.assertEqual(len(planner.requests), 1)
        self.assertNotIn(str(_apple_company_id().value), result.message)

    def test_research_run_mismatch_fails_closed(self) -> None:
        other_run = ResearchRunId.new(created_at=NOW)
        planner = _ScriptedPlanner(_ok_for(_apple_company_id(), run_id_override=other_run))
        result = _use_case(planner).execute(_query())
        self.assertIs(result.status, ResearchPlanStatus.UNAVAILABLE)
        self.assertIsNone(result.plan)

    def test_planner_not_called_when_company_unresolved(self) -> None:
        planner = _ScriptedPlanner(_ok_for(_apple_company_id()))
        result = _use_case(planner).execute(_query("ZZZZNOTACOMPANY"))
        self.assertIs(result.status, ResearchPlanStatus.RESOLUTION_BLOCKED)
        self.assertEqual(planner.requests, [])

    def test_planner_outcome_status_mapping(self) -> None:
        cases = (
            (PlannerOutcomeStatus.INVALID, "bad", ResearchPlanStatus.INVALID),
            (PlannerOutcomeStatus.UNAVAILABLE, "nope", ResearchPlanStatus.UNAVAILABLE),
            (PlannerOutcomeStatus.FAILED, "boom", ResearchPlanStatus.UNAVAILABLE),
            (
                PlannerOutcomeStatus.FAILED,
                PLANNER_BUDGET_EXCEEDED_MESSAGE,
                ResearchPlanStatus.BUDGET_EXCEEDED,
            ),
        )
        for status, message, expected in cases:
            with self.subTest(status=status.value, message=message):
                result = _use_case(_ScriptedPlanner(_status_only(status, message))).execute(
                    _query()
                )
                self.assertIs(result.status, expected)
                self.assertIsNone(result.plan)
                self.assertEqual(result.message, message)

    def test_budget_exceeded_result_carries_budget(self) -> None:
        budget = ResearchExecutionBudget(max_tasks=1)
        planner = DeterministicPlannerAdapter(_real_planner(budget=budget), _resolver())
        use_case = CreateResearchPlan(_resolver(), planner, budget=budget, clock=_clock)
        result = use_case.execute(_query(objective=ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH))
        self.assertIs(result.status, ResearchPlanStatus.BUDGET_EXCEEDED)
        self.assertEqual(result.budget, budget)
        self.assertIsNone(result.plan)

    def test_deterministic_behavior_unchanged_through_adapter(self) -> None:
        use_case = _use_case(_adapter())
        result = use_case.execute(_query(objective=ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH))
        self.assertIs(result.status, ResearchPlanStatus.OK)
        self.assertEqual(result.message, "research plan created (not executed)")
        assert result.plan is not None
        self.assertEqual(result.plan.planner_version, PLANNER_VERSION)
        self.assertEqual(len(result.plan.tasks), 5)

    def test_invalid_request_never_reaches_planner(self) -> None:
        planner = _ScriptedPlanner(_ok_for(_apple_company_id()))
        result = _use_case(planner).execute(_query(jurisdiction="USA"))
        self.assertIs(result.status, ResearchPlanStatus.INVALID)
        self.assertEqual(planner.requests, [])


class _ExplodingRouter:
    """Test-only LlmRouterPort that fails the test if it is ever called."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        raise AssertionError("LLM router must not be called by default planning")


class CompositionTests(TestCase):
    def test_default_planner_is_deterministic_adapter_behind_planner_port(self) -> None:
        container = build_container(_settings(), clock=_clock)
        planner = container.create_research_plan._planner
        self.assertIsInstance(planner, PlannerPort)
        self.assertIsInstance(planner, DeterministicPlannerAdapter)
        self.assertEqual(planner.planner_version, PLANNER_VERSION)

    def test_default_planning_is_deterministic_without_llm_or_key(self) -> None:
        router = _ExplodingRouter()
        self.assertIsInstance(router, LlmRouterPort)
        container = build_container(_settings(), clock=_clock, llm_router=router)
        result = container.create_research_plan.execute(
            _query(objective=ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH)
        )
        self.assertIs(result.status, ResearchPlanStatus.OK)
        assert result.plan is not None
        self.assertEqual(result.plan.planner_version, PLANNER_VERSION)
        self.assertEqual(router.calls, 0)
        self.assertFalse(container.settings.openrouter_live_enabled)

    def test_planner_is_constructed_once_and_shared(self) -> None:
        from financial_intelligence import composition

        with (
            patch.object(
                composition,
                "DeterministicPlanner",
                wraps=DeterministicPlanner,
            ) as planner_cls,
            patch.object(
                composition,
                "DeterministicPlannerAdapter",
                wraps=DeterministicPlannerAdapter,
            ) as adapter_cls,
        ):
            container = build_container(_settings(), clock=_clock)
        planner_cls.assert_called_once()
        adapter_cls.assert_called_once()
        self.assertIsInstance(container.create_research_plan._planner, DeterministicPlannerAdapter)

    def test_workflow_and_execution_share_the_same_create_research_plan(self) -> None:
        container = build_container(_settings(), clock=_clock)
        self.assertIs(
            container.create_research_workflow._create_plan,
            container.create_research_plan,
        )
        self.assertIs(
            container.execute_research_plan._create_plan,
            container.create_research_plan,
        )

    def test_container_construction_makes_no_network_call(self) -> None:
        def _blocked(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("network access attempted")

        with (
            patch.object(socket.socket, "connect", _blocked),
            patch.object(socket, "getaddrinfo", _blocked),
        ):
            container = build_container(_settings(), clock=_clock)
            result = container.create_research_plan.execute(_query())
        self.assertIs(result.status, ResearchPlanStatus.OK)


class ModuleExportTests(TestCase):
    def test_adapter_module_is_exported_from_package(self) -> None:
        self.assertIs(
            deterministic_planner_adapter.DeterministicPlannerAdapter,
            DeterministicPlannerAdapter,
        )
