"""Report-generation contracts for bounded Phase 9 rendering adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.synthesis import LanguagePreference, SynthesisId


class ReportFormat(StrEnum):
    """Declared output formats; DOCX rendering remains future work."""

    STRUCTURED_JSON = "structured_json"
    MARKDOWN = "markdown"
    DOCX = "docx"


class ReportArtifactStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ResearchReportGenerationRequest:
    """Request passed to a replaceable report generator."""

    synthesis_id: SynthesisId
    report_format: ReportFormat
    language: LanguagePreference
    title: str = "Research Report"

    def __post_init__(self) -> None:
        title = " ".join(self.title.strip().split())
        if not title or len(title) > 128:
            raise ValueError("report title empty or exceeds bounds")
        object.__setattr__(self, "title", title)


@dataclass(frozen=True, slots=True)
class ReportArtifact:
    """Transport-neutral report artifact metadata/content boundary."""

    artifact_id: str
    synthesis_id: SynthesisId
    report_format: ReportFormat
    status: ReportArtifactStatus
    media_type: str
    content: str | None = None
    locator: str | None = None
    error_message: str | None = None
    content_encoding: str = "utf-8"
    filename: str | None = None

    def __post_init__(self) -> None:
        artifact_id = self.artifact_id.strip()
        if not artifact_id or len(artifact_id) > 128:
            raise ValueError("artifact_id empty or exceeds bounds")
        object.__setattr__(self, "artifact_id", artifact_id)
        media_type = self.media_type.strip().lower()
        if not media_type or len(media_type) > 128:
            raise ValueError("media_type empty or exceeds bounds")
        object.__setattr__(self, "media_type", media_type)
        if (
            self.status is ReportArtifactStatus.READY
            and self.content is None
            and self.locator is None
        ):
            raise ValueError("ready report artifact requires content or locator")
        if self.status is ReportArtifactStatus.FAILED and not self.error_message:
            raise ValueError("failed report artifact requires error_message")
        if self.content_encoding not in {"utf-8", "base64"}:
            raise ValueError("unsupported report content encoding")
        if self.report_format is ReportFormat.DOCX and self.status is ReportArtifactStatus.READY:
            if self.content_encoding != "base64":
                raise ValueError("ready DOCX artifact requires base64 content encoding")
            if self.filename is None or not self.filename.endswith(".docx"):
                raise ValueError("ready DOCX artifact requires a .docx filename")
        if self.filename is not None and (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.filename)
            or ".." in self.filename
        ):
            raise ValueError("report filename is unsafe or exceeds bounds")

    def to_dict(self) -> dict[str, object]:
        """Return deterministic transport-safe artifact metadata and content."""

        return {
            "artifact_id": self.artifact_id,
            "synthesis_id": self.synthesis_id.as_text(),
            "report_format": self.report_format.value,
            "status": self.status.value,
            "media_type": self.media_type,
            "content": self.content,
            "locator": self.locator,
            "error_message": self.error_message,
            "content_encoding": self.content_encoding,
            "filename": self.filename,
        }
