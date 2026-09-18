"""Application contracts for ResearchOrchestrator (Manager/Orchestrator seam)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.workflow_contracts import WorkflowOperationResult
from financial_intelligence.domain.orchestration import PlannerOutcome


class OrchestrationOutcomeStatus(StrEnum):
    """Outcome of one ResearchOrchestrator.execute call."""

    OK = "ok"
    INVALID = "invalid"
    PLANNER_UNAVAILABLE = "planner_unavailable"
    PLANNER_FAILED = "planner_failed"
    WORKFLOW_FAILED = "workflow_failed"


@dataclass(frozen=True, slots=True)
class OrchestrateResearchRequestResult:
    """Traceable result of the Manager/Orchestrator -> PlannerPort seam.

    Always carries the ``planner_outcome`` that produced it (when the planner
    was reached at all), so callers can distinguish "planner unavailable"
    from "planner attempted and failed" from "request was invalid before the
    planner was ever called."
    """

    status: OrchestrationOutcomeStatus
    message: str
    planner_outcome: PlannerOutcome | None = None
    workflow_result: WorkflowOperationResult | None = None
    correlation_id: str | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            msg = "evaluated_at must be timezone-aware"
            raise ValueError(msg)
        if self.status is OrchestrationOutcomeStatus.OK and self.workflow_result is None:
            msg = "ok results require a workflow result"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
            "kind": "orchestrate_research_request_result",
        }
        if self.correlation_id is not None:
            payload["correlation_id"] = self.correlation_id
        if self.evaluated_at is not None:
            payload["evaluated_at"] = self.evaluated_at.isoformat().replace("+00:00", "Z")
        if self.planner_outcome is not None:
            payload["planner_outcome"] = self.planner_outcome.to_dict()
        if self.workflow_result is not None:
            payload["workflow_result"] = self.workflow_result.to_dict()
        return payload
