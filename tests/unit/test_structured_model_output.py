"""Domain tests for LLM Foundation Phase 4 — structured model output parsing."""

from __future__ import annotations

import json
from unittest import TestCase

from financial_intelligence.domain.llm.structured_output import (
    StructuredModelOutput,
    StructuredOutputKind,
    ToolCallPayload,
)


class StructuredModelOutputParseFinalAnswerTests(TestCase):
    def test_parses_valid_final_answer(self) -> None:
        content = json.dumps({"type": "final_answer", "text": "Apple trades as AAPL."})
        output = StructuredModelOutput.parse(content)
        self.assertEqual(output.kind, StructuredOutputKind.FINAL_ANSWER)
        self.assertEqual(output.final_text, "Apple trades as AAPL.")
        self.assertIsNone(output.tool_call)

    def test_strips_surrounding_whitespace_from_final_text(self) -> None:
        content = json.dumps({"type": "final_answer", "text": "  padded  "})
        output = StructuredModelOutput.parse(content)
        self.assertEqual(output.final_text, "padded")

    def test_rejects_empty_final_text(self) -> None:
        content = json.dumps({"type": "final_answer", "text": "   "})
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_non_string_final_text(self) -> None:
        content = json.dumps({"type": "final_answer", "text": 123})
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)


class StructuredModelOutputParseToolCallTests(TestCase):
    def test_parses_valid_tool_call(self) -> None:
        content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "company_resolution",
                "arguments": {"raw_query": "Apple"},
            }
        )
        output = StructuredModelOutput.parse(content)
        self.assertEqual(output.kind, StructuredOutputKind.TOOL_CALL)
        self.assertIsNone(output.final_text)
        assert output.tool_call is not None
        self.assertEqual(output.tool_call.tool_name, "company_resolution")
        self.assertEqual(output.tool_call.arguments, {"raw_query": "Apple"})

    def test_tool_call_defaults_to_empty_arguments(self) -> None:
        content = json.dumps({"type": "tool_call", "tool_name": "company_resolution"})
        output = StructuredModelOutput.parse(content)
        assert output.tool_call is not None
        self.assertEqual(output.tool_call.arguments, {})

    def test_rejects_non_string_tool_name(self) -> None:
        content = json.dumps({"type": "tool_call", "tool_name": 42, "arguments": {}})
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_non_object_arguments(self) -> None:
        content = json.dumps(
            {"type": "tool_call", "tool_name": "company_resolution", "arguments": ["a", "b"]}
        )
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_nested_argument_values(self) -> None:
        content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "company_resolution",
                "arguments": {"raw_query": {"nested": "value"}},
            }
        )
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_too_many_arguments(self) -> None:
        arguments = {f"key_{i}": "value" for i in range(20)}
        content = json.dumps(
            {"type": "tool_call", "tool_name": "company_resolution", "arguments": arguments}
        )
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_arbitrary_python_dotted_name_as_tool_name(self) -> None:
        """A dotted/attribute-style name is parsed as an opaque string, not resolved."""

        content = json.dumps(
            {"type": "tool_call", "tool_name": "os.system", "arguments": {"raw_query": "rm -rf"}}
        )
        output = StructuredModelOutput.parse(content)
        assert output.tool_call is not None
        self.assertEqual(output.tool_call.tool_name, "os.system")


class StructuredModelOutputParseMalformedTests(TestCase):
    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse("{not valid json")

    def test_rejects_json_array(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(json.dumps(["final_answer", "text"]))

    def test_rejects_unknown_type(self) -> None:
        content = json.dumps({"type": "execute_shell", "command": "ls"})
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_missing_type(self) -> None:
        content = json.dumps({"text": "no type field"})
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse("   ")

    def test_rejects_oversized_content(self) -> None:
        content = json.dumps({"type": "final_answer", "text": "x" * 40_000})
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(content)

    def test_rejects_non_string_content(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput.parse(None)  # type: ignore[arg-type]


class ToolCallPayloadTests(TestCase):
    def test_rejects_empty_tool_name(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallPayload(tool_name="   ", arguments={})

    def test_rejects_oversized_tool_name(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallPayload(tool_name="x" * 200, arguments={})

    def test_rejects_control_characters_in_tool_name(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallPayload(tool_name="tool\x00name", arguments={})

    def test_rejects_oversized_argument_value(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallPayload(tool_name="company_resolution", arguments={"raw_query": "x" * 600})


class StructuredModelOutputConstructionTests(TestCase):
    def test_final_answer_rejects_tool_call_present(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput(
                kind=StructuredOutputKind.FINAL_ANSWER,
                final_text="ok",
                tool_call=ToolCallPayload(tool_name="company_resolution", arguments={}),
            )

    def test_tool_call_rejects_final_text_present(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput(
                kind=StructuredOutputKind.TOOL_CALL,
                final_text="ok",
                tool_call=ToolCallPayload(tool_name="company_resolution", arguments={}),
            )

    def test_tool_call_requires_payload(self) -> None:
        with self.assertRaises(ValueError):
            StructuredModelOutput(kind=StructuredOutputKind.TOOL_CALL)
