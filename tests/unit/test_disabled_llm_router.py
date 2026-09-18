"""Phase 3 — DisabledLlmRouterAdapter tests (fail-closed stand-in, no network)."""

from __future__ import annotations

from unittest import TestCase

from financial_intelligence.application.ports import LlmRouterPort
from financial_intelligence.domain.llm import (
    ModelCallId,
    ModelCallStatus,
    ModelFailureKind,
    ModelMessage,
    ModelRequest,
)
from financial_intelligence.infrastructure.llm import DisabledLlmRouterAdapter


def _request() -> ModelRequest:
    return ModelRequest(
        call_id=ModelCallId.new(),
        prompt_version="synthesis-v1",
        messages=(ModelMessage(role="user", content="Summarize the filing."),),
        max_output_tokens=256,
    )


class DisabledLlmRouterAdapterTests(TestCase):
    def test_satisfies_llm_router_port(self) -> None:
        adapter = DisabledLlmRouterAdapter()
        self.assertIsInstance(adapter, LlmRouterPort)

    def test_always_returns_a_typed_policy_violation_failure(self) -> None:
        adapter = DisabledLlmRouterAdapter()
        request = _request()
        response = adapter.complete(request)

        self.assertEqual(response.call_id, request.call_id)
        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.POLICY_VIOLATION)
        self.assertIsNone(response.model_used)
        self.assertIsNone(response.content)
        self.assertEqual(response.retry_count, 0)

    def test_never_fabricates_a_successful_result(self) -> None:
        adapter = DisabledLlmRouterAdapter()
        for _ in range(3):
            response = adapter.complete(_request())
            self.assertNotEqual(response.status, ModelCallStatus.SUCCEEDED)
