"""Prompt 2 deep validation for configuration edge cases."""

from __future__ import annotations

import os
from unittest import TestCase, mock

from pydantic import ValidationError

from financial_intelligence.config.settings import Settings

_BASE_ENV = {
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


class SettingsDeepValidationTests(TestCase):
    """Expand configuration fail-closed and secret-safety coverage."""

    def test_truthy_paid_model_variants_all_fail_closed(self) -> None:
        for raw in ("true", "TRUE", "True", "1", "yes", "on"):
            with (
                self.subTest(raw=raw),
                mock.patch.dict(os.environ, {**_BASE_ENV, "ALLOW_PAID_MODELS": raw}, clear=True),
                self.assertRaises(ValidationError),
            ):
                Settings(_env_file=None)

    def test_falsey_paid_model_variants_remain_disabled(self) -> None:
        for raw in ("false", "FALSE", "0", "no", "off"):
            with self.subTest(raw=raw):
                with mock.patch.dict(
                    os.environ,
                    {**_BASE_ENV, "ALLOW_PAID_MODELS": raw},
                    clear=True,
                ):
                    settings = Settings(_env_file=None)
                self.assertFalse(settings.allow_paid_models)

    def test_invalid_log_level_and_environment_rejected(self) -> None:
        with (
            mock.patch.dict(os.environ, {**_BASE_ENV, "LOG_LEVEL": "VERBOSE"}, clear=True),
            self.assertRaises(ValidationError),
        ):
            Settings(_env_file=None)
        with (
            mock.patch.dict(os.environ, {**_BASE_ENV, "APP_ENV": "local"}, clear=True),
            self.assertRaises(ValidationError),
        ):
            Settings(_env_file=None)

    def test_unknown_environment_keys_are_ignored(self) -> None:
        with mock.patch.dict(
            os.environ,
            {**_BASE_ENV, "TOTALLY_UNKNOWN_SETTING": "value"},
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertFalse(hasattr(settings, "totally_unknown_setting"))

    def test_secret_repr_str_and_dump_do_not_leak(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                **_BASE_ENV,
                "OPENROUTER_API_KEY": "super-secret-key",
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
                "REDIS_URL": "redis://:pass@localhost:6379/0",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        rendered = " ".join(
            [
                repr(settings),
                str(settings),
                str(settings.model_dump()),
                str(settings.safe_log_context()),
            ]
        )
        self.assertNotIn("super-secret-key", rendered)
        self.assertNotIn("postgresql://user:pass", rendered)
        self.assertNotIn("redis://:pass", rendered)
        self.assertIn("**********", repr(settings))
