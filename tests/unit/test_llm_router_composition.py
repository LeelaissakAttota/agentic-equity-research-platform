"""Phase 3 — composition wiring tests for LlmRouterPort selection.

Covers the fail-closed default (``openrouter_live_enabled=False`` or no
configured model) and live wiring when both are set. No live network calls:
``build_container`` only constructs the adapter, it never calls it.
"""

from __future__ import annotations

from unittest import TestCase

from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.llm import DisabledLlmRouterAdapter, OpenRouterAdapter


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
            OPENROUTER_API_KEY="sk-or-test-value",
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
