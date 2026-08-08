"""Structured logging safety tests."""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest import TestCase

from financial_intelligence.observability.correlation import (
    bind_correlation_id,
    reset_correlation_id,
)
from financial_intelligence.observability.logging import StructuredFormatter


class LoggingSafetyTests(TestCase):
    """Ensure sensitive fields are redacted from structured logs."""

    def test_sensitive_extras_are_redacted_and_correlation_is_included(self) -> None:
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger = logging.getLogger("financial_intelligence.test.logging")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        token = bind_correlation_id("corr-123")
        try:
            logger.info(
                "settings_loaded",
                extra={
                    "api_key": "should-not-appear",
                    "authorization": "Bearer secret",
                    "app_env": "test",
                },
            )
        finally:
            reset_correlation_id(token)

        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["correlation_id"], "corr-123")
        self.assertEqual(payload["api_key"], "[REDACTED]")
        self.assertEqual(payload["authorization"], "[REDACTED]")
        self.assertEqual(payload["app_env"], "test")
        self.assertNotIn("should-not-appear", stream.getvalue())
        self.assertNotIn("Bearer secret", stream.getvalue())
