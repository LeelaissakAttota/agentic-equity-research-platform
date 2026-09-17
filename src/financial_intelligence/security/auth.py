"""API-key authentication dependency for FastAPI routes (Phase 11.2).

Clients authenticate by supplying a Bearer token in the Authorization header::

    Authorization: Bearer <API_KEY>

Authentication is enforced in production and staging environments.
In development and test environments it is bypassed so local workflows and
the existing test suite remain unaffected.

The dependency never logs or returns the submitted credential.
All authentication failures produce the same generic 401 response to avoid
distinguishing missing credentials from invalid ones.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from financial_intelligence.api.errors import AuthenticationError
from financial_intelligence.composition import AppContainer
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.security.auth")

# Environments that enforce authentication even when auth_enabled=True.
# Development and test bypass auth so the local workflow and existing test
# suite continue to work without reconfiguration.
_ENFORCED_ENVIRONMENTS = frozenset({"production", "staging"})

# F11: a native FastAPI security scheme, declared as a dependency parameter
# below, so FastAPI's OpenAPI generator can discover and describe this
# route's Bearer-authentication requirement (components.securitySchemes and
# each protected operation's `security` list). `auto_error=False` is
# deliberate: it makes this scheme parse the header and hand back `None` on
# any absence/malformed/wrong-scheme header instead of raising its own
# HTTPException, so the existing application-level logic below remains the
# single place that decides the final authentication outcome and error
# response -- this scheme only supplies OpenAPI metadata plus the parsed
# credential, it does not change what counts as authenticated.
_bearer_scheme = HTTPBearer(
    scheme_name="ApiKeyBearer",
    description="Opaque API key issued to the caller, presented as a Bearer token.",
    auto_error=False,
)


def _get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _correlation_id(request: Request) -> str:
    state_value = getattr(request.state, "correlation_id", None)
    if isinstance(state_value, str) and state_value:
        return state_value
    return ""


def _reject_401(request: Request) -> None:
    """Raise AuthenticationError that the registered handler converts to HTTP 401.

    Uses the same safe error infrastructure as every other application error.
    The message is always the same generic string regardless of the specific
    failure reason (missing/malformed/invalid) to avoid information leakage.
    """
    correlation_id = _correlation_id(request)
    logger.info(
        "authentication_failed",
        extra={
            "correlation_id": correlation_id,
            "operation": getattr(
                getattr(request.scope.get("route"), "path", None), "__str__", lambda: "unmatched"
            )(),
        },
    )
    raise AuthenticationError()


async def require_api_key(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> None:
    """FastAPI dependency that enforces API-key authentication.

    Inject with ``dependencies=[Depends(require_api_key)]`` on protected
    ``include_router()`` calls in ``api/app.py``.

    Behaviour by environment:

    - ``production`` / ``staging``: authentication is always enforced.
    - ``development`` / ``test``: authentication is bypassed regardless of
      ``auth_enabled`` so the existing development workflow and test suite
      are unaffected.

    The dependency does NOT raise for health/readiness/version routes because
    those routers are registered without this dependency.

    ``credentials`` is supplied by the module-level ``_bearer_scheme``
    (``HTTPBearer(auto_error=False)``, see F11). It parses the exact same
    ``scheme, credential = get_authorization_scheme_param(authorization)``
    logic this dependency used to perform manually -- ``credentials`` is
    ``None`` whenever the header is missing, has no space-separated scheme,
    has an empty credential part, or the scheme is not (case-insensitively)
    "bearer" -- so every rejection reason below is unchanged from before this
    scheme was introduced. Declaring it as a typed parameter here (rather
    than reading ``request.headers`` manually) is what makes FastAPI's
    OpenAPI generator able to discover and describe this authentication
    requirement.
    """
    container = _get_container(request)
    settings = container.settings

    # Bypass auth in development and test environments.
    if settings.app_env not in _ENFORCED_ENVIRONMENTS:
        return

    # In production/staging: authentication is always enforced.
    # (Settings validation already rejects auth_enabled=false in these envs.)
    if credentials is None or not credentials.credentials:
        _reject_401(request)
        return  # unreachable; _reject_401 raises

    if not container.api_key_store.is_valid(credentials.credentials):
        _reject_401(request)
