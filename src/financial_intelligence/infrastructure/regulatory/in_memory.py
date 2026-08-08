"""In-memory regulatory adapter (fixture-backed)."""

from __future__ import annotations

from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.regulatory import CompanyRegulatoryPackage
from financial_intelligence.infrastructure.regulatory.reference_dataset import (
    build_reference_regulatory_packages,
)


class InMemoryRegulatoryAdapter:
    """Fixture-backed RegulatoryEventPort implementation (no network)."""

    def __init__(
        self,
        packages_by_company: dict[str, CompanyRegulatoryPackage] | None = None,
        *,
        provider_name: str = "fixture",
    ) -> None:
        data = (
            packages_by_company
            if packages_by_company is not None
            else build_reference_regulatory_packages()
        )
        self._packages = dict(data)
        self.provider_name = provider_name

    def get_regulatory_package(
        self,
        company_id: CompanyId,
    ) -> CompanyRegulatoryPackage | None:
        package = self._packages.get(company_id.as_text())
        if package is None:
            return None
        return CompanyRegulatoryPackage(
            company_id=package.company_id,
            retrieved_at=package.retrieved_at,
            events=package.events,
            provider_name=self.provider_name,
            availability=package.availability,
            data_origin=package.data_origin,
        )
