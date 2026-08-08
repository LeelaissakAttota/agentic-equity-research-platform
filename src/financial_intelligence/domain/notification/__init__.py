"""Notification domain package."""

from financial_intelligence.domain.notification.model import (
    NotificationEvent,
    NotificationId,
    NotificationType,
)

__all__ = ["NotificationEvent", "NotificationId", "NotificationType"]
