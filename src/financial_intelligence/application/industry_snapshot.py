"""GetIndustryContextSnapshot use case — Phase 5 industry/competitor foundation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import (
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.application.industry_contracts import (
    IndustrySnapshotQuery,
    IndustrySnapshotResult,
    IndustrySnapshotStatus,
    resolution_blocks_industry,
)
from financial_intelligence.application.ports import IndustryContextPort
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.industry import (
    CompanyIndustryPackage,
    IndustryAvailability,
)


class GetIndustryContextSnapshot:
    """Resolve company identity safely, then load industry/competitor context."""

    def __init__(
        self,
        resolve_company: ResolveCompany,
        industry: IndustryContextPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._resolve_company = resolve_company
        self._industry = industry
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, query: IndustrySnapshotQuery) -> IndustrySnapshotResult:
        evaluated_at = self._clock()
        if evaluated_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        resolution = self._resolve_company.execute(query.company_query)

        if resolution.status is ResolutionStatus.INVALID:
            return IndustrySnapshotResult(
                query=query,
                status=IndustrySnapshotStatus.INVALID,
                message=resolution.message or "invalid company query",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if resolution_blocks_industry(resolution.status):
            return IndustrySnapshotResult(
                query=query,
                status=IndustrySnapshotStatus.RESOLUTION_BLOCKED,
                message="industry data is withheld until company identity is uniquely resolved",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        assert resolution.company is not None
        package = self._industry.get_industry_package(resolution.company.company_id)
        if package is None:
            return IndustrySnapshotResult(
                query=query,
                status=IndustrySnapshotStatus.UNAVAILABLE,
                message="industry/competitor data is unavailable for the resolved company",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )
        if package.company_id != resolution.company.company_id:
            return IndustrySnapshotResult(
                query=query,
                status=IndustrySnapshotStatus.UNAVAILABLE,
                message="industry adapter returned data for a different company",
                resolution=resolution,
                provider_name=package.provider_name,
                evaluated_at=evaluated_at,
            )
        return self._build_success(query, resolution, package, evaluated_at)

    def _build_success(
        self,
        query: IndustrySnapshotQuery,
        resolution: ResolutionResult,
        package: CompanyIndustryPackage,
        evaluated_at: datetime,
    ) -> IndustrySnapshotResult:
        if package.availability is IndustryAvailability.PARTIAL:
            status = IndustrySnapshotStatus.PARTIAL
            message = "industry coverage is partial"
        elif package.availability is IndustryAvailability.DEGRADED:
            status = IndustrySnapshotStatus.DEGRADED
            message = "industry data returned in degraded mode"
        else:
            status = IndustrySnapshotStatus.OK
            message = "industry context snapshot computed"
        return IndustrySnapshotResult(
            query=query,
            status=status,
            message=message,
            resolution=resolution,
            package=package,
            provider_name=package.provider_name,
            evaluated_at=evaluated_at,
        )
