"""Company resolution application contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.identity import (
    MAX_QUERY_LENGTH,
    CompanyIdentity,
    CountryCode,
    ExchangeCode,
    ListingIdentity,
    TickerSymbol,
)


class ResolutionStatus(StrEnum):
    """First-class resolution outcomes; ambiguity is never silently guessed."""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"


class MatchMethod(StrEnum):
    """Deterministic match quality labels (not calibrated probabilities)."""

    EXACT_CANONICAL_ID = "exact_canonical_id"
    EXACT_TICKER_EXCHANGE = "exact_ticker_exchange"
    EXACT_TICKER = "exact_ticker"
    EXACT_ALIAS = "exact_alias"
    EXACT_NORMALIZED_NAME = "exact_normalized_name"
    FUZZY_CANDIDATE = "fuzzy_candidate"
    NONE = "none"
    INVALID_INPUT = "invalid_input"


class ConfidenceBand(StrEnum):
    """Bounded confidence vocabulary aligned with MatchMethod semantics.

    These bands describe deterministic match quality only. They are not
    scientifically calibrated probabilities.
    """

    EXACT = "exact"
    STRONG = "strong"
    CANDIDATE = "candidate"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class CompanyQuery:
    """Untrusted company-resolution input."""

    raw_query: str
    country: CountryCode | None = None
    exchange: ExchangeCode | None = None
    ticker: TickerSymbol | None = None

    def __post_init__(self) -> None:
        # Preserve raw text for diagnostics; length bound enforced by use case.
        object.__setattr__(self, "raw_query", self.raw_query)


@dataclass(frozen=True, slots=True)
class ResolutionCandidate:
    """One structured candidate identity with match provenance."""

    company: CompanyIdentity
    matched_by: MatchMethod
    confidence: ConfidenceBand
    matched_listings: tuple[ListingIdentity, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "company": self.company.to_dict(),
            "matched_by": self.matched_by.value,
            "confidence": self.confidence.value,
            "matched_listings": [listing.to_dict() for listing in self.matched_listings],
        }


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Structured company-resolution outcome."""

    query: CompanyQuery
    status: ResolutionStatus
    matched_by: MatchMethod
    confidence: ConfidenceBand
    company: CompanyIdentity | None = None
    candidates: tuple[ResolutionCandidate, ...] = ()
    message: str = ""
    normalized_query: str = ""

    def __post_init__(self) -> None:
        if self.status is ResolutionStatus.RESOLVED:
            if self.company is None or len(self.candidates) != 1:
                msg = "RESOLVED requires exactly one company candidate"
                raise ValueError(msg)
            if self.confidence is ConfidenceBand.CANDIDATE:
                msg = "RESOLVED cannot use candidate confidence"
                raise ValueError(msg)
        elif self.status is ResolutionStatus.AMBIGUOUS:
            if self.company is not None:
                msg = "AMBIGUOUS must not set a definitive company"
                raise ValueError(msg)
            if not self.candidates:
                msg = "AMBIGUOUS requires candidates"
                raise ValueError(msg)
        elif self.status in {ResolutionStatus.NOT_FOUND, ResolutionStatus.INVALID}:
            if self.company is not None or self.candidates:
                msg = f"{self.status.value} must not carry resolved identity data"
                raise ValueError(msg)
            if self.confidence is not ConfidenceBand.NONE:
                msg = f"{self.status.value} confidence must be none"
                raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "query": {
                "raw_query": self.query.raw_query,
                "country": self.query.country.as_text() if self.query.country else None,
                "exchange": self.query.exchange.as_text() if self.query.exchange else None,
                "ticker": self.query.ticker.as_text() if self.query.ticker else None,
            },
            "status": self.status.value,
            "matched_by": self.matched_by.value,
            "confidence": self.confidence.value,
            "normalized_query": self.normalized_query,
            "message": self.message,
            "company": self.company.to_dict() if self.company is not None else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def confidence_for(method: MatchMethod) -> ConfidenceBand:
    """Map match method to a bounded confidence band."""

    if method in {
        MatchMethod.EXACT_CANONICAL_ID,
        MatchMethod.EXACT_TICKER_EXCHANGE,
        MatchMethod.EXACT_TICKER,
        MatchMethod.EXACT_ALIAS,
        MatchMethod.EXACT_NORMALIZED_NAME,
    }:
        return ConfidenceBand.EXACT
    if method is MatchMethod.FUZZY_CANDIDATE:
        return ConfidenceBand.CANDIDATE
    return ConfidenceBand.NONE


# Re-export bound for API/use-case validation without inventing a second constant.
QUERY_MAX_LENGTH = MAX_QUERY_LENGTH
