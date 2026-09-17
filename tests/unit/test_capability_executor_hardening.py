"""F04 regression tests: exception message leakage via the capability executor.

Confirms that an unexpected exception raised inside a capability adapter can
no longer reach the client through `POST /research/execute` (in either of its
two serialized locations: `task_results` and the nested `orchestration.results`),
while the exception's real type and message remain available server-side via
structured logging. See F04_EXCEPTION_LEAKAGE_REMEDIATION_PLAN.md and
F04_EXCEPTION_LEAKAGE_IMPLEMENTATION_REPORT.md.
"""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.orchestration.capability_executor import (
    _SAFE_CAPABILITY_FAILURE_MESSAGE,
)
from financial_intelligence.observability.logging import StructuredFormatter

_SYNTHETIC_HOST = "internal-db-host.corp.local"
_SYNTHETIC_PATH = "/var/app/secrets/db.conf"
_SYNTHETIC_MARKER = (
    f"AUDIT_MARKER: connection failed to {_SYNTHETIC_HOST}:5432 at {_SYNTHETIC_PATH}"
)


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class _RaisingSnapshot:
    """Stand-in for a capability's inner use case: always raises."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def execute(self, query: object) -> object:
        raise self._exc


def _client_with_market_failure(exc: Exception) -> TestClient:
    container = build_container(settings=_settings())
    # Inject the failure INSIDE Phase6CapabilityExecutor's dispatch -- the
    # exact boundary F04's try/except lives at -- not by replacing the
    # executor wholesale (which would bypass the code path under test).
    container.execute_research_plan._executor._market = _RaisingSnapshot(exc)
    return TestClient(create_app(settings=_settings(), container=container))


def _execute_body() -> dict:
    return {"q": "Apple", "exchange": "NASDAQ", "objective": "market_analysis"}


class ExceptionLeakageHardeningTests(TestCase):
    """1-6: the response must be safe, structured, and contract-preserving."""

    def test_unexpected_exception_returns_safe_client_facing_message(self) -> None:
        client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
        response = client.post("/research/execute", json=_execute_body())
        payload = response.json()
        task_result = payload["task_results"][0]
        self.assertEqual(task_result["message"], _SAFE_CAPABILITY_FAILURE_MESSAGE)
        self.assertEqual(task_result["status"], "failed")
        self.assertEqual(task_result["error_code"], "executor_exception")
        self.assertTrue(task_result["retryable"])

    def test_synthetic_hostname_does_not_appear_in_response(self) -> None:
        client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
        response = client.post("/research/execute", json=_execute_body())
        self.assertNotIn(_SYNTHETIC_HOST, response.text)

    def test_synthetic_filesystem_path_does_not_appear_in_response(self) -> None:
        client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
        response = client.post("/research/execute", json=_execute_body())
        self.assertNotIn(_SYNTHETIC_PATH, response.text)

    def test_raw_exception_text_does_not_appear_anywhere_in_response(self) -> None:
        client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
        response = client.post("/research/execute", json=_execute_body())
        self.assertNotIn(_SYNTHETIC_MARKER, response.text)
        self.assertNotIn("RuntimeError", response.text)
        self.assertNotIn("capability executor exception", response.text)

    def test_traceback_and_implementation_details_do_not_appear_in_response(self) -> None:
        """Parametrized across several exception shapes (ValueError, KeyError,
        a generic Exception subclass), per the audit's instruction that the
        fix must sanitize by mechanism, not by pattern-matching one exception
        type."""
        cases: list[Exception] = [
            ValueError(f"bad value near {_SYNTHETIC_PATH}"),
            KeyError(_SYNTHETIC_HOST),
            Exception(f"generic failure referencing {_SYNTHETIC_HOST}"),
        ]
        for exc in cases:
            with self.subTest(exc_type=type(exc).__name__):
                client = _client_with_market_failure(exc)
                response = client.post("/research/execute", json=_execute_body())
                self.assertNotIn(_SYNTHETIC_HOST, response.text)
                self.assertNotIn(_SYNTHETIC_PATH, response.text)
                self.assertNotIn("Traceback", response.text)
                self.assertNotIn(".py", response.text)

    def test_failure_remains_inside_existing_200_partial_failure_contract(self) -> None:
        """The endpoint's intentional 200-with-structured-failure contract
        must be unchanged -- this fix must not escalate to a 5xx."""
        client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
        response = client.post("/research/execute", json=_execute_body())
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(payload["completed_count"], 0)

    def test_duplicated_orchestration_results_location_is_also_safe(self) -> None:
        """The same failure is also serialized a second time, nested under
        `orchestration.results` -- both locations must be sanitized, not just
        `task_results`."""
        client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
        response = client.post("/research/execute", json=_execute_body())
        payload = response.json()
        nested_results = payload["orchestration"]["results"]
        self.assertTrue(nested_results)
        for result in nested_results:
            self.assertEqual(result["message"], _SAFE_CAPABILITY_FAILURE_MESSAGE)
        self.assertNotIn(_SYNTHETIC_HOST, json.dumps(nested_results))
        self.assertNotIn(_SYNTHETIC_PATH, json.dumps(nested_results))


class SafeDomainErrorRegressionTests(TestCase):
    """7: safe, intentional domain/application validation errors must remain
    unchanged -- this fix must not over-sanitize legitimate error messages
    that are already part of the public API contract."""

    def test_invalid_objective_still_returns_its_own_safe_message(self) -> None:
        client = TestClient(create_app(settings=_settings()))
        response = client.post(
            "/research/execute",
            json={"q": "Apple", "exchange": "NASDAQ", "objective": "not_a_real_objective"},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        # This is a deliberately-authored, bounded validation message (not an
        # internal exception) and must still reach the client, unchanged.
        self.assertEqual(payload["error"]["code"], "invalid_research_execution_query")
        self.assertTrue(payload["error"]["message"])


class ServerSideDiagnosticsTests(TestCase):
    """8: the real exception detail must remain available server-side even
    though it no longer reaches the client."""

    def test_capability_execution_failure_is_logged_with_full_detail(self) -> None:
        logger_name = "financial_intelligence.infrastructure.orchestration.capability_executor"
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        target_logger = logging.getLogger(logger_name)
        original_handlers = target_logger.handlers
        original_level = target_logger.level
        original_propagate = target_logger.propagate
        target_logger.handlers = [handler]
        target_logger.setLevel(logging.ERROR)
        target_logger.propagate = False
        try:
            client = _client_with_market_failure(RuntimeError(_SYNTHETIC_MARKER))
            response = client.post("/research/execute", json=_execute_body())
            self.assertEqual(response.status_code, 200)
        finally:
            target_logger.handlers = original_handlers
            target_logger.setLevel(original_level)
            target_logger.propagate = original_propagate

        log_output = stream.getvalue()
        self.assertIn(_SYNTHETIC_MARKER, log_output)
        self.assertIn(_SYNTHETIC_HOST, log_output)
        self.assertIn("RuntimeError", log_output)
        payload = json.loads(log_output.strip().splitlines()[-1])
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertEqual(payload["error_detail"], _SYNTHETIC_MARKER)
        self.assertEqual(payload["capability_id"], "market_intelligence")
        self.assertIn("task_id", payload)
        # And, in the same request, confirm the client-facing response the
        # logging was captured alongside never received this detail.
        self.assertNotIn(_SYNTHETIC_MARKER, response.text)
