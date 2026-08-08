"""Research planning and execution HTTP routes (Phase 6).

POST /research/plans — create a deterministic plan (does not execute).
POST /research/execute — create-and-execute a plan synchronously within budget.

Plans are not persisted. There is no plan-id lookup endpoint.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.research_execution_contracts import (
    ExecuteResearchPlanQuery,
    ResearchExecutionStatus,
)
from financial_intelligence.application.research_plan_contracts import (
    CreateResearchPlanQuery,
    ResearchPlanStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.domain.orchestration import ResearchExecutionBudget, ResearchObjective
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["research"])
logger = get_logger("financial_intelligence.api.research")


class CreateResearchPlanBody(BaseModel):
    """Request body for plan creation."""

    q: str = Field(default="", max_length=QUERY_MAX_LENGTH)
    objective: str = Field(min_length=1, max_length=64)
    country: str | None = Field(default=None, max_length=2)
    exchange: str | None = Field(default=None, max_length=32)
    ticker: str | None = Field(default=None, max_length=32)
    objective_text: str | None = Field(default=None, max_length=512)
    jurisdiction: str | None = Field(default=None, max_length=2)
    time_horizon_days: int | None = Field(default=None, ge=1, le=3650)


class ExecuteResearchPlanBody(CreateResearchPlanBody):
    """Create-and-execute body with optional budget overrides."""

    max_tasks: int | None = Field(default=None, ge=1, le=100)
    max_attempts_per_task: int | None = Field(default=None, ge=1, le=10)
    max_total_attempts: int | None = Field(default=None, ge=1, le=500)
    max_plan_depth: int | None = Field(default=None, ge=1, le=50)
    max_external_calls: int | None = Field(default=None, ge=1, le=500)


class ResearchPlanResponse(BaseModel):
    status: str
    message: str
    research_run_id: str | None = None
    plan_id: str | None = None
    planner_version: str | None = None
    objective: str
    evaluated_at: str | None = None
    query: dict[str, Any]
    resolution: dict[str, Any] | None = None
    company: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] | None = None
    request: dict[str, Any] | None = None


class ResearchExecutionResponse(BaseModel):
    status: str
    message: str
    research_run_id: str | None = None
    plan_id: str | None = None
    objective: str
    completed_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    partial_count: int = 0
    skipped_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    task_results: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    query: dict[str, Any]
    plan: dict[str, Any] | None = None
    orchestration: dict[str, Any] | None = None
    resolution: dict[str, Any] | None = None
    company: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None
    idempotency_note: str | None = None
    kind: str | None = None


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _company_query(body: CreateResearchPlanBody) -> CompanyQuery:
    return CompanyQuery(
        raw_query=body.q,
        country=CountryCode(body.country) if body.country else None,
        exchange=ExchangeCode(body.exchange) if body.exchange else None,
        ticker=TickerSymbol(body.ticker) if body.ticker else None,
    )


def _budget_from_body(body: ExecuteResearchPlanBody) -> ResearchExecutionBudget | None:
    overrides = {
        "max_tasks": body.max_tasks,
        "max_attempts_per_task": body.max_attempts_per_task,
        "max_total_attempts": body.max_total_attempts,
        "max_plan_depth": body.max_plan_depth,
        "max_external_calls": body.max_external_calls,
    }
    if all(v is None for v in overrides.values()):
        return None
    base = ResearchExecutionBudget()
    return ResearchExecutionBudget(
        max_tasks=body.max_tasks if body.max_tasks is not None else base.max_tasks,
        max_attempts_per_task=(
            body.max_attempts_per_task
            if body.max_attempts_per_task is not None
            else base.max_attempts_per_task
        ),
        max_total_attempts=(
            body.max_total_attempts
            if body.max_total_attempts is not None
            else base.max_total_attempts
        ),
        max_plan_depth=(
            body.max_plan_depth if body.max_plan_depth is not None else base.max_plan_depth
        ),
        max_external_calls=(
            body.max_external_calls
            if body.max_external_calls is not None
            else base.max_external_calls
        ),
    )


@router.post(
    "/research/plans",
    response_model=ResearchPlanResponse,
    responses={400: {"description": "Invalid research plan request"}},
)
def create_research_plan(
    request: Request,
    body: CreateResearchPlanBody,
) -> ResearchPlanResponse | JSONResponse:
    """Create a deterministic research plan for a uniquely resolved company."""

    container = _container(request)
    try:
        objective = ResearchObjective(body.objective)
        snapshot_query = CreateResearchPlanQuery(
            company_query=_company_query(body),
            objective=objective,
            objective_text=body.objective_text,
            jurisdiction=body.jurisdiction,
            time_horizon_days=body.time_horizon_days,
        )
    except ValueError as exc:
        return build_error_response(
            code="invalid_research_plan_query",
            message=str(exc),
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.create_research_plan.execute(snapshot_query)
    logger.info(
        "create_research_plan",
        extra={
            "plan_status": result.status.value,
            "objective": body.objective,
            "task_count": len(result.plan.tasks) if result.plan is not None else 0,
            "query_length": len(body.q),
        },
    )
    if result.status is ResearchPlanStatus.INVALID:
        return build_error_response(
            code="invalid_research_plan_query",
            message=result.message or "invalid research plan query",
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return ResearchPlanResponse.model_validate(result.to_dict())


@router.post(
    "/research/execute",
    response_model=ResearchExecutionResponse,
    responses={400: {"description": "Invalid research execution request"}},
)
def execute_research_plan(
    request: Request,
    body: ExecuteResearchPlanBody,
) -> ResearchExecutionResponse | JSONResponse:
    """Create a deterministic plan and execute it synchronously within budget.

    Plans are not persisted. Each request builds a fresh plan and runs it.
    """

    container = _container(request)
    try:
        objective = ResearchObjective(body.objective)
        budget = _budget_from_body(body)
        exec_query = ExecuteResearchPlanQuery(
            company_query=_company_query(body),
            objective=objective,
            objective_text=body.objective_text,
            jurisdiction=body.jurisdiction,
            time_horizon_days=body.time_horizon_days,
            budget=budget,
        )
    except ValueError as exc:
        return build_error_response(
            code="invalid_research_execution_query",
            message=str(exc),
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.execute_research_plan.execute(exec_query)
    logger.info(
        "execute_research_plan",
        extra={
            "execution_status": result.status.value,
            "objective": body.objective,
            "completed_count": result.completed_count,
            "failed_count": result.failed_count,
            "query_length": len(body.q),
        },
    )
    if result.status is ResearchExecutionStatus.INVALID:
        return build_error_response(
            code="invalid_research_execution_query",
            message=result.message or "invalid research execution query",
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return ResearchExecutionResponse.model_validate(result.to_dict())
