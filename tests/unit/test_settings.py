"""Configuration and paid-model fail-closed tests."""

from __future__ import annotations

import os
from unittest import TestCase, mock

from pydantic import ValidationError

from financial_intelligence.config.settings import Settings

_ISOLATED_ENV = {
    "APP_ENV": "development",
    "LOG_LEVEL": "INFO",
    "ALLOW_PAID_MODELS": "false",
    "OPENROUTER_API_KEY": "",
    "PRIMARY_FREE_MODEL": "",
    "FALLBACK_FREE_MODEL_1": "",
    "FALLBACK_FREE_MODEL_2": "",
    "DATABASE_URL": "",
    "REDIS_URL": "",
    "ALPHA_VANTAGE_API_KEY": "",
    "FINNHUB_API_KEY": "",
}


class SettingsTests(TestCase):
    """Validate typed settings behavior without mutating global process state."""

    def test_safe_defaults(self) -> None:
        with mock.patch.dict(os.environ, _ISOLATED_ENV, clear=True):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.app_env, "development")
        self.assertEqual(settings.log_level, "INFO")
        self.assertFalse(settings.allow_paid_models)
        self.assertEqual(settings.primary_free_model, "")
        self.assertEqual(settings.openrouter_api_key.get_secret_value(), "")
        self.assertFalse(settings.openrouter_live_enabled)
        self.assertEqual(settings.openrouter_timeout_seconds, 30)
        self.assertEqual(settings.openrouter_max_retries, 2)
        self.assertEqual(settings.openrouter_max_output_tokens, 1024)

    def test_environment_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                **_ISOLATED_ENV,
                "APP_ENV": "test",
                "LOG_LEVEL": "WARNING",
                "PRIMARY_FREE_MODEL": "free/model-a",
                "HTTP_TIMEOUT_SECONDS": "15",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.app_env, "test")
        self.assertEqual(settings.log_level, "WARNING")
        self.assertEqual(settings.primary_free_model, "free/model-a")
        self.assertEqual(settings.http_timeout_seconds, 15)

    def test_llm_environment_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                **_ISOLATED_ENV,
                "PRIMARY_FREE_MODEL": "free/model-a",
                "OPENROUTER_LIVE_ENABLED": "true",
                "OPENROUTER_TIMEOUT_SECONDS": "45",
                "OPENROUTER_MAX_RETRIES": "3",
                "OPENROUTER_MAX_OUTPUT_TOKENS": "2048",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertTrue(settings.openrouter_live_enabled)
        self.assertEqual(settings.openrouter_timeout_seconds, 45)
        self.assertEqual(settings.openrouter_max_retries, 3)
        self.assertEqual(settings.openrouter_max_output_tokens, 2048)

    def test_openrouter_live_enabled_requires_primary_free_model(self) -> None:
        with (
            mock.patch.dict(
                os.environ,
                {**_ISOLATED_ENV, "OPENROUTER_LIVE_ENABLED": "true", "PRIMARY_FREE_MODEL": ""},
                clear=True,
            ),
            self.assertRaises(ValidationError),
        ):
            Settings(_env_file=None)

    def test_paid_models_fail_closed(self) -> None:
        with (
            mock.patch.dict(os.environ, {**_ISOLATED_ENV, "ALLOW_PAID_MODELS": "true"}, clear=True),
            self.assertRaises(ValidationError),
        ):
            Settings(_env_file=None)

    def test_duplicate_free_models_rejected(self) -> None:
        with (
            mock.patch.dict(
                os.environ,
                {
                    **_ISOLATED_ENV,
                    "PRIMARY_FREE_MODEL": "free/same",
                    "FALLBACK_FREE_MODEL_1": "free/same",
                },
                clear=True,
            ),
            self.assertRaises(ValidationError),
        ):
            Settings(_env_file=None)

    def test_safe_log_context_excludes_secrets(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                **_ISOLATED_ENV,
                "OPENROUTER_API_KEY": "super-secret-key",
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
                "REDIS_URL": "redis://:pass@localhost:6379/0",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        context = settings.safe_log_context()
        rendered = str(context)
        self.assertNotIn("super-secret-key", rendered)
        self.assertNotIn("postgresql://", rendered)
        self.assertNotIn("redis://", rendered)
        self.assertTrue(context["openrouter_key_configured"])
        self.assertTrue(context["database_configured"])
        self.assertFalse(context["allow_paid_models"])
        self.assertIn("openrouter_live_enabled", context)
        self.assertIn("openrouter_timeout_seconds", context)
        self.assertIn("openrouter_max_retries", context)
        self.assertIn("openrouter_max_output_tokens", context)
