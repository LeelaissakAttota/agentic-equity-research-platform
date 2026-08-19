"""Prompt 2 logging redaction and import side-effect checks."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest import TestCase

from financial_intelligence.observability.correlation import (
    bind_correlation_id,
    reset_correlation_id,
)
from financial_intelligence.observability.logging import StructuredFormatter

ROOT = Path(__file__).resolve().parents[2]


class NestedLoggingRedactionTests(TestCase):
    """Ensure nested sensitive values are redacted."""

    def test_nested_mapping_and_list_redaction(self) -> None:
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger = logging.getLogger("financial_intelligence.test.nested")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        token = bind_correlation_id("corr-nested")
        try:
            logger.info(
                "payload",
                extra={
                    "wrapper": {
                        "api_key": "secret-value",
                        "Authorization": "Bearer abc",
                        "nested": [{"access_token": "tok", "ok": True}],
                    },
                    "client_secret": "cs",
                },
            )
        finally:
            reset_correlation_id(token)

        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["correlation_id"], "corr-nested")
        self.assertEqual(payload["client_secret"], "[REDACTED]")
        self.assertEqual(payload["wrapper"]["api_key"], "[REDACTED]")
        self.assertEqual(payload["wrapper"]["Authorization"], "[REDACTED]")
        self.assertEqual(payload["wrapper"]["nested"][0]["access_token"], "[REDACTED]")
        self.assertTrue(payload["wrapper"]["nested"][0]["ok"])
        self.assertNotIn("secret-value", stream.getvalue())
        self.assertNotIn("Bearer abc", stream.getvalue())


class ImportSideEffectTests(TestCase):
    """Package imports must remain offline and side-effect light."""

    def test_package_import_subprocess_is_safe(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["ALLOW_PAID_MODELS"] = "false"
        env["OPENROUTER_API_KEY"] = ""
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import financial_intelligence as fi; "
                    "from financial_intelligence.api import create_app; "
                    "print(fi.__version__); "
                    "print(create_app.__name__)"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("1.0.0", completed.stdout)
        self.assertIn("create_app", completed.stdout)
        combined = completed.stdout + completed.stderr
        self.assertNotIn("OpenRouter", combined)
