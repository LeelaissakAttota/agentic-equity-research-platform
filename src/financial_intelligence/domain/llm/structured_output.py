"""LLM Foundation Phase 4 — provider-agnostic structured model output.

Parses the *text* content of a completed ``ModelResponse`` (see
``domain/llm/model.py``) into one of two closed shapes: a final textual
answer, or a request to invoke a tool/capability. This module knows nothing
about OpenRouter, HTTP, or any other provider/transport concern — it is a
pure text-in, typed-object-out parser, matching MODEL_POLICY.md's stance
that "LLM output must never directly execute a tool".

Convention: the model is prompted (elsewhere, in application/infrastructure
prompt templates — out of scope here) to emit a single JSON object shaped as
either::

    {"type": "final_answer", "text": "..."}

or::

    {"type": "tool_call", "tool_name": "...", "arguments": {"k": "v", ...}}

Anything else — invalid JSON, wrong top-level type, missing/oversized
fields, disallowed argument value types — is rejected by raising
``ValueError`` from ``StructuredModelOutput.parse``, matching this
codebase's domain convention (frozen dataclasses validated in
``__post_init__``, plain ``ValueError`` on invalid input; see
``domain/llm/model.py`` and ``domain/orchestration/tasks.py``). Callers in
the application layer are responsible for turning a raised ``ValueError``
into a typed, safe failure object rather than leaking the raw error text to
a client (see ``application/tool_call_execution.py``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

_MAX_STRUCTURED_CONTENT_LENGTH = 32_768
_MAX_FINAL_ANSWER_TEXT_LENGTH = 32_768
_MAX_TOOL_NAME_LENGTH = 128
_MAX_TOOL_ARGUMENTS = 16
_MAX_ARGUMENT_KEY_LENGTH = 64
_MAX_ARGUMENT_VALUE_LENGTH = 512

# Scalar JSON value types a tool-call argument may hold. Nested objects/arrays
# are rejected: they would widen the surface a caller must validate and are
# never required by any current capability's ``required_inputs``.
_ALLOWED_ARGUMENT_VALUE_TYPES = (str, int, float, bool, type(None))


class StructuredOutputKind(StrEnum):
    """The two closed shapes a parsed model output may take."""

    FINAL_ANSWER = "final_answer"
    TOOL_CALL = "tool_call"


@dataclass(frozen=True, slots=True)
class ToolCallPayload:
    """The tool-call portion of a structured model output, pre-validation.

    This is a syntactic/shape check only (non-empty bounded tool name,
    bounded flat scalar argument map). It intentionally does not know
    whether ``tool_name`` refers to a real, registered capability — that
    resolution happens against ``CapabilityRegistry`` in the application
    layer, which is the explicit validation step between "the model asked
    for a tool" and "a tool actually runs".
    """

    tool_name: str
    arguments: Mapping[str, str | int | float | bool | None]

    def __post_init__(self) -> None:
        name = self.tool_name.strip()
        if not name or len(name) > _MAX_TOOL_NAME_LENGTH:
            msg = "tool_name is empty or exceeds bounds"
            raise ValueError(msg)
        if any(ord(ch) < 32 for ch in name):
            msg = "tool_name must not contain control characters"
            raise ValueError(msg)
        object.__setattr__(self, "tool_name", name)

        if len(self.arguments) > _MAX_TOOL_ARGUMENTS:
            msg = "tool_call arguments exceed maximum count"
            raise ValueError(msg)
        for key, value in self.arguments.items():
            if not isinstance(key, str) or not key.strip() or len(key) > _MAX_ARGUMENT_KEY_LENGTH:
                msg = "tool_call argument key is empty or exceeds bounds"
                raise ValueError(msg)
            if any(ord(ch) < 32 for ch in key):
                msg = "tool_call argument key must not contain control characters"
                raise ValueError(msg)
            if not isinstance(value, _ALLOWED_ARGUMENT_VALUE_TYPES):
                msg = "tool_call argument value must be a scalar"
                raise ValueError(msg)
            if isinstance(value, str) and len(value) > _MAX_ARGUMENT_VALUE_LENGTH:
                msg = "tool_call argument value exceeds bounds"
                raise ValueError(msg)
        object.__setattr__(self, "arguments", dict(self.arguments))


@dataclass(frozen=True, slots=True)
class StructuredModelOutput:
    """Provider-neutral parsed shape of one model response's text content."""

    kind: StructuredOutputKind
    final_text: str | None = None
    tool_call: ToolCallPayload | None = None

    def __post_init__(self) -> None:
        if self.kind is StructuredOutputKind.FINAL_ANSWER:
            if self.tool_call is not None:
                msg = "final_answer output must not carry a tool_call"
                raise ValueError(msg)
            if self.final_text is None or not self.final_text.strip():
                msg = "final_answer output requires non-empty text"
                raise ValueError(msg)
            if len(self.final_text) > _MAX_FINAL_ANSWER_TEXT_LENGTH:
                msg = "final_answer text exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "final_text", self.final_text.strip())
        elif self.kind is StructuredOutputKind.TOOL_CALL:
            if self.tool_call is None:
                msg = "tool_call output requires a tool_call payload"
                raise ValueError(msg)
            if self.final_text is not None:
                msg = "tool_call output must not carry final_text"
                raise ValueError(msg)

    @classmethod
    def parse(cls, content: str) -> StructuredModelOutput:
        """Parse a model response's raw text content into a closed shape.

        Raises ``ValueError`` for anything that is not valid JSON, is not a
        JSON object, or does not match one of the two authorized shapes.
        Never executes, imports, or evaluates anything from ``content`` —
        this is a pure data-shape parser (``json.loads`` only).
        """

        if not isinstance(content, str) or not content.strip():
            msg = "structured output content must be a non-empty string"
            raise ValueError(msg)
        if len(content) > _MAX_STRUCTURED_CONTENT_LENGTH:
            msg = "structured output content exceeds bounds"
            raise ValueError(msg)

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            msg = "structured output is not valid JSON"
            raise ValueError(msg) from exc

        if not isinstance(payload, dict):
            msg = "structured output must be a JSON object"
            raise ValueError(msg)

        output_type = payload.get("type")
        if output_type == StructuredOutputKind.FINAL_ANSWER.value:
            text = payload.get("text")
            if not isinstance(text, str):
                msg = "final_answer output requires a string 'text' field"
                raise ValueError(msg)
            return cls(kind=StructuredOutputKind.FINAL_ANSWER, final_text=text)

        if output_type == StructuredOutputKind.TOOL_CALL.value:
            tool_name = payload.get("tool_name")
            arguments = payload.get("arguments", {})
            if not isinstance(tool_name, str):
                msg = "tool_call output requires a string 'tool_name' field"
                raise ValueError(msg)
            if not isinstance(arguments, dict):
                msg = "tool_call output requires an 'arguments' object"
                raise ValueError(msg)
            return cls(
                kind=StructuredOutputKind.TOOL_CALL,
                tool_call=ToolCallPayload(tool_name=tool_name, arguments=arguments),
            )

        msg = "structured output 'type' must be 'final_answer' or 'tool_call'"
        raise ValueError(msg)
