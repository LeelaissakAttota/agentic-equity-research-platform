"""GetRegulatorySnapshot use case — Phase 5 regulatory foundation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import (
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.application.ports import RegulatoryEventPort
from financial_intelligence.application.regulatory_contracts import (
    RegulatorySnapshotQuery,
    RegulatorySnapshotResult,
    RegulatorySnapshotStatus,
    resolution_blocks_regulatory,
)
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.regulatory import (
    CompanyRegulatoryPackage,
    RegulatoryAvailability,
)


class GetRegulatorySnapshot:
    """Resolve company identity safely, then load regulatory events."""

    def __init__(
        self,
        resolve_company: ResolveCompany,
        regulatory: RegulatoryEventPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._resolve_company = resolve_company
        self._regulatory = regulatory
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, query: RegulatorySnapshotQuery) -> RegulatorySnapshotResult:
        evaluated_at = self._clock()
        if evaluated_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        resolution = self._resolve_company.execute(query.company_query)

        if resolution.status is ResolutionStatus.INVALID:
            return RegulatorySnapshotResult(
                query=query,
                status=RegulatorySnapshotStatus.INVALID,
                message=resolution.message or "invalid company query",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if resolution_blocks_regulatory(resolution.status):
            return RegulatorySnapshotResult(
                query=query,
                status=RegulatorySnapshotStatus.RESOLUTION_BLOCKED,
                message=("regulatory data is withheld until company identity is uniquely resolved"),
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        assert resolution.company is not None
        package = self._regulatory.get_regulatory_package(resolution.company.company_id)
        if package is None:
            return RegulatorySnapshotResult(
                query=query,
                status=RegulatorySnapshotStatus.UNAVAILABLE,
                message="regulatory data is unavailable for the resolved company",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if package.company_id != resolution.company.company_id:
            return RegulatorySnapshotResult(
                query=query,
                status=RegulatorySnapshotStatus.UNAVAILABLE,
                message="regulatory adapter returned data for a different company",
                resolution=resolution,
                provider_name=package.provider_name,
                evaluated_at=evaluated_at,
            )
        return self._build_success(query, resolution, package, evaluated_at)

    def _build_success(
        self,
        query: RegulatorySnapshotQuery,
        resolution: ResolutionResult,
        package: CompanyRegulatoryPackage,
        evaluated_at: datetime,
    ) -> RegulatorySnapshotResult:
        if package.availability is RegulatoryAvailability.PARTIAL:
            status = RegulatorySnapshotStatus.PARTIAL
            message = "regulatory coverage is partial"
        elif package.availability is RegulatoryAvailability.DEGRADED:
            status = RegulatorySnapshotStatus.DEGRADED
            message = "regulatory data returned in degraded mode"
        else:
            status = RegulatorySnapshotStatus.OK
            message = "regulatory snapshot computed"
        return RegulatorySnapshotResult(
            query=query,
            status=status,
            message=message,
            resolution=resolution,
            package=package,
            provider_name=package.provider_name,
            evaluated_at=evaluated_at,
        )
