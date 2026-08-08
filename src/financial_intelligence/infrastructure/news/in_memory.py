"""In-memory news/event adapter backed by Phase 5 reference fixtures."""

from __future__ import annotations

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.news import (
    CompanyEventPackage,
    EventConflict,
    EventType,
    NewsEventAvailability,
)
from financial_intelligence.infrastructure.news.reference_dataset import (
    build_reference_event_packages,
)


class InMemoryNewsEventAdapter:
    """Fixture-backed NewsEventPort implementation (no network)."""

    def __init__(
        self,
        packages_by_company: dict[str, CompanyEventPackage] | None = None,
        *,
        provider_name: str = "fixture",
    ) -> None:
        data = (
            packages_by_company
            if packages_by_company is not None
            else build_reference_event_packages()
        )
        self._packages = dict(data)
        self.provider_name = provider_name

    def get_event_package(
        self,
        company_id: CompanyId,
        *,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> CompanyEventPackage | None:
        package = self._packages.get(company_id.as_text())
        if package is None:
            return None

        events = package.events
        if event_type is not None:
            try:
                wanted = EventType(event_type)
            except ValueError:
                return None
            events = tuple(e for e in events if e.event_type is wanted)
        if limit is not None:
            events = events[:limit]

        if not events:
            return None

        availability = (
            NewsEventAvailability.PARTIAL
            if event_type is not None and len(events) < len(package.events)
            else package.availability
        )
        # Filtering to a subset of types is still available coverage for that filter.
        if event_type is not None:
            availability = NewsEventAvailability.AVAILABLE

        surviving_ids = {e.event_id.as_text() for e in events}
        conflicts: tuple[EventConflict, ...] = ()
        if event_type is None:
            kept: list[EventConflict] = []
            for conflict in package.conflicts:
                candidate_ids = {c.event_id.as_text() for c in conflict.candidates}
                if candidate_ids & surviving_ids:
                    kept.append(conflict)
            conflicts = tuple(kept)

        result = CompanyEventPackage(
            company_id=package.company_id,
            retrieved_at=package.retrieved_at,
            events=events,
            conflicts=conflicts,
            provider_name=self.provider_name,
            availability=availability,
            data_origin=DataOrigin.FIXTURE,
        )
        return result
