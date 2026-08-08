"""Extensible readiness registry for currently implemented dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
    ReadinessStatus,
)

ReadinessProbe = Callable[[], ReadinessCheckResult]


@dataclass
class ReadinessRegistry:
    """Collect named readiness probes without inventing future dependencies."""

    _probes: dict[str, ReadinessProbe] = field(default_factory=dict)

    def register(self, name: str, probe: ReadinessProbe) -> None:
        """Register or replace a named readiness probe."""

        cleaned = name.strip()
        if not cleaned:
            msg = "readiness probe name must be non-empty"
            raise ValueError(msg)
        self._probes[cleaned] = probe

    def evaluate(self, metadata: ApplicationMetadata) -> ReadinessStatus:
        """Evaluate registered probes in stable name order.

        Empty registry means foundation-ready. Probe exceptions become failed
        checks so ``/ready`` remains a controlled signal instead of a crash.
        """

        checks: list[ReadinessCheckResult] = []
        for name in sorted(self._probes):
            probe = self._probes[name]
            try:
                result = probe()
            except Exception as exc:
                checks.append(
                    ReadinessCheckResult(
                        name=name,
                        ready=False,
                        detail=f"probe_error:{type(exc).__name__}",
                    )
                )
                continue
            if result.name != name:
                checks.append(
                    ReadinessCheckResult(
                        name=name,
                        ready=False,
                        detail="probe_error:name_mismatch",
                    )
                )
                continue
            checks.append(result)

        ready = all(check.ready for check in checks)
        return ReadinessStatus(
            status="ready" if ready else "not_ready",
            service=metadata.service,
            version=metadata.version,
            checks=tuple(checks),
        )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._probes))

    def as_mapping(self) -> Mapping[str, ReadinessProbe]:
        return dict(self._probes)
