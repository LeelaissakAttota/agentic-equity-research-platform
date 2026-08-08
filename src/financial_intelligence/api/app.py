"""Deterministic FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from financial_intelligence.api.errors import register_exception_handlers
from financial_intelligence.api.middleware import CorrelationIdMiddleware
from financial_intelligence.api.routes import companies, health
from financial_intelligence.composition import AppContainer, build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.observability.logging import configure_logging, get_logger
from financial_intelligence.security.headers import SecurityHeadersMiddleware


def create_app(
    settings: Settings | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    """Create a FastAPI application with explicit composition and lifecycle."""

    resolved_container = container if container is not None else build_container(settings)
    configure_logging(resolved_container.settings.log_level)
    logger = get_logger("financial_intelligence.api")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Extension points for PostgreSQL, Redis, providers, and research
        # services belong here in later phases. Phase 2 uses in-memory catalog only.
        logger.info(
            "application_startup",
            extra=resolved_container.settings.safe_log_context(),
        )
        yield
        logger.info("application_shutdown")

    application = FastAPI(
        title="Agentic Financial Intelligence & Equity Research Platform",
        version=resolved_container.metadata.version,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    application.state.container = resolved_container
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(companies.router)
    return application
