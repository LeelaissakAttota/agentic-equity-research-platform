"""Lightweight cancellation / execution control (no background workers)."""

from __future__ import annotations


class ExecutionControl:
    """Mutable cancellation token checked between task executions.

    Cancellation is cooperative: the engine stops before starting the next
    ready task. It does not interrupt an in-flight capability call.
    """

    __slots__ = ("_cancelled", "_reason")

    def __init__(self) -> None:
        self._cancelled = False
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def reason(self) -> str | None:
        return self._reason

    def cancel(self, reason: str = "cancelled") -> None:
        text = " ".join(reason.strip().split())
        if not text or len(text) > 256:
            msg = "cancellation reason empty or exceeds bounds"
            raise ValueError(msg)
        self._cancelled = True
        self._reason = text

    def to_dict(self) -> dict[str, object]:
        return {
            "cancelled": self._cancelled,
            "reason": self._reason,
            "kind": "execution_control",
        }
