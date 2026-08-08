"""Foundational application contracts for Phase 1 service metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

HealthState = Literal["ok"]
ReadinessState = Literal["ready", "not_ready"]


@dataclass(frozen=True, slots=True)
class ApplicationMetadata:
    """Stable service identity metadata."""

    service: str
    version: str
    environment: str


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Process liveness signal; never probes external dependencies."""

    status: HealthState
    service: str
    version: str


@dataclass(frozen=True, slots=True)
class ReadinessCheckResult:
    """Result of one named readiness probe."""

    name: str
    ready: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ReadinessStatus:
    """Aggregate readiness for currently implemented dependencies."""

    status: ReadinessState
    service: str
    version: str
    checks: tuple[ReadinessCheckResult, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.status == "ready"
