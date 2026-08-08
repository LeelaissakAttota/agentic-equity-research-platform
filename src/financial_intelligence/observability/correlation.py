"""Request correlation identity helpers."""

from __future__ import annotations

import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import uuid4

CORRELATION_HEADER = "X-Correlation-ID"
MAX_CORRELATION_ID_LENGTH = 64
_SAFE_CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


@dataclass(frozen=True, slots=True)
class CorrelationId:
    """Validated correlation identifier used across logs and API errors."""

    value: str

    def __post_init__(self) -> None:
        if not _SAFE_CORRELATION_PATTERN.fullmatch(self.value):
            msg = "correlation id failed validation"
            raise ValueError(msg)


def generate_correlation_id() -> CorrelationId:
    """Create a new UUID-based correlation identifier."""

    return CorrelationId(value=str(uuid4()))


def resolve_correlation_id(raw: str | None) -> CorrelationId:
    """Accept a safe inbound correlation ID or generate a new one."""

    if raw is None:
        return generate_correlation_id()
    candidate = raw.strip()
    if not candidate or len(candidate) > MAX_CORRELATION_ID_LENGTH:
        return generate_correlation_id()
    if not _SAFE_CORRELATION_PATTERN.fullmatch(candidate):
        return generate_correlation_id()
    return CorrelationId(value=candidate)


def bind_correlation_id(correlation_id: str) -> Token[str | None]:
    """Bind a correlation ID into the current context."""

    return _correlation_id_var.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the previous correlation ID context."""

    _correlation_id_var.reset(token)


def get_correlation_id() -> str | None:
    """Return the currently bound correlation ID, if any."""

    return _correlation_id_var.get()
