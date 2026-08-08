"""Workflow identity value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class WorkflowId:
    """Opaque research-workflow identity (UUIDv4).

    Not interchangeable with ResearchRunId, RequestId, or CompanyId.
    """

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "workflow_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> WorkflowId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> WorkflowId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)
