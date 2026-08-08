"""Stabilization tests for logging configuration and redaction gaps."""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest import TestCase

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings
from financial_intelligence.observability.logging import (
    StructuredFormatter,
    configure_logging,
    reset_logging_configuration,
)


class LoggingConfigurationTests(TestCase):
    """Repeated app construction must not destroy logging handlers."""

    def setUp(self) -> None:
        reset_logging_configuration()

    def tearDown(self) -> None:
        reset_logging_configuration()

    def test_repeated_create_app_does_not_stack_or_wipe_handlers(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")
        create_app(settings=settings)
        first_handlers = list(logging.getLogger().handlers)
        create_app(settings=settings)
        second_handlers = list(logging.getLogger().handlers)
        our_handlers = [
            handler
            for handler in second_handlers
            if getattr(handler, "name", None) == "financial_intelligence.structured"
        ]
        self.assertEqual(len(our_handlers), 1)
        self.assertEqual(len(second_handlers), len(first_handlers))

    def test_force_reconfigure_replaces_structured_handler(self) -> None:
        configure_logging("INFO", force=True)
        configure_logging("ERROR", force=True)
        our_handlers = [
            handler
            for handler in logging.getLogger().handlers
            if getattr(handler, "name", None) == "financial_intelligence.structured"
        ]
        self.assertEqual(len(our_handlers), 1)
        self.assertEqual(logging.getLogger().level, logging.ERROR)


class ExtendedRedactionTests(TestCase):
    """Cover additional sensitive fragments required by Prompt 3."""

    def test_passwd_and_refresh_token_are_redacted(self) -> None:
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger = logging.getLogger("financial_intelligence.test.redact")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.info(
            "creds",
            extra={"passwd": "x", "refresh_token": "y", "revenue": 10},
        )
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["passwd"], "[REDACTED]")
        self.assertEqual(payload["refresh_token"], "[REDACTED]")
        self.assertEqual(payload["revenue"], 10)
