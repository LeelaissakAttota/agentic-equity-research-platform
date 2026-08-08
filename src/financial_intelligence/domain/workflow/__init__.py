"""Phase 7 workflow domain package — autonomous research workflow foundation."""

from financial_intelligence.domain.workflow.approval import (
    ApprovalDecision,
    ApprovalRequirement,
    ApprovalStatus,
)
from financial_intelligence.domain.workflow.checkpoint import WorkflowCheckpoint
from financial_intelligence.domain.workflow.ids import WorkflowId
from financial_intelligence.domain.workflow.model import ResearchWorkflow, WorkflowCompanyQuery
from financial_intelligence.domain.workflow.status import (
    WorkflowStatus,
    WorkflowTransitionError,
    assert_transition,
    is_terminal,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalRequirement",
    "ApprovalStatus",
    "ResearchWorkflow",
    "WorkflowCheckpoint",
    "WorkflowCompanyQuery",
    "WorkflowId",
    "WorkflowStatus",
    "WorkflowTransitionError",
    "assert_transition",
    "is_terminal",
]
