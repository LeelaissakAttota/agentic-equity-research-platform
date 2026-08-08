"""Application contracts for industry/competitor snapshot use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.domain.industry import CompanyIndustryPackage


class IndustrySnapshotStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    PARTIAL = "partial"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class IndustrySnapshotQuery:
    company_query: CompanyQuery


@dataclass(frozen=True, slots=True)
class IndustrySnapshotResult:
    query: IndustrySnapshotQuery
    status: IndustrySnapshotStatus
    message: str
    resolution: ResolutionResult | None = None
    package: CompanyIndustryPackage | None = None
    provider_name: str | None = None
    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        blocked = {
            IndustrySnapshotStatus.RESOLUTION_BLOCKED,
            IndustrySnapshotStatus.INVALID,
            IndustrySnapshotStatus.UNAVAILABLE,
        }
        if self.status in blocked and self.package is not None:
            msg = f"{self.status.value} results must not attach industry data"
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
            },
            "industry": (
                self.package.industry.to_dict()
                if self.package is not None and self.package.industry is not None
                else None
            ),
            "competitors": (
                [c.to_dict() for c in self.package.competitors] if self.package is not None else []
            ),
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
        return payload


def resolution_blocks_industry(status: ResolutionStatus) -> bool:
    return status is not ResolutionStatus.RESOLVED
