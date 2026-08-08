"""ResearchWorkflow aggregate — Phase 7 Prompt 1 foundation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from financial_intelligence.domain.identity import (
    CompanyId,
    CountryCode,
    ExchangeCode,
    TickerSymbol,
)
from financial_intelligence.domain.orchestration import (
    RequestId,
    ResearchObjective,
    ResearchPlan,
)
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.workflow.approval import (
    ApprovalDecision,
    ApprovalRequirement,
    ApprovalStatus,
)
from financial_intelligence.domain.workflow.checkpoint import WorkflowCheckpoint
from financial_intelligence.domain.workflow.ids import WorkflowId
from financial_intelligence.domain.workflow.status import (
    WorkflowStatus,
    assert_transition,
    is_terminal,
)


@dataclass(frozen=True, slots=True)
class WorkflowCompanyQuery:
    """Minimal company-query snapshot owned by the workflow domain."""

    raw_query: str
    country: CountryCode | None = None
    exchange: ExchangeCode | None = None
    ticker: TickerSymbol | None = None

    def __post_init__(self) -> None:
        text = self.raw_query.strip()
        if len(text) > 200:
            msg = "raw_query exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "raw_query", text)

    def to_dict(self) -> dict[str, object]:
        return {
            "raw_query": self.raw_query,
            "country": self.country.as_text() if self.country else None,
            "exchange": self.exchange.as_text() if self.exchange else None,
            "ticker": self.ticker.as_text() if self.ticker else None,
        }


@dataclass(frozen=True, slots=True)
class ResearchWorkflow:
    """Persistent, human-governed research workflow wrapping a Phase 6 plan."""

    workflow_id: WorkflowId
    research_run_id: ResearchRunId
    request_id: RequestId
    company_id: CompanyId
    objective: ResearchObjective
    plan: ResearchPlan
    company_query: WorkflowCompanyQuery
    status: WorkflowStatus
    approval_status: ApprovalStatus
    approval_requirement: ApprovalRequirement
    created_at: datetime
    updated_at: datetime
    checkpoint_version: int = 0
    latest_checkpoint: WorkflowCheckpoint | None = None
    approval_decision: ApprovalDecision | None = None
    execution_message: str | None = None
    completed_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    partial_count: int = 0
    evidence_count: int = 0
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            msg = "workflow timestamps must be timezone-aware"
            raise ValueError(msg)
        if self.plan.research_run_id.as_text() != self.research_run_id.as_text():
            msg = "workflow research_run_id must match plan"
            raise ValueError(msg)
        if self.plan.company_id != self.company_id:
            msg = "workflow company_id must match plan"
            raise ValueError(msg)
        if self.checkpoint_version < 0:
            msg = "checkpoint_version must be non-negative"
            raise ValueError(msg)
        if (
            self.latest_checkpoint is not None
            and self.latest_checkpoint.workflow_id != self.workflow_id
        ):
            msg = "checkpoint workflow_id mismatch"
            raise ValueError(msg)

    def with_status(self, status: WorkflowStatus, *, at: datetime) -> ResearchWorkflow:
        if at.tzinfo is None:
            msg = "transition timestamp must be timezone-aware"
            raise ValueError(msg)
        assert_transition(self.status, status)
        return replace(self, status=status, updated_at=at)

    def with_checkpoint(self, checkpoint: WorkflowCheckpoint, *, at: datetime) -> ResearchWorkflow:
        if checkpoint.workflow_id != self.workflow_id:
            msg = "checkpoint workflow_id mismatch"
            raise ValueError(msg)
        if checkpoint.version != self.checkpoint_version + 1:
            msg = (
                f"checkpoint version must be {self.checkpoint_version + 1}, "
                f"got {checkpoint.version}"
            )
            raise ValueError(msg)
        return replace(
            self,
            plan=checkpoint.plan,
            latest_checkpoint=checkpoint,
            checkpoint_version=checkpoint.version,
            updated_at=at,
            warnings=checkpoint.warnings,
        )

    def with_approval(
        self,
        decision: ApprovalDecision,
        *,
        at: datetime,
        next_status: WorkflowStatus,
    ) -> ResearchWorkflow:
        if self.approval_status is not ApprovalStatus.PENDING:
            msg = f"cannot decide approval when status is {self.approval_status.value}"
            raise ValueError(msg)
        if is_terminal(self.status):
            msg = "cannot approve/reject a terminal workflow"
            raise ValueError(msg)
        updated = self.with_status(next_status, at=at)
        return replace(
            updated,
            approval_status=decision.status,
            approval_decision=decision,
            updated_at=at,
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "workflow_id": self.workflow_id.as_text(),
            "research_run_id": self.research_run_id.as_text(),
            "request_id": self.request_id.as_text(),
            "company_id": self.company_id.as_text(),
            "objective": self.objective.value,
            "status": self.status.value,
            "approval_status": self.approval_status.value,
            "approval_requirement": self.approval_requirement.to_dict(),
            "company_query": self.company_query.to_dict(),
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z"),
            "checkpoint_version": self.checkpoint_version,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "blocked_count": self.blocked_count,
            "partial_count": self.partial_count,
            "evidence_count": self.evidence_count,
            "warnings": list(self.warnings),
            "execution_message": self.execution_message,
            "task_count": len(self.plan.tasks),
            "kind": "research_workflow",
        }
        if self.approval_decision is not None:
            payload["approval_decision"] = self.approval_decision.to_dict()
        if self.latest_checkpoint is not None:
            payload["latest_checkpoint"] = {
                "version": self.latest_checkpoint.version,
                "created_at": self.latest_checkpoint.created_at.isoformat().replace("+00:00", "Z"),
                "completed_task_ids": list(self.latest_checkpoint.completed_task_ids),
                "pending_task_ids": list(self.latest_checkpoint.pending_task_ids),
                "failed_task_ids": list(self.latest_checkpoint.failed_task_ids),
                "blocked_task_ids": list(self.latest_checkpoint.blocked_task_ids),
                "total_attempts": self.latest_checkpoint.total_attempts,
                "external_calls": self.latest_checkpoint.external_calls,
                "message": self.latest_checkpoint.message,
            }
        return payload
