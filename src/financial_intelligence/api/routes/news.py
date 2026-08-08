"""News/event snapshot HTTP routes (Phase 5 News & Event Intelligence).

HTTP semantics:

- OK / UNAVAILABLE / DEGRADED / PARTIAL / RESOLUTION_BLOCKED → ``200``
- INVALID company/news query → ``400`` with stable error envelope
- Framework parameter validation → ``422``

Ambiguity and missing news/event data are successful protocol outcomes carrying
status, not fabricated success payloads.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.news_event_contracts import (
    NewsEventSnapshotQuery,
    NewsEventSnapshotStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.domain.news import EventType
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["news"])
logger = get_logger("financial_intelligence.api.news")


class NewsEventSnapshotResponse(BaseModel):
    """Structured news/event-snapshot response contract."""

    status: str
    message: str
    provider_name: str | None = None
    data_origin: str | None = None
    evaluated_at: str | None = None
    query: dict[str, Any]
    resolution: dict[str, Any] | None = None
    package: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get(
    "/news/events/snapshot",
    response_model=NewsEventSnapshotResponse,
    responses={
        400: {"description": "Invalid news/event or company query"},
    },
)
def news_events_snapshot(
    request: Request,
    q: str = Query(default="", max_length=QUERY_MAX_LENGTH),
    country: str | None = Query(default=None, max_length=2),
    exchange: str | None = Query(default=None, max_length=32),
    ticker: str | None = Query(default=None, max_length=32),
    event_type: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
) -> NewsEventSnapshotResponse | JSONResponse:
    """Return traceable news/events for a safely resolved company."""

    container = _container(request)
    try:
        country_code = CountryCode(country) if country else None
        exchange_code = ExchangeCode(exchange) if exchange else None
        ticker_symbol = TickerSymbol(ticker) if ticker else None
        typed_event = EventType(event_type) if event_type else None
        snapshot_query = NewsEventSnapshotQuery(
            company_query=CompanyQuery(
                raw_query=q,
                country=country_code,
                exchange=exchange_code,
                ticker=ticker_symbol,
            ),
            event_type=typed_event,
            limit=limit,
        )
    except ValueError as exc:
        logger.info(
            "news_events_snapshot",
            extra={
                "news_status": NewsEventSnapshotStatus.INVALID.value,
                "query_length": len(q),
            },
        )
        return build_error_response(
            code="invalid_news_event_query",
            message=str(exc),
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.get_news_event_snapshot.execute(snapshot_query)
    logger.info(
        "news_events_snapshot",
        extra={
            "news_status": result.status.value,
            "provider_name": result.provider_name,
            "data_origin": (
                result.package.data_origin.value if result.package is not None else None
            ),
            "event_count": len(result.package.events) if result.package is not None else 0,
            "company_id": (
                result.resolution.company.company_id.as_text()
                if result.resolution and result.resolution.company
                else None
            ),
            "query_length": len(q),
        },
    )

    if result.status is NewsEventSnapshotStatus.INVALID:
        return build_error_response(
            code="invalid_news_event_query",
            message=result.message or "invalid news/event query",
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return NewsEventSnapshotResponse.model_validate(result.to_dict())
