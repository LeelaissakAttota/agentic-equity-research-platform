"""Application contracts for deterministic research synthesis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionResult,
)
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.synthesis import (
    LanguagePreference,
    ResearchSynthesis,
    VerifiedClaimInput,
)


class SynthesisOperationStatus(StrEnum):
    OK = "ok"
    RESOLUTION_BLOCKED = "resolution_blocked"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class GenerateResearchSynthesisQuery:
    company_query: CompanyQuery
    research_run_id: str
    verified_claims: tuple[VerifiedClaimInput, ...]
    language: LanguagePreference = field(default_factory=LanguagePreference)

    def __post_init__(self) -> None:
        ResearchRunId.from_string(self.research_run_id)
        if not self.verified_claims or len(self.verified_claims) > 100:
            raise ValueError("synthesis requires between 1 and 100 verified claims")
        if any(item.research_run_id != self.research_run_id for item in self.verified_claims):
            raise ValueError("verified claim research_run_id mismatch")


@dataclass(frozen=True, slots=True)
class GenerateResearchSynthesisResult:
    status: SynthesisOperationStatus
    message: str
    synthesis: ResearchSynthesis | None
    resolution: ResolutionResult
    evaluated_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "synthesis": self.synthesis.to_dict() if self.synthesis is not None else None,
            "resolution": self.resolution.to_dict(),
            "evaluated_at": self.evaluated_at.isoformat().replace("+00:00", "Z"),
            "kind": "generate_research_synthesis_result",
        }
