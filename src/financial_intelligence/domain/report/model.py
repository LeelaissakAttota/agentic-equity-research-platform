"""Automated report workflow contracts — no document rendering in Prompt 2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from financial_intelligence.domain.workflow.ids import WorkflowId


class ReportStatus(StrEnum):
    REPORT_PENDING = "report_pending"
    REPORT_READY = "report_ready"
    REPORT_FAILED = "report_failed"


class ReportRequestId:
    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        if value.version != 4:
            msg = "report_request_id must be a UUIDv4"
            raise ValueError(msg)
        self._value = value

    @classmethod
    def new(cls) -> ReportRequestId:
        return cls(uuid4())

    def as_text(self) -> str:
        return str(self._value)


@dataclass(frozen=True, slots=True)
class ReportArtifactMetadata:
    """Metadata placeholder for a future report artifact (no binary content)."""

    format: str = "deferred"
    title: str = "research_report"

    def __post_init__(self) -> None:
        fmt = self.format.strip().lower()
        if fmt not in {"deferred", "markdown", "docx"}:
            msg = "unsupported report format"
            raise ValueError(msg)
        title = " ".join(self.title.strip().split())
        if not title or len(title) > 128:
            msg = "report title empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "format", fmt)
        object.__setattr__(self, "title", title)

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "title": self.title,
            "kind": "report_artifact_metadata",
        }


@dataclass(frozen=True, slots=True)
class ReportRequest:
    """Request to generate a research report from a completed workflow.

    Prompt 2 establishes the contract only. Actual Word/PDF rendering is deferred.
    """

    request_id: ReportRequestId
    workflow_id: WorkflowId
    status: ReportStatus
    created_at: datetime
    updated_at: datetime
    artifact: ReportArtifactMetadata | None = None
    message: str = "report generation deferred"

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            msg = "report timestamps must be timezone-aware"
            raise ValueError(msg)
        text = " ".join(self.message.strip().split())
        if not text or len(text) > 512:
            msg = "report message empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "message", text)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id.as_text(),
            "workflow_id": self.workflow_id.as_text(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z"),
            "artifact": self.artifact.to_dict() if self.artifact else None,
            "message": self.message,
            "kind": "report_request",
        }
