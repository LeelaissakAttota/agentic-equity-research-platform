"""Market snapshot HTTP routes (Phase 3 Market Intelligence).

HTTP semantics:

- OK / UNAVAILABLE / DEGRADED / PARTIAL / RESOLUTION_BLOCKED → ``200``
- INVALID company/market query → ``400`` with stable error envelope
- Framework parameter validation → ``422``

Ambiguity and missing market data are successful protocol outcomes carrying
status, not fabricated success payloads.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.market_contracts import (
    MarketSnapshotQuery,
    MarketSnapshotStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["market"])
logger = get_logger("financial_intelligence.api.market")


class MarketSnapshotResponse(BaseModel):
    """Structured market-snapshot response contract."""

    status: str
    message: str
    freshness: str
    provider_name: str | None = None
    data_origin: str | None = None
    evaluated_at: str | None = None
    query: dict[str, Any]
    resolution: dict[str, Any] | None = None
    listing: dict[str, Any] | None = None
    series: dict[str, Any] | None = None
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    source: dict[str, Any] | None = None


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get(
    "/market/snapshot",
    response_model=MarketSnapshotResponse,
    responses={
        400: {"description": "Invalid market or company query"},
    },
)
def market_snapshot(
    request: Request,
    q: str = Query(default="", max_length=QUERY_MAX_LENGTH),
    country: str | None = Query(default=None, max_length=2),
    exchange: str | None = Query(default=None, max_length=32),
    ticker: str | None = Query(default=None, max_length=32),
    listing_id: str | None = Query(default=None, max_length=36),
    sma_window: int = Query(default=3, ge=1, le=60),
) -> MarketSnapshotResponse | JSONResponse:
    """Return a traceable market snapshot for a safely resolved listing."""

    container = _container(request)
    try:
        country_code = CountryCode(country) if country else None
        exchange_code = ExchangeCode(exchange) if exchange else None
        ticker_symbol = TickerSymbol(ticker) if ticker else None
        snapshot_query = MarketSnapshotQuery(
            company_query=CompanyQuery(
                raw_query=q,
                country=country_code,
                exchange=exchange_code,
                ticker=ticker_symbol,
            ),
            listing_id=listing_id,
            sma_window=sma_window,
        )
    except ValueError as exc:
        logger.info(
            "market_snapshot",
            extra={
                "market_status": MarketSnapshotStatus.INVALID.value,
                "query_length": len(q),
            },
        )
        return build_error_response(
            code="invalid_market_query",
            message=str(exc),
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.get_market_snapshot.execute(snapshot_query)
    logger.info(
        "market_snapshot",
        extra={
            "market_status": result.status.value,
            "freshness": result.freshness.value,
            "provider_name": result.provider_name,
            "data_origin": (result.series.data_origin.value if result.series is not None else None),
            "metric_count": len(result.metrics),
            "listing_id": result.listing.listing_id.as_text() if result.listing else None,
            "company_id": (
                result.resolution.company.company_id.as_text()
                if result.resolution and result.resolution.company
                else None
            ),
            "query_length": len(q),
        },
    )

    if result.status is MarketSnapshotStatus.INVALID:
        return build_error_response(
            code="invalid_market_query",
            message=result.message or "invalid market query",
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return MarketSnapshotResponse.model_validate(result.to_dict())
