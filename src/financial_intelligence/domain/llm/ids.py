"""Stable provider-neutral identity primitives for LLM model calls.

Canonical IDs are UUIDv4 values, matching the identity convention used
throughout the rest of the domain layer (see ``domain/identity/ids.py``
and ``domain/orchestration/tasks.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ModelCallId:
    """Opaque identity for a single LLM model-call attempt."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "model_call_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> ModelCallId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> ModelCallId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ToolCallId:
    """Opaque identity for a single LLM-requested tool-call attempt (Phase 4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "tool_call_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> ToolCallId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> ToolCallId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)
