"""Lightweight cancellation / execution control (no background workers)."""

from __future__ import annotations


class ExecutionControl:
    """Mutable cancellation/pause token checked between task executions.

    Cancellation is cooperative: the engine stops before starting the next
    ready task. It does not interrupt an in-flight capability call.

    ``cancel`` is a hard stop that may terminalize remaining pending work.
    ``request_pause`` is a soft stop that preserves pending tasks for resume
    (Phase 7 workflow foundation).
    """

    __slots__ = ("_cancelled", "_pause", "_reason")

    def __init__(self) -> None:
        self._cancelled = False
        self._reason: str | None = None
        self._pause = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def is_pause(self) -> bool:
        return self._pause

    @property
    def reason(self) -> str | None:
        return self._reason

    def cancel(self, reason: str = "cancelled") -> None:
        text = " ".join(reason.strip().split())
        if not text or len(text) > 256:
            msg = "cancellation reason empty or exceeds bounds"
            raise ValueError(msg)
        self._cancelled = True
        self._pause = False
        self._reason = text

    def request_pause(self, reason: str = "paused") -> None:
        """Soft-stop: halt scheduling while preserving PENDING/READY tasks."""

        text = " ".join(reason.strip().split())
        if not text or len(text) > 256:
            msg = "pause reason empty or exceeds bounds"
            raise ValueError(msg)
        self._cancelled = True
        self._pause = True
        self._reason = text

    def to_dict(self) -> dict[str, object]:
        return {
            "cancelled": self._cancelled,
            "pause": self._pause,
            "reason": self._reason,
            "kind": "execution_control",
        }
