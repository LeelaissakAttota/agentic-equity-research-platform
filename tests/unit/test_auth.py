"""Phase 11.2 authentication tests.

Covers:
- InMemoryApiKeyStore unit behaviour and constant-time comparison
- Authentication dependency: public endpoints remain open
- Authentication dependency: protected endpoints reject unauthenticated requests
  in production/staging mode
- Authentication dependency: test/development environments bypass auth
- Settings: production AUTH_ENABLED=false is rejected at startup
- Security invariants: no credential leakage
"""

from __future__ import annotations

from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.auth.in_memory_api_key_store import InMemoryApiKeyStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _test_settings(**kwargs: object) -> Settings:
    """Build settings with APP_ENV=test (auth bypass active)."""
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING", **kwargs)  # type: ignore[arg-type]


def _production_settings(*, api_keys: str = "test-key-prod-1") -> Settings:
    """Build production settings with auth enabled and explicit keys."""
    return Settings(
        _env_file=None,
        APP_ENV="production",
        LOG_LEVEL="INFO",
        ALLOWED_HOSTS="example.com",
        AUTH_ENABLED="true",
        API_KEYS=api_keys,
    )


def _staging_settings(*, api_keys: str = "test-key-staging-1") -> Settings:
    """Build staging settings with auth enabled."""
    return Settings(
        _env_file=None,
        APP_ENV="staging",
        LOG_LEVEL="INFO",
        ALLOWED_HOSTS="staging.example.com",
        AUTH_ENABLED="true",
        API_KEYS=api_keys,
    )


# ---------------------------------------------------------------------------
# InMemoryApiKeyStore unit tests
# ---------------------------------------------------------------------------


class TestInMemoryApiKeyStore(TestCase):
    def test_valid_key_returns_true(self) -> None:
        store = InMemoryApiKeyStore.from_csv("my-secret-key")
        self.assertTrue(store.is_valid("my-secret-key"))

    def test_invalid_key_returns_false(self) -> None:
        store = InMemoryApiKeyStore.from_csv("my-secret-key")
        self.assertFalse(store.is_valid("wrong-key"))

    def test_empty_presented_key_returns_false(self) -> None:
        store = InMemoryApiKeyStore.from_csv("my-secret-key")
        self.assertFalse(store.is_valid(""))

    def test_empty_store_returns_false(self) -> None:
        store = InMemoryApiKeyStore.from_csv("")
        self.assertFalse(store.is_valid("any-key"))

    def test_multiple_keys_any_valid(self) -> None:
        store = InMemoryApiKeyStore.from_csv("key-a,key-b,key-c")
        self.assertTrue(store.is_valid("key-a"))
        self.assertTrue(store.is_valid("key-b"))
        self.assertTrue(store.is_valid("key-c"))
        self.assertFalse(store.is_valid("key-d"))

    def test_whitespace_only_token_ignored(self) -> None:
        store = InMemoryApiKeyStore.from_csv("  ,  ,valid-key")
        self.assertTrue(store.is_valid("valid-key"))
        self.assertFalse(store.is_valid("  "))

    def test_has_keys_true_when_configured(self) -> None:
        store = InMemoryApiKeyStore.from_csv("key-x")
        self.assertTrue(store.has_keys)

    def test_has_keys_false_when_empty(self) -> None:
        store = InMemoryApiKeyStore.from_csv("")
        self.assertFalse(store.has_keys)

    def test_uses_compare_digest_not_equals(self) -> None:
        """Structural: is_valid must use secrets.compare_digest.

        We verify via behavioural means: comparison must not raise even when
        presented key differs in length (plain == behaves differently from
        compare_digest for timing, but both return False for mismatches;
        the important thing is we confirm the code path is reachable without
        exception and returns False for mismatches).
        """
        store = InMemoryApiKeyStore.from_csv("short")
        # Longer key — must return False, not raise or leak timing
        self.assertFalse(store.is_valid("a" * 256))
        # Empty key — must return False immediately
        self.assertFalse(store.is_valid(""))

    def test_compare_digest_import_and_use(self) -> None:
        """Confirm secrets.compare_digest is used (code inspection via import)."""
        import inspect

        import financial_intelligence.infrastructure.auth.in_memory_api_key_store as m

        source = inspect.getsource(m)
        self.assertIn("secrets.compare_digest", source)
        self.assertNotIn("presented_key ==", source)


# ---------------------------------------------------------------------------
# Settings configuration tests
# ---------------------------------------------------------------------------


class TestAuthSettings(TestCase):
    def test_production_auth_disabled_rejected(self) -> None:
        """Production with AUTH_ENABLED=false must raise at startup."""
        with self.assertRaises(ValueError):
            Settings(
                _env_file=None,
                APP_ENV="production",
                LOG_LEVEL="INFO",
                ALLOWED_HOSTS="example.com",
                AUTH_ENABLED="false",
                API_KEYS="some-key",
            )

    def test_staging_auth_disabled_rejected(self) -> None:
        """Staging with AUTH_ENABLED=false must raise at startup."""
        with self.assertRaises(ValueError):
            Settings(
                _env_file=None,
                APP_ENV="staging",
                LOG_LEVEL="INFO",
                ALLOWED_HOSTS="staging.example.com",
                AUTH_ENABLED="false",
                API_KEYS="some-key",
            )

    def test_development_auth_disabled_allowed(self) -> None:
        """Development with AUTH_ENABLED=false is permitted."""
        s = Settings(_env_file=None, APP_ENV="development", AUTH_ENABLED="false")
        self.assertFalse(s.auth_enabled)

    def test_test_env_auth_disabled_allowed(self) -> None:
        """Test environment with AUTH_ENABLED=false is permitted."""
        s = _test_settings(AUTH_ENABLED="false")
        self.assertFalse(s.auth_enabled)

    def test_api_keys_not_in_safe_log_context(self) -> None:
        """API key value must never appear in safe_log_context."""
        s = Settings(_env_file=None, APP_ENV="test", API_KEYS="secret-log-test-key")
        context = s.safe_log_context()
        self.assertNotIn("api_keys", context)
        context_str = str(context)
        self.assertNotIn("secret-log-test-key", context_str)

    def test_api_keys_configured_bool_in_safe_log_context(self) -> None:
        """Only the boolean flag api_keys_configured appears in safe_log_context."""
        s = Settings(_env_file=None, APP_ENV="test", API_KEYS="any-key")
        context = s.safe_log_context()
        self.assertIn("api_keys_configured", context)
        self.assertTrue(context["api_keys_configured"])

    def test_auth_enabled_in_safe_log_context(self) -> None:
        s = Settings(_env_file=None, APP_ENV="test", AUTH_ENABLED="true")
        context = s.safe_log_context()
        self.assertIn("auth_enabled", context)
        self.assertTrue(context["auth_enabled"])

    def test_production_valid_settings(self) -> None:
        """Production with AUTH_ENABLED=true and a key must be accepted."""
        s = _production_settings(api_keys="a-valid-prod-key")
        self.assertTrue(s.auth_enabled)
        self.assertEqual(s.api_keys.get_secret_value(), "a-valid-prod-key")


# ---------------------------------------------------------------------------
# Public endpoints — must remain accessible without credentials
# ---------------------------------------------------------------------------


class TestPublicEndpoints(TestCase):
    """Public health/version endpoints must be accessible in all environments."""

    def _prod_client(self) -> TestClient:
        return TestClient(create_app(settings=_production_settings()))

    def test_health_no_key_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/health")
        self.assertEqual(r.status_code, 200)

    def test_ready_no_key_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/ready")
        self.assertEqual(r.status_code, 200)

    def test_version_no_key_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/version")
        self.assertEqual(r.status_code, 200)

    def test_v1_health_no_key_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/v1/health")
        self.assertEqual(r.status_code, 200)

    def test_v1_ready_no_key_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/v1/ready")
        self.assertEqual(r.status_code, 200)

    def test_v1_version_no_key_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/v1/version")
        self.assertEqual(r.status_code, 200)

    def test_health_no_key_production(self) -> None:
        with self._prod_client() as client:
            r = client.get("/health", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)

    def test_ready_no_key_production(self) -> None:
        with self._prod_client() as client:
            r = client.get("/ready", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)

    def test_version_no_key_production(self) -> None:
        with self._prod_client() as client:
            r = client.get("/version", headers={"HOST": "example.com"})
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# Protected endpoints — authentication enforced in production/staging
# ---------------------------------------------------------------------------


class TestProtectedEndpointsProduction(TestCase):
    """In production, protected endpoints must reject unauthenticated requests."""

    TEST_KEY = "prod-test-key-abc"

    def setUp(self) -> None:
        self.app = create_app(settings=_production_settings(api_keys=self.TEST_KEY))

    def _host_header(self) -> dict[str, str]:
        return {"HOST": "example.com"}

    def test_companies_resolve_no_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/companies/resolve?q=Apple", headers=self._host_header())
        self.assertEqual(r.status_code, 401)

    def test_companies_resolve_wrong_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": "Bearer wrong-key"},
            )
        self.assertEqual(r.status_code, 401)

    def test_companies_resolve_valid_key_returns_2xx(self) -> None:
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": f"Bearer {self.TEST_KEY}"},
            )
        self.assertIn(r.status_code, (200, 404, 422))  # auth passed, business logic varies

    def test_market_snapshot_no_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/market/snapshot?q=Apple", headers=self._host_header())
        self.assertEqual(r.status_code, 401)

    def test_research_plans_no_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.post(
                "/research/plans",
                json={"q": "Apple", "objective": "market_analysis"},
                headers=self._host_header(),
            )
        self.assertEqual(r.status_code, 401)

    def test_v1_companies_resolve_no_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/v1/companies/resolve?q=Apple", headers=self._host_header())
        self.assertEqual(r.status_code, 401)

    def test_watchlist_create_no_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.post(
                "/watchlists",
                json={"name": "test"},
                headers=self._host_header(),
            )
        self.assertEqual(r.status_code, 401)

    def test_missing_auth_header_returns_same_as_invalid(self) -> None:
        """Missing and invalid credentials must produce identical responses."""
        host = self._host_header()
        with TestClient(self.app) as client:
            r_missing = client.get("/companies/resolve?q=Apple", headers=host)
            r_invalid = client.get(
                "/companies/resolve?q=Apple",
                headers={**host, "Authorization": "Bearer garbage-key"},
            )
        self.assertEqual(r_missing.status_code, r_invalid.status_code)
        self.assertEqual(r_missing.json()["error"]["code"], r_invalid.json()["error"]["code"])
        self.assertEqual(
            r_missing.json()["error"]["message"],
            r_invalid.json()["error"]["message"],
        )


class TestProtectedEndpointsStaging(TestCase):
    """Staging behaves identically to production for auth enforcement."""

    TEST_KEY = "staging-test-key-xyz"

    def setUp(self) -> None:
        self.app = create_app(settings=_staging_settings(api_keys=self.TEST_KEY))

    def test_companies_no_key_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={"HOST": "staging.example.com"},
            )
        self.assertEqual(r.status_code, 401)

    def test_companies_valid_key_passes(self) -> None:
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={
                    "HOST": "staging.example.com",
                    "Authorization": f"Bearer {self.TEST_KEY}",
                },
            )
        self.assertIn(r.status_code, (200, 404, 422))


# ---------------------------------------------------------------------------
# Test/development auth bypass — existing tests must be unaffected
# ---------------------------------------------------------------------------


class TestAuthBypassInTestEnv(TestCase):
    """In test/development environments, protected endpoints bypass auth."""

    def test_protected_endpoint_no_key_succeeds_in_test_env(self) -> None:
        with TestClient(create_app(settings=_test_settings())) as client:
            r = client.get("/companies/resolve?q=Apple")
        # Auth bypass: status code reflects business logic, not auth failure
        self.assertNotEqual(r.status_code, 401)

    def test_development_env_bypasses_auth(self) -> None:
        s = Settings(_env_file=None, APP_ENV="development", LOG_LEVEL="INFO")
        with TestClient(create_app(settings=s)) as client:
            r = client.get("/companies/resolve?q=Apple")
        self.assertNotEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Security invariants — credential leakage
# ---------------------------------------------------------------------------


class TestSecurityInvariants(TestCase):
    """Credentials must never appear in responses, headers, or error bodies."""

    TEST_KEY = "super-secret-do-not-leak"

    def setUp(self) -> None:
        self.app = create_app(settings=_production_settings(api_keys=self.TEST_KEY))

    def _host_header(self) -> dict[str, str]:
        return {"HOST": "example.com"}

    def test_submitted_key_not_in_401_body(self) -> None:
        submitted = "wrong-submitted-key-xyz"
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": f"Bearer {submitted}"},
            )
        self.assertEqual(r.status_code, 401)
        self.assertNotIn(submitted, r.text)

    def test_configured_key_not_in_401_body(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/companies/resolve?q=Apple", headers=self._host_header())
        self.assertEqual(r.status_code, 401)
        self.assertNotIn(self.TEST_KEY, r.text)

    def test_401_body_uses_generic_message(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/companies/resolve?q=Apple", headers=self._host_header())
        payload = r.json()
        self.assertEqual(payload["error"]["message"], "Authentication required")
        self.assertEqual(payload["error"]["code"], "authentication_required")

    def test_401_includes_correlation_id(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/companies/resolve?q=Apple", headers=self._host_header())
        self.assertEqual(r.status_code, 401)
        self.assertIn("X-Correlation-ID", r.headers)
        correlation_id = r.headers["X-Correlation-ID"]
        self.assertTrue(len(correlation_id) > 0)

    def test_no_key_in_response_headers(self) -> None:
        submitted = "another-wrong-key"
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": f"Bearer {submitted}"},
            )
        response_header_str = str(dict(r.headers))
        self.assertNotIn(submitted, response_header_str)

    def test_malformed_bearer_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": "NotBearer token"},
            )
        self.assertEqual(r.status_code, 401)

    def test_missing_header_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get("/companies/resolve?q=Apple", headers=self._host_header())
        self.assertEqual(r.status_code, 401)

    def test_empty_bearer_returns_401(self) -> None:
        with TestClient(self.app) as client:
            r = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": "Bearer "},
            )
        self.assertEqual(r.status_code, 401)
