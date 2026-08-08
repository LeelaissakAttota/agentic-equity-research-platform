"""Financial snapshot HTTP routes (Phase 4 Financial Intelligence).

HTTP semantics:

- OK / UNAVAILABLE / DEGRADED / PARTIAL / RESOLUTION_BLOCKED → ``200``
- INVALID company/financial query → ``400`` with stable error envelope
- Framework parameter validation → ``422``

Ambiguity and missing financial data are successful protocol outcomes carrying
status, not fabricated success payloads.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.financial_contracts import (
    FinancialSnapshotQuery,
    FinancialSnapshotStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["financials"])
logger = get_logger("financial_intelligence.api.financials")


class FinancialSnapshotResponse(BaseModel):
    """Structured financial-snapshot response contract."""

    status: str
    message: str
    provider_name: str | None = None
    data_origin: str | None = None
    evaluated_at: str | None = None
    query: dict[str, Any]
    resolution: dict[str, Any] | None = None
    package: dict[str, Any] | None = None
    filing: dict[str, Any] | None = None
    source: dict[str, Any] | None = None
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    omissions: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get(
    "/financials/snapshot",
    response_model=FinancialSnapshotResponse,
    responses={
        400: {"description": "Invalid financial or company query"},
    },
)
def financial_snapshot(
    request: Request,
    q: str = Query(default="", max_length=QUERY_MAX_LENGTH),
    country: str | None = Query(default=None, max_length=2),
    exchange: str | None = Query(default=None, max_length=32),
    ticker: str | None = Query(default=None, max_length=32),
    fiscal_year: int | None = Query(default=None, ge=1900, le=2100),
) -> FinancialSnapshotResponse | JSONResponse:
    """Return traceable financial fundamentals for a safely resolved company."""

    container = _container(request)
    try:
        country_code = CountryCode(country) if country else None
        exchange_code = ExchangeCode(exchange) if exchange else None
        ticker_symbol = TickerSymbol(ticker) if ticker else None
        snapshot_query = FinancialSnapshotQuery(
            company_query=CompanyQuery(
                raw_query=q,
                country=country_code,
                exchange=exchange_code,
                ticker=ticker_symbol,
            ),
            fiscal_year=fiscal_year,
        )
    except ValueError as exc:
        logger.info(
            "financial_snapshot",
            extra={
                "financial_status": FinancialSnapshotStatus.INVALID.value,
                "query_length": len(q),
            },
        )
        return build_error_response(
            code="invalid_financial_query",
            message=str(exc),
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.get_financial_snapshot.execute(snapshot_query)
    logger.info(
        "financial_snapshot",
        extra={
            "financial_status": result.status.value,
            "provider_name": result.provider_name,
            "data_origin": (
                result.package.data_origin.value if result.package is not None else None
            ),
            "metric_count": len(result.metrics),
            "company_id": (
                result.resolution.company.company_id.as_text()
                if result.resolution and result.resolution.company
                else None
            ),
            "fiscal_year": fiscal_year,
            "query_length": len(q),
        },
    )

    if result.status is FinancialSnapshotStatus.INVALID:
        return build_error_response(
            code="invalid_financial_query",
            message=result.message or "invalid financial query",
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return FinancialSnapshotResponse.model_validate(result.to_dict())
