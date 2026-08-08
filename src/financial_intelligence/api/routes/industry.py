"""Industry/competitor snapshot HTTP routes (Phase 5)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.industry_contracts import (
    IndustrySnapshotQuery,
    IndustrySnapshotStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["industry"])
logger = get_logger("financial_intelligence.api.industry")


class IndustrySnapshotResponse(BaseModel):
    status: str
    message: str
    provider_name: str | None = None
    data_origin: str | None = None
    evaluated_at: str | None = None
    query: dict[str, Any]
    resolution: dict[str, Any] | None = None
    package: dict[str, Any] | None = None
    industry: dict[str, Any] | None = None
    competitors: list[dict[str, Any]] = Field(default_factory=list)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get(
    "/industry/context/snapshot",
    response_model=IndustrySnapshotResponse,
    responses={400: {"description": "Invalid industry or company query"}},
)
def industry_context_snapshot(
    request: Request,
    q: str = Query(default="", max_length=QUERY_MAX_LENGTH),
    country: str | None = Query(default=None, max_length=2),
    exchange: str | None = Query(default=None, max_length=32),
    ticker: str | None = Query(default=None, max_length=32),
) -> IndustrySnapshotResponse | JSONResponse:
    container = _container(request)
    try:
        snapshot_query = IndustrySnapshotQuery(
            company_query=CompanyQuery(
                raw_query=q,
                country=CountryCode(country) if country else None,
                exchange=ExchangeCode(exchange) if exchange else None,
                ticker=TickerSymbol(ticker) if ticker else None,
            )
        )
    except ValueError as exc:
        return build_error_response(
            code="invalid_industry_query",
            message=str(exc),
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.get_industry_snapshot.execute(snapshot_query)
    logger.info(
        "industry_context_snapshot",
        extra={
            "industry_status": result.status.value,
            "provider_name": result.provider_name,
            "data_origin": (
                result.package.data_origin.value if result.package is not None else None
            ),
            "query_length": len(q),
        },
    )
    if result.status is IndustrySnapshotStatus.INVALID:
        return build_error_response(
            code="invalid_industry_query",
            message=result.message or "invalid industry query",
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return IndustrySnapshotResponse.model_validate(result.to_dict())
