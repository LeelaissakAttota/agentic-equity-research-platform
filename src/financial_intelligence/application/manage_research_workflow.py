"""Execute / pause / resume / approve / cancel / list research workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.execute_research_plan import ExecuteResearchPlan
from financial_intelligence.application.ports import (
    NotificationPort,
    ResearchMemoryPort,
    ResearchWorkflowStorePort,
)
from financial_intelligence.application.research_execution_contracts import (
    ExecuteResearchPlanQuery,
    ResearchExecutionResult,
    ResearchExecutionStatus,
)
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.application.workflow_contracts import (
    ApprovalActionQuery,
    WorkflowListQuery,
    WorkflowListResult,
    WorkflowOperationResult,
    WorkflowOperationStatus,
)
from financial_intelligence.domain.memory import (
    MemoryRecordId,
    MemoryRecordStatus,
    ResearchMemoryRecord,
)
from financial_intelligence.domain.notification import (
    NotificationEvent,
    NotificationId,
    NotificationType,
)
from financial_intelligence.domain.orchestration import ExecutionControl, TaskStatus
from financial_intelligence.domain.workflow import (
    ApprovalDecision,
    ApprovalStatus,
    ResearchWorkflow,
    WorkflowCheckpoint,
    WorkflowId,
    WorkflowStatus,
    is_terminal,
)


class ManageResearchWorkflow:
    """Coordinate Phase 6 execution through a persisted workflow aggregate."""

    def __init__(
        self,
        workflow_store: ResearchWorkflowStorePort,
        execute_research_plan: ExecuteResearchPlan,
        resolve_company: ResolveCompany,
        *,
        research_memory: ResearchMemoryPort | None = None,
        notifications: NotificationPort | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = workflow_store
        self._execute = execute_research_plan
        self._resolve = resolve_company
        self._memory = research_memory
        self._notifications = notifications
        self._clock = clock or (lambda: datetime.now(UTC))

    def get(self, workflow_id: WorkflowId) -> WorkflowOperationResult:
        now = self._clock()
        workflow = self._store.get_workflow(workflow_id)
        if workflow is None:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        return WorkflowOperationResult(
            status=WorkflowOperationStatus.OK,
            message="workflow loaded",
            workflow=workflow,
            evaluated_at=now,
        )

    def list(self, query: WorkflowListQuery) -> WorkflowListResult:
        now = self._clock()
        workflows = self._store.list_workflows(
            status=query.status,
            company_id_text=query.company_id,
            limit=query.limit,
            offset=query.offset,
        )
        return WorkflowListResult(
            status=WorkflowOperationStatus.OK,
            message="workflow list",
            workflows=workflows,
            limit=query.limit,
            offset=query.offset,
            evaluated_at=now,
        )

    def execute(
        self,
        workflow_id: WorkflowId,
        *,
        control: ExecutionControl | None = None,
    ) -> WorkflowOperationResult:
        now = self._clock()
        workflow = self._store.get_workflow(workflow_id)
        if workflow is None:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        if is_terminal(workflow.status):
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=f"cannot execute terminal workflow status={workflow.status.value}",
                workflow=workflow,
                evaluated_at=now,
            )
        if workflow.approval_status is ApprovalStatus.PENDING:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.APPROVAL_REQUIRED,
                message="human approval required before execution",
                workflow=workflow,
                evaluated_at=now,
            )
        if workflow.approval_status is ApprovalStatus.REJECTED:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.REJECTED,
                message="workflow approval was rejected",
                workflow=workflow,
                evaluated_at=now,
            )
        if workflow.status not in {
            WorkflowStatus.READY,
            WorkflowStatus.PAUSED,
            WorkflowStatus.RUNNING,
        }:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=f"invalid status for execution: {workflow.status.value}",
                workflow=workflow,
                evaluated_at=now,
            )

        try:
            running = workflow.with_status(WorkflowStatus.RUNNING, at=now)
        except ValueError as exc:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=str(exc),
                workflow=workflow,
                evaluated_at=now,
            )
        self._store.save_workflow(running)

        company_query = CompanyQuery(
            raw_query=running.company_query.raw_query,
            country=running.company_query.country,
            exchange=running.company_query.exchange,
            ticker=running.company_query.ticker,
        )
        resolution = self._resolve.execute(company_query)
        if resolution.company is None or resolution.company.company_id != running.company_id:
            failed = running.with_status(WorkflowStatus.FAILED, at=self._clock())
            failed = replace(failed, execution_message="company identity mismatch on execute")
            self._store.save_workflow(failed)
            self._notify(
                NotificationType.WORKFLOW_FAILED,
                failed,
                message="company identity mismatch on execute",
            )
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.FAILED,
                message="company identity mismatch on execute",
                workflow=failed,
                resolution=resolution,
                evaluated_at=self._clock(),
            )

        control = control or ExecutionControl()
        prior = running.latest_checkpoint
        exec_result = self._execute.execute_prepared(
            running.plan,
            company=resolution.company,
            company_query=company_query,
            resolution=resolution,
            query=ExecuteResearchPlanQuery(
                company_query=company_query,
                objective=running.objective,
            ),
            control=control,
            started_at=now,
            initial_total_attempts=prior.total_attempts if prior else 0,
            initial_external_calls=prior.external_calls if prior else 0,
            initial_results=prior.task_results if prior else (),
            initial_warnings=prior.warnings if prior else (),
        )
        return self._apply_execution_result(running, exec_result, pause_requested=control.is_pause)

    def pause(self, workflow_id: WorkflowId) -> WorkflowOperationResult:
        now = self._clock()
        workflow = self._store.get_workflow(workflow_id)
        if workflow is None:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        if workflow.status is WorkflowStatus.PAUSED:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.OK,
                message="workflow already paused",
                workflow=workflow,
                evaluated_at=now,
            )
        if workflow.status is not WorkflowStatus.RUNNING:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=f"cannot pause workflow status={workflow.status.value}",
                workflow=workflow,
                evaluated_at=now,
            )
        checkpoint = self._build_checkpoint(workflow, at=now, message="manual pause checkpoint")
        paused = workflow.with_checkpoint(checkpoint, at=now).with_status(
            WorkflowStatus.PAUSED, at=now
        )
        self._store.save_checkpoint(checkpoint)
        self._store.save_workflow(paused)
        return WorkflowOperationResult(
            status=WorkflowOperationStatus.OK,
            message="workflow paused",
            workflow=paused,
            evaluated_at=now,
        )

    def resume(self, workflow_id: WorkflowId) -> WorkflowOperationResult:
        now = self._clock()
        workflow = self._store.get_workflow(workflow_id)
        if workflow is None:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        if workflow.status is not WorkflowStatus.PAUSED:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=f"cannot resume workflow status={workflow.status.value}",
                workflow=workflow,
                evaluated_at=now,
            )
        if workflow.approval_status is ApprovalStatus.PENDING:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.APPROVAL_REQUIRED,
                message="human approval required before resume",
                workflow=workflow,
                evaluated_at=now,
            )
        ready = workflow.with_status(WorkflowStatus.READY, at=now)
        self._store.save_workflow(ready)
        return self.execute(workflow_id)

    def cancel(self, workflow_id: WorkflowId) -> WorkflowOperationResult:
        """Terminal cancel — distinct from soft pause; not resumable."""

        now = self._clock()
        workflow = self._store.get_workflow(workflow_id)
        if workflow is None:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        if is_terminal(workflow.status):
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=f"cannot cancel terminal workflow status={workflow.status.value}",
                workflow=workflow,
                evaluated_at=now,
            )
        try:
            cancelled = workflow.with_status(WorkflowStatus.CANCELLED, at=now)
        except ValueError as exc:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=str(exc),
                workflow=workflow,
                evaluated_at=now,
            )
        cancelled = replace(cancelled, execution_message="workflow cancelled by trusted API")
        self._store.save_workflow(cancelled)
        self._notify(
            NotificationType.WORKFLOW_CANCELLED,
            cancelled,
            message="workflow cancelled",
        )
        return WorkflowOperationResult(
            status=WorkflowOperationStatus.OK,
            message="workflow cancelled",
            workflow=cancelled,
            evaluated_at=now,
        )

    def approve(self, query: ApprovalActionQuery) -> WorkflowOperationResult:
        now = self._clock()
        workflow = self._store.get_workflow(query.workflow_id)
        if workflow is None:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        if workflow.status is not WorkflowStatus.AWAITING_APPROVAL:
            return WorkflowOperationResult(
                status=WorkflowOperationStatus.CONFLICT,
                message=f"workflow not awaiting approval status={workflow.status.value}",
                workflow=workflow,
                evaluated_at=now,
            )
        decision = ApprovalDecision(
            status=query.decision,
            decided_at=now,
            note=query.note,
            decision_source=query.decision_source,
        )
        if query.decision is ApprovalStatus.APPROVED:
            updated = workflow.with_approval(decision, at=now, next_status=WorkflowStatus.READY)
            message = "workflow approved"
            op = WorkflowOperationStatus.OK
        else:
            updated = workflow.with_approval(decision, at=now, next_status=WorkflowStatus.FAILED)
            updated = replace(updated, execution_message="approval rejected")
            message = "workflow approval rejected"
            op = WorkflowOperationStatus.REJECTED
        self._store.save_workflow(updated)
        return WorkflowOperationResult(
            status=op,
            message=message,
            workflow=updated,
            evaluated_at=now,
        )

    def _apply_execution_result(
        self,
        workflow: ResearchWorkflow,
        exec_result: object,
        *,
        pause_requested: bool,
    ) -> WorkflowOperationResult:
        now = self._clock()
        assert isinstance(exec_result, ResearchExecutionResult)
        plan = exec_result.plan if exec_result.plan is not None else workflow.plan
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow.workflow_id,
            research_run_id=workflow.research_run_id,
            version=workflow.checkpoint_version + 1,
            plan=plan,
            created_at=now,
            total_attempts=(
                exec_result.orchestration.total_attempts
                if exec_result.orchestration is not None
                else 0
            ),
            external_calls=(
                exec_result.orchestration.external_calls
                if exec_result.orchestration is not None
                else 0
            ),
            warnings=exec_result.warnings,
            task_results=exec_result.task_results,
            evidence_refs=exec_result.evidence_refs,
            message=exec_result.message,
        )
        updated = workflow.with_checkpoint(checkpoint, at=now)
        notify_type: NotificationType | None = None
        if pause_requested:
            terminal = WorkflowStatus.PAUSED
            op = WorkflowOperationStatus.OK
            message = "workflow paused with checkpoint"
        elif exec_result.status is ResearchExecutionStatus.CANCELLED:
            terminal = WorkflowStatus.CANCELLED
            op = WorkflowOperationStatus.OK
            message = "workflow cancelled"
            notify_type = NotificationType.WORKFLOW_CANCELLED
        elif exec_result.status is ResearchExecutionStatus.COMPLETED:
            terminal = WorkflowStatus.COMPLETED
            op = WorkflowOperationStatus.OK
            message = "workflow completed"
            notify_type = NotificationType.WORKFLOW_COMPLETED
        elif exec_result.status is ResearchExecutionStatus.PARTIAL:
            terminal = WorkflowStatus.PARTIAL
            op = WorkflowOperationStatus.OK
            message = "workflow completed with partial results"
            notify_type = NotificationType.WORKFLOW_PARTIAL
        elif exec_result.status is ResearchExecutionStatus.BUDGET_EXCEEDED:
            terminal = WorkflowStatus.FAILED
            op = WorkflowOperationStatus.FAILED
            message = "workflow failed: budget exceeded"
            notify_type = NotificationType.WORKFLOW_FAILED
        else:
            terminal = WorkflowStatus.FAILED
            op = WorkflowOperationStatus.FAILED
            message = f"workflow failed: {exec_result.status.value}"
            notify_type = NotificationType.WORKFLOW_FAILED

        warnings = list(exec_result.warnings)
        memory_warning = self._persist_memory(updated, plan=plan, at=now)
        if memory_warning is not None:
            warnings.append(memory_warning)

        updated = replace(
            updated,
            completed_count=exec_result.completed_count,
            failed_count=exec_result.failed_count,
            blocked_count=exec_result.blocked_count,
            partial_count=exec_result.partial_count,
            evidence_count=len(exec_result.evidence_refs),
            execution_message=exec_result.message,
            warnings=tuple(warnings),
        )
        updated = updated.with_status(terminal, at=now)
        self._store.save_checkpoint(checkpoint)
        self._store.save_workflow(updated)
        if notify_type is not None:
            notify_warning = self._notify(notify_type, updated, message=message)
            if notify_warning is not None:
                updated = replace(updated, warnings=(*updated.warnings, notify_warning))
                self._store.save_workflow(updated)
        return WorkflowOperationResult(
            status=op,
            message=message,
            workflow=updated,
            evaluated_at=now,
        )

    def _persist_memory(
        self, workflow: ResearchWorkflow, *, plan: object, at: datetime
    ) -> str | None:
        if self._memory is None:
            return None
        from financial_intelligence.domain.orchestration import ResearchPlan

        assert isinstance(plan, ResearchPlan)
        try:
            for task in plan.tasks:
                if task.status not in {
                    TaskStatus.SUCCEEDED,
                    TaskStatus.FAILED,
                    TaskStatus.SKIPPED,
                    TaskStatus.BLOCKED,
                }:
                    continue
                status_map = {
                    TaskStatus.SUCCEEDED: MemoryRecordStatus.SUCCEEDED,
                    TaskStatus.FAILED: MemoryRecordStatus.FAILED,
                    TaskStatus.SKIPPED: MemoryRecordStatus.SKIPPED,
                    TaskStatus.BLOCKED: MemoryRecordStatus.FAILED,
                }
                refs = tuple(
                    r
                    for r in (
                        workflow.latest_checkpoint.evidence_refs
                        if workflow.latest_checkpoint
                        else ()
                    )
                    if r.company_id == workflow.company_id
                )
                origin = refs[0].data_origin if refs else None
                record = ResearchMemoryRecord(
                    record_id=MemoryRecordId.new(),
                    workflow_id=workflow.workflow_id,
                    research_run_id=workflow.research_run_id,
                    company_id=workflow.company_id,
                    capability=task.capability_id,
                    task_id=task.task_id,
                    status=status_map[task.status],
                    summary=task.description[:1000] if task.description else task.capability_id,
                    created_at=at,
                    evidence_refs=refs,
                    data_origin=origin,
                )
                try:
                    self._memory.append(record)
                except ValueError:
                    # Duplicate task completion on resume is expected; skip.
                    continue
        except Exception as exc:
            return f"research_memory_write_failed:{type(exc).__name__}"
        return None

    def _notify(
        self,
        notification_type: NotificationType,
        workflow: ResearchWorkflow,
        *,
        message: str,
    ) -> str | None:
        if self._notifications is None:
            return None
        event = NotificationEvent(
            notification_id=NotificationId.new(),
            notification_type=notification_type,
            created_at=self._clock(),
            workflow_id=workflow.workflow_id,
            company_id=workflow.company_id.as_text(),
            message=message,
            metadata=(
                ("status", workflow.status.value),
                ("approval_status", workflow.approval_status.value),
            ),
        )
        try:
            self._notifications.publish(event)
        except Exception as exc:
            return f"notification_failed:{type(exc).__name__}"
        return None

    def _build_checkpoint(
        self, workflow: ResearchWorkflow, *, at: datetime, message: str
    ) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            workflow_id=workflow.workflow_id,
            research_run_id=workflow.research_run_id,
            version=workflow.checkpoint_version + 1,
            plan=workflow.plan,
            created_at=at,
            total_attempts=(
                workflow.latest_checkpoint.total_attempts if workflow.latest_checkpoint else 0
            ),
            external_calls=(
                workflow.latest_checkpoint.external_calls if workflow.latest_checkpoint else 0
            ),
            warnings=workflow.warnings,
            task_results=(
                workflow.latest_checkpoint.task_results if workflow.latest_checkpoint else ()
            ),
            evidence_refs=(
                workflow.latest_checkpoint.evidence_refs if workflow.latest_checkpoint else ()
            ),
            message=message,
        )
