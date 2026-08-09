"""Replaceable report-generation port for deterministic Phase 9 adapters."""

from __future__ import annotations

from typing import Protocol

from financial_intelligence.domain.report import (
    ReportArtifact,
    ResearchReportGenerationRequest,
)
from financial_intelligence.domain.synthesis import ResearchSynthesis


class ResearchReportGeneratorPort(Protocol):
    """Generate an artifact solely from an existing structured synthesis."""

    def generate(
        self,
        request: ResearchReportGenerationRequest,
        synthesis: ResearchSynthesis,
    ) -> ReportArtifact: ...
