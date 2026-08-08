"""Application contracts for financial snapshot use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.domain.financial import (
    CompanyFinancialPackage,
    FinancialMetric,
    OmittedMetric,
)


class FinancialSnapshotStatus(StrEnum):
    """Outcome of a financial snapshot request."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class FinancialSnapshotQuery:
    """Financial snapshot request bound to company resolution inputs."""

    company_query: CompanyQuery
    fiscal_year: int | None = None

    def __post_init__(self) -> None:
        if self.fiscal_year is not None and (self.fiscal_year < 1900 or self.fiscal_year > 2100):
            msg = "fiscal_year out of supported bounds"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class FinancialSnapshotResult:
    """Traceable financial snapshot with statements, metrics, and provenance."""

    query: FinancialSnapshotQuery
    status: FinancialSnapshotStatus
    message: str
    resolution: ResolutionResult | None = None
    package: CompanyFinancialPackage | None = None
    metrics: tuple[FinancialMetric, ...] = ()
    omissions: tuple[OmittedMetric, ...] = ()
    provider_name: str | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        blocked = {
            FinancialSnapshotStatus.RESOLUTION_BLOCKED,
            FinancialSnapshotStatus.INVALID,
        }
        if self.status in blocked and (self.package is not None or self.metrics or self.omissions):
            msg = f"{self.status.value} results must not attach financial data or metrics"
            raise ValueError(msg)
        if self.status is FinancialSnapshotStatus.UNAVAILABLE and (self.metrics or self.omissions):
            msg = "unavailable results must not include derived metrics or omissions"
            raise ValueError(msg)
        if self.evaluated_at is not None and self.evaluated_at.tzinfo is None:
            msg = "evaluated_at must be timezone-aware"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "message": self.message,
            "provider_name": self.provider_name,
            "data_origin": (self.package.data_origin.value if self.package is not None else None),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "omissions": [omission.to_dict() for omission in self.omissions],
            "query": {
                "raw_query": self.query.company_query.raw_query,
                "country": (
                    self.query.company_query.country.as_text()
                    if self.query.company_query.country
                    else None
                ),
                "exchange": (
                    self.query.company_query.exchange.as_text()
                    if self.query.company_query.exchange
                    else None
                ),
                "ticker": (
                    self.query.company_query.ticker.as_text()
                    if self.query.company_query.ticker
                    else None
                ),
                "fiscal_year": self.query.fiscal_year,
            },
        }
        if self.evaluated_at is not None:
            payload["evaluated_at"] = self.evaluated_at.isoformat().replace("+00:00", "Z")
        if self.resolution is not None:
            payload["resolution"] = {
                "status": self.resolution.status.value,
                "matched_by": self.resolution.matched_by.value,
                "confidence": self.resolution.confidence.value,
                "message": self.resolution.message,
                "company_id": (
                    self.resolution.company.company_id.as_text()
                    if self.resolution.company is not None
                    else None
                ),
            }
        if self.package is not None:
            payload["package"] = self.package.to_dict()
            if self.package.filing is not None:
                payload["filing"] = self.package.filing.to_dict()
                payload["source"] = {
                    "source_id": self.package.filing.source_id.as_text(),
                    "authority_tier": int(self.package.filing.authority_tier),
                    "form_type": self.package.filing.form_type.value,
                    "provider_name": self.package.filing.provider_name,
                    "accession_or_reference": self.package.filing.accession_or_reference,
                    "source_url": self.package.filing.source_url,
                }
            if self.package.conflicts:
                payload["conflicts"] = [c.to_dict() for c in self.package.conflicts]
        return payload


def resolution_blocks_financials(status: ResolutionStatus) -> bool:
    """True when financial data must not be attached to an unresolved company."""

    return status is not ResolutionStatus.RESOLVED
