"""Prompt 2 deep API contract, OpenAPI, and route-surface validation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class ApplicationFactoryDeepTests(TestCase):
    """Factory behavior under repeated construction."""

    def test_independent_app_instances(self) -> None:
        first = create_app(settings=_settings())
        second = create_app(settings=_settings())
        self.assertIsNot(first, second)
        self.assertIsNot(first.state.container, second.state.container)
        with TestClient(first) as client_one, TestClient(second) as client_two:
            self.assertEqual(client_one.get("/health").status_code, 200)
            self.assertEqual(client_two.get("/ready").status_code, 200)

    def test_repeated_startup_shutdown_cycles(self) -> None:
        app = create_app(settings=_settings())
        for _ in range(3):
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").json()["status"], "ok")


class ApiContractDeepTests(TestCase):
    """Health/error/OpenAPI/route surface contracts."""

    def test_health_content_type_and_schema(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["content-type"])
        self.assertEqual(
            set(response.json()),
            {"status", "service", "version"},
        )
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_method_not_allowed_and_not_found_use_error_envelope(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            missing = client.get("/nope", headers={"X-Correlation-ID": "missing-1"})
            method = client.post("/health", headers={"X-Correlation-ID": "method-1"})
        for response, code in ((missing, "http_error"), (method, "http_error")):
            payload = response.json()
            self.assertEqual(set(payload.keys()), {"error"})
            self.assertEqual(
                set(payload["error"].keys()),
                {"code", "message", "correlation_id", "details"},
            )
            self.assertEqual(payload["error"]["code"], code)
            self.assertIn("X-Correlation-ID", response.headers)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_malformed_json_is_normalized(self) -> None:
        app = create_app(settings=_settings())

        @app.post("/_test/echo")
        def echo(payload: dict[str, str]) -> dict[str, str]:
            return payload

        with TestClient(app) as client:
            response = client.post(
                "/_test/echo",
                content="{not-json",
                headers={
                    "Content-Type": "application/json",
                    "X-Correlation-ID": "json-1",
                },
            )
        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "validation_error")
        self.assertEqual(payload["error"]["correlation_id"], "json-1")
        self.assertNotIn("not-json", str(payload["error"]["details"]))

    def test_openapi_and_route_surface(self) -> None:
        app = create_app(settings=_settings())
        paths = set(app.openapi()["paths"])
        self.assertEqual(paths, {"/health", "/ready", "/version"})
        self.assertEqual(
            app.openapi()["info"]["title"],
            "Agentic Financial Intelligence & Equity Research Platform",
        )
        self.assertEqual(app.openapi()["info"]["version"], "0.1.0")
        forbidden = {
            "/research",
            "/company",
            "/market",
            "/news",
            "/filings",
            "/report",
            "/chat",
            "/agents",
            "/mcp",
        }
        self.assertTrue(paths.isdisjoint(forbidden))


class CorrelationConcurrencyTests(TestCase):
    """Correlation ID adversarial and isolation checks."""

    def test_adversarial_headers_are_replaced(self) -> None:
        cases = [
            "",
            "   ",
            "a" * 65,
            "bad\r\ninjected",
            "bad\ninjected",
            "@@@",
            "id with spaces",
        ]
        with TestClient(create_app(settings=_settings())) as client:
            for value in cases:
                with self.subTest(value=repr(value)):
                    response = client.get("/health", headers={"X-Correlation-ID": value})
                    header = response.headers["X-Correlation-ID"]
                    self.assertNotEqual(header, value)
                    self.assertNotIn("\r", header)
                    self.assertNotIn("\n", header)
                    self.assertLessEqual(len(header), 64)

        # Non-ASCII cannot be transported as an HTTP header via httpx; validate
        # resolver behavior directly instead.
        from financial_intelligence.observability.correlation import resolve_correlation_id

        replaced = resolve_correlation_id("unicodé")
        self.assertNotEqual(replaced.value, "unicodé")

    def test_concurrent_requests_keep_distinct_correlation_ids(self) -> None:
        app = create_app(settings=_settings())

        def invoke(index: int) -> str:
            with TestClient(app) as client:
                response = client.get(
                    "/health",
                    headers={"X-Correlation-ID": f"worker-{index}"},
                )
                return response.headers["X-Correlation-ID"]

        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(invoke, range(24)))
        self.assertEqual(values, [f"worker-{index}" for index in range(24)])
