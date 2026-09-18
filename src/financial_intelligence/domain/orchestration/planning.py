"""Provider-neutral planning outcome contract for PlannerPort.

This module defines the typed result a planner (deterministic today, LLM-backed
in a future phase) returns when asked to turn a :class:`ResearchRequest` into a
:class:`ResearchPlan`. It carries no provider-specific types and no network
concerns — those live behind ``application.ports.PlannerPort`` and its
concrete adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.orchestration.plan import ResearchPlan


class PlannerOutcomeStatus(StrEnum):
    """Outcome of a single planning attempt.

    Mirrors the "never fabricate success" convention used by every other
    typed outcome in this codebase (e.g. ``TaskResultStatus``,
    ``ModelCallStatus``): a closed enum plus a dataclass, not a generic
    Result/Either type.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PlannerOutcome:
    """Typed result of ``PlannerPort.create_plan``.

    A planner that has no working implementation (this phase's stub) must
    return ``UNAVAILABLE`` and must never attach a plan. ``INVALID`` covers a
    malformed/unsupported request. ``FAILED`` covers a planner that attempted
    to plan and could not (e.g. a future LLM call failure) — also without a
    plan attached.
    """

    status: PlannerOutcomeStatus
    message: str
    plan: ResearchPlan | None = None
    planner_version: str | None = None

    def __post_init__(self) -> None:
        message = " ".join(self.message.strip().split())
        if not message or len(message) > 512:
            msg = "message empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "message", message)
        if self.status is PlannerOutcomeStatus.OK and self.plan is None:
            msg = "ok outcomes require a research plan"
            raise ValueError(msg)
        if self.status is not PlannerOutcomeStatus.OK and self.plan is not None:
            msg = f"{self.status.value} outcomes must not attach a plan"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "planner_version": self.planner_version,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "kind": "planner_outcome",
        }
