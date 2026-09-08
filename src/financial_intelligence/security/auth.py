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

from typing import cast

from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param

from financial_intelligence.api.errors import AuthenticationError
from financial_intelligence.composition import AppContainer
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.security.auth")

# Environments that enforce authentication even when auth_enabled=True.
# Development and test bypass auth so the local workflow and existing test
# suite continue to work without reconfiguration.
_ENFORCED_ENVIRONMENTS = frozenset({"production", "staging"})


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


async def require_api_key(request: Request) -> None:
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
    """
    container = _get_container(request)
    settings = container.settings

    # Bypass auth in development and test environments.
    if settings.app_env not in _ENFORCED_ENVIRONMENTS:
        return

    # In production/staging: authentication is always enforced.
    # (Settings validation already rejects auth_enabled=false in these envs.)
    authorization: str = request.headers.get("Authorization", "")
    scheme, credential = get_authorization_scheme_param(authorization)

    if not authorization or scheme.lower() != "bearer" or not credential:
        _reject_401(request)
        return  # unreachable; _reject_401 raises

    if not container.api_key_store.is_valid(credential):
        _reject_401(request)
