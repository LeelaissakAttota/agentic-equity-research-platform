"""Phase 3 — composition wiring tests for LlmRouterPort selection.

Covers the fail-closed default (``openrouter_live_enabled=False`` or no
configured model) and live wiring when both are set. No live network calls:
``build_container`` only constructs the adapter, it never calls it.

Also covers Step 4E.3 production integration tests for explicit planner selection.
"""

from __future__ import annotations

import json
import socket
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.create_research_plan import (
    CreateResearchPlanQuery,
    ResearchPlanStatus,
)
from financial_intelligence.application.create_research_workflow import (
    CreateResearchWorkflowQuery,
    WorkflowOperationStatus,
)
from financial_intelligence.application.ports import PlannerPort
from financial_intelligence.application.workflow_contracts import PreparedResearchPlan
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import ExchangeCode
from financial_intelligence.domain.llm import (
    ModelCallStatus,
    ModelFailureKind,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)
from financial_intelligence.domain.orchestration import ExecutionControl, ResearchObjective
from financial_intelligence.infrastructure.llm import DisabledLlmRouterAdapter, OpenRouterAdapter
from financial_intelligence.infrastructure.orchestration import (
    DeterministicPlannerAdapter,
    LlmPlannerAdapter,
)


class LlmRouterCompositionTests(TestCase):
    def test_defaults_to_disabled_router_when_live_routing_is_off(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")
        container = build_container(settings)
        self.assertIsInstance(container.llm_router, DisabledLlmRouterAdapter)

    def test_wires_live_openrouter_adapter_when_enabled_and_model_configured(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="«redacted:sk-…»",
        )
        container = build_container(settings)
        self.assertIsInstance(container.llm_router, OpenRouterAdapter)

    def test_explicit_llm_router_override_takes_precedence(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
        )
        sentinel = DisabledLlmRouterAdapter()
        container = build_container(settings, llm_router=sentinel)
        self.assertIs(container.llm_router, sentinel)


class PlannerSelectionCompositionTests(TestCase):
    """Tests for explicit PLANNER_MODE composition selection."""

    def test_default_mode_constructs_deterministic_planner(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")
        container = build_container(settings)
        self.assertIsInstance(container.create_research_plan._planner, DeterministicPlannerAdapter)

    def test_explicit_deterministic_mode_constructs_deterministic_planner(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="deterministic",
        )
        container = build_container(settings)
        self.assertIsInstance(container.create_research_plan._planner, DeterministicPlannerAdapter)

    def test_llm_mode_constructs_llm_planner_adapter(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="llm",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        self.assertIsInstance(container.create_research_plan._planner, LlmPlannerAdapter)

    def test_deterministic_mode_does_not_construct_llm_planner_adapter(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="deterministic",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        self.assertNotIsInstance(container.create_research_plan._planner, LlmPlannerAdapter)

    def test_llm_mode_does_not_construct_deterministic_planner_adapter(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="llm",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        self.assertNotIsInstance(
            container.create_research_plan._planner, DeterministicPlannerAdapter
        )

    def test_openrouter_live_enabled_alone_does_not_switch_planner_mode(self) -> None:
        """OPENROUTER_LIVE_ENABLED=true by itself must not activate LLM planner."""
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        # Default PLANNER_MODE=deterministic should still be used
        self.assertIsInstance(container.create_research_plan._planner, DeterministicPlannerAdapter)

    def test_invalid_planner_mode_fails_closed(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="invalid",
            )

    def test_llm_mode_missing_live_enabled_fails_closed(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError) as cm:
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="llm",
                PRIMARY_FREE_MODEL="free/model-a",
                OPENROUTER_API_KEY="sk-test-key",
            )
        self.assertIn("OPENROUTER_LIVE_ENABLED", str(cm.exception))

    def test_llm_mode_missing_primary_free_model_fails_closed(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError) as cm:
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="llm",
                OPENROUTER_LIVE_ENABLED=True,
                OPENROUTER_API_KEY="sk-test-key",
            )
        self.assertIn("primary free model", str(cm.exception).lower())

    def test_llm_mode_missing_api_key_fails_closed(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError) as cm:
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="llm",
                OPENROUTER_LIVE_ENABLED=True,
                PRIMARY_FREE_MODEL="free/model-a",
            )
        self.assertIn("OPENROUTER_API_KEY", str(cm.exception))

    def test_llm_planner_receives_openrouter_max_output_tokens(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="llm",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
            OPENROUTER_MAX_OUTPUT_TOKENS=2048,
        )
        container = build_container(settings)
        llm_planner = container.create_research_plan._planner
        self.assertIsInstance(llm_planner, LlmPlannerAdapter)
        self.assertEqual(llm_planner._max_output_tokens, 2048)

    def test_shared_resolve_company_reused(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")
        container = build_container(settings)
        # The planner should use the same resolve_company instance
        planner = container.create_research_plan._planner
        self.assertIs(planner._resolve_company, container.resolve_company)

    def test_shared_capability_registry_reused(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="llm",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        # The planner should use the same capability_registry instance
        planner = container.create_research_plan._planner
        self.assertIsInstance(planner, LlmPlannerAdapter)
        self.assertIs(planner._registry, container.capability_registry)

    def test_exactly_one_planner_port_implementation_selected(self) -> None:
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="llm",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        # Only one planner should exist in the container
        planner = container.create_research_plan._planner
        self.assertIsInstance(planner, PlannerPort)
        # It should be either deterministic or llm, not both
        is_deterministic = isinstance(planner, DeterministicPlannerAdapter)
        is_llm = isinstance(planner, LlmPlannerAdapter)
        self.assertTrue(
            is_deterministic ^ is_llm,
            "Exactly one planner implementation must be selected",
        )


class ProductionIntegrationTests(TestCase):
    """End-to-end production integration tests for explicit planner selection.

    These tests verify the complete production wiring without making real
    network requests, using dependency injection and fake routers.
    """

    def _llm_settings(self) -> Settings:
        """Valid LLM-mode settings with fake credentials."""
        return Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            PLANNER_MODE="llm",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
            OPENROUTER_MAX_OUTPUT_TOKENS=2048,
        )

    def _make_success_router(self):
        """Create a fake router that returns a valid planner response."""

        class FakeSuccessRouter:
            def __init__(self):
                self.calls = 0

            def complete(self, request: ModelRequest) -> ModelResponse:
                self.calls += 1
                plan_json = json.dumps(
                    {
                        "type": "research_plan",
                        "tasks": [
                            {
                                "capability_id": "market_intelligence",
                                "description": "Fetch current market intelligence",
                                "depends_on": [],
                                "priority": 10,
                            }
                        ],
                    }
                )
                return ModelResponse(
                    call_id=request.call_id,
                    status=ModelCallStatus.SUCCEEDED,
                    model_used="free/model-a",
                    content=plan_json,
                    usage=ModelUsage(),
                    retry_count=0,
                )

        return FakeSuccessRouter()

    def _make_failing_router(self):
        """Create a fake router that returns a failed response."""

        class FakeFailingRouter:
            def complete(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(
                    call_id=request.call_id,
                    status=ModelCallStatus.FAILED,
                    model_used=None,
                    content=None,
                    usage=ModelUsage(),
                    retry_count=0,
                    failure_kind=ModelFailureKind.UPSTREAM_ERROR,
                )

        return FakeFailingRouter()

    def _make_malformed_router(self):
        """Create a fake router that returns malformed JSON."""

        class FakeMalformedRouter:
            def complete(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(
                    call_id=request.call_id,
                    status=ModelCallStatus.SUCCEEDED,
                    model_used="free/model-a",
                    content="not valid json {{{",
                    usage=ModelUsage(),
                    retry_count=0,
                )

        return FakeMalformedRouter()

    def test_llm_mode_end_to_end_with_fake_router(self) -> None:
        """LLM planner integration: composition selects LlmPlannerAdapter,
        fake router returns valid planner JSON, full pipeline produces ResearchPlan."""
        settings = self._llm_settings()
        fake_router = self._make_success_router()
        container = build_container(settings, llm_router=fake_router)

        # 1. Production composition selects LlmPlannerAdapter
        planner = container.create_research_plan._planner
        self.assertIsInstance(planner, LlmPlannerAdapter)

        # 2-5. Shared dependencies received correctly
        self.assertIs(planner._resolve_company, container.resolve_company)
        self.assertIs(planner._registry, container.capability_registry)
        self.assertIs(planner._budget, container.create_research_plan._budget)
        self.assertEqual(planner._max_output_tokens, 2048)

        # 6-9. Execute full pipeline: CreateResearchPlan -> PlannerPort -> ResearchPlan
        query = CreateResearchPlanQuery(
            company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
            objective=ResearchObjective.MARKET_ANALYSIS,
        )
        result = container.create_research_plan.execute(query)

        # 7-9. Valid successful planner JSON -> PlannerOutcome -> ResearchPlan
        self.assertIs(result.status, ResearchPlanStatus.OK)
        self.assertIsNotNone(result.plan)
        self.assertEqual(len(result.plan.tasks), 1)
        self.assertEqual(result.plan.tasks[0].capability_id, "market_intelligence")

        # 10. No deterministic planner invoked
        self.assertEqual(fake_router.calls, 1)

        # 11. No real HTTP/network request occurred (fake router only)
        # 12. Resulting workflow can proceed through existing workflow path
        workflow_query = CreateResearchWorkflowQuery(
            company_query=query.company_query,
            objective=query.objective,
        )
        prepared = PreparedResearchPlan(
            plan=result.plan,
            request=result.request,
        )
        workflow_result = container.create_research_workflow.execute(
            workflow_query, prepared_plan=prepared
        )
        self.assertIs(workflow_result.status, WorkflowOperationStatus.OK)
        self.assertIsNotNone(workflow_result.workflow)

    def test_llm_mode_planner_failure_no_deterministic_fallback(self) -> None:
        """LLM planner failure propagates; no silent fallback to deterministic."""
        settings = self._llm_settings()
        fake_router = self._make_failing_router()
        container = build_container(settings, llm_router=fake_router)

        query = CreateResearchPlanQuery(
            company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
            objective=ResearchObjective.MARKET_ANALYSIS,
        )
        result = container.create_research_plan.execute(query)

        # Failure propagates through existing PlannerOutcome semantics
        self.assertIsNot(result.status, ResearchPlanStatus.OK)
        self.assertIsNone(result.plan)
        # No deterministic planner was constructed or invoked
        planner = container.create_research_plan._planner
        self.assertIsInstance(planner, LlmPlannerAdapter)

    def test_llm_mode_malformed_planner_json_fails_closed(self) -> None:
        """Malformed planner JSON -> planner failure, no fake successful ResearchPlan."""
        settings = self._llm_settings()
        fake_router = self._make_malformed_router()
        container = build_container(settings, llm_router=fake_router)

        query = CreateResearchPlanQuery(
            company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
            objective=ResearchObjective.MARKET_ANALYSIS,
        )
        result = container.create_research_plan.execute(query)

        self.assertIsNot(result.status, ResearchPlanStatus.OK)
        self.assertIsNone(result.plan)

    def test_workflow_execution_does_not_replan(self) -> None:
        """Planner called during workflow creation only; execution uses persisted plan."""
        call_count = {"create": 0}

        class CountingRouter:
            def complete(self, request: ModelRequest) -> ModelResponse:
                call_count["create"] += 1
                plan_json = json.dumps(
                    {
                        "type": "research_plan",
                        "tasks": [
                            {
                                "capability_id": "market_intelligence",
                                "description": "Fetch current market intelligence",
                                "depends_on": [],
                                "priority": 10,
                            }
                        ],
                    }
                )
                return ModelResponse(
                    call_id=request.call_id,
                    status=ModelCallStatus.SUCCEEDED,
                    model_used="free/model-a",
                    content=plan_json,
                    usage=ModelUsage(),
                    retry_count=0,
                )

        settings = self._llm_settings()
        fake_router = CountingRouter()
        container = build_container(settings, llm_router=fake_router)

        # 1. Workflow creation (planner called)
        query = CreateResearchPlanQuery(
            company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
            objective=ResearchObjective.MARKET_ANALYSIS,
        )
        create_result = container.create_research_plan.execute(query)
        self.assertIs(create_result.status, ResearchPlanStatus.OK)
        calls_during_creation = call_count["create"]
        self.assertEqual(calls_during_creation, 1)

        # 2. Workflow creation with prepared plan (no re-planning)
        workflow_query = CreateResearchWorkflowQuery(
            company_query=query.company_query,
            objective=query.objective,
        )
        prepared = PreparedResearchPlan(
            plan=create_result.plan,
            request=create_result.request,
        )
        workflow_result = container.create_research_workflow.execute(
            workflow_query, prepared_plan=prepared
        )
        self.assertIs(workflow_result.status, WorkflowOperationStatus.OK)

        # 3. Workflow execution (planner NOT called again)
        _ = container.manage_research_workflow.execute(
            workflow_result.workflow.workflow_id, control=ExecutionControl()
        )

        # Execution should not call planner/router
        self.assertEqual(
            call_count["create"],
            calls_during_creation,
            "Planner/router must not be invoked during workflow execution",
        )

    def test_llm_mode_network_safety(self) -> None:
        """LLM-mode composition does not itself perform network I/O.

        The fake router is used; no real OpenRouter request occurs.
        """

        def _blocked(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("network access attempted during composition or setup")

        settings = self._llm_settings()

        class FakeRouter:
            def complete(self, request: ModelRequest) -> ModelResponse:
                plan_json = json.dumps(
                    {
                        "type": "research_plan",
                        "tasks": [
                            {
                                "capability_id": "market_intelligence",
                                "description": "Fetch current market intelligence",
                                "depends_on": [],
                                "priority": 10,
                            }
                        ],
                    }
                )
                return ModelResponse(
                    call_id=request.call_id,
                    status=ModelCallStatus.SUCCEEDED,
                    model_used="free/model-a",
                    content=plan_json,
                    usage=ModelUsage(),
                    retry_count=0,
                )

        with (
            patch.object(socket.socket, "connect", _blocked),
            patch.object(socket, "getaddrinfo", _blocked),
        ):
            fake_router = FakeRouter()
            container = build_container(settings, llm_router=fake_router)

            # Verify no network call during composition
            planner = container.create_research_plan._planner
            self.assertIsInstance(planner, LlmPlannerAdapter)

            # Verify no network call during actual planning
            query = CreateResearchPlanQuery(
                company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
                objective=ResearchObjective.MARKET_ANALYSIS,
            )
            result = container.create_research_plan.execute(query)
            self.assertIs(result.status, ResearchPlanStatus.OK)

    def test_openrouter_live_enabled_independence(self) -> None:
        """OPENROUTER_LIVE_ENABLED=true with default PLANNER_MODE=deterministic
        still selects DeterministicPlannerAdapter."""
        settings = Settings(
            _env_file=None,
            APP_ENV="test",
            LOG_LEVEL="WARNING",
            OPENROUTER_LIVE_ENABLED=True,
            PRIMARY_FREE_MODEL="free/model-a",
            OPENROUTER_API_KEY="sk-test-key",
        )
        container = build_container(settings)
        self.assertIsInstance(container.create_research_plan._planner, DeterministicPlannerAdapter)

    def test_invalid_planner_mode_fails_closed(self) -> None:
        """Invalid PLANNER_MODE -> startup/configuration failure."""
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="invalid",
            )

    def test_llm_mode_missing_prerequisites_fails_closed(self) -> None:
        """PLANNER_MODE=llm + missing prerequisites -> startup/configuration failure."""
        from pydantic import ValidationError

        # Missing OPENROUTER_LIVE_ENABLED
        with self.assertRaises(ValidationError) as cm:
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="llm",
                PRIMARY_FREE_MODEL="free/model-a",
                OPENROUTER_API_KEY="sk-test-key",
            )
        self.assertIn("OPENROUTER_LIVE_ENABLED", str(cm.exception))

        # Missing PRIMARY_FREE_MODEL
        with self.assertRaises(ValidationError) as cm:
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="llm",
                OPENROUTER_LIVE_ENABLED=True,
                OPENROUTER_API_KEY="sk-test-key",
            )
        self.assertIn("primary free model", str(cm.exception).lower())

        # Missing OPENROUTER_API_KEY
        with self.assertRaises(ValidationError) as cm:
            Settings(
                _env_file=None,
                APP_ENV="test",
                LOG_LEVEL="WARNING",
                PLANNER_MODE="llm",
                OPENROUTER_LIVE_ENABLED=True,
                PRIMARY_FREE_MODEL="free/model-a",
            )
        self.assertIn("OPENROUTER_API_KEY", str(cm.exception))

    def test_shared_dependencies_single_instance(self) -> None:
        """Production composition uses single shared instances for dependencies."""
        settings = self._llm_settings()
        fake_router = self._make_success_router()
        container = build_container(settings, llm_router=fake_router)

        planner = container.create_research_plan._planner

        # Shared ResolveCompany
        self.assertIs(planner._resolve_company, container.resolve_company)

        # Shared CapabilityRegistry
        self.assertIs(planner._registry, container.capability_registry)

        # Shared ResearchExecutionBudget (via CreateResearchPlan)
        self.assertIs(planner._budget, container.create_research_plan._budget)

        # LlmRouterPort is the same injected instance
        self.assertIs(container.llm_router, fake_router)
