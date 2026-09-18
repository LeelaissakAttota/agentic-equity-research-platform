"""LLM Foundation domain package for model calls and structured output."""

from financial_intelligence.domain.llm.errors import ModelFailureKind
from financial_intelligence.domain.llm.ids import ModelCallId, ToolCallId
from financial_intelligence.domain.llm.model import (
    ModelCallStatus,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)
from financial_intelligence.domain.llm.structured_output import (
    StructuredModelOutput,
    StructuredOutputKind,
    ToolCallPayload,
)

__all__ = [
    "ModelCallId",
    "ModelCallStatus",
    "ModelFailureKind",
    "ModelMessage",
    "ModelMessageRole",
    "ModelRequest",
    "ModelResponse",
    "ModelUsage",
    "StructuredModelOutput",
    "StructuredOutputKind",
    "ToolCallId",
    "ToolCallPayload",
]
