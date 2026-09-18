"""Fail-closed PlannerPort stand-in used while no real planner is wired.

Mirrors ``infrastructure.llm.disabled_router.DisabledLlmRouterAdapter``: a
``PlannerPort`` implementation must always be available to callers, but this
one never silently succeeds or fabricates a plan. It makes no LLM calls and
requires no configuration. A future phase may wire a concrete adapter that
composes ``PlannerPort`` on top of ``LlmRouterPort``; until then, any caller
of ``PlannerPort`` receives an explicit ``UNAVAILABLE`` outcome.
"""

from __future__ import annotations

from financial_intelligence.domain.orchestration import (
    PlannerOutcome,
    PlannerOutcomeStatus,
    ResearchRequest,
)


class UnavailablePlannerAdapter:
    """PlannerPort implementation that always returns a typed UNAVAILABLE outcome.

    Makes no network calls, performs no planning, and never attaches a plan.
    """

    def create_plan(self, request: ResearchRequest) -> PlannerOutcome:
        del request  # unused: this stub never inspects the request
        return PlannerOutcome(
            status=PlannerOutcomeStatus.UNAVAILABLE,
            message="planner not implemented in this phase",
        )
