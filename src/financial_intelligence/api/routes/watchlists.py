"""Watchlist HTTP routes (Phase 7 Prompt 2 foundation)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.manage_watchlist import (
    CreateWatchlistQuery,
    WatchlistEntryInput,
    WatchlistOperationStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.watchlist import WatchlistId

router = APIRouter(tags=["watchlists"])


class WatchlistEntryBody(BaseModel):
    q: str = Field(min_length=1, max_length=200)
    exchange: str | None = Field(default=None, max_length=32)


class CreateWatchlistBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    entries: list[WatchlistEntryBody] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=lambda: ["market"])
    interval_hours: int = Field(default=24, ge=1, le=720)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "") or "")


@router.post("/watchlists", response_model=None)
def create_watchlist(request: Request, body: CreateWatchlistBody) -> dict[str, Any] | JSONResponse:
    container = _container(request)
    result = container.manage_watchlist.create(
        CreateWatchlistQuery(
            name=body.name,
            entries=tuple(WatchlistEntryInput(q=e.q, exchange=e.exchange) for e in body.entries),
            capabilities=tuple(body.capabilities),
            interval_hours=body.interval_hours,
        )
    )
    if result.status is WatchlistOperationStatus.INVALID:
        return build_error_response(
            code="invalid_watchlist",
            message=result.message,
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return result.to_dict()


@router.get("/watchlists/{watchlist_id}", response_model=None)
def get_watchlist(request: Request, watchlist_id: str) -> dict[str, Any] | JSONResponse:
    container = _container(request)
    try:
        wid = WatchlistId.from_string(watchlist_id)
    except ValueError:
        return build_error_response(
            code="invalid_watchlist_id",
            message="watchlist_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_watchlist.get(wid)
    if result.status is WatchlistOperationStatus.NOT_FOUND:
        return build_error_response(
            code="watchlist_not_found",
            message=result.message,
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return result.to_dict()


@router.post("/watchlists/{watchlist_id}/checks", response_model=None)
def evaluate_watchlist(request: Request, watchlist_id: str) -> dict[str, Any] | JSONResponse:
    """Explicit one-shot monitoring check (no background scheduler)."""

    container = _container(request)
    try:
        wid = WatchlistId.from_string(watchlist_id)
    except ValueError:
        return build_error_response(
            code="invalid_watchlist_id",
            message="watchlist_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_watchlist.evaluate(wid)
    if result.status is WatchlistOperationStatus.NOT_FOUND:
        return build_error_response(
            code="watchlist_not_found",
            message=result.message,
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return result.to_dict()
