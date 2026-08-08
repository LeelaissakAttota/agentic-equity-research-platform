"""Phase 6 orchestration domain — research request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from financial_intelligence.domain.identity import (
    MAX_QUERY_LENGTH,
    CountryCode,
    ExchangeCode,
    TickerSymbol,
)
from financial_intelligence.domain.orchestration.objectives import ResearchObjective
from financial_intelligence.domain.research_run import ResearchRunId

_OBJECTIVE_TEXT_MAX = 512


def _reject_control_chars(value: str, field: str) -> str:
    if any(ord(ch) < 32 for ch in value):
        msg = f"{field} must not contain control characters"
        raise ValueError(msg)
    return value


@dataclass(frozen=True, slots=True)
class RequestId:
    """Opaque research-request identity (UUIDv4)."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "request_id must be a UUIDv4"
            raise ValueError(msg)

    @classmethod
    def new(cls) -> RequestId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> RequestId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    """Framework-independent research planning request (untrusted user data)."""

    request_id: RequestId
    research_run_id: ResearchRunId
    objective: ResearchObjective
    raw_query: str
    created_at: datetime
    country: CountryCode | None = None
    exchange: ExchangeCode | None = None
    ticker: TickerSymbol | None = None
    objective_text: str | None = None
    jurisdiction: str | None = None
    time_horizon_days: int | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            msg = "created_at must be timezone-aware"
            raise ValueError(msg)
        raw = _reject_control_chars(self.raw_query, "raw_query")
        if not raw.strip() and self.ticker is None:
            msg = "raw_query empty unless ticker is provided"
            raise ValueError(msg)
        if len(raw) > MAX_QUERY_LENGTH:
            msg = f"raw_query exceeds {MAX_QUERY_LENGTH} characters"
            raise ValueError(msg)
        object.__setattr__(self, "raw_query", raw)
        if self.objective_text is not None:
            text = _reject_control_chars(self.objective_text, "objective_text").strip()
            if not text or len(text) > _OBJECTIVE_TEXT_MAX:
                msg = "objective_text empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "objective_text", text)
        if self.jurisdiction is not None:
            jur = self.jurisdiction.strip().upper()
            if len(jur) != 2:
                msg = "jurisdiction must be ISO alpha-2 when set"
                raise ValueError(msg)
            object.__setattr__(self, "jurisdiction", jur)
        if self.time_horizon_days is not None and (
            self.time_horizon_days < 1 or self.time_horizon_days > 3650
        ):
            msg = "time_horizon_days must be between 1 and 3650"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id.as_text(),
            "research_run_id": self.research_run_id.as_text(),
            "objective": self.objective.value,
            "raw_query": self.raw_query,
            "country": self.country.as_text() if self.country else None,
            "exchange": self.exchange.as_text() if self.exchange else None,
            "ticker": self.ticker.as_text() if self.ticker else None,
            "objective_text": self.objective_text,
            "jurisdiction": self.jurisdiction,
            "time_horizon_days": self.time_horizon_days,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "kind": "research_request",
        }
