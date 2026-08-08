"""Composition root: wires concrete adapters to application ports."""

from __future__ import annotations

from dataclasses import dataclass

from financial_intelligence import __version__
from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
)
from financial_intelligence.application.ports import CompanyCatalogPort
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog


@dataclass(slots=True)
class AppContainer:
    """Application composition container."""

    settings: Settings
    readiness: ReadinessRegistry
    metadata: ApplicationMetadata
    company_catalog: CompanyCatalogPort
    resolve_company: ResolveCompany


def build_container(settings: Settings | None = None) -> AppContainer:
    """Wire settings, readiness, and company-resolution foundation."""

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
    catalog: CompanyCatalogPort = InMemoryCompanyCatalog()
    resolve_company = ResolveCompany(catalog)
    return AppContainer(
        settings=resolved,
        readiness=readiness,
        metadata=metadata,
        company_catalog=catalog,
        resolve_company=resolve_company,
    )
