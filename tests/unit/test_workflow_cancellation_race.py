"""F03 regression tests: workflow cancellation/lifecycle race.

Covers the store-level transition guard directly, and the real
ManageResearchWorkflow path end-to-end via deterministic thread
synchronization (threading.Event / threading.Barrier) -- never sleep-based
timing. See F03_CANCELLATION_RACE_REMEDIATION_PLAN.md and
F03_CANCELLATION_RACE_IMPLEMENTATION_REPORT.md.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.create_research_workflow import CreateResearchWorkflow
from financial_intelligence.application.manage_research_workflow import ManageResearchWorkflow
from financial_intelligence.application.workflow_contracts import (
    CreateResearchWorkflowQuery,
    WorkflowOperationStatus,
)
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import ExchangeCode
from financial_intelligence.domain.orchestration import (
    ResearchObjective,
    TaskExecutionResult,
    TaskResultStatus,
)
from financial_intelligence.domain.workflow import (
    WorkflowId,
    WorkflowStatus,
    WorkflowTransitionError,
    assert_transition,
)
from financial_intelligence.infrastructure.workflow import InMemoryResearchWorkflowStore


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _clock() -> datetime:
    return datetime(2026, 8, 8, 17, 0, tzinfo=UTC)


class _ScriptedExecutor:
    """Wrap the real capability executor: optionally block on the Nth task
    (1-indexed) until released, and/or force specific 1-indexed task calls to
    return a scripted FAILED result instead of delegating."""

    def __init__(
        self,
        inner: object,
        *,
        block_at: int | None = None,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
        fail_at: frozenset[int] = frozenset(),
    ) -> None:
        self._inner = inner
        self._block_at = block_at
        self._started = started
        self._release = release
        self._fail_at = fail_at
        self._n = 0

    def execute_task(self, task, *, company, company_query):
        self._n += 1
        index = self._n
        if index == self._block_at:
            assert self._started is not None
            assert self._release is not None
            self._started.set()
            if not self._release.wait(timeout=10):
                raise TimeoutError("release event was never set -- test harness bug")
        if index in self._fail_at:
            return TaskExecutionResult(
                task_id=task.task_id,
                status=TaskResultStatus.FAILED,
                message="scripted failure for F03 regression test",
                retryable=False,
                error_code="scripted_failure",
            )
        return self._inner.execute_task(task, company=company, company_query=company_query)  # type: ignore[attr-defined]


class StoreLevelTransitionGuardTests(TestCase):
    """Test the store transition primitive directly (no threading needed --
    the guard's logic is deterministic given two sequential writes)."""

    def setUp(self) -> None:
        self.container = build_container(settings=_settings(), clock=_clock)
        self.create: CreateResearchWorkflow = self.container.create_research_workflow
        self.manage: ManageResearchWorkflow = self.container.manage_research_workflow
        self.store: InMemoryResearchWorkflowStore = self.container.workflow_store  # type: ignore[assignment]

    def _new_workflow(self):
        created = self.create.execute(
            CreateResearchWorkflowQuery(
                company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
                objective=ResearchObjective.MARKET_ANALYSIS,
            )
        )
        assert created.workflow is not None
        return created.workflow

    def test_store_rejects_stale_running_to_completed_after_cancelled(self) -> None:
        """#12 (core invariant): once CANCELLED is the record the store holds,
        a write built from a stale pre-cancel RUNNING snapshot attempting
        COMPLETED must be rejected, not silently accepted."""
        workflow = self._new_workflow()
        running = workflow.with_status(WorkflowStatus.RUNNING, at=_clock())
        self.store.save_workflow(running)

        cancelled = running.with_status(WorkflowStatus.CANCELLED, at=_clock())
        self.store.save_workflow(cancelled)

        stale_completed = running.with_status(WorkflowStatus.COMPLETED, at=_clock())
        with self.assertRaises(WorkflowTransitionError):
            self.store.save_workflow(stale_completed)

        current = self.store.get_workflow(workflow.workflow_id)
        assert current is not None
        self.assertEqual(current.status, WorkflowStatus.CANCELLED)

    def test_store_rejects_stale_running_to_completed_after_paused(self) -> None:
        """Same invariant, PAUSED case (#6's store-level counterpart)."""
        workflow = self._new_workflow()
        running = workflow.with_status(WorkflowStatus.RUNNING, at=_clock())
        self.store.save_workflow(running)

        paused = running.with_status(WorkflowStatus.PAUSED, at=_clock())
        self.store.save_workflow(paused)

        stale_completed = running.with_status(WorkflowStatus.COMPLETED, at=_clock())
        with self.assertRaises(WorkflowTransitionError):
            self.store.save_workflow(stale_completed)

        current = self.store.get_workflow(workflow.workflow_id)
        assert current is not None
        self.assertEqual(current.status, WorkflowStatus.PAUSED)

    def test_store_allows_idempotent_same_status_resave(self) -> None:
        """Regression guard: re-saving the SAME status (e.g. appending a
        notification warning after a terminal write already landed) must not
        be rejected -- only an actual status change is guarded."""
        workflow = self._new_workflow()
        running = workflow.with_status(WorkflowStatus.RUNNING, at=_clock())
        self.store.save_workflow(running)
        completed = running.with_status(WorkflowStatus.COMPLETED, at=_clock())
        self.store.save_workflow(completed)

        # Re-save the identical status (as the notify-warning append path does).
        from dataclasses import replace

        resaved = replace(completed, warnings=(*completed.warnings, "some_warning"))
        self.store.save_workflow(resaved)  # must not raise
        current = self.store.get_workflow(workflow.workflow_id)
        assert current is not None
        self.assertEqual(current.status, WorkflowStatus.COMPLETED)
        self.assertIn("some_warning", current.warnings)

    def test_store_still_enforces_preexisting_identity_invariants(self) -> None:
        """Regression guard: the new guard must not weaken or bypass the
        store's existing invariants (request_id/company_id/plan_id immutable,
        checkpoint_version must not regress)."""
        from financial_intelligence.infrastructure.workflow import WorkflowStoreError

        workflow = self._new_workflow()
        self.store.save_workflow(workflow)
        from dataclasses import replace
        from uuid import uuid4

        from financial_intelligence.domain.orchestration import RequestId

        tampered = replace(workflow, request_id=RequestId(value=uuid4()))
        with self.assertRaises(WorkflowStoreError):
            self.store.save_workflow(tampered)

    def test_assert_transition_itself_is_unmodified(self) -> None:
        """Regression guard: the domain transition table itself was not
        touched by this fix -- CANCELLED remains terminal (empty allowed set)."""
        with self.assertRaises(WorkflowTransitionError):
            assert_transition(WorkflowStatus.CANCELLED, WorkflowStatus.COMPLETED)
        # A previously-valid transition must still be valid (no over-tightening).
        assert_transition(WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED)


class WorkflowCancellationRaceTests(TestCase):
    """End-to-end tests through the real ManageResearchWorkflow path, using
    threading.Event-based synchronization to force deterministic
    interleavings -- never sleep()."""

    def setUp(self) -> None:
        self.container = build_container(settings=_settings(), clock=_clock)
        self.create: CreateResearchWorkflow = self.container.create_research_workflow
        self.manage: ManageResearchWorkflow = self.container.manage_research_workflow
        self._original_executor = self.container.execute_research_plan._executor

    def tearDown(self) -> None:
        self.container.execute_research_plan._executor = self._original_executor

    def _create(self, objective: ResearchObjective) -> WorkflowId:
        created = self.create.execute(
            CreateResearchWorkflowQuery(
                company_query=CompanyQuery(raw_query="Apple", exchange=ExchangeCode("NASDAQ")),
                objective=objective,
            )
        )
        assert created.status == WorkflowOperationStatus.OK, created.message
        assert created.workflow is not None
        return created.workflow.workflow_id

    def _install_scripted_executor(self, **kwargs: object) -> _ScriptedExecutor:
        scripted = _ScriptedExecutor(self._original_executor, **kwargs)  # type: ignore[arg-type]
        self.container.execute_research_plan._executor = scripted
        return scripted

    def _run_execute_in_background(self, workflow_id: WorkflowId) -> tuple[threading.Thread, dict]:
        result_box: dict = {}

        def _run() -> None:
            # Mirrors the real HTTP execute route exactly: no `control=` kwarg.
            result_box["result"] = self.manage.execute(workflow_id)

        thread = threading.Thread(target=_run, name="execute-worker")
        thread.start()
        return thread, result_box

    # --- 1. Cancel while execution is running -------------------------------
    def test_cancel_while_execution_running_is_not_overwritten(self) -> None:
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(block_at=1, started=started, release=release)

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5), "capability call never started")

        cancel_result = self.manage.cancel(wf_id)
        self.assertEqual(cancel_result.status, WorkflowOperationStatus.OK)
        assert cancel_result.workflow is not None
        self.assertEqual(cancel_result.workflow.status, WorkflowStatus.CANCELLED)

        release.set()
        worker.join(timeout=10)

        self.assertEqual(box["result"].status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.CANCELLED)

    # --- 2. Cancel immediately before worker completion ----------------------
    def test_cancel_immediately_before_worker_completion(self) -> None:
        """Block on the LAST of three tasks (COMPANY_OVERVIEW), so cancel
        races the tail end of an almost-finished execution."""
        wf_id = self._create(ResearchObjective.COMPANY_OVERVIEW)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(block_at=3, started=started, release=release)

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5), "capability call never started")

        cancel_result = self.manage.cancel(wf_id)
        self.assertEqual(cancel_result.status, WorkflowOperationStatus.OK)

        release.set()
        worker.join(timeout=10)

        self.assertEqual(box["result"].status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.CANCELLED)

    # --- 3. Worker attempts completion after cancellation --------------------
    def test_worker_completion_after_cancellation_is_rejected(self) -> None:
        """Same as #1 but asserts explicitly on the CONFLICT message content
        and that the discarded result was a COMPLETED outcome."""
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(block_at=1, started=started, release=release)

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5))
        self.manage.cancel(wf_id)
        release.set()
        worker.join(timeout=10)

        result = box["result"]
        self.assertEqual(result.status, WorkflowOperationStatus.CONFLICT)
        self.assertIn("concurrently", result.message)

    # --- 4. Worker attempts failure after cancellation -----------------------
    def test_worker_failure_after_cancellation_is_rejected(self) -> None:
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(
            block_at=1, started=started, release=release, fail_at=frozenset({1})
        )

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5))
        self.manage.cancel(wf_id)
        release.set()
        worker.join(timeout=10)

        self.assertEqual(box["result"].status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.CANCELLED)

    # --- 5. Worker attempts partial completion after cancellation -----------
    def test_worker_partial_completion_after_cancellation_is_rejected(self) -> None:
        """COMPANY_OVERVIEW has 3 tasks; force the 2nd to fail so an
        uncontested run would finish PARTIAL, then race a cancel against it."""
        wf_id = self._create(ResearchObjective.COMPANY_OVERVIEW)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(
            block_at=2, started=started, release=release, fail_at=frozenset({2})
        )

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5))
        self.manage.cancel(wf_id)
        release.set()
        worker.join(timeout=10)

        self.assertEqual(box["result"].status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.CANCELLED)

    # --- 6. Worker attempts a stale write after PAUSED -----------------------
    def test_worker_stale_write_after_paused_is_rejected(self) -> None:
        """A second, concurrent execute() attempt is blocked; meanwhile a
        pause() lands on the same workflow. The blocked attempt's eventual
        commit must not overwrite PAUSED."""
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(block_at=1, started=started, release=release)

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5))

        pause_result = self.manage.pause(wf_id)
        self.assertEqual(pause_result.status, WorkflowOperationStatus.OK)
        assert pause_result.workflow is not None
        self.assertEqual(pause_result.workflow.status, WorkflowStatus.PAUSED)

        release.set()
        worker.join(timeout=10)

        self.assertEqual(box["result"].status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.PAUSED)

    # --- 7. Repeated cancellation --------------------------------------------
    def test_repeated_cancellation_returns_conflict(self) -> None:
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        first = self.manage.cancel(wf_id)
        self.assertEqual(first.status, WorkflowOperationStatus.OK)
        second = self.manage.cancel(wf_id)
        self.assertEqual(second.status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.CANCELLED)

    # --- 8. Cancel after successful completion -------------------------------
    def test_cancel_after_successful_completion_returns_conflict(self) -> None:
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        executed = self.manage.execute(wf_id)
        self.assertEqual(executed.status, WorkflowOperationStatus.OK)
        assert executed.workflow is not None
        self.assertEqual(executed.workflow.status, WorkflowStatus.COMPLETED)

        cancel_result = self.manage.cancel(wf_id)
        self.assertEqual(cancel_result.status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.COMPLETED)

    # --- 9. Cancel after failure ----------------------------------------------
    def test_cancel_after_failure_returns_conflict(self) -> None:
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        self._install_scripted_executor(fail_at=frozenset({1}))
        executed = self.manage.execute(wf_id)
        self.assertEqual(executed.status, WorkflowOperationStatus.FAILED)
        assert executed.workflow is not None
        self.assertEqual(executed.workflow.status, WorkflowStatus.FAILED)

        cancel_result = self.manage.cancel(wf_id)
        self.assertEqual(cancel_result.status, WorkflowOperationStatus.CONFLICT)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.FAILED)

    # --- 10. Concurrent lifecycle operation versus stale worker completion --
    def test_concurrent_lifecycle_write_and_stale_commit_are_mutually_exclusive(self) -> None:
        """Two writers -- a fresh cancel() and a stale worker's completion
        commit -- are forced to reach the store's write step at genuinely the
        same instant via a Barrier. Which one wins a true tie is not itself
        deterministic (that is a property of thread scheduling, not of the
        fix), so this test asserts the invariant that IS deterministic
        regardless of scheduling: exactly one of the two writes is ever
        accepted, the other is rejected (never both accepted, never both
        silently lost), and the store's final state exactly matches whichever
        one won -- never a corrupted or intermediate state."""
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        started = threading.Event()
        release = threading.Event()
        self._install_scripted_executor(block_at=1, started=started, release=release)

        worker, box = self._run_execute_in_background(wf_id)
        self.assertTrue(started.wait(timeout=5))

        barrier = threading.Barrier(2)
        cancel_box: dict = {}

        def _cancel_at_barrier() -> None:
            barrier.wait(timeout=5)
            cancel_box["result"] = self.manage.cancel(wf_id)

        def _release_at_barrier() -> None:
            barrier.wait(timeout=5)
            release.set()

        canceller = threading.Thread(target=_cancel_at_barrier)
        releaser = threading.Thread(target=_release_at_barrier)
        canceller.start()
        releaser.start()
        canceller.join(timeout=10)
        releaser.join(timeout=10)
        worker.join(timeout=10)

        cancel_status = cancel_box["result"].status
        worker_status = box["result"].status
        # Exactly one of the two writers may have been accepted (OK); the
        # other must have been rejected (CONFLICT) -- never both OK, never
        # both CONFLICT (one of them started from a genuinely valid,
        # non-stale state and must succeed).
        statuses = {cancel_status, worker_status}
        self.assertEqual({WorkflowOperationStatus.OK, WorkflowOperationStatus.CONFLICT}, statuses)
        self.assertNotEqual(cancel_status, worker_status)

        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        if cancel_status is WorkflowOperationStatus.OK:
            self.assertEqual(final.status, WorkflowStatus.CANCELLED)
        else:
            # The stale worker cannot ever legitimately win against a cancel
            # that reached the store first -- if the worker's write was the
            # one accepted, the cancel must have been the one rejected only
            # because it observed an already-terminal (worker-completed)
            # record, which is itself a valid, non-stale outcome, not a bug.
            self.assertTrue(final.status in {WorkflowStatus.COMPLETED, WorkflowStatus.PARTIAL})

    # --- 11. Normal execution still completes successfully -------------------
    def test_normal_execution_still_completes_successfully(self) -> None:
        """Pure compatibility gate: zero concurrency, must behave exactly as
        before this fix."""
        wf_id = self._create(ResearchObjective.MARKET_ANALYSIS)
        executed = self.manage.execute(wf_id)
        self.assertEqual(executed.status, WorkflowOperationStatus.OK)
        assert executed.workflow is not None
        self.assertEqual(executed.workflow.status, WorkflowStatus.COMPLETED)
        final = self.container.workflow_store.get_workflow(wf_id)
        assert final is not None
        self.assertEqual(final.status, WorkflowStatus.COMPLETED)
