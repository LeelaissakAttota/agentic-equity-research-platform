"""In-memory notification adapter (no external channels)."""

from __future__ import annotations

from threading import RLock

from financial_intelligence.domain.notification import NotificationEvent


class NotificationAdapterError(RuntimeError):
    """Notification adapter failure."""


class InMemoryNotificationAdapter:
    """Records notifications for tests/dashboard; can be forced to fail."""

    def __init__(self, *, fail_closed: bool = False) -> None:
        self._lock = RLock()
        self._events: list[NotificationEvent] = []
        self._fail_closed = fail_closed

    def set_fail_closed(self, value: bool) -> None:
        self._fail_closed = value

    def publish(self, event: NotificationEvent) -> None:
        if self._fail_closed:
            msg = "notification adapter unavailable"
            raise NotificationAdapterError(msg)
        with self._lock:
            self._events.append(event)

    def list_events(self, *, limit: int = 100) -> tuple[NotificationEvent, ...]:
        if limit < 1 or limit > 500:
            msg = "limit must be between 1 and 500"
            raise NotificationAdapterError(msg)
        with self._lock:
            return tuple(self._events[-limit:])
