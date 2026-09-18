"""Fail-closed LlmRouterPort stand-in used when live OpenRouter calls are disabled.

Wired by composition whenever ``openrouter_live_enabled`` is False, or no
primary free model is configured. Matches this project's fail-closed posture:
an LlmRouterPort is always available to callers, but it never silently
succeeds or fabricates a result when live routing is off (MODEL_POLICY.md's
"Graceful degradation": never conceal the outage, never fabricate an answer).
"""

from __future__ import annotations

from financial_intelligence.domain.llm import (
    ModelCallStatus,
    ModelFailureKind,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)


class DisabledLlmRouterAdapter:
    """LlmRouterPort implementation that always returns a typed failure.

    Makes no network calls and requires no configuration.
    """

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            call_id=request.call_id,
            status=ModelCallStatus.FAILED,
            model_used=None,
            content=None,
            usage=ModelUsage(),
            retry_count=0,
            failure_kind=ModelFailureKind.POLICY_VIOLATION,
        )
