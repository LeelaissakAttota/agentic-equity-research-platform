"""F11 regression: the generated OpenAPI schema must accurately describe the
Bearer authentication requirement `require_api_key` already enforces at
runtime (see F11_OPENAPI_MISSING_SECURITY_SCHEME_REMEDIATION_PLAN.md /
F11_OPENAPI_MISSING_SECURITY_SCHEME_IMPLEMENTATION_REPORT.md).

Before the fix, `require_api_key` read `request.headers.get("Authorization")`
manually, which is invisible to FastAPI's OpenAPI generator: the generated
schema had no `components.securitySchemes` entry and no protected route
carried a `security` requirement -- a protected route like
`/companies/resolve` and the public `/health` route were indistinguishable
in the schema. The fix declares a native `HTTPBearer(auto_error=False)`
dependency parameter (`security/auth.py`'s module-level `_bearer_scheme`)
that FastAPI's generator can discover, while `auto_error=False` keeps the
existing application-level logic as the sole authority over the actual
authentication decision and error response.

These tests inspect the real, generated schema from the real `create_app()`
factory (not a hand-built fixture), and separately re-confirm runtime
authentication behavior is unaffected.
"""

from __future__ import annotations

from typing import Any
from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings


def _production_settings(*, api_keys: str = "openapi-test-key") -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="production",
        LOG_LEVEL="INFO",
        ALLOWED_HOSTS="example.com",
        AUTH_ENABLED="true",
        API_KEYS=api_keys,
    )


def _security_schemes(schema: dict[str, Any]) -> dict[str, Any]:
    return schema.get("components", {}).get("securitySchemes", {}) or {}


def _operation_security(schema: dict[str, Any], path: str, method: str = "get") -> Any:
    return schema["paths"][path][method].get("security")


class OpenApiSecuritySchemeTests(TestCase):
    """The schema itself must declare the Bearer scheme and use it correctly."""

    def setUp(self) -> None:
        self.app = create_app(settings=_production_settings())
        self.schema = self.app.openapi()

    def test_security_schemes_are_present(self) -> None:
        schemes = _security_schemes(self.schema)
        self.assertTrue(schemes, "expected at least one entry in components.securitySchemes")

    def test_bearer_http_scheme_is_declared(self) -> None:
        schemes = _security_schemes(self.schema)
        bearer_schemes = [
            definition
            for definition in schemes.values()
            if isinstance(definition, dict)
            and definition.get("type") == "http"
            and definition.get("scheme") == "bearer"
        ]
        self.assertTrue(
            bearer_schemes,
            f"expected an HTTP bearer securityScheme, found: {schemes!r}",
        )

    def test_companies_resolve_requires_the_bearer_scheme(self) -> None:
        schemes = _security_schemes(self.schema)
        bearer_names = {
            name
            for name, definition in schemes.items()
            if isinstance(definition, dict)
            and definition.get("type") == "http"
            and definition.get("scheme") == "bearer"
        }
        security = _operation_security(self.schema, "/companies/resolve")
        self.assertTrue(security, "/companies/resolve must declare a security requirement")
        referenced_names = {name for requirement in security for name in requirement}
        self.assertTrue(
            referenced_names & bearer_names,
            f"/companies/resolve's security requirement {security!r} does not reference "
            f"the declared bearer scheme(s) {bearer_names!r}",
        )

    def test_market_snapshot_also_requires_the_bearer_scheme(self) -> None:
        """A second protected route, proving this isn't a single-route fluke."""
        security = _operation_security(self.schema, "/market/snapshot")
        self.assertTrue(security, "/market/snapshot must declare a security requirement")

    def test_research_plans_post_also_requires_the_bearer_scheme(self) -> None:
        """A third protected route on a different HTTP method (POST)."""
        security = _operation_security(self.schema, "/research/plans", method="post")
        self.assertTrue(security, "/research/plans (POST) must declare a security requirement")

    def test_health_remains_public_with_no_security_requirement(self) -> None:
        security = _operation_security(self.schema, "/health")
        self.assertFalse(
            security,
            f"/health is public and must not carry a security requirement, got {security!r}",
        )

    def test_ready_and_version_remain_public_with_no_security_requirement(self) -> None:
        self.assertFalse(_operation_security(self.schema, "/ready"))
        self.assertFalse(_operation_security(self.schema, "/version"))

    def test_openapi_json_is_served_and_matches_the_in_process_schema(self) -> None:
        """Confirm the fix is visible through the real HTTP boundary, not just
        the in-process app.openapi() call."""
        with TestClient(self.app) as client:
            response = client.get("/openapi.json", headers={"HOST": "example.com"})
        self.assertEqual(response.status_code, 200)
        served_schema = response.json()
        self.assertTrue(_security_schemes(served_schema))
        self.assertTrue(_operation_security(served_schema, "/companies/resolve"))
        self.assertFalse(_operation_security(served_schema, "/health"))


class OpenApiFixDoesNotAlterRuntimeAuthenticationTests(TestCase):
    """The OpenAPI correction must not change any runtime authentication
    outcome -- these mirror test_auth.py's own assertions as a direct,
    co-located proof that the schema fix and the enforcement path agree."""

    TEST_KEY = "openapi-runtime-check-key"

    def setUp(self) -> None:
        self.app = create_app(settings=_production_settings(api_keys=self.TEST_KEY))

    def _host_header(self) -> dict[str, str]:
        return {"HOST": "example.com"}

    def test_missing_credentials_still_returns_401(self) -> None:
        with TestClient(self.app) as client:
            response = client.get("/companies/resolve?q=Apple", headers=self._host_header())
        self.assertEqual(response.status_code, 401)

    def test_invalid_credentials_still_return_401(self) -> None:
        with TestClient(self.app) as client:
            response = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": "Bearer wrong-key"},
            )
        self.assertEqual(response.status_code, 401)

    def test_valid_credentials_still_succeed(self) -> None:
        with TestClient(self.app) as client:
            response = client.get(
                "/companies/resolve?q=Apple",
                headers={**self._host_header(), "Authorization": f"Bearer {self.TEST_KEY}"},
            )
        self.assertIn(response.status_code, (200, 404, 422))

    def test_health_remains_publicly_accessible(self) -> None:
        with TestClient(self.app) as client:
            response = client.get("/health", headers=self._host_header())
        self.assertEqual(response.status_code, 200)
