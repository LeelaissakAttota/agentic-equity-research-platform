"""Primary→secondary financial data fallback with provenance preservation."""

from __future__ import annotations

from financial_intelligence.application.ports import FinancialDataPort
from financial_intelligence.domain.financial import CompanyFinancialPackage
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.infrastructure.financial.fallback")


class FallbackFinancialDataAdapter:
    """Try primary adapter; on None or exception, fall back to secondary."""

    def __init__(self, primary: FinancialDataPort, secondary: FinancialDataPort) -> None:
        self._primary = primary
        self._secondary = secondary

    def get_financial_package(
        self,
        company_id: CompanyId,
        *,
        fiscal_year: int | None = None,
    ) -> CompanyFinancialPackage | None:
        try:
            package = self._primary.get_financial_package(company_id, fiscal_year=fiscal_year)
            if package is not None:
                return package
        except Exception as exc:
            logger.warning(
                "financial_primary_failed",
                extra={
                    "company_id": company_id.as_text(),
                    "fiscal_year": fiscal_year,
                    "error_type": type(exc).__name__,
                },
            )
        return self._secondary.get_financial_package(company_id, fiscal_year=fiscal_year)
