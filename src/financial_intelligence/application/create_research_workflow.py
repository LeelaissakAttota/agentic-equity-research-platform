"""CreateResearchWorkflow — Phase 7 foundation (reuses Phase 6 planner)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime

from financial_intelligence.application.approval_policy import DeterministicApprovalPolicy
from financial_intelligence.application.create_research_plan import CreateResearchPlan
from financial_intelligence.application.ports import NotificationPort, ResearchWorkflowStorePort
from financial_intelligence.application.research_plan_contracts import (
    CreateResearchPlanQuery,
    ResearchPlanStatus,
)
from financial_intelligence.application.workflow_contracts import (
    CreateResearchWorkflowQuery,
    PreparedResearchPlan,
    WorkflowOperationResult,
    WorkflowOperationStatus,
)
from financial_intelligence.domain.notification import (
    NotificationEvent,
    NotificationId,
    NotificationType,
)
from financial_intelligence.domain.orchestration import ResearchPlan
from financial_intelligence.domain.workflow import (
    ApprovalStatus,
    ResearchWorkflow,
    WorkflowCompanyQuery,
    WorkflowId,
    WorkflowStatus,
)


class CreateResearchWorkflow:
    """Resolve + Phase 6 plan + persist workflow. Does not execute research."""

    def __init__(
        self,
        create_research_plan: CreateResearchPlan,
        workflow_store: ResearchWorkflowStorePort,
        *,
        approval_policy: DeterministicApprovalPolicy | None = None,
        notifications: NotificationPort | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._create_plan = create_research_plan
        self._store = workflow_store
        self._policy = approval_policy or DeterministicApprovalPolicy()
        self._notifications = notifications
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        query: CreateResearchWorkflowQuery,
        *,
        prepared_plan: PreparedResearchPlan | None = None,
    ) -> WorkflowOperationResult:
        """Resolve + plan + persist a workflow, or use an already-produced plan.

        When ``prepared_plan`` is supplied (by ``ResearchOrchestrator``, once
        ``PlannerPort`` has already returned a plan), that exact ``ResearchPlan`` is
        used and ``CreateResearchPlan``/``DeterministicPlanner`` is never invoked —
        there is no second plan generated. Existing callers that omit
        ``prepared_plan`` keep today's behavior unchanged: this use case builds its
        own plan via ``CreateResearchPlan``.
        """

        now = self._clock()
        if now.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)

        if prepared_plan is not None:
            plan: ResearchPlan = prepared_plan.plan
            request_id = prepared_plan.request.request_id
            resolution = None
        else:
            plan_result = self._create_plan.execute(
                CreateResearchPlanQuery(
                    company_query=query.company_query,
                    objective=query.objective,
                    objective_text=query.objective_text,
                    jurisdiction=query.jurisdiction,
                    time_horizon_days=query.time_horizon_days,
                )
            )
            if plan_result.status is ResearchPlanStatus.INVALID:
                return WorkflowOperationResult(
                    status=WorkflowOperationStatus.INVALID,
                    message=plan_result.message,
                    resolution=plan_result.resolution,
                    evaluated_at=now,
                )
            if plan_result.status is ResearchPlanStatus.RESOLUTION_BLOCKED:
                return WorkflowOperationResult(
                    status=WorkflowOperationStatus.RESOLUTION_BLOCKED,
                    message=plan_result.message,
                    resolution=plan_result.resolution,
                    evaluated_at=now,
                )
            if plan_result.status is not ResearchPlanStatus.OK or plan_result.plan is None:
                return WorkflowOperationResult(
                    status=WorkflowOperationStatus.FAILED,
                    message=plan_result.message or "plan unavailable",
                    resolution=plan_result.resolution,
                    evaluated_at=now,
                )
            assert plan_result.request is not None
            assert plan_result.resolution is not None and plan_result.resolution.company is not None
            plan = plan_result.plan
            request_id = plan_result.request.request_id
            resolution = plan_result.resolution

        requirement = self._policy.evaluate(
            objective=query.objective,
            require_approval=query.require_approval,
        )
        if requirement.required:
            status = WorkflowStatus.AWAITING_APPROVAL
            approval_status = ApprovalStatus.PENDING
        else:
            status = WorkflowStatus.READY
            approval_status = ApprovalStatus.NOT_REQUIRED

        cq = query.company_query
        workflow = ResearchWorkflow(
            workflow_id=WorkflowId.new(),
            research_run_id=plan.research_run_id,
            request_id=request_id,
            company_id=plan.company_id,
            objective=query.objective,
            plan=plan,
            company_query=WorkflowCompanyQuery(
                raw_query=cq.raw_query,
                country=cq.country,
                exchange=cq.exchange,
                ticker=cq.ticker,
            ),
            status=WorkflowStatus.CREATED,
            approval_status=approval_status,
            approval_requirement=requirement,
            created_at=now,
            updated_at=now,
        )
        workflow = workflow.with_status(status, at=now)
        self._store.save_workflow(workflow)
        if status is WorkflowStatus.AWAITING_APPROVAL and self._notifications is not None:
            with suppress(Exception):
                self._notifications.publish(
                    NotificationEvent(
                        notification_id=NotificationId.new(),
                        notification_type=NotificationType.APPROVAL_REQUIRED,
                        created_at=now,
                        workflow_id=workflow.workflow_id,
                        company_id=workflow.company_id.as_text(),
                        message="human approval required before workflow execution",
                        metadata=(("status", workflow.status.value),),
                    )
                )
        return WorkflowOperationResult(
            status=WorkflowOperationStatus.OK,
            message="research workflow created",
            workflow=workflow,
            resolution=resolution,
            evaluated_at=now,
        )
