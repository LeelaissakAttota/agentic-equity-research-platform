"""Application contracts for Phase 7 research workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import CompanyQuery, ResolutionResult
from financial_intelligence.domain.orchestration import ResearchObjective
from financial_intelligence.domain.workflow import (
    ApprovalStatus,
    ResearchWorkflow,
    WorkflowId,
    WorkflowStatus,
)


class WorkflowOperationStatus(StrEnum):
    """Outcome of a workflow application operation."""

    OK = "ok"
    INVALID = "invalid"
    RESOLUTION_BLOCKED = "resolution_blocked"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    APPROVAL_REQUIRED = "approval_required"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CreateResearchWorkflowQuery:
    company_query: CompanyQuery
    objective: ResearchObjective
    objective_text: str | None = None
    jurisdiction: str | None = None
    time_horizon_days: int | None = None
    require_approval: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowOperationResult:
    status: WorkflowOperationStatus
    message: str
    workflow: ResearchWorkflow | None = None
    resolution: ResolutionResult | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            msg = "evaluated_at must be timezone-aware"
            raise ValueError(msg)
        if self.status is WorkflowOperationStatus.OK and self.workflow is None:
            msg = "ok results require a workflow"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
            "kind": "workflow_operation_result",
        }
        if self.evaluated_at is not None:
            payload["evaluated_at"] = self.evaluated_at.isoformat().replace("+00:00", "Z")
        if self.workflow is not None:
            payload["workflow"] = self.workflow.to_dict()
            payload["workflow_id"] = self.workflow.workflow_id.as_text()
            payload["approval_status"] = self.workflow.approval_status.value
        if self.resolution is not None:
            payload["resolution"] = {
                "status": self.resolution.status.value,
                "message": self.resolution.message,
                "company_id": (
                    self.resolution.company.company_id.as_text()
                    if self.resolution.company is not None
                    else None
                ),
            }
            if self.resolution.company is not None:
                payload["company"] = self.resolution.company.to_dict()
        return payload


@dataclass(frozen=True, slots=True)
class WorkflowListQuery:
    status: WorkflowStatus | None = None
    company_id: str | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 200:
            msg = "limit must be between 1 and 200"
            raise ValueError(msg)
        if self.offset < 0:
            msg = "offset must be non-negative"
            raise ValueError(msg)
        if self.company_id is not None and len(self.company_id) > 128:
            msg = "company_id filter exceeds bounds"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class WorkflowListResult:
    status: WorkflowOperationStatus
    message: str
    workflows: tuple[ResearchWorkflow, ...] = ()
    limit: int = 50
    offset: int = 0
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "limit": self.limit,
            "offset": self.offset,
            "count": len(self.workflows),
            "workflows": [w.to_dict() for w in self.workflows],
            "evaluated_at": (
                self.evaluated_at.isoformat().replace("+00:00", "Z") if self.evaluated_at else None
            ),
            "kind": "workflow_list_result",
        }


@dataclass(frozen=True, slots=True)
class ApprovalActionQuery:
    workflow_id: WorkflowId
    decision: ApprovalStatus
    note: str | None = None
    decision_source: str = "trusted_api"

    def __post_init__(self) -> None:
        if self.decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            msg = "approval decision must be approved or rejected"
            raise ValueError(msg)
        source = " ".join(self.decision_source.strip().split())
        if not source or len(source) > 64:
            msg = "decision_source empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "decision_source", source)
