"""In-memory financial-data adapter backed by Phase 4 reference fixtures."""

from __future__ import annotations

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import CompanyFinancialPackage
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.infrastructure.financial.reference_dataset import (
    build_reference_financial_packages,
)


class InMemoryFinancialDataAdapter:
    """Fixture-backed FinancialDataPort implementation (no network)."""

    def __init__(
        self,
        packages_by_company: dict[str, CompanyFinancialPackage] | None = None,
        *,
        provider_name: str = "fixture",
    ) -> None:
        data = (
            packages_by_company
            if packages_by_company is not None
            else build_reference_financial_packages()
        )
        self._packages = dict(data)
        self.provider_name = provider_name

    def get_financial_package(
        self,
        company_id: CompanyId,
        *,
        fiscal_year: int | None = None,
    ) -> CompanyFinancialPackage | None:
        latest = self._packages.get(company_id.as_text())
        if latest is None:
            return None
        if fiscal_year is None:
            if latest.data_origin is not DataOrigin.FIXTURE:
                return latest.with_data_origin(DataOrigin.FIXTURE)
            return latest
        package: CompanyFinancialPackage | None = latest
        while package is not None:
            if package.reporting_period.fiscal_year == fiscal_year:
                if package.data_origin is not DataOrigin.FIXTURE:
                    return package.with_data_origin(DataOrigin.FIXTURE)
                return package
            package = package.prior_period_package
        return None
