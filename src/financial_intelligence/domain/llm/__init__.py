"""LLM Foundation Phase 1 — provider-agnostic domain package for model calls."""

from financial_intelligence.domain.llm.errors import ModelFailureKind
from financial_intelligence.domain.llm.ids import ModelCallId
from financial_intelligence.domain.llm.model import (
    ModelCallStatus,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelUsage,
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
]
