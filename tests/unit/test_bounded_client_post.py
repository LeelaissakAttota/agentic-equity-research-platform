"""Phase 2 — bounded JSON POST capability tests (offline, fake transport only)."""

from __future__ import annotations

import json
from unittest import TestCase

from financial_intelligence.infrastructure.http import (
    BoundedHttpClient,
    HttpFailureKind,
    HttpResponse,
    HttpTransport,
    HttpTransportError,
    UrlLibHttpTransport,
)


class FakeTransport:
    """Records every call so tests can assert on method/headers/body/timeout."""

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
        transport, timeout_seconds=1, max_retries=max_retries, user_agent="test"
    )


class PostJsonSuccessTests(TestCase):
    def test_successful_post_returns_parsed_json(self) -> None:
        def handler(method, url, headers, timeout, body):
            return HttpResponse(
                200, json.dumps({"ok": True}).encode(), "application/json", {}
            )

        transport = FakeTransport(handler)
        client = _client(transport)
        result = client.post_json("https://example.invalid/v1/chat", {"model": "free/x"})
        self.assertEqual(result, {"ok": True})

    def test_request_body_is_valid_json_serialization_of_payload(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, timeout, body):
            captured["body"] = body
            return HttpResponse(200, b"{}", "application/json", {})

        client = _client(FakeTransport(handler))
        payload = {"model": "free/x", "messages": [{"role": "user", "content": "hi"}]}
        client.post_json("https://example.invalid/v1/chat", payload)

        sent_body = captured["body"]
        assert isinstance(sent_body, bytes)
        self.assertEqual(json.loads(sent_body.decode("utf-8")), payload)

    def test_content_type_header_is_application_json(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, timeout, body):
            captured["headers"] = headers
            return HttpResponse(200, b"{}", "application/json", {})

        client = _client(FakeTransport(handler))
        client.post_json("https://example.invalid/v1/chat", {"a": 1})

        headers = captured["headers"]
        assert isinstance(headers, dict)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["User-Agent"], "test")

    def test_method_sent_is_post(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, b"{}", "application/json", {}
            )
        )
        client = _client(transport)
        client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(transport.calls[0]["method"], "POST")

    def test_extra_headers_are_included_but_cannot_override_reserved_ones(self) -> None:
        captured: dict[str, object] = {}

        def handler(method, url, headers, timeout, body):
            captured["headers"] = headers
            return HttpResponse(200, b"{}", "application/json", {})

        client = _client(FakeTransport(handler))
        client.post_json(
            "https://example.invalid/v1/chat",
            {"a": 1},
            extra_headers={
                "Authorization": "Bearer secret-token",
                "Content-Type": "text/plain",
            },
        )

        headers = captured["headers"]
        assert isinstance(headers, dict)
        self.assertEqual(headers["Authorization"], "Bearer secret-token")
        self.assertEqual(headers["Content-Type"], "application/json")


class PostJsonFailureTests(TestCase):
    def test_malformed_json_response_raises_invalid_response(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, b"not json {{{", "application/json", {}
            )
        )
        client = _client(transport)
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.INVALID_RESPONSE)

    def test_non_dict_json_root_rejected(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, b"[1, 2, 3]", "application/json", {}
            )
        )
        client = _client(transport)
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.INVALID_RESPONSE)

    def test_400_status_raises_without_retry(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                400, b"{}", "application/json", {}
            )
        )
        client = _client(transport, max_retries=3)
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.INVALID_RESPONSE)
        self.assertEqual(len(transport.calls), 1)

    def test_401_status_classified_unauthorized(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                401, b"{}", "application/json", {}
            )
        )
        client = _client(transport, max_retries=3)
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.UNAUTHORIZED)
        self.assertEqual(len(transport.calls), 1)

    def test_transport_network_error_propagates_as_http_transport_error(self) -> None:
        def handler(method, url, headers, timeout, body):
            raise HttpTransportError(HttpFailureKind.NETWORK_ERROR, "boom")

        client = _client(FakeTransport(handler))
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.NETWORK_ERROR)

    def test_timeout_transport_failure_classified(self) -> None:
        def handler(method, url, headers, timeout, body):
            raise HttpTransportError(HttpFailureKind.TIMEOUT, "timed out")

        client = _client(FakeTransport(handler))
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.TIMEOUT)

    def test_oversized_response_propagates(self) -> None:
        def handler(method, url, headers, timeout, body):
            raise HttpTransportError(HttpFailureKind.OVERSIZED, "too big")

        client = _client(FakeTransport(handler))
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.OVERSIZED)


class PostJsonRetryTests(TestCase):
    def test_retries_429_then_succeeds(self) -> None:
        responses = [
            HttpResponse(429, b"{}", "application/json", {"retry-after": "0"}),
            HttpResponse(200, json.dumps({"ok": True}).encode(), "application/json", {}),
        ]

        def handler(method, url, headers, timeout, body):
            return responses.pop(0)

        transport = FakeTransport(handler)
        client = _client(transport, max_retries=2)
        result = client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(transport.calls), 2)

    def test_retries_timeout_then_succeeds(self) -> None:
        state = {"attempt": 0}

        def handler(method, url, headers, timeout, body):
            state["attempt"] += 1
            if state["attempt"] == 1:
                raise HttpTransportError(HttpFailureKind.TIMEOUT, "timed out")
            return HttpResponse(200, b'{"ok": true}', "application/json", {})

        transport = FakeTransport(handler)
        client = _client(transport, max_retries=1)
        result = client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(transport.calls), 2)

    def test_exhausts_retries_then_raises_last_error(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                503, b"{}", "application/json", {}
            )
        )
        client = _client(transport, max_retries=2)
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(ctx.exception.kind, HttpFailureKind.UPSTREAM_ERROR)
        self.assertEqual(len(transport.calls), 3)

    def test_retry_after_header_bounds_delay(self) -> None:
        responses = [
            HttpResponse(429, b"{}", "application/json", {"retry-after": "999"}),
            HttpResponse(200, b'{"ok": true}', "application/json", {}),
        ]

        def handler(method, url, headers, timeout, body):
            return responses.pop(0)

        transport = FakeTransport(handler)
        client = _client(transport, max_retries=1)
        result = client.post_json("https://example.invalid/v1/chat", {"a": 1})
        self.assertEqual(result, {"ok": True})


class GetJsonCompatibilityTests(TestCase):
    """Confirm GET behavior and legacy (body-less) fake transports are unaffected."""

    def test_legacy_fake_transport_without_body_param_still_works_for_get(self) -> None:
        class LegacyFakeTransport:
            def request(
                self, method: str, url: str, *, headers: dict[str, str], timeout: float
            ) -> HttpResponse:
                assert method == "GET"
                return HttpResponse(200, b'{"ok": true}', "application/json", {})

        client = _client(LegacyFakeTransport())
        result = client.get_json("https://example.invalid/v1/data")
        self.assertEqual(result, {"ok": True})

    def test_get_json_does_not_send_a_body(self) -> None:
        transport = FakeTransport(
            lambda method, url, headers, timeout, body: HttpResponse(
                200, b'{"ok": true}', "application/json", {}
            )
        )
        client = _client(transport)
        client.get_json("https://example.invalid/v1/data")
        self.assertIsNone(transport.calls[0]["body"])
        self.assertEqual(transport.calls[0]["method"], "GET")

    def test_get_json_retries_429_then_succeeds(self) -> None:
        responses = [
            HttpResponse(429, b"{}", "application/json", {"retry-after": "0"}),
            HttpResponse(200, json.dumps({"ok": True}).encode(), "application/json", {}),
        ]

        def handler(method, url, headers, timeout, body):
            return responses.pop(0)

        transport = FakeTransport(handler)
        client = _client(transport, max_retries=2)
        self.assertEqual(client.get_json("https://example.invalid/v1/data"), {"ok": True})
        self.assertEqual(len(transport.calls), 2)


class UrlLibHttpTransportPostTests(TestCase):
    """Exercise the real stdlib transport's POST branch without live network."""

    def test_get_rejects_a_body(self) -> None:
        transport = UrlLibHttpTransport(max_response_bytes=1024)
        with self.assertRaises(ValueError):
            transport.request(
                "GET",
                "https://example.invalid/x",
                headers={},
                timeout=1,
                body=b"{}",
            )

    def test_post_requires_a_body(self) -> None:
        transport = UrlLibHttpTransport(max_response_bytes=1024)
        with self.assertRaises(ValueError):
            transport.request(
                "POST",
                "https://example.invalid/x",
                headers={},
                timeout=1,
            )

    def test_unsupported_method_rejected(self) -> None:
        transport = UrlLibHttpTransport(max_response_bytes=1024)
        with self.assertRaises(ValueError):
            transport.request(
                "DELETE",
                "https://example.invalid/x",
                headers={},
                timeout=1,
            )


class SecretAndBodyNonLeakageTests(TestCase):
    """Confirm no request body or secret header is ever logged by this module."""

    def test_module_source_contains_no_logging_calls(self) -> None:
        import inspect

        from financial_intelligence.infrastructure.http import bounded_client

        source = inspect.getsource(bounded_client)
        self.assertNotIn("logging.", source)
        self.assertNotIn("logger.", source)

    def test_authorization_header_value_never_appears_in_raised_error_message(self) -> None:
        def handler(method, url, headers, timeout, body):
            return HttpResponse(401, b"{}", "application/json", {})

        client = _client(FakeTransport(handler))
        with self.assertRaises(HttpTransportError) as ctx:
            client.post_json(
                "https://example.invalid/v1/chat",
                {"a": 1},
                extra_headers={"Authorization": "Bearer super-secret-token"},
            )
        self.assertNotIn("super-secret-token", str(ctx.exception))
