"""LLM Foundation Phase 1 — provider-agnostic domain contracts for model calls.

These types describe a single model-call attempt and its outcome only.
They intentionally say nothing about OpenRouter, HTTP transport, routing,
fallback, caching, or tool calling — those are infrastructure/application
concerns for later phases (see MODEL_POLICY.md and ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from financial_intelligence.domain.llm.errors import ModelFailureKind
from financial_intelligence.domain.llm.ids import ModelCallId

ModelMessageRole = Literal["system", "user", "assistant"]

_MAX_MESSAGE_CONTENT_LENGTH = 32_768
_MAX_PROMPT_VERSION_LENGTH = 64
_MAX_MODEL_IDENTIFIER_LENGTH = 128
_MAX_OUTPUT_TOKENS_CEILING = 32_768


class ModelCallStatus(StrEnum):
    """Outcome of a single model-call attempt."""

    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    """One provider-agnostic chat message."""

    role: ModelMessageRole
    content: str

    def __post_init__(self) -> None:
        content = self.content.strip()
        if not content:
            msg = "message content must not be empty"
            raise ValueError(msg)
        if len(content) > _MAX_MESSAGE_CONTENT_LENGTH:
            msg = "message content exceeds maximum length"
            raise ValueError(msg)
        object.__setattr__(self, "content", content)


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """Token and cost accounting for one model-call attempt.

    The $0 cost policy requires that a successful model call must have an
    explicitly established finite zero cost. Unknown, missing, malformed,
    or non-finite costs are a policy violation and must not be silently
    treated as zero. The ``cost_known`` flag tracks whether the provider
    returned a parseable, finite cost value.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal = Decimal("0")
    cost_known: bool = False

    def __post_init__(self) -> None:
        if self.input_tokens is not None and self.input_tokens < 0:
            msg = "input_tokens must not be negative"
            raise ValueError(msg)
        if self.output_tokens is not None and self.output_tokens < 0:
            msg = "output_tokens must not be negative"
            raise ValueError(msg)
        if not self.estimated_cost.is_finite():
            msg = "estimated_cost must be finite"
            raise ValueError(msg)
        if self.estimated_cost < 0:
            msg = "estimated_cost must not be negative"
            raise ValueError(msg)
        if self.cost_known and not self.estimated_cost.is_finite():
            msg = "estimated_cost must be finite when cost_known is True"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """A provider-agnostic request for a single model completion."""

    call_id: ModelCallId
    prompt_version: str
    messages: tuple[ModelMessage, ...]
    max_output_tokens: int
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        version = self.prompt_version.strip()
        if not version or len(version) > _MAX_PROMPT_VERSION_LENGTH:
            msg = "prompt_version is required and bounded in length"
            raise ValueError(msg)
        object.__setattr__(self, "prompt_version", version)
        if not self.messages:
            msg = "messages must not be empty"
            raise ValueError(msg)
        if self.max_output_tokens < 1 or self.max_output_tokens > _MAX_OUTPUT_TOKENS_CEILING:
            msg = "max_output_tokens must be between 1 and 32768"
            raise ValueError(msg)
        if self.correlation_id is not None and not self.correlation_id.strip():
            msg = "correlation_id must not be blank when provided"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """The typed outcome of a completed (or failed) model-call attempt."""

    call_id: ModelCallId
    status: ModelCallStatus
    model_used: str | None
    content: str | None
    usage: ModelUsage
    retry_count: int
    failure_kind: ModelFailureKind | None = None

    def __post_init__(self) -> None:
        if self.retry_count < 0:
            msg = "retry_count must not be negative"
            raise ValueError(msg)
        if self.model_used is not None:
            model_used = self.model_used.strip()
            if not model_used or len(model_used) > _MAX_MODEL_IDENTIFIER_LENGTH:
                msg = "model_used must not be blank or exceed maximum length when provided"
                raise ValueError(msg)
            object.__setattr__(self, "model_used", model_used)
        if self.status is ModelCallStatus.SUCCEEDED:
            if self.content is None or not self.content.strip():
                msg = "succeeded responses must include non-empty content"
                raise ValueError(msg)
            if self.failure_kind is not None:
                msg = "succeeded responses must not carry a failure_kind"
                raise ValueError(msg)
        if self.status is ModelCallStatus.FAILED and self.failure_kind is None:
            msg = "failed responses must include a failure_kind"
            raise ValueError(msg)
