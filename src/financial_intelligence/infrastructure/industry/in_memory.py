"""In-memory industry/competitor adapter (fixture-backed)."""

from __future__ import annotations

from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.industry import CompanyIndustryPackage
from financial_intelligence.infrastructure.industry.reference_dataset import (
    build_reference_industry_packages,
)


class InMemoryIndustryAdapter:
    """Fixture-backed IndustryContextPort implementation (no network)."""

    def __init__(
        self,
        packages_by_company: dict[str, CompanyIndustryPackage] | None = None,
        *,
        provider_name: str = "fixture",
    ) -> None:
        data = (
            packages_by_company
            if packages_by_company is not None
            else build_reference_industry_packages()
        )
        self._packages = dict(data)
        self.provider_name = provider_name

    def get_industry_package(self, company_id: CompanyId) -> CompanyIndustryPackage | None:
        package = self._packages.get(company_id.as_text())
        if package is None:
            return None
        return CompanyIndustryPackage(
            company_id=package.company_id,
            retrieved_at=package.retrieved_at,
            industry=package.industry,
            competitors=package.competitors,
            provider_name=self.provider_name,
            availability=package.availability,
            data_origin=package.data_origin,
        )
