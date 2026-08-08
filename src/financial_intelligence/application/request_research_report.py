"""Report workflow contract use case — no document rendering."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from financial_intelligence.application.ports import ResearchWorkflowStorePort
from financial_intelligence.domain.report import (
    ReportArtifactMetadata,
    ReportRequest,
    ReportRequestId,
    ReportStatus,
)
from financial_intelligence.domain.workflow import WorkflowId, WorkflowStatus, is_terminal


class ReportOperationStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class ReportOperationResult:
    status: ReportOperationStatus
    message: str
    report: ReportRequest | None = None
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "report": self.report.to_dict() if self.report else None,
            "evaluated_at": (
                self.evaluated_at.isoformat().replace("+00:00", "Z") if self.evaluated_at else None
            ),
            "kind": "report_operation_result",
        }


class RequestResearchReport:
    """Establish report-request state for a completed/partial workflow.

    Prompt 2 intentionally leaves rendering deferred (ADR).
    """

    def __init__(
        self,
        workflow_store: ResearchWorkflowStorePort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = workflow_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._requests: dict[str, ReportRequest] = {}

    def execute(self, workflow_id: WorkflowId) -> ReportOperationResult:
        now = self._clock()
        workflow = self._store.get_workflow(workflow_id)
        if workflow is None:
            return ReportOperationResult(
                status=ReportOperationStatus.NOT_FOUND,
                message="workflow not found",
                evaluated_at=now,
            )
        if workflow.status not in {WorkflowStatus.COMPLETED, WorkflowStatus.PARTIAL}:
            return ReportOperationResult(
                status=ReportOperationStatus.CONFLICT,
                message=(
                    "report request requires completed or partial workflow; "
                    f"status={workflow.status.value}"
                ),
                evaluated_at=now,
            )
        if not is_terminal(workflow.status):
            return ReportOperationResult(
                status=ReportOperationStatus.CONFLICT,
                message="workflow not terminal",
                evaluated_at=now,
            )
        report = ReportRequest(
            request_id=ReportRequestId.new(),
            workflow_id=workflow_id,
            status=ReportStatus.REPORT_PENDING,
            created_at=now,
            updated_at=now,
            artifact=ReportArtifactMetadata(format="deferred", title="research_report"),
            message=(
                "report generation deferred: contract established; "
                "no Word/PDF/LLM synthesis in Prompt 2"
            ),
        )
        self._requests[report.request_id.as_text()] = report
        return ReportOperationResult(
            status=ReportOperationStatus.OK,
            message="report request recorded (rendering deferred)",
            report=report,
            evaluated_at=now,
        )
