"""Composition root: the only place that wires concrete Phase 1 components."""

from __future__ import annotations

from dataclasses import dataclass

from financial_intelligence import __version__
from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
)
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.config.settings import Settings


@dataclass(slots=True)
class AppContainer:
    """Minimal Phase 1 composition container."""

    settings: Settings
    readiness: ReadinessRegistry
    metadata: ApplicationMetadata


def build_container(settings: Settings | None = None) -> AppContainer:
    """Wire settings, metadata, and readiness without future providers."""

    resolved = settings if settings is not None else Settings()
    metadata = ApplicationMetadata(
        service=resolved.service_name,
        version=__version__,
        environment=resolved.app_env,
    )
    readiness = ReadinessRegistry()
    readiness.register(
        "application",
        lambda: ReadinessCheckResult(
            name="application",
            ready=True,
            detail="application foundation loaded",
        ),
    )
    return AppContainer(settings=resolved, readiness=readiness, metadata=metadata)
