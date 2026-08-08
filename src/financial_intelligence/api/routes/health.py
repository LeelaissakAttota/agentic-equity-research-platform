"""Health, readiness, and version HTTP routes."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field

from financial_intelligence.composition import AppContainer

router = APIRouter(tags=["foundation"])


class HealthResponse(BaseModel):
    """Liveness response contract."""

    status: str
    service: str
    version: str


class ReadinessCheckResponse(BaseModel):
    """One readiness probe result."""

    name: str
    ready: bool
    detail: str = ""


class ReadinessResponse(BaseModel):
    """Readiness response contract for currently implemented dependencies."""

    status: str
    service: str
    version: str
    checks: list[ReadinessCheckResponse] = Field(default_factory=list)


class VersionResponse(BaseModel):
    """Application metadata response."""

    service: str
    version: str
    environment: str


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    """Return process liveness without probing external systems."""

    container = _container(request)
    return HealthResponse(
        status="ok",
        service=container.metadata.service,
        version=container.metadata.version,
    )


@router.get("/ready", response_model=ReadinessResponse)
def get_ready(request: Request, response: Response) -> ReadinessResponse:
    """Return readiness for currently implemented foundation dependencies."""

    container = _container(request)
    readiness = container.readiness.evaluate(container.metadata)
    payload = ReadinessResponse(
        status=readiness.status,
        service=readiness.service,
        version=readiness.version,
        checks=[
            ReadinessCheckResponse(
                name=check.name,
                ready=check.ready,
                detail=check.detail,
            )
            for check in readiness.checks
        ],
    )
    if not readiness.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload


@router.get("/version", response_model=VersionResponse)
def get_version(request: Request) -> VersionResponse:
    """Return application/version metadata."""

    container = _container(request)
    return VersionResponse(
        service=container.metadata.service,
        version=container.metadata.version,
        environment=container.metadata.environment,
    )
