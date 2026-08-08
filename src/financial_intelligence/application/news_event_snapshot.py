"""GetNewsEventSnapshot use case — Phase 5 News & Event Intelligence slice."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import (
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.application.news_event_contracts import (
    NewsEventSnapshotQuery,
    NewsEventSnapshotResult,
    NewsEventSnapshotStatus,
    resolution_blocks_news_events,
)
from financial_intelligence.application.ports import NewsEventPort
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.news import (
    CompanyEventPackage,
    NewsEventAvailability,
)


class GetNewsEventSnapshot:
    """Resolve company identity safely, then load traceable news/events.

    Never attaches events to AMBIGUOUS / NOT_FOUND / INVALID companies.
    Never fabricates events when the adapter has no package.
    """

    def __init__(
        self,
        resolve_company: ResolveCompany,
        news_events: NewsEventPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._resolve_company = resolve_company
        self._news_events = news_events
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(self, query: NewsEventSnapshotQuery) -> NewsEventSnapshotResult:
        evaluated_at = self._clock()
        if evaluated_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        resolution = self._resolve_company.execute(query.company_query)

        if resolution.status is ResolutionStatus.INVALID:
            return NewsEventSnapshotResult(
                query=query,
                status=NewsEventSnapshotStatus.INVALID,
                message=resolution.message or "invalid company query",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        if resolution_blocks_news_events(resolution.status):
            return NewsEventSnapshotResult(
                query=query,
                status=NewsEventSnapshotStatus.RESOLUTION_BLOCKED,
                message="news/event data is withheld until company identity is uniquely resolved",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        assert resolution.company is not None
        package = self._news_events.get_event_package(
            resolution.company.company_id,
            event_type=query.event_type.value if query.event_type else None,
            limit=query.limit,
        )
        if package is None:
            return NewsEventSnapshotResult(
                query=query,
                status=NewsEventSnapshotStatus.UNAVAILABLE,
                message="news/event data is unavailable for the resolved company",
                resolution=resolution,
                evaluated_at=evaluated_at,
            )

        if package.company_id != resolution.company.company_id:
            return NewsEventSnapshotResult(
                query=query,
                status=NewsEventSnapshotStatus.UNAVAILABLE,
                message="news/event adapter returned data for a different company",
                resolution=resolution,
                provider_name=package.provider_name,
                evaluated_at=evaluated_at,
            )

        return self._build_success(query, resolution, package, evaluated_at)

    def _build_success(
        self,
        query: NewsEventSnapshotQuery,
        resolution: ResolutionResult,
        package: CompanyEventPackage,
        evaluated_at: datetime,
    ) -> NewsEventSnapshotResult:
        availability = package.availability
        if availability is NewsEventAvailability.PARTIAL:
            status = NewsEventSnapshotStatus.PARTIAL
            message = "news/event coverage is partial"
        elif availability is NewsEventAvailability.DEGRADED:
            status = NewsEventSnapshotStatus.DEGRADED
            message = "news/event data returned in degraded mode"
        else:
            status = NewsEventSnapshotStatus.OK
            message = "news/event snapshot computed"

        return NewsEventSnapshotResult(
            query=query,
            status=status,
            message=message,
            resolution=resolution,
            package=package,
            provider_name=package.provider_name,
            evaluated_at=evaluated_at,
        )
