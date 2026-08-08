"""In-memory ResearchMemoryPort — Prompt 2 (not vector memory)."""

from __future__ import annotations

from threading import RLock

from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.memory import MemoryRecordId, ResearchMemoryRecord
from financial_intelligence.domain.workflow import WorkflowId


class ResearchMemoryStoreError(ValueError):
    """Memory store invariant violation."""


class InMemoryResearchMemoryStore:
    """Process-local structured research memory."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, ResearchMemoryRecord] = {}
        self._task_keys: set[str] = set()

    def append(self, record: ResearchMemoryRecord) -> None:
        key = record.record_id.as_text()
        task_key = f"{record.workflow_id.as_text()}:{record.task_id.as_text()}"
        with self._lock:
            if key in self._records:
                msg = f"duplicate memory record_id: {key}"
                raise ResearchMemoryStoreError(msg)
            if task_key in self._task_keys:
                msg = f"duplicate memory for workflow task: {task_key}"
                raise ResearchMemoryStoreError(msg)
            self._records[key] = record
            self._task_keys.add(task_key)

    def get_record(self, record_id: MemoryRecordId) -> ResearchMemoryRecord | None:
        with self._lock:
            return self._records.get(record_id.as_text())

    def list_for_workflow(
        self, workflow_id: WorkflowId, *, limit: int = 100
    ) -> tuple[ResearchMemoryRecord, ...]:
        if limit < 1 or limit > 500:
            msg = "limit must be between 1 and 500"
            raise ResearchMemoryStoreError(msg)
        with self._lock:
            items = [
                r
                for r in self._records.values()
                if r.workflow_id.as_text() == workflow_id.as_text()
            ]
        items.sort(key=lambda r: (r.created_at.isoformat(), r.record_id.as_text()))
        return tuple(items[:limit])

    def list_for_company(
        self, company_id: CompanyId, *, limit: int = 100
    ) -> tuple[ResearchMemoryRecord, ...]:
        if limit < 1 or limit > 500:
            msg = "limit must be between 1 and 500"
            raise ResearchMemoryStoreError(msg)
        with self._lock:
            items = [r for r in self._records.values() if r.company_id == company_id]
        items.sort(key=lambda r: (r.created_at.isoformat(), r.record_id.as_text()))
        return tuple(items[:limit])
