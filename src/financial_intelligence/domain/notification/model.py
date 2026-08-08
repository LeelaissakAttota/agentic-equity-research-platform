"""Notification domain contracts — no external channel integrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from financial_intelligence.domain.workflow.ids import WorkflowId


class NotificationType(StrEnum):
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_PARTIAL = "workflow_partial"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    APPROVAL_REQUIRED = "approval_required"
    MONITORING_CHECK_CREATED = "monitoring_check_created"


class NotificationId:
    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        if value.version != 4:
            msg = "notification_id must be a UUIDv4"
            raise ValueError(msg)
        self._value = value

    @classmethod
    def new(cls) -> NotificationId:
        return cls(uuid4())

    def as_text(self) -> str:
        return str(self._value)


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    """Bounded structured notification metadata (no secrets / stack traces)."""

    notification_id: NotificationId
    notification_type: NotificationType
    created_at: datetime
    workflow_id: WorkflowId | None = None
    company_id: str | None = None
    message: str = "notification"
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            msg = "notification created_at must be timezone-aware"
            raise ValueError(msg)
        text = " ".join(self.message.strip().split())
        if not text or len(text) > 512:
            msg = "notification message empty or exceeds bounds"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in text):
            msg = "notification message must not contain control characters"
            raise ValueError(msg)
        object.__setattr__(self, "message", text)
        if len(self.metadata) > 20:
            msg = "notification metadata exceeds bounds"
            raise ValueError(msg)
        for key, value in self.metadata:
            if len(key) > 64 or len(value) > 256:
                msg = "notification metadata entry exceeds bounds"
                raise ValueError(msg)
            lowered = f"{key} {value}".lower()
            if any(token in lowered for token in ("secret", "api_key", "password", "token=")):
                msg = "notification metadata must not contain secrets"
                raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "notification_id": self.notification_id.as_text(),
            "notification_type": self.notification_type.value,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "workflow_id": self.workflow_id.as_text() if self.workflow_id else None,
            "company_id": self.company_id,
            "message": self.message,
            "metadata": dict(self.metadata),
            "kind": "notification_event",
        }
