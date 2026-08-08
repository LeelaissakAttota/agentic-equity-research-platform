"""In-memory ResearchWorkflowStorePort — Prompt 1/2 (not durable)."""

from __future__ import annotations

from threading import RLock

from financial_intelligence.domain.workflow import (
    ResearchWorkflow,
    WorkflowCheckpoint,
    WorkflowId,
    WorkflowStatus,
)


class WorkflowStoreError(ValueError):
    """Workflow store conflict or invariant violation."""


class InMemoryResearchWorkflowStore:
    """Process-local workflow store.

    IN-MEMORY ≠ durable production persistence. Data is lost on process exit.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._workflows: dict[str, ResearchWorkflow] = {}
        self._checkpoints: dict[str, WorkflowCheckpoint] = {}

    def save_workflow(self, workflow: ResearchWorkflow) -> None:
        key = workflow.workflow_id.as_text()
        with self._lock:
            existing = self._workflows.get(key)
            if existing is not None:
                if existing.research_run_id.as_text() != workflow.research_run_id.as_text():
                    msg = f"duplicate workflow_id: {key}"
                    raise WorkflowStoreError(msg)
                if existing.request_id.as_text() != workflow.request_id.as_text():
                    msg = f"workflow request_id immutable for {key}"
                    raise WorkflowStoreError(msg)
                if existing.company_id != workflow.company_id:
                    msg = f"workflow company_id immutable for {key}"
                    raise WorkflowStoreError(msg)
                if existing.plan.plan_id.as_text() != workflow.plan.plan_id.as_text():
                    msg = f"workflow plan_id immutable for {key}"
                    raise WorkflowStoreError(msg)
                if workflow.checkpoint_version < existing.checkpoint_version:
                    msg = (
                        f"workflow checkpoint_version regression for {key}: "
                        f"{workflow.checkpoint_version} < {existing.checkpoint_version}"
                    )
                    raise WorkflowStoreError(msg)
            self._workflows[key] = workflow

    def get_workflow(self, workflow_id: WorkflowId) -> ResearchWorkflow | None:
        with self._lock:
            return self._workflows.get(workflow_id.as_text())

    def list_workflows(
        self,
        *,
        status: WorkflowStatus | None = None,
        company_id_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[ResearchWorkflow, ...]:
        if limit < 1 or limit > 200:
            msg = "limit must be between 1 and 200"
            raise WorkflowStoreError(msg)
        if offset < 0:
            msg = "offset must be non-negative"
            raise WorkflowStoreError(msg)
        with self._lock:
            items = list(self._workflows.values())
        if status is not None:
            items = [w for w in items if w.status is status]
        if company_id_text is not None:
            items = [w for w in items if w.company_id.as_text() == company_id_text]
        items.sort(
            key=lambda w: (w.created_at.isoformat(), w.workflow_id.as_text()),
        )
        return tuple(items[offset : offset + limit])

    def save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> None:
        key = checkpoint.workflow_id.as_text()
        with self._lock:
            workflow = self._workflows.get(key)
            if workflow is not None:
                if workflow.research_run_id.as_text() != checkpoint.research_run_id.as_text():
                    msg = "checkpoint research_run_id mismatch with workflow"
                    raise WorkflowStoreError(msg)
                if workflow.plan.plan_id.as_text() != checkpoint.plan.plan_id.as_text():
                    msg = "checkpoint plan_id mismatch with workflow"
                    raise WorkflowStoreError(msg)
                if checkpoint.plan.company_id != workflow.company_id:
                    msg = "checkpoint company_id mismatch with workflow"
                    raise WorkflowStoreError(msg)
            current = self._checkpoints.get(key)
            if current is not None and checkpoint.version <= current.version:
                msg = (
                    f"checkpoint version {checkpoint.version} must exceed "
                    f"stored version {current.version}"
                )
                raise WorkflowStoreError(msg)
            self._checkpoints[key] = checkpoint

    def get_latest_checkpoint(self, workflow_id: WorkflowId) -> WorkflowCheckpoint | None:
        with self._lock:
            return self._checkpoints.get(workflow_id.as_text())
