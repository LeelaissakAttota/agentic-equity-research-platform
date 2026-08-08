"""Phase 6 orchestration domain — research tasks and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class TaskType(StrEnum):
    """Deterministic task types mapped to Phase 2-5 capabilities."""

    COMPANY_RESOLUTION = "company_resolution"
    MARKET_INTELLIGENCE = "market_intelligence"
    FINANCIAL_INTELLIGENCE = "financial_intelligence"
    NEWS_EVENT_INTELLIGENCE = "news_event_intelligence"
    INDUSTRY_INTELLIGENCE = "industry_intelligence"
    REGULATORY_INTELLIGENCE = "regulatory_intelligence"


class TaskStatus(StrEnum):
    """Task lifecycle states."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.SKIPPED}),
    TaskStatus.READY: frozenset(
        {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.SKIPPED, TaskStatus.PENDING}
    ),
    TaskStatus.RUNNING: frozenset(
        {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.SKIPPED}
    ),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.READY}),  # bounded retry only
    TaskStatus.SKIPPED: frozenset(),
    TaskStatus.BLOCKED: frozenset({TaskStatus.READY, TaskStatus.SKIPPED}),
}


@dataclass(frozen=True, slots=True)
class TaskId:
    """Opaque research-task identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "task_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> TaskId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> TaskId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ResearchTask:
    """One dependency-aware research task within a plan."""

    task_id: TaskId
    task_type: TaskType
    capability_id: str
    description: str
    dependencies: tuple[TaskId, ...] = ()
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 100
    required: bool = True
    attempt_count: int = 0
    max_attempts: int = 1
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            msg = "capability_id is required"
            raise ValueError(msg)
        object.__setattr__(self, "capability_id", self.capability_id.strip())
        desc = " ".join(self.description.strip().split())
        if not desc or len(desc) > 512:
            msg = "task description empty or exceeds bounds"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in desc):
            msg = "task description must not contain control characters"
            raise ValueError(msg)
        object.__setattr__(self, "description", desc)
        if self.priority < 1 or self.priority > 1000:
            msg = "priority must be between 1 and 1000"
            raise ValueError(msg)
        if self.max_attempts < 1 or self.max_attempts > 10:
            msg = "max_attempts must be between 1 and 10"
            raise ValueError(msg)
        if self.attempt_count < 0 or self.attempt_count > self.max_attempts:
            msg = "attempt_count out of bounds"
            raise ValueError(msg)
        if self.task_id in self.dependencies:
            msg = "task cannot depend on itself"
            raise ValueError(msg)
        for ts in (self.created_at, self.started_at, self.completed_at):
            if ts is not None and ts.tzinfo is None:
                msg = "task timestamps must be timezone-aware when set"
                raise ValueError(msg)

    def with_status(
        self,
        status: TaskStatus,
        *,
        at: datetime | None = None,
        authorized_retry: bool = False,
    ) -> ResearchTask:
        """Return a copy after a validated lifecycle transition.

        FAILED → READY is allowed only when ``authorized_retry=True`` (RetryPolicy).
        """

        allowed = _ALLOWED_TRANSITIONS[self.status]
        if status not in allowed:
            msg = f"invalid task transition {self.status.value} -> {status.value}"
            raise ValueError(msg)
        if self.status is TaskStatus.FAILED and status is TaskStatus.READY and not authorized_retry:
            msg = "FAILED → READY requires authorized_retry=True"
            raise ValueError(msg)
        started = self.started_at
        completed = self.completed_at
        attempts = self.attempt_count
        if status is TaskStatus.RUNNING:
            started = at
            attempts = self.attempt_count + 1
            if attempts > self.max_attempts:
                msg = "max_attempts exceeded"
                raise ValueError(msg)
        if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.SKIPPED}:
            completed = at
        return replace(
            self,
            status=status,
            started_at=started,
            completed_at=completed,
            attempt_count=attempts,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id.as_text(),
            "task_type": self.task_type.value,
            "capability_id": self.capability_id,
            "description": self.description,
            "dependencies": [d.as_text() for d in self.dependencies],
            "status": self.status.value,
            "priority": self.priority,
            "required": self.required,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "created_at": (
                self.created_at.isoformat().replace("+00:00", "Z") if self.created_at else None
            ),
            "started_at": (
                self.started_at.isoformat().replace("+00:00", "Z") if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat().replace("+00:00", "Z") if self.completed_at else None
            ),
            "kind": "research_task",
        }
