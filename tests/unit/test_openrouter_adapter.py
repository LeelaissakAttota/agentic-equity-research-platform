"""Phase 3 — OpenRouterAdapter tests (offline, fake HTTP transport only).

No live network calls. All assertions run against ``BoundedHttpClient`` wired
to a fake transport, matching the existing convention in
``test_bounded_client_post.py``.
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from unittest import TestCase

from pydantic import SecretStr

from financial_intelligence.domain.llm import (
    ModelCallId,
    ModelCallStatus,
    ModelFailureKind,
    ModelMessage,
    ModelRequest,
)
from financial_intelligence.infrastructure.http import (
    BoundedHttpClient,
    HttpResponse,
    HttpTransport,
)
from financial_intelligence.infrastructure.llm import (
    openrouter_adapter as openrouter_adapter_module,
)
from financial_intelligence.infrastructure.llm.openrouter_adapter import OpenRouterAdapter

_SECRET_TOKEN = "sk-or-test-secret-value-should-never-leak"


class FakeTransport:
    """Records every call so tests can assert on method/url/headers/body."""

    def __init__(self, handler) -> None:
        self._handler = handler
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        body: bytes | None = None,
    ) -> HttpResponse:
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "timeout": timeout, "body": body}
        )
        return self._handler(method, url, headers, timeout, body)


def _client(transport: HttpTransport, *, max_retries: int = 0) -> BoundedHttpClient:
    return BoundedHttpClient(
        transport, timeout_seconds=1, max_retries=max_retries, user_agent="test-agent"
    )


def _adapter(
    transport: HttpTransport,
    *,
    model: str = "free/model-a",
    api_key: str = _SECRET_TOKEN,
    max_output_tokens_ceiling: int = 1024,
    max_retries: int = 0,
) -> OpenRouterAdapter:
    return OpenRouterAdapter(
        _client(transport, max_retries=max_retries),
        api_key=SecretStr(api_key),
        model=model,
        max_output_tokens_ceiling=max_output_tokens_ceiling,
    )


def _request(*, max_output_tokens: int = 256, correlation_id: str | None = None) -> ModelRequest:
    return ModelRequest(
        call_id=ModelCallId.new(),
        prompt_version="synthesis-v1",
        messages=(ModelMessage(role="user", content="Summarize the filing."),),
        max_output_tokens=max_output_tokens,
        correlation_id=correlation_id,
    )


def _success_body(
    *,
    content: str = "The filing shows steady revenue growth.",
    model: str = "free/model-a",
    prompt_tokens: int = 42,
    completion_tokens: int = 17,
    cost: object = 0,
) -> dict[str, object]:
    return {
        "id": "gen-123",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
        },
    }


class RequestMappingTests(TestCase):
    def test_sends_post_to_chat_completions_with_model_messages_and_max_tokens(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body()), "application/json", {}
            )
        )
        adapter = _adapter(transport, model="free/model-a")
        request = _request(max_output_tokens=256)

        response = adapter.complete(request)

        self.assertEqual(response.status, ModelCallStatus.SUCCEEDED)
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "https://openrouter.ai/api/v1/chat/completions")
        payload = _loads(call["body"])
        self.assertEqual(payload["model"], "free/model-a")
        self.assertEqual(
            payload["messages"], [{"role": "user", "content": "Summarize the filing."}]
        )
        self.assertEqual(payload["max_tokens"], 256)

    def test_authorization_header_carries_bearer_secret(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body()), "application/json", {}
            )
        )
        adapter = _adapter(transport, api_key=_SECRET_TOKEN)
        adapter.complete(_request())

        headers = transport.calls[0]["headers"]
        assert isinstance(headers, dict)
        self.assertEqual(headers["Authorization"], f"Bearer {_SECRET_TOKEN}")

    def test_configured_model_is_used_never_hardcoded(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body(model="free/other-model")), "application/json", {}
            )
        )
        adapter = _adapter(transport, model="free/other-model")
        adapter.complete(_request())

        payload = _loads(transport.calls[0]["body"])
        self.assertEqual(payload["model"], "free/other-model")

    def test_request_exceeding_configured_ceiling_is_rejected_before_any_call(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body()), "application/json", {}
            )
        )
        adapter = _adapter(transport, max_output_tokens_ceiling=100)
        response = adapter.complete(_request(max_output_tokens=200))

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.INVALID_REQUEST)
        self.assertEqual(transport.calls, [])


class ResponseMappingTests(TestCase):
    def test_successful_response_maps_content_model_and_call_id(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body(content="Answer text.")), "application/json", {}
            )
        )
        adapter = _adapter(transport)
        request = _request()
        response = adapter.complete(request)

        self.assertEqual(response.status, ModelCallStatus.SUCCEEDED)
        self.assertEqual(response.call_id, request.call_id)
        self.assertEqual(response.model_used, "free/model-a")
        self.assertEqual(response.content, "Answer text.")
        self.assertIsNone(response.failure_kind)

    def test_usage_maps_prompt_completion_and_zero_cost(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200,
                _dumps(_success_body(prompt_tokens=100, completion_tokens=50, cost=0)),
                "application/json",
                {},
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.usage.input_tokens, 100)
        self.assertEqual(response.usage.output_tokens, 50)
        self.assertEqual(response.usage.estimated_cost, Decimal("0"))
        self.assertIsInstance(response.usage.estimated_cost, Decimal)

    def test_missing_usage_block_falls_back_to_domain_defaults(self) -> None:
        body = _success_body()
        del body["usage"]
        transport = FakeTransport(
            lambda method, url, headers, timeout, body_: HttpResponse(
                200, _dumps(body), "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.SUCCEEDED)
        self.assertIsNone(response.usage.input_tokens)
        self.assertIsNone(response.usage.output_tokens)
        self.assertEqual(response.usage.estimated_cost, Decimal("0"))

    def test_nonzero_cost_is_a_fail_closed_policy_violation(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body(cost="0.002")), "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.POLICY_VIOLATION)
        self.assertIsNone(response.content)

    def test_response_validates_against_model_response_domain_invariants(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body()), "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())
        # ModelResponse.__post_init__ already ran during construction inside
        # the adapter; reaching this line without raising is the assertion.
        self.assertEqual(response.retry_count, 0)


class MalformedResponseTests(TestCase):
    def test_malformed_json_body_maps_to_malformed_output(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, b"not json {{{", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.MALFORMED_OUTPUT)

    def test_missing_choices_maps_to_malformed_output(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps({"model": "free/model-a", "choices": []}), "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.MALFORMED_OUTPUT)

    def test_empty_content_maps_to_malformed_output(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200,
                _dumps(_success_body(content="   ")),
                "application/json",
                {},
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.MALFORMED_OUTPUT)


class FailureMappingTests(TestCase):
    def test_401_maps_to_authentication_error(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                401, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.AUTHENTICATION_ERROR)

    def test_429_maps_to_rate_limited(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                429, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.RATE_LIMITED)

    def test_503_maps_to_upstream_error(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                503, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.UPSTREAM_ERROR)

    def test_timeout_maps_to_timeout(self) -> None:
        from financial_intelligence.infrastructure.http import HttpFailureKind, HttpTransportError

        def handler(method, url, headers, timeout, body):
            raise HttpTransportError(HttpFailureKind.TIMEOUT, "timed out")

        adapter = _adapter(FakeTransport(handler))
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.TIMEOUT)

    def test_network_error_maps_to_network_error(self) -> None:
        from financial_intelligence.infrastructure.http import HttpFailureKind, HttpTransportError

        def handler(method, url, headers, timeout, body):
            raise HttpTransportError(HttpFailureKind.NETWORK_ERROR, "boom")

        adapter = _adapter(FakeTransport(handler))
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.NETWORK_ERROR)

    def test_400_maps_to_invalid_request(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                400, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertEqual(response.status, ModelCallStatus.FAILED)
        self.assertEqual(response.failure_kind, ModelFailureKind.INVALID_REQUEST)

    def test_failed_response_never_carries_model_used_or_content(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                500, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())

        self.assertIsNone(response.model_used)
        self.assertIsNone(response.content)


class SecretAndBodyNonLeakageTests(TestCase):
    def test_module_source_calls_get_secret_value_only_when_building_the_header(self) -> None:
        source = inspect.getsource(openrouter_adapter_module)
        self.assertEqual(source.count("get_secret_value()"), 1)

    def test_api_key_never_appears_in_a_failure_response(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                401, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport, api_key=_SECRET_TOKEN)
        response = adapter.complete(_request())

        self.assertNotIn(_SECRET_TOKEN, repr(response))
        self.assertNotIn(_SECRET_TOKEN, str(response))

    def test_api_key_never_appears_in_adapter_repr(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body()), "application/json", {}
            )
        )
        adapter = _adapter(transport, api_key=_SECRET_TOKEN)
        self.assertNotIn(_SECRET_TOKEN, repr(adapter))

    def test_request_body_is_not_echoed_into_a_raised_failure(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                400, b"{}", "application/json", {}
            )
        )
        adapter = _adapter(transport)
        response = adapter.complete(_request())
        self.assertNotIn("Summarize the filing.", str(response))


class CorrelationIdTests(TestCase):
    def test_correlation_id_is_preserved_on_the_request_and_not_sent_upstream(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, _dumps(_success_body()), "application/json", {}
            )
        )
        adapter = _adapter(transport)
        request = _request(correlation_id="corr-123")
        adapter.complete(request)

        payload = _loads(transport.calls[0]["body"])
        self.assertNotIn("correlation_id", payload)
        self.assertEqual(request.correlation_id, "corr-123")


def _dumps(payload: dict[str, object]) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")


def _loads(raw: object) -> dict[str, object]:
    import json

    assert isinstance(raw, bytes)
    return json.loads(raw.decode("utf-8"))
