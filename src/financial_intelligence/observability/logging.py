"""Structured logging foundation with secret-safe defaults."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from financial_intelligence.observability.correlation import get_correlation_id

_CONFIGURED = False
_HANDLER_NAME = "financial_intelligence.structured"
_NOISY_OR_URL_BEARING_LOGGERS = ("uvicorn.access", "httpx", "httpcore")
_SECRET_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "database_url",
    "redis_url",
    "dsn",
)


class StructuredFormatter(logging.Formatter):
    """Emit one JSON object per log record with correlation context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = get_correlation_id()
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            }
        }
        for key, value in extras.items():
            payload[key] = _redact_value(key, value)

        if record.exc_info:
            exception_type = record.exc_info[0]
            payload["exception_type"] = (
                exception_type.__name__ if exception_type is not None else "Exception"
            )
        return json.dumps(payload, default=str, ensure_ascii=False)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS)


def _redact_value(key: str, value: Any) -> Any:
    """Redact sensitive keys, including nested mappings and sequences."""

    if _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(child_key): _redact_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(key, item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(key, item) for item in value)
    return value


def configure_logging(level: str = "INFO", *, force: bool = False) -> None:
    """Configure process logging once, unless ``force`` is requested.

    Repeated ``create_app()`` calls must not wipe handlers installed by prior
    instances in the same process.
    """

    global _CONFIGURED
    root = logging.getLogger()
    normalized = level.upper()
    if _CONFIGURED and not force:
        root.setLevel(normalized)
        for logger_name in _NOISY_OR_URL_BEARING_LOGGERS:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
        return

    # Remove only our previous structured handler to avoid stacking duplicates
    # when force=True, without deleting unrelated application handlers.
    root.handlers = [
        handler for handler in root.handlers if getattr(handler, "name", None) != _HANDLER_NAME
    ]
    handler = logging.StreamHandler(sys.stdout)
    handler.name = _HANDLER_NAME
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(normalized)
    for logger_name in _NOISY_OR_URL_BEARING_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    _CONFIGURED = True


def reset_logging_configuration() -> None:
    """Test helper to clear the one-time logging configuration latch."""

    global _CONFIGURED
    root = logging.getLogger()
    root.handlers = [
        handler for handler in root.handlers if getattr(handler, "name", None) != _HANDLER_NAME
    ]
    _CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""

    return logging.getLogger(name)
