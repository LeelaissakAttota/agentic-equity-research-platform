"""Prompt 2 deep validation for readiness registry robustness."""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
)
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings


class ReadinessRegistryTests(TestCase):
    """Verify readiness evaluation is stable and failure-safe."""

    def setUp(self) -> None:
        self.metadata = ApplicationMetadata(
            service="agentic-financial-intelligence",
            version="0.1.0",
            environment="test",
        )

    def test_checks_are_evaluated_in_sorted_name_order(self) -> None:
        registry = ReadinessRegistry()
        registry.register("zulu", lambda: ReadinessCheckResult(name="zulu", ready=True))
        registry.register("alpha", lambda: ReadinessCheckResult(name="alpha", ready=True))
        result = registry.evaluate(self.metadata)
        self.assertEqual([check.name for check in result.checks], ["alpha", "zulu"])

    def test_probe_exception_becomes_not_ready(self) -> None:
        registry = ReadinessRegistry()
        registry.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = registry.evaluate(self.metadata)
        self.assertFalse(result.ready)
        self.assertEqual(result.status, "not_ready")
        self.assertEqual(result.checks[0].detail, "probe_error:RuntimeError")

    def test_empty_name_rejected(self) -> None:
        registry = ReadinessRegistry()
        with self.assertRaises(ValueError):
            registry.register("  ", lambda: ReadinessCheckResult(name="x", ready=True))

    def test_name_mismatch_becomes_not_ready(self) -> None:
        registry = ReadinessRegistry()
        registry.register(
            "expected",
            lambda: ReadinessCheckResult(name="other", ready=True),
        )
        result = registry.evaluate(self.metadata)
        self.assertFalse(result.ready)
        self.assertEqual(result.checks[0].detail, "probe_error:name_mismatch")

    def test_http_ready_returns_503_when_probe_fails(self) -> None:
        container = build_container(Settings(_env_file=None, APP_ENV="test"))
        container.readiness.register(
            "future_dependency",
            lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
        )
        with TestClient(create_app(container=container)) as client:
            response = client.get("/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertTrue(any(check["name"] == "future_dependency" for check in payload["checks"]))


# ---------------------------------------------------------------------------
# F09 — /ready must reflect authentication readiness (see
# F09_READINESS_EMPTY_KEYSET_REMEDIATION_PLAN.md /
# F09_READINESS_EMPTY_KEYSET_IMPLEMENTATION_REPORT.md).
#
# Before the fix, the "configuration" readiness check was an unconditional
# `ready=True` constant that never inspected the API-key store, so
# `/ready` reported "ready" even when authentication was enforced
# (production/staging) with zero usable keys -- a state in which every
# protected endpoint unconditionally returns 401 for every caller. The fix
# adds a dedicated "authentication" probe that mirrors require_api_key's own
# environment-based bypass (development/test) and otherwise reports ready
# only when at least one usable key is configured.
# ---------------------------------------------------------------------------


def _readiness_check(payload: dict[str, object], name: str) -> dict[str, object]:
    checks = payload["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        if check["name"] == name:
            return check
    raise AssertionError(f"no readiness check named {name!r} in {checks!r}")


class AuthenticationReadinessTests(TestCase):
    """F09: /ready must fail when auth is enforced but no key can authenticate."""

    def _build(self, **kwargs: object) -> TestClient:
        settings = Settings(
            _env_file=None,
            LOG_LEVEL="ERROR",
            ALLOWED_HOSTS="example.com",
            **kwargs,  # type: ignore[arg-type]
        )
        return TestClient(create_app(settings=settings))

    def test_production_configured_key_is_ready(self) -> None:
        with self._build(
            APP_ENV="production", AUTH_ENABLED="true", API_KEYS="prod-key-f09"
        ) as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["status"], "ready")
        auth_check = _readiness_check(payload, "authentication")
        self.assertTrue(auth_check["ready"])
        self.assertEqual(auth_check["detail"], "usable_api_keys_configured")

    def test_production_zero_keys_is_not_ready(self) -> None:
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 503)
        payload = r.json()
        self.assertEqual(payload["status"], "not_ready")
        auth_check = _readiness_check(payload, "authentication")
        self.assertFalse(auth_check["ready"])
        self.assertEqual(auth_check["detail"], "auth_enabled_but_no_usable_api_keys_configured")

    def test_production_whitespace_only_keys_is_not_ready(self) -> None:
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="   ") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 503)
        auth_check = _readiness_check(r.json(), "authentication")
        self.assertFalse(auth_check["ready"])

    def test_production_comma_only_empty_entries_is_not_ready(self) -> None:
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS=" , , ") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 503)
        auth_check = _readiness_check(r.json(), "authentication")
        self.assertFalse(auth_check["ready"])

    def test_staging_zero_keys_is_not_ready(self) -> None:
        with self._build(APP_ENV="staging", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 503)
        auth_check = _readiness_check(r.json(), "authentication")
        self.assertFalse(auth_check["ready"])

    def test_staging_configured_key_is_ready(self) -> None:
        with self._build(
            APP_ENV="staging", AUTH_ENABLED="true", API_KEYS="staging-key-f09"
        ) as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(_readiness_check(r.json(), "authentication")["ready"])

    def test_development_zero_keys_remains_ready(self) -> None:
        with self._build(APP_ENV="development", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["status"], "ready")
        auth_check = _readiness_check(payload, "authentication")
        self.assertTrue(auth_check["ready"])
        self.assertEqual(auth_check["detail"], "authentication_not_enforced_in_this_environment")

    def test_development_zero_keys_with_auth_enabled_true_remains_ready(self) -> None:
        """AUTH_ENABLED=true in development is still bypassed by environment
        (require_api_key's own rule) -- readiness must not contradict that."""
        with self._build(APP_ENV="development", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(_readiness_check(r.json(), "authentication")["ready"])

    def test_test_env_zero_keys_remains_ready(self) -> None:
        with self._build(APP_ENV="test", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(_readiness_check(r.json(), "authentication")["ready"])

    def test_health_unaffected_by_zero_keys_in_production(self) -> None:
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/health", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_protected_endpoint_still_401_with_zero_keys(self) -> None:
        """The readiness fix must not change the authentication decision itself."""
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/companies/resolve?q=Apple", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 401)

    def test_protected_endpoint_succeeds_with_configured_key(self) -> None:
        with self._build(
            APP_ENV="production", AUTH_ENABLED="true", API_KEYS="prod-key-f09"
        ) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={"HOST": "example.com", "Authorization": "Bearer prod-key-f09"},
            )
        self.assertIn(r.status_code, (200, 404, 422))

    def test_not_ready_response_identifies_failed_check_without_leaking_keys(self) -> None:
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        payload = r.json()
        self.assertEqual(payload["status"], "not_ready")
        auth_check = _readiness_check(payload, "authentication")
        self.assertEqual(auth_check["name"], "authentication")
        self.assertFalse(auth_check["ready"])
        body_text = r.text
        self.assertNotIn("prod-key", body_text)

    def test_existing_application_and_configuration_checks_still_pass(self) -> None:
        """The new probe must not disturb the pre-existing readiness checks."""
        with self._build(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="") as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        payload = r.json()
        self.assertTrue(_readiness_check(payload, "application")["ready"])
        self.assertTrue(_readiness_check(payload, "configuration")["ready"])
