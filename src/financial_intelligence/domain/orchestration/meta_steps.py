"""Orchestration-level meta-step model — distinct from ``TaskType``.

``TaskType`` (tasks.py) is exclusively for *executable research capabilities*:
every value has a 1:1 mapping to a ``CapabilityDescriptor`` in
``CapabilityRegistry`` and is dispatchable by ``Phase6CapabilityExecutor``.
That invariant is load-bearing — the executor relies on every ``TaskType``
being backed by a real, registered capability, and never fabricates success
for one that is not.

``MetaStepType`` is a separate, parallel concept for *orchestration
operations about other steps* — planning, gathering evidence across tasks,
critiquing a run, synthesizing a final answer. These are not capabilities a
``Phase6CapabilityExecutor`` can dispatch to, so they intentionally do not
appear in ``TaskType`` and are never registered in ``CapabilityRegistry``.
Forcing them through that dispatch path would either require fake capability
entries with no real behavior behind them, or special-casing inside the
executor — both would corrupt the existing capability-registry invariant.

This module only defines the typed vocabulary for meta-steps. No orchestrator
in this phase drives ``MetaStep`` through ``Phase6CapabilityExecutor`` or any
other capability-execution path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class MetaStepType(StrEnum):
    """Orchestration/meta operations around capability-dispatchable tasks."""

    PLAN = "plan"
    EVIDENCE_COLLECTION = "evidence_collection"
    CRITIQUE = "critique"
    SYNTHESIS = "synthesis"


class MetaStepStatus(StrEnum):
    """Meta-step lifecycle states.

    ``UNSUPPORTED`` is the explicit terminal state for a meta-step whose
    backing agent has no implementation yet (this phase's reality for all
    four ``MetaStepType`` values) — it must never be confused with
    ``COMPLETED``.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"


_ALLOWED_TRANSITIONS: dict[MetaStepStatus, frozenset[MetaStepStatus]] = {
    MetaStepStatus.PENDING: frozenset(
        {MetaStepStatus.RUNNING, MetaStepStatus.SKIPPED, MetaStepStatus.UNSUPPORTED}
    ),
    MetaStepStatus.RUNNING: frozenset({MetaStepStatus.COMPLETED, MetaStepStatus.FAILED}),
    MetaStepStatus.COMPLETED: frozenset(),
    MetaStepStatus.FAILED: frozenset(),
    MetaStepStatus.SKIPPED: frozenset(),
    MetaStepStatus.UNSUPPORTED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class MetaStepId:
    """Opaque meta-step identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "meta_step_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> MetaStepId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> MetaStepId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class MetaStep:
    """One orchestration-level meta-step (not a capability-dispatchable task).

    Deliberately has no ``capability_id`` field (unlike ``ResearchTask``) —
    a meta-step is never looked up in ``CapabilityRegistry`` or executed via
    ``ResearchCapabilityExecutorPort``.
    """

    step_id: MetaStepId
    step_type: MetaStepType
    sequence: int
    description: str
    status: MetaStepStatus = MetaStepStatus.PENDING
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            msg = "sequence must be non-negative"
            raise ValueError(msg)
        desc = " ".join(self.description.strip().split())
        if not desc or len(desc) > 512:
            msg = "meta-step description empty or exceeds bounds"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in desc):
            msg = "meta-step description must not contain control characters"
            raise ValueError(msg)
        object.__setattr__(self, "description", desc)
        if self.message is not None:
            note = " ".join(self.message.strip().split())
            if not note or len(note) > 512:
                msg = "meta-step message empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "message", note)
        for ts in (self.created_at, self.started_at, self.completed_at):
            if ts is not None and ts.tzinfo is None:
                msg = "meta-step timestamps must be timezone-aware when set"
                raise ValueError(msg)

    def with_status(
        self,
        status: MetaStepStatus,
        *,
        at: datetime | None = None,
        message: str | None = None,
    ) -> MetaStep:
        """Return a copy after a validated lifecycle transition."""

        allowed = _ALLOWED_TRANSITIONS[self.status]
        if status not in allowed:
            msg = f"invalid meta-step transition {self.status.value} -> {status.value}"
            raise ValueError(msg)
        started = self.started_at
        completed = self.completed_at
        if status is MetaStepStatus.RUNNING:
            started = at
        if status in {
            MetaStepStatus.COMPLETED,
            MetaStepStatus.FAILED,
            MetaStepStatus.SKIPPED,
            MetaStepStatus.UNSUPPORTED,
        }:
            completed = at
        return replace(
            self,
            status=status,
            started_at=started,
            completed_at=completed,
            message=message if message is not None else self.message,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id.as_text(),
            "step_type": self.step_type.value,
            "sequence": self.sequence,
            "description": self.description,
            "status": self.status.value,
            "message": self.message,
            "created_at": (
                self.created_at.isoformat().replace("+00:00", "Z") if self.created_at else None
            ),
            "started_at": (
                self.started_at.isoformat().replace("+00:00", "Z") if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat().replace("+00:00", "Z") if self.completed_at else None
            ),
            "kind": "meta_step",
        }
