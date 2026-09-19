"""Phase 3 — composition wiring tests for LlmRouterPort selection.

Covers the fail-closed default (``openrouter_live_enabled=False`` or no
configured model) and live wiring when both are set. No live network calls:
``build_container`` only constructs the adapter, it never calls it.
"""

from __future__ import annotations

from unittest import TestCase

from financial_intelligence.application.ports import PlannerPort
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
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
