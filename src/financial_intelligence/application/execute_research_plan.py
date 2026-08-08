"""ExecuteResearchPlan — bounded synchronous plan execution (Phase 6 Prompt 2)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from financial_intelligence.application.create_research_plan import CreateResearchPlan
from financial_intelligence.application.ports import ResearchCapabilityExecutorPort
from financial_intelligence.application.research_execution_contracts import (
    ExecuteResearchPlanQuery,
    ResearchExecutionResult,
    ResearchExecutionStatus,
)
from financial_intelligence.application.research_plan_contracts import ResearchPlanStatus
from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.orchestration import (
    ExecutionControl,
    OrchestrationState,
    OrchestrationStatus,
    PlanStatus,
    ResearchExecutionBudget,
    ResearchPlan,
    ResearchTask,
    RetryPolicy,
    TaskExecutionResult,
    TaskResultStatus,
    TaskStatus,
    apply_failure_propagation,
    dedupe_evidence_refs,
    select_next_ready_task,
)


def _result_to_task_status(result: TaskExecutionResult) -> TaskStatus:
    """Map capability outcome to task lifecycle state.

    PARTIAL maps to SUCCEEDED so dependents may proceed; the PARTIAL outcome
    remains visible on TaskExecutionResult and elevates run status to PARTIAL.
    """

    if result.status is TaskResultStatus.SUCCESS:
        return TaskStatus.SUCCEEDED
    if result.status is TaskResultStatus.PARTIAL:
        return TaskStatus.SUCCEEDED
    if result.status is TaskResultStatus.BLOCKED:
        return TaskStatus.BLOCKED
    if result.status is TaskResultStatus.UNAVAILABLE:
        return TaskStatus.FAILED
    return TaskStatus.FAILED


class ExecuteResearchPlan:
    """Validate plan → execute one ready task at a time → terminate deterministically.

    No autonomous unbounded loops. No LLM. Plans are not persisted; each call
    creates and executes a fresh plan (create-and-execute semantics).
    """

    def __init__(
        self,
        create_research_plan: CreateResearchPlan,
        capability_executor: ResearchCapabilityExecutorPort,
        *,
        budget: ResearchExecutionBudget | None = None,
        retry_policy: RetryPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._create_plan = create_research_plan
        self._executor = capability_executor
        self._budget = budget or ResearchExecutionBudget()
        self._retry = retry_policy or RetryPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        query: ExecuteResearchPlanQuery,
        *,
        control: ExecutionControl | None = None,
    ) -> ResearchExecutionResult:
        started_at = self._clock()
        if started_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        control = control or ExecutionControl()
        budget = query.budget or self._budget

        plan_result = self._create_plan.execute(query.as_plan_query())
        if plan_result.status is ResearchPlanStatus.INVALID:
            return ResearchExecutionResult(
                query=query,
                status=ResearchExecutionStatus.INVALID,
                message=plan_result.message,
                resolution=plan_result.resolution,
                budget=budget,
                started_at=started_at,
                completed_at=self._clock(),
            )
        if plan_result.status is ResearchPlanStatus.RESOLUTION_BLOCKED:
            return ResearchExecutionResult(
                query=query,
                status=ResearchExecutionStatus.RESOLUTION_BLOCKED,
                message=plan_result.message,
                resolution=plan_result.resolution,
                budget=budget,
                started_at=started_at,
                completed_at=self._clock(),
            )
        if plan_result.status is ResearchPlanStatus.BUDGET_EXCEEDED:
            return ResearchExecutionResult(
                query=query,
                status=ResearchExecutionStatus.BUDGET_EXCEEDED,
                message=plan_result.message,
                resolution=plan_result.resolution,
                budget=budget,
                started_at=started_at,
                completed_at=self._clock(),
            )
        if plan_result.status is not ResearchPlanStatus.OK or plan_result.plan is None:
            return ResearchExecutionResult(
                query=query,
                status=ResearchExecutionStatus.UNAVAILABLE,
                message=plan_result.message or "plan unavailable",
                resolution=plan_result.resolution,
                budget=budget,
                started_at=started_at,
                completed_at=self._clock(),
            )

        assert plan_result.resolution is not None and plan_result.resolution.company is not None
        company: CompanyIdentity = plan_result.resolution.company
        plan = plan_result.plan
        return self.execute_prepared(
            plan,
            company=company,
            company_query=query.company_query,
            resolution=plan_result.resolution,
            query=query,
            budget=budget,
            control=control,
            started_at=started_at,
        )

    def execute_prepared(
        self,
        plan: ResearchPlan,
        *,
        company: CompanyIdentity,
        company_query: object,
        resolution: object,
        query: ExecuteResearchPlanQuery,
        budget: ResearchExecutionBudget | None = None,
        control: ExecutionControl | None = None,
        started_at: datetime | None = None,
    ) -> ResearchExecutionResult:
        """Execute an already-built plan (tests / advanced callers). Plans are not stored."""

        from financial_intelligence.application.company_resolution import CompanyQuery
        from financial_intelligence.application.company_resolution import (
            ResolutionResult as ResolutionResultType,
        )

        if not isinstance(company_query, CompanyQuery):
            msg = "company_query must be CompanyQuery"
            raise TypeError(msg)
        started_at = started_at or self._clock()
        if started_at.tzinfo is None:
            msg = "clock must return timezone-aware datetime"
            raise ValueError(msg)
        control = control or ExecutionControl()
        budget = budget or self._budget
        if company.company_id != plan.company_id:
            return ResearchExecutionResult(
                query=query,
                status=ResearchExecutionStatus.FAILED,
                message=(
                    "execution company identity contradicts plan CompanyId: "
                    f"plan={plan.company_id.as_text()} company={company.company_id.as_text()}"
                ),
                research_run_id=plan.research_run_id.as_text(),
                plan_id=plan.plan_id.as_text(),
                resolution=resolution if isinstance(resolution, ResolutionResultType) else None,
                budget=budget,
                started_at=started_at,
                completed_at=self._clock(),
            )
        try:
            budget.validate_tasks(plan.tasks)
        except Exception as exc:  # BudgetExceededError
            return ResearchExecutionResult(
                query=query,
                status=ResearchExecutionStatus.BUDGET_EXCEEDED,
                message=str(exc),
                research_run_id=plan.research_run_id.as_text(),
                plan_id=plan.plan_id.as_text(),
                resolution=resolution if isinstance(resolution, ResolutionResultType) else None,
                budget=budget,
                started_at=started_at,
                completed_at=self._clock(),
            )

        if control.is_cancelled:
            return self._cancelled_before_start(
                query=query,
                plan=plan,
                company_resolution=resolution,
                budget=budget,
                started_at=started_at,
                control=control,
            )

        state = OrchestrationState(
            research_run_id=plan.research_run_id,
            plan=plan.with_status(PlanStatus.EXECUTING),
            started_at=started_at,
            updated_at=started_at,
            status=OrchestrationStatus.RUNNING,
        )
        executed_success_ids: set[str] = set()
        max_rounds = len(plan.tasks) * budget.max_attempts_per_task + len(plan.tasks) + 2
        rounds = 0
        warnings: list[str] = []

        while rounds < max_rounds:
            rounds += 1
            now = self._clock()

            if control.is_cancelled:
                state = self._apply_cancellation(
                    state, now=now, reason=control.reason or "cancelled"
                )
                break

            if state.total_attempts >= budget.max_total_attempts:
                state = replace(
                    state,
                    status=OrchestrationStatus.BUDGET_EXCEEDED,
                    terminal_reason="max_total_attempts exhausted",
                    updated_at=now,
                    plan=state.plan.with_status(PlanStatus.FAILED),
                )
                break
            if state.external_calls >= budget.max_external_calls:
                state = replace(
                    state,
                    status=OrchestrationStatus.BUDGET_EXCEEDED,
                    terminal_reason="max_external_calls exhausted",
                    updated_at=now,
                    plan=state.plan.with_status(PlanStatus.FAILED),
                )
                break

            propagated = apply_failure_propagation(state.plan.tasks)
            state = state.with_updated_plan(
                state.plan.with_tasks(propagated, status=PlanStatus.EXECUTING),
                updated_at=now,
            )

            next_task = select_next_ready_task(state.plan.tasks)
            if next_task is None:
                state = self._finalize_no_ready(state, now=now, warnings=warnings)
                break

            task_key = next_task.task_id.as_text()
            if task_key in executed_success_ids:
                warnings.append(f"duplicate execution prevented for task {task_key}")
                skipped = next_task
                if skipped.status is TaskStatus.PENDING or skipped.status is TaskStatus.READY:
                    skipped = skipped.with_status(TaskStatus.SKIPPED, at=now)
                state = self._replace_task(state, skipped, now=now)
                continue

            # Budget check before external work
            if state.external_calls + 1 > budget.max_external_calls:
                state = replace(
                    state,
                    status=OrchestrationStatus.BUDGET_EXCEEDED,
                    terminal_reason="max_external_calls would be exceeded",
                    updated_at=now,
                    plan=state.plan.with_status(PlanStatus.FAILED),
                )
                break
            if next_task.attempt_count >= budget.max_attempts_per_task:
                # Do not start another attempt; terminalize without exceeding max_attempts.
                exhausted = next_task
                if exhausted.status is TaskStatus.PENDING:
                    exhausted = exhausted.with_status(TaskStatus.READY)
                if exhausted.status is TaskStatus.READY:
                    if exhausted.attempt_count < exhausted.max_attempts:
                        exhausted = exhausted.with_status(TaskStatus.RUNNING, at=now)
                        exhausted = exhausted.with_status(TaskStatus.FAILED, at=now)
                    else:
                        exhausted = exhausted.with_status(TaskStatus.SKIPPED, at=now)
                result = TaskExecutionResult(
                    task_id=next_task.task_id,
                    status=TaskResultStatus.FAILED,
                    message="max_attempts_per_task budget exhausted before execution",
                    retryable=False,
                    error_code="budget_violation",
                )
                state = self._replace_task(state, exhausted, now=now)
                state = replace(
                    state,
                    results=(*state.results, result),
                    updated_at=now,
                )
                continue

            running = next_task
            if running.status is TaskStatus.PENDING:
                running = running.with_status(TaskStatus.READY)
            try:
                running = running.with_status(TaskStatus.RUNNING, at=now)
            except ValueError as exc:
                warnings.append(str(exc))
                state = replace(
                    state,
                    status=OrchestrationStatus.FAILED,
                    terminal_reason=str(exc),
                    updated_at=now,
                    plan=state.plan.with_status(PlanStatus.FAILED),
                )
                break

            state = self._replace_task(state, running, now=now)

            # Pre-check total attempts before capability invocation (counts as external call).
            if state.total_attempts + 1 > budget.max_total_attempts:
                failed = running.with_status(TaskStatus.FAILED, at=now)
                result = TaskExecutionResult(
                    task_id=running.task_id,
                    status=TaskResultStatus.FAILED,
                    message="max_total_attempts would be exceeded",
                    retryable=False,
                    error_code="budget_violation",
                )
                state = self._replace_task(state, failed, now=now)
                state = replace(
                    state,
                    results=(*state.results, result),
                    status=OrchestrationStatus.BUDGET_EXCEEDED,
                    terminal_reason="max_total_attempts would be exceeded",
                    updated_at=now,
                    plan=state.plan.with_status(PlanStatus.FAILED),
                )
                break

            result = self._executor.execute_task(
                running,
                company=company,
                company_query=company_query,
            )
            state = replace(
                state,
                total_attempts=state.total_attempts + 1,
                external_calls=state.external_calls + 1,
                updated_at=now,
            )

            result = self._enforce_identity(result, company=company, running=running)

            terminal_status = _result_to_task_status(result)
            finished = running.with_status(terminal_status, at=now)

            if terminal_status is TaskStatus.FAILED and self._retry.should_retry(
                finished,
                result,
                budget=budget,
                total_attempts=state.total_attempts,
            ):
                # Authorized retry: FAILED → READY
                finished = finished.with_status(TaskStatus.READY, authorized_retry=True)
            elif terminal_status is TaskStatus.SUCCEEDED:
                executed_success_ids.add(task_key)
                if result.status is TaskResultStatus.PARTIAL:
                    warnings.append(
                        f"task {task_key} completed with PARTIAL result "
                        "(downstream deps may proceed; completeness not claimed)"
                    )

            state = self._replace_task(state, finished, now=now)
            state = replace(state, results=(*state.results, result), updated_at=now)
        else:
            # max_rounds exhausted — no-progress guard
            warnings.append("no-progress guard terminated execution loop")
            state = replace(
                state,
                status=OrchestrationStatus.FAILED,
                terminal_reason="no-progress guard: max orchestration rounds exceeded",
                updated_at=self._clock(),
                warnings=tuple(warnings),
                plan=state.plan.with_status(PlanStatus.FAILED),
            )

        return self._to_result(
            query=query,
            state=state,
            resolution=resolution,
            budget=budget,
            started_at=started_at,
            extra_warnings=tuple(warnings),
        )

    @staticmethod
    def _enforce_identity(
        result: TaskExecutionResult,
        *,
        company: CompanyIdentity,
        running: ResearchTask,
    ) -> TaskExecutionResult:
        """Fail closed when evidence identity contradicts the plan company."""

        known_securities = {s.security_id for s in company.securities}
        known_listings = {listing.listing_id for listing in company.all_listings()}
        for ref in result.evidence_refs:
            if ref.company_id != company.company_id:
                return TaskExecutionResult(
                    task_id=running.task_id,
                    status=TaskResultStatus.FAILED,
                    message="evidence company_id contradicts plan CompanyId",
                    retryable=False,
                    error_code="identity_mismatch",
                )
            if ref.security_id is not None and ref.security_id not in known_securities:
                return TaskExecutionResult(
                    task_id=running.task_id,
                    status=TaskResultStatus.FAILED,
                    message="evidence security_id is not owned by plan CompanyId",
                    retryable=False,
                    error_code="identity_mismatch",
                )
            if ref.listing_id is not None and ref.listing_id not in known_listings:
                return TaskExecutionResult(
                    task_id=running.task_id,
                    status=TaskResultStatus.FAILED,
                    message="evidence listing_id is not owned by plan CompanyId",
                    retryable=False,
                    error_code="identity_mismatch",
                )
        return result

    def _replace_task(
        self, state: OrchestrationState, task: ResearchTask, *, now: datetime
    ) -> OrchestrationState:
        tasks = tuple(task if t.task_id == task.task_id else t for t in state.plan.tasks)
        return state.with_updated_plan(state.plan.with_tasks(tasks), updated_at=now)

    def _apply_cancellation(
        self, state: OrchestrationState, *, now: datetime, reason: str
    ) -> OrchestrationState:
        updated: list[ResearchTask] = []
        for task in state.plan.tasks:
            if task.status in {TaskStatus.PENDING, TaskStatus.READY}:
                current = task
                if current.status is TaskStatus.PENDING:
                    current = current.with_status(TaskStatus.READY)
                # READY → SKIPPED
                current = current.with_status(TaskStatus.SKIPPED, at=now)
                updated.append(current)
            else:
                updated.append(task)
        plan = state.plan.with_tasks(tuple(updated), status=PlanStatus.CANCELLED)
        return replace(
            state,
            plan=plan,
            status=OrchestrationStatus.CANCELLED,
            terminal_reason=reason,
            updated_at=now,
        )

    def _cancelled_before_start(
        self,
        *,
        query: ExecuteResearchPlanQuery,
        plan: ResearchPlan,
        company_resolution: object,
        budget: ResearchExecutionBudget,
        started_at: datetime,
        control: ExecutionControl,
    ) -> ResearchExecutionResult:
        now = self._clock()
        tasks: list[ResearchTask] = []
        for task in plan.tasks:
            current = (
                task.with_status(TaskStatus.READY) if task.status is TaskStatus.PENDING else task
            )
            if current.status is TaskStatus.READY:
                current = current.with_status(TaskStatus.SKIPPED, at=now)
            tasks.append(current)
        cancelled_plan = plan.with_tasks(tuple(tasks), status=PlanStatus.CANCELLED)
        state = OrchestrationState(
            research_run_id=plan.research_run_id,
            plan=cancelled_plan,
            started_at=started_at,
            updated_at=now,
            status=OrchestrationStatus.CANCELLED,
            terminal_reason=control.reason or "cancelled",
        )
        return ResearchExecutionResult(
            query=query,
            status=ResearchExecutionStatus.CANCELLED,
            message=control.reason or "cancelled before first task",
            research_run_id=plan.research_run_id.as_text(),
            plan_id=plan.plan_id.as_text(),
            plan=cancelled_plan,
            orchestration=state,
            resolution=company_resolution,  # type: ignore[arg-type]
            budget=budget,
            started_at=started_at,
            completed_at=now,
            skipped_count=len(tasks),
        )

    def _finalize_no_ready(
        self,
        state: OrchestrationState,
        *,
        now: datetime,
        warnings: list[str],
    ) -> OrchestrationState:
        # Mark remaining PENDING that cannot run as BLOCKED/SKIPPED via propagation
        propagated = apply_failure_propagation(state.plan.tasks)
        # Any leftover PENDING with unmet deps → BLOCKED if required else SKIPPED
        final_tasks: list[ResearchTask] = []
        for task in propagated:
            if task.status is TaskStatus.PENDING:
                if task.required:
                    final_tasks.append(task.with_status(TaskStatus.BLOCKED))
                else:
                    cur = task.with_status(TaskStatus.READY)
                    final_tasks.append(cur.with_status(TaskStatus.SKIPPED, at=now))
            else:
                final_tasks.append(task)
        plan = state.plan.with_tasks(tuple(final_tasks))
        return replace(
            state,
            plan=plan,
            updated_at=now,
            warnings=tuple(warnings),
        )

    def _to_result(
        self,
        *,
        query: ExecuteResearchPlanQuery,
        state: OrchestrationState,
        resolution: object,
        budget: ResearchExecutionBudget,
        started_at: datetime,
        extra_warnings: tuple[str, ...],
    ) -> ResearchExecutionResult:
        completed_at = self._clock()
        tasks = state.plan.tasks
        completed = sum(1 for t in tasks if t.status is TaskStatus.SUCCEEDED)
        failed = sum(1 for t in tasks if t.status is TaskStatus.FAILED)
        blocked = sum(1 for t in tasks if t.status is TaskStatus.BLOCKED)
        skipped = sum(1 for t in tasks if t.status is TaskStatus.SKIPPED)
        partial = sum(1 for r in state.results if r.status is TaskResultStatus.PARTIAL)
        evidence = dedupe_evidence_refs(
            tuple(ref for result in state.results for ref in result.evidence_refs)
        )
        warnings = tuple(dict.fromkeys([*state.warnings, *extra_warnings]))

        if state.status is OrchestrationStatus.CANCELLED:
            run_status = ResearchExecutionStatus.CANCELLED
            plan_status = PlanStatus.CANCELLED
            message = state.terminal_reason or "execution cancelled"
        elif state.status is OrchestrationStatus.BUDGET_EXCEEDED:
            run_status = ResearchExecutionStatus.BUDGET_EXCEEDED
            plan_status = PlanStatus.FAILED
            message = state.terminal_reason or "execution budget exceeded"
        else:
            required = [t for t in tasks if t.required]
            optional = [t for t in tasks if not t.required]
            req_failed = any(t.status is TaskStatus.FAILED for t in required)
            req_blocked = any(t.status is TaskStatus.BLOCKED for t in required)
            req_succeeded = sum(1 for t in required if t.status is TaskStatus.SUCCEEDED)
            req_ok = bool(required) and all(t.status is TaskStatus.SUCCEEDED for t in required)
            optional_failed = any(t.status is TaskStatus.FAILED for t in optional)
            # Transparent partial status when some required work succeeded alongside failures.
            if req_failed and req_succeeded > 0:
                run_status = ResearchExecutionStatus.PARTIAL
                plan_status = PlanStatus.COMPLETED
                message = (
                    "transparent partial: one or more required tasks failed while others succeeded"
                )
            elif req_failed:
                run_status = ResearchExecutionStatus.FAILED
                plan_status = PlanStatus.FAILED
                message = "one or more required tasks failed"
            elif req_blocked and req_succeeded > 0:
                run_status = ResearchExecutionStatus.PARTIAL
                plan_status = PlanStatus.COMPLETED
                message = (
                    "transparent partial: one or more required tasks blocked while others succeeded"
                )
            elif req_blocked:
                run_status = ResearchExecutionStatus.BLOCKED
                plan_status = PlanStatus.FAILED
                message = "one or more required tasks blocked"
            elif req_ok and (partial > 0 or optional_failed):
                run_status = ResearchExecutionStatus.PARTIAL
                plan_status = PlanStatus.COMPLETED
                message = (
                    "required tasks finished with PARTIAL capability results "
                    "and/or optional task failures"
                    if optional_failed or partial > 0
                    else "required tasks finished with limitations"
                )
            elif req_ok:
                run_status = ResearchExecutionStatus.COMPLETED
                plan_status = PlanStatus.COMPLETED
                message = "research plan executed within bounds"
            else:
                run_status = ResearchExecutionStatus.PARTIAL
                plan_status = PlanStatus.COMPLETED
                message = "execution finished with incomplete required coverage"

        final_plan = state.plan.with_status(plan_status)
        final_state = replace(
            state,
            plan=final_plan,
            status={
                ResearchExecutionStatus.COMPLETED: OrchestrationStatus.COMPLETED,
                ResearchExecutionStatus.PARTIAL: OrchestrationStatus.PARTIAL,
                ResearchExecutionStatus.FAILED: OrchestrationStatus.FAILED,
                ResearchExecutionStatus.BLOCKED: OrchestrationStatus.BLOCKED,
                ResearchExecutionStatus.CANCELLED: OrchestrationStatus.CANCELLED,
                ResearchExecutionStatus.BUDGET_EXCEEDED: OrchestrationStatus.BUDGET_EXCEEDED,
            }.get(run_status, OrchestrationStatus.FAILED),
            warnings=warnings,
            terminal_reason=state.terminal_reason or message,
            updated_at=completed_at,
        )
        return ResearchExecutionResult(
            query=query,
            status=run_status,
            message=message,
            research_run_id=final_plan.research_run_id.as_text(),
            plan_id=final_plan.plan_id.as_text(),
            plan=final_plan,
            orchestration=final_state,
            task_results=final_state.results,
            evidence_refs=evidence,
            warnings=warnings,
            completed_count=completed,
            failed_count=failed,
            blocked_count=blocked,
            partial_count=partial,
            skipped_count=skipped,
            resolution=resolution,  # type: ignore[arg-type]
            budget=budget,
            started_at=started_at,
            completed_at=completed_at,
        )
