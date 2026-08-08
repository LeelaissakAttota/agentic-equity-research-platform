"""Workflow lifecycle states and validated transitions."""

from __future__ import annotations

from enum import StrEnum


class WorkflowTransitionError(ValueError):
    """Invalid workflow lifecycle transition."""


class WorkflowStatus(StrEnum):
    """Explicit autonomous research workflow lifecycle."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.CREATED: frozenset(
        {WorkflowStatus.READY, WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.READY: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.RUNNING: frozenset(
        {
            WorkflowStatus.PAUSED,
            WorkflowStatus.AWAITING_APPROVAL,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.PARTIAL,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }
    ),
    WorkflowStatus.PAUSED: frozenset(
        {WorkflowStatus.READY, WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.AWAITING_APPROVAL: frozenset(
        {WorkflowStatus.READY, WorkflowStatus.CANCELLED, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.COMPLETED: frozenset(),
    WorkflowStatus.PARTIAL: frozenset(),
    WorkflowStatus.FAILED: frozenset(),
    WorkflowStatus.CANCELLED: frozenset(),
}


def assert_transition(current: WorkflowStatus, new: WorkflowStatus) -> None:
    """Fail closed on invalid lifecycle transitions."""

    if new not in _ALLOWED[current]:
        msg = f"invalid workflow transition {current.value} -> {new.value}"
        raise WorkflowTransitionError(msg)


def is_terminal(status: WorkflowStatus) -> bool:
    return status in {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    }
