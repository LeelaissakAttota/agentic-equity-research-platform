"""Domain tests for LLM Foundation Phase 1 — provider-agnostic model-call contracts."""

from __future__ import annotations

from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from financial_intelligence.domain.llm import (
    ModelCallId,
    ModelCallStatus,
    ModelFailureKind,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)

_UUID_V4_TEXT = "11111111-1111-4111-8111-111111111111"


class ModelCallIdTests(TestCase):
    def test_new_generates_uuid_v4(self) -> None:
        call_id = ModelCallId.new()
        self.assertEqual(call_id.value.version, 4)

    def test_from_string_round_trips(self) -> None:
        call_id = ModelCallId.from_string(_UUID_V4_TEXT)
        self.assertEqual(call_id.as_text(), _UUID_V4_TEXT)
        self.assertEqual(call_id.value, UUID(_UUID_V4_TEXT))

    def test_rejects_non_v4_uuid(self) -> None:
        uuid1_text = "e29b41d4-a716-1170-9226-00242ac81004"
        with self.assertRaises(ValueError):
            ModelCallId.from_string(uuid1_text)

    def test_equality_and_hash_by_value(self) -> None:
        first = ModelCallId.from_string(_UUID_V4_TEXT)
        second = ModelCallId.from_string(_UUID_V4_TEXT)
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))


class ModelMessageTests(TestCase):
    def test_valid_message(self) -> None:
        message = ModelMessage(role="user", content="What is the ticker for Acme Corp?")
        self.assertEqual(message.content, "What is the ticker for Acme Corp?")

    def test_strips_surrounding_whitespace(self) -> None:
        message = ModelMessage(role="system", content="  be concise  ")
        self.assertEqual(message.content, "be concise")

    def test_rejects_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            ModelMessage(role="user", content="   ")

    def test_rejects_oversized_content(self) -> None:
        with self.assertRaises(ValueError):
            ModelMessage(role="user", content="x" * 32_769)


class ModelUsageTests(TestCase):
    def test_default_usage_has_zero_cost(self) -> None:
        usage = ModelUsage()
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.output_tokens)
        self.assertEqual(usage.estimated_cost, Decimal("0"))

    def test_accepts_explicit_decimal_cost(self) -> None:
        usage = ModelUsage(input_tokens=100, output_tokens=50, estimated_cost=Decimal("0.00"))
        self.assertEqual(usage.estimated_cost, Decimal("0.00"))
        self.assertIsInstance(usage.estimated_cost, Decimal)

    def test_rejects_negative_input_tokens(self) -> None:
        with self.assertRaises(ValueError):
            ModelUsage(input_tokens=-1)

    def test_rejects_negative_output_tokens(self) -> None:
        with self.assertRaises(ValueError):
            ModelUsage(output_tokens=-1)

    def test_rejects_negative_cost(self) -> None:
        with self.assertRaises(ValueError):
            ModelUsage(estimated_cost=Decimal("-0.01"))


class ModelRequestTests(TestCase):
    def _messages(self) -> tuple[ModelMessage, ...]:
        return (ModelMessage(role="user", content="Summarize the filing."),)

    def test_valid_request(self) -> None:
        request = ModelRequest(
            call_id=ModelCallId.new(),
            prompt_version="synthesis-v1",
            messages=self._messages(),
            max_output_tokens=256,
        )
        self.assertEqual(request.prompt_version, "synthesis-v1")
        self.assertEqual(len(request.messages), 1)
        self.assertIsNone(request.correlation_id)

    def test_strips_prompt_version_whitespace(self) -> None:
        request = ModelRequest(
            call_id=ModelCallId.new(),
            prompt_version="  synthesis-v1  ",
            messages=self._messages(),
            max_output_tokens=256,
        )
        self.assertEqual(request.prompt_version, "synthesis-v1")

    def test_rejects_blank_prompt_version(self) -> None:
        with self.assertRaises(ValueError):
            ModelRequest(
                call_id=ModelCallId.new(),
                prompt_version="   ",
                messages=self._messages(),
                max_output_tokens=256,
            )

    def test_rejects_empty_messages(self) -> None:
        with self.assertRaises(ValueError):
            ModelRequest(
                call_id=ModelCallId.new(),
                prompt_version="synthesis-v1",
                messages=(),
                max_output_tokens=256,
            )

    def test_rejects_max_output_tokens_below_minimum(self) -> None:
        with self.assertRaises(ValueError):
            ModelRequest(
                call_id=ModelCallId.new(),
                prompt_version="synthesis-v1",
                messages=self._messages(),
                max_output_tokens=0,
            )

    def test_rejects_max_output_tokens_above_ceiling(self) -> None:
        with self.assertRaises(ValueError):
            ModelRequest(
                call_id=ModelCallId.new(),
                prompt_version="synthesis-v1",
                messages=self._messages(),
                max_output_tokens=32_769,
            )

    def test_rejects_blank_correlation_id_when_provided(self) -> None:
        with self.assertRaises(ValueError):
            ModelRequest(
                call_id=ModelCallId.new(),
                prompt_version="synthesis-v1",
                messages=self._messages(),
                max_output_tokens=256,
                correlation_id="   ",
            )

    def test_accepts_valid_correlation_id(self) -> None:
        request = ModelRequest(
            call_id=ModelCallId.new(),
            prompt_version="synthesis-v1",
            messages=self._messages(),
            max_output_tokens=256,
            correlation_id="req-123",
        )
        self.assertEqual(request.correlation_id, "req-123")


class ModelResponseTests(TestCase):
    def test_succeeded_response_requires_content(self) -> None:
        with self.assertRaises(ValueError):
            ModelResponse(
                call_id=ModelCallId.new(),
                status=ModelCallStatus.SUCCEEDED,
                model_used="free/model-a",
                content=None,
                usage=ModelUsage(),
                retry_count=0,
            )

    def test_succeeded_response_rejects_blank_content(self) -> None:
        with self.assertRaises(ValueError):
            ModelResponse(
                call_id=ModelCallId.new(),
                status=ModelCallStatus.SUCCEEDED,
                model_used="free/model-a",
                content="   ",
                usage=ModelUsage(),
                retry_count=0,
            )

    def test_succeeded_response_rejects_failure_kind(self) -> None:
        with self.assertRaises(ValueError):
            ModelResponse(
                call_id=ModelCallId.new(),
                status=ModelCallStatus.SUCCEEDED,
                model_used="free/model-a",
                content="answer",
                usage=ModelUsage(),
                retry_count=0,
                failure_kind=ModelFailureKind.TIMEOUT,
            )

    def test_valid_succeeded_response(self) -> None:
        response = ModelResponse(
            call_id=ModelCallId.new(),
            status=ModelCallStatus.SUCCEEDED,
            model_used="free/model-a",
            content="answer",
            usage=ModelUsage(input_tokens=10, output_tokens=5),
            retry_count=0,
        )
        self.assertEqual(response.status, ModelCallStatus.SUCCEEDED)
        self.assertIsNone(response.failure_kind)

    def test_failed_response_requires_failure_kind(self) -> None:
        with self.assertRaises(ValueError):
            ModelResponse(
                call_id=ModelCallId.new(),
                status=ModelCallStatus.FAILED,
                model_used=None,
                content=None,
                usage=ModelUsage(),
                retry_count=1,
            )

    def test_valid_failed_response(self) -> None:
        response = ModelResponse(
            call_id=ModelCallId.new(),
            status=ModelCallStatus.FAILED,
            model_used=None,
            content=None,
            usage=ModelUsage(),
            retry_count=3,
            failure_kind=ModelFailureKind.RATE_LIMITED,
        )
        self.assertEqual(response.failure_kind, ModelFailureKind.RATE_LIMITED)
        self.assertIsNone(response.model_used)

    def test_degraded_response_permits_partial_content_absence(self) -> None:
        response = ModelResponse(
            call_id=ModelCallId.new(),
            status=ModelCallStatus.DEGRADED,
            model_used="free/fallback-model",
            content=None,
            usage=ModelUsage(),
            retry_count=2,
            failure_kind=ModelFailureKind.UPSTREAM_ERROR,
        )
        self.assertEqual(response.status, ModelCallStatus.DEGRADED)

    def test_rejects_negative_retry_count(self) -> None:
        with self.assertRaises(ValueError):
            ModelResponse(
                call_id=ModelCallId.new(),
                status=ModelCallStatus.FAILED,
                model_used=None,
                content=None,
                usage=ModelUsage(),
                retry_count=-1,
                failure_kind=ModelFailureKind.NETWORK_ERROR,
            )

    def test_rejects_blank_model_used_when_provided(self) -> None:
        with self.assertRaises(ValueError):
            ModelResponse(
                call_id=ModelCallId.new(),
                status=ModelCallStatus.FAILED,
                model_used="   ",
                content=None,
                usage=ModelUsage(),
                retry_count=1,
                failure_kind=ModelFailureKind.UNKNOWN,
            )


class ModelFailureKindTests(TestCase):
    def test_all_members_are_str_enum_values(self) -> None:
        for member in ModelFailureKind:
            self.assertIsInstance(member.value, str)
            self.assertEqual(member, ModelFailureKind(member.value))

    def test_contains_expected_categories(self) -> None:
        expected = {
            "timeout",
            "rate_limited",
            "authentication_error",
            "invalid_request",
            "context_exceeded",
            "content_policy",
            "malformed_output",
            "upstream_error",
            "network_error",
            "policy_violation",
            "unknown",
        }
        self.assertEqual({member.value for member in ModelFailureKind}, expected)
