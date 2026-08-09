"""Application orchestration for deterministic verified research synthesis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from financial_intelligence.application.company_resolution import ResolutionStatus
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.application.synthesis_contracts import (
    GenerateResearchSynthesisQuery,
    GenerateResearchSynthesisResult,
    SynthesisOperationStatus,
)
from financial_intelligence.domain.synthesis import DeterministicSynthesisAssembler


@dataclass(frozen=True, slots=True)
class GenerateResearchSynthesis:
    """Resolve canonical identity and assemble only Phase 8 verified artifacts."""

    resolve_company: ResolveCompany
    assembler: DeterministicSynthesisAssembler
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def execute(self, query: GenerateResearchSynthesisQuery) -> GenerateResearchSynthesisResult:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("synthesis clock must return timezone-aware datetime")
        resolution = self.resolve_company.execute(query.company_query)
        if resolution.status is not ResolutionStatus.RESOLVED or resolution.company is None:
            return GenerateResearchSynthesisResult(
                status=SynthesisOperationStatus.RESOLUTION_BLOCKED,
                message="synthesis requires one canonically resolved company",
                synthesis=None,
                resolution=resolution,
                evaluated_at=now,
            )
        try:
            synthesis = self.assembler.assemble(
                company=resolution.company,
                verified_claims=query.verified_claims,
                language=query.language,
                generated_at=now,
            )
        except ValueError as exc:
            return GenerateResearchSynthesisResult(
                status=SynthesisOperationStatus.INVALID,
                message=str(exc),
                synthesis=None,
                resolution=resolution,
                evaluated_at=now,
            )
        return GenerateResearchSynthesisResult(
            status=SynthesisOperationStatus.OK,
            message="deterministic research synthesis generated",
            synthesis=synthesis,
            resolution=resolution,
            evaluated_at=now,
        )
