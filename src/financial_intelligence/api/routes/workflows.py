"""Research workflow HTTP routes (Phase 7 Prompt 1 foundation).

Minimum vertical slice:
- POST   /research/workflows
- GET    /research/workflows/{workflow_id}
- POST   /research/workflows/{workflow_id}/execute
- POST   /research/workflows/{workflow_id}/pause
- POST   /research/workflows/{workflow_id}/resume
- POST   /research/workflows/{workflow_id}/approval

In-memory store only — not durable production persistence.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.workflow_contracts import (
    ApprovalActionQuery,
    CreateResearchWorkflowQuery,
    WorkflowListQuery,
    WorkflowOperationStatus,
)
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.domain.orchestration import ResearchObjective
from financial_intelligence.domain.workflow import ApprovalStatus, WorkflowId, WorkflowStatus
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["research-workflows"])
logger = get_logger("financial_intelligence.api.workflows")


class CreateResearchWorkflowBody(BaseModel):
    """Request body for workflow creation."""

    q: str = Field(default="", max_length=QUERY_MAX_LENGTH)
    objective: str = Field(min_length=1, max_length=64)
    country: str | None = Field(default=None, max_length=2)
    exchange: str | None = Field(default=None, max_length=32)
    ticker: str | None = Field(default=None, max_length=32)
    objective_text: str | None = Field(default=None, max_length=512)
    jurisdiction: str | None = Field(default=None, max_length=2)
    time_horizon_days: int | None = Field(default=None, ge=1, le=3650)
    require_approval: bool = False


class ApprovalBody(BaseModel):
    """Human approval decision body."""

    decision: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=512)
    decision_source: str = Field(default="trusted_api", max_length=64)


class WorkflowResponse(BaseModel):
    status: str
    message: str
    workflow_id: str | None = None
    approval_status: str | None = None
    evaluated_at: str | None = None
    workflow: dict[str, Any] | None = None
    resolution: dict[str, Any] | None = None
    company: dict[str, Any] | None = None
    kind: str | None = None


class WorkflowListResponse(BaseModel):
    status: str
    message: str
    limit: int
    offset: int
    count: int
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    evaluated_at: str | None = None
    kind: str | None = None


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _company_query(body: CreateResearchWorkflowBody) -> CompanyQuery:
    return CompanyQuery(
        raw_query=body.q,
        country=CountryCode(body.country) if body.country else None,
        exchange=ExchangeCode(body.exchange) if body.exchange else None,
        ticker=TickerSymbol(body.ticker) if body.ticker else None,
    )


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "") or "")


def _to_response(
    request: Request,
    result: object,
) -> WorkflowResponse | JSONResponse:
    from financial_intelligence.application.workflow_contracts import WorkflowOperationResult

    assert isinstance(result, WorkflowOperationResult)
    if result.status is WorkflowOperationStatus.INVALID:
        return build_error_response(
            code="invalid_research_workflow_query",
            message=result.message or "invalid research workflow query",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if result.status is WorkflowOperationStatus.NOT_FOUND:
        return build_error_response(
            code="workflow_not_found",
            message=result.message or "workflow not found",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    # Operational outcomes (including approval_required / conflict / rejected / failed)
    # remain structured 200 responses so clients can branch on `status`.
    return WorkflowResponse.model_validate(result.to_dict())


@router.post(
    "/research/workflows",
    response_model=WorkflowResponse,
    responses={400: {"description": "Invalid research workflow request"}},
)
def create_research_workflow(
    request: Request,
    body: CreateResearchWorkflowBody,
) -> WorkflowResponse | JSONResponse:
    """Create a persistent research workflow (plan + initial state). Does not execute."""

    container = _container(request)
    try:
        objective = ResearchObjective(body.objective)
        query = CreateResearchWorkflowQuery(
            company_query=_company_query(body),
            objective=objective,
            objective_text=body.objective_text,
            jurisdiction=body.jurisdiction,
            time_horizon_days=body.time_horizon_days,
            require_approval=body.require_approval,
        )
    except ValueError as exc:
        return build_error_response(
            code="invalid_research_workflow_query",
            message=str(exc),
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = container.create_research_workflow.execute(query)
    logger.info(
        "create_research_workflow",
        extra={
            "workflow_status": result.status.value,
            "objective": body.objective,
            "require_approval": body.require_approval,
            "query_length": len(body.q),
        },
    )
    return _to_response(request, result)


@router.get(
    "/research/workflows",
    response_model=WorkflowListResponse,
)
def list_research_workflows(
    request: Request,
    status_filter: str | None = None,
    company_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowListResponse | JSONResponse:
    """Dashboard-facing bounded workflow listing."""

    container = _container(request)
    try:
        wf_status = WorkflowStatus(status_filter) if status_filter else None
        query = WorkflowListQuery(
            status=wf_status,
            company_id=company_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        return build_error_response(
            code="invalid_workflow_list_query",
            message=str(exc),
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.list(query)
    return WorkflowListResponse.model_validate(result.to_dict())


@router.get(
    "/research/workflows/{workflow_id}",
    response_model=WorkflowResponse,
    responses={404: {"description": "Workflow not found"}},
)
def get_research_workflow(
    request: Request,
    workflow_id: str,
) -> WorkflowResponse | JSONResponse:
    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.get(wid)
    return _to_response(request, result)


@router.post(
    "/research/workflows/{workflow_id}/execute",
    response_model=WorkflowResponse,
    responses={404: {"description": "Workflow not found"}},
)
def execute_research_workflow(
    request: Request,
    workflow_id: str,
) -> WorkflowResponse | JSONResponse:
    """Execute (or continue) a workflow through Phase 6 ExecuteResearchPlan."""

    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.execute(wid)
    logger.info(
        "execute_research_workflow",
        extra={
            "workflow_id": workflow_id,
            "operation_status": result.status.value,
            "workflow_lifecycle": (
                result.workflow.status.value if result.workflow is not None else None
            ),
        },
    )
    return _to_response(request, result)


@router.post(
    "/research/workflows/{workflow_id}/pause",
    response_model=WorkflowResponse,
    responses={404: {"description": "Workflow not found"}},
)
def pause_research_workflow(
    request: Request,
    workflow_id: str,
) -> WorkflowResponse | JSONResponse:
    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.pause(wid)
    return _to_response(request, result)


@router.post(
    "/research/workflows/{workflow_id}/resume",
    response_model=WorkflowResponse,
    responses={404: {"description": "Workflow not found"}},
)
def resume_research_workflow(
    request: Request,
    workflow_id: str,
) -> WorkflowResponse | JSONResponse:
    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.resume(wid)
    return _to_response(request, result)


@router.post(
    "/research/workflows/{workflow_id}/cancel",
    response_model=WorkflowResponse,
    responses={404: {"description": "Workflow not found"}},
)
def cancel_research_workflow(
    request: Request,
    workflow_id: str,
) -> WorkflowResponse | JSONResponse:
    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.cancel(wid)
    return _to_response(request, result)


@router.post(
    "/research/workflows/{workflow_id}/approval",
    response_model=WorkflowResponse,
    responses={
        400: {"description": "Invalid approval decision"},
        404: {"description": "Not found"},
    },
)
def approve_research_workflow(
    request: Request,
    workflow_id: str,
    body: ApprovalBody,
) -> WorkflowResponse | JSONResponse:
    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
        decision = ApprovalStatus(body.decision)
        query = ApprovalActionQuery(
            workflow_id=wid,
            decision=decision,
            note=body.note,
            decision_source=body.decision_source,
        )
    except ValueError as exc:
        return build_error_response(
            code="invalid_approval_decision",
            message=str(exc),
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.manage_research_workflow.approve(query)
    return _to_response(request, result)


@router.get("/research/workflows/{workflow_id}/memory", response_model=None)
def list_workflow_memory(
    request: Request,
    workflow_id: str,
    limit: int = 100,
) -> dict[str, Any] | JSONResponse:
    container = _container(request)
    if limit < 1 or limit > 200:
        return build_error_response(
            code="invalid_memory_list_query",
            message="limit must be between 1 and 200",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    records = container.research_memory.list_for_workflow(wid, limit=limit)
    return {
        "status": "ok",
        "count": len(records),
        "records": [r.to_dict() for r in records],
        "kind": "research_memory_list",
    }


@router.post("/research/workflows/{workflow_id}/report", response_model=None)
def request_workflow_report(
    request: Request,
    workflow_id: str,
) -> dict[str, Any] | JSONResponse:
    container = _container(request)
    try:
        wid = WorkflowId.from_string(workflow_id)
    except ValueError:
        return build_error_response(
            code="invalid_workflow_id",
            message="workflow_id must be a UUIDv4",
            correlation_id=_correlation_id(request),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.request_research_report.execute(wid)
    return result.to_dict()
