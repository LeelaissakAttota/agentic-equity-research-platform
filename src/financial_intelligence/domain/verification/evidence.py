"""Evidence references for verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from urllib.parse import urlparse

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.verification.claim import Claim, ClaimType

AuthorityTier = SourceAuthorityTier


class _Polarity(Enum):
    """Deterministic, best-effort polarity signal between a claim and a snippet."""

    CLEAR = "clear"  # no negation/hedge marker detected on either side
    CONFLICT = "conflict"  # exactly one side carries a negation marker
    AMBIGUOUS = "ambiguous"  # both sides negate, or a hedge marker was found


class _MatchOutcome(Enum):
    """Result of comparing a claim's expectation against one piece of evidence."""

    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"


# Fixed, explicit negation/hedge marker sets. This is NOT natural-language
# understanding: it is a bounded, testable heuristic that only recognizes a
# specific set of lexical markers. It deliberately fails toward AMBIGUOUS/CONFLICT
# rather than CLEAR whenever polarity cannot be confidently established, so that
# keyword-overlap evidence alone can never assert an agreement it has not confirmed.
_NEGATION_MARKERS = frozenset(
    {"not", "never", "no", "cannot", "neither", "nor", "denies", "denied", "false", "incorrect"}
)
_HEDGE_MARKERS = frozenset(
    {
        "may",
        "might",
        "could",
        "allegedly",
        "reportedly",
        "possibly",
        "rumored",
        "unconfirmed",
        "purportedly",
        "supposedly",
        "reputedly",
    }
)
_TOKEN_STRIP_CHARS = ".,;:!?\"'()[]{}"


def _tokenize(text: str) -> list[str]:
    return [token.strip(_TOKEN_STRIP_CHARS) for token in text.lower().split()]


def _negation_count(tokens: list[str]) -> int:
    return sum(1 for token in tokens if token in _NEGATION_MARKERS or token.endswith("n't"))


def _hedge_count(tokens: list[str]) -> int:
    return sum(1 for token in tokens if token in _HEDGE_MARKERS)


def _assess_polarity(claim_text: str, snippet: str) -> _Polarity:
    """Best-effort, deterministic polarity check for prose (non-numeric) claims.

    This has no semantic/NLU capability: it only counts a fixed set of explicit
    negation and hedge markers. Double negation, scope ambiguity, paraphrase, and
    sarcasm are known-unhandled (see F01_F02_REMEDIATION_DESIGN.md, section B.7) --
    such cases are intentionally routed to AMBIGUOUS rather than guessed at.
    """
    claim_tokens = _tokenize(claim_text)
    snippet_tokens = _tokenize(snippet)
    claim_negations = _negation_count(claim_tokens)
    snippet_negations = _negation_count(snippet_tokens)
    if claim_negations > 0 and snippet_negations > 0:
        # Both sides negate; parity (e.g. double negation) is not reliably resolvable.
        return _Polarity.AMBIGUOUS
    if claim_negations != snippet_negations:
        # Exactly one side negates the shared assertion.
        return _Polarity.CONFLICT
    if _hedge_count(claim_tokens) > 0 or _hedge_count(snippet_tokens) > 0:
        return _Polarity.AMBIGUOUS
    return _Polarity.CLEAR


def _coerce_finite_decimal(value: object) -> Decimal | None:
    """Parse a claim/evidence value into a finite Decimal, or None if not possible.

    Returns None for anything that is not a finite number: unparsable strings,
    NaN, +/-Infinity, or non-numeric types (e.g. datetime). This is the single
    normalization point numeric claim/evidence values pass through before being
    compared -- see F01_F02_REMEDIATION_DESIGN.md section A.5.
    """
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            candidate = Decimal(text)
        except InvalidOperation:
            return None
    else:
        return None
    return candidate if candidate.is_finite() else None


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Reference to a piece of supporting evidence."""

    evidence_id: str  # UUID as text
    source_id: str  # Source identifier (e.g., "SEC", "Yahoo", "NSE")
    authority_tier: AuthorityTier
    data_origin: DataOrigin
    claim_type: str  # ClaimType value
    extracted_value: str | Decimal | datetime | None = None
    extracted_unit: str | None = None
    extracted_currency: str | None = None
    extracted_period: str | None = None
    as_of: datetime | None = None
    retrieved_at: datetime = None  # type: ignore[assignment]
    raw_snippet: str = ""
    url: str | None = None

    def __post_init__(self) -> None:
        evidence_id = self.evidence_id.strip()
        if not evidence_id or len(evidence_id) > 128:
            raise ValueError("evidence_id empty or exceeds bounds")
        object.__setattr__(self, "evidence_id", evidence_id)
        source_id = self.source_id.strip()
        if not source_id or len(source_id) > 128:
            raise ValueError("source_id empty or exceeds bounds")
        object.__setattr__(self, "source_id", source_id)
        try:
            ClaimType(self.claim_type)
        except ValueError as exc:
            raise ValueError("claim_type is not recognized") from exc
        if self.retrieved_at is None:
            object.__setattr__(self, "retrieved_at", datetime.now(UTC))
        elif self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if isinstance(self.extracted_value, datetime) and self.extracted_value.tzinfo is None:
            raise ValueError("datetime extracted_value must be timezone-aware")
        snippet = " ".join(self.raw_snippet.strip().split())
        if len(snippet) > 2000:
            snippet = snippet[:2000]
        object.__setattr__(self, "raw_snippet", snippet)
        if self.url is not None:
            parsed = urlparse(self.url)
            if (
                len(self.url) > 2048
                or parsed.scheme.lower() not in {"http", "https"}
                or not parsed.hostname
            ):
                raise ValueError("url must be a bounded HTTP(S) URL")

    def supports_claim(self, claim_text: str, claim_type: ClaimType) -> bool:
        """Heuristic: does the snippet appear to support the claim?"""
        # First, check that the evidence's claim type matches the claim's claim type
        if self.claim_type != claim_type.value:
            return False
        claim_keywords = set(claim_text.lower().split())
        snippet_keywords = set(self.raw_snippet.lower().split())
        stop = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "was",
            "were",
            "are",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
        }
        claim_kw = claim_keywords - stop
        snippet_kw = snippet_keywords - stop
        if not claim_kw:
            return False
        overlap = len(claim_kw & snippet_kw)
        return overlap >= max(1, len(claim_kw) // 2)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "authority_tier": self.authority_tier.value,
            "data_origin": self.data_origin.value,
            "claim_type": self.claim_type,
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "raw_snippet": self.raw_snippet,
        }
        if self.extracted_value is not None:
            payload["extracted_value"] = str(self.extracted_value)
        if self.extracted_unit is not None:
            payload["extracted_unit"] = self.extracted_unit
        if self.extracted_currency is not None:
            payload["extracted_currency"] = self.extracted_currency
        if self.extracted_period is not None:
            payload["extracted_period"] = self.extracted_period
        if self.as_of is not None:
            payload["as_of"] = self.as_of.isoformat().replace("+00:00", "Z")
        if self.url is not None:
            payload["url"] = self.url
        return payload


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Collection of evidence references for a claim."""

    claim_id: str  # ClaimId as_text
    evidence_refs: tuple[EvidenceRef, ...]
    supporting: tuple[EvidenceRef, ...] = ()
    contradicting: tuple[EvidenceRef, ...] = ()
    neutral: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        claim_id = self.claim_id.strip()
        if not claim_id or len(claim_id) > 128:
            raise ValueError("claim_id empty or exceeds bounds")
        object.__setattr__(self, "claim_id", claim_id)
        evidence_ids = [ref.evidence_id for ref in self.evidence_refs]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate evidence_id in evidence bundle")

    @classmethod
    def classify(cls, claim: Claim, evidence_refs: tuple[EvidenceRef, ...]) -> EvidenceBundle:
        """Classify evidence as supporting, contradicting, or neutral."""
        supporting = []
        contradicting = []
        neutral = []

        for ref in evidence_refs:
            if ref.supports_claim(claim.text, claim.claim_type):
                outcome = cls._evaluate_match(claim, ref)
                if outcome is _MatchOutcome.SUPPORTING:
                    supporting.append(ref)
                elif outcome is _MatchOutcome.CONTRADICTING:
                    contradicting.append(ref)
                else:
                    neutral.append(ref)
            else:
                neutral.append(ref)

        # Handle empty evidence case - return bundle with empty evidence_refs
        # This allows unverifiable status to be tested
        return cls(
            claim_id=claim.claim_id.as_text(),
            evidence_refs=evidence_refs,
            supporting=tuple(supporting),
            contradicting=tuple(contradicting),
            neutral=tuple(neutral),
        )

    @staticmethod
    def _evaluate_match(claim: Claim, evidence_ref: EvidenceRef) -> _MatchOutcome:
        """Decide whether evidence explicitly supports, contradicts, or is inconclusive.

        Structured (typed) values are compared numerically/exactly -- never as text
        (see F01_F02_REMEDIATION_DESIGN.md section A.5). Prose claims with no
        expected value can only reach SUPPORTING when no negation/hedge signal was
        found on either side (see `_assess_polarity`); a detected polarity mismatch
        or ambiguity is routed to CONTRADICTING/NEUTRAL and can never resolve to
        VERIFIED through this path (section B.6/B.8).
        """
        if claim.expected_value is None:
            if claim.claim_type == ClaimType.NUMERIC:
                # A numeric claim with no expected value cannot be confirmed by text.
                return _MatchOutcome.CONTRADICTING
            polarity = _assess_polarity(claim.text, evidence_ref.raw_snippet)
            if polarity is _Polarity.CONFLICT:
                return _MatchOutcome.CONTRADICTING
            if polarity is _Polarity.AMBIGUOUS:
                return _MatchOutcome.NEUTRAL
            return _MatchOutcome.SUPPORTING

        if claim.claim_type == ClaimType.NUMERIC:
            expected_num = _coerce_finite_decimal(claim.expected_value)
            extracted_num = _coerce_finite_decimal(evidence_ref.extracted_value)
            if expected_num is None or extracted_num is None or expected_num != extracted_num:
                return _MatchOutcome.CONTRADICTING
            return (
                _MatchOutcome.SUPPORTING
                if EvidenceBundle._context_matches(claim, evidence_ref)
                else _MatchOutcome.CONTRADICTING
            )

        # Non-numeric claim types with an explicit expected value (e.g. DATE): preserve
        # the original bounded finiteness guard and string-normalized comparison.
        if isinstance(claim.expected_value, Decimal) and not claim.expected_value.is_finite():
            return _MatchOutcome.CONTRADICTING
        if (
            isinstance(evidence_ref.extracted_value, Decimal)
            and not evidence_ref.extracted_value.is_finite()
        ):
            return _MatchOutcome.CONTRADICTING
        comparable_types = (str, int, float, Decimal, datetime)
        if (
            evidence_ref.extracted_value is not None
            and isinstance(evidence_ref.extracted_value, comparable_types)
            and isinstance(claim.expected_value, comparable_types)
        ):
            ev_val = str(evidence_ref.extracted_value).strip().lower()
            exp_val = str(claim.expected_value).strip().lower()
            if ev_val == exp_val and EvidenceBundle._context_matches(claim, evidence_ref):
                return _MatchOutcome.SUPPORTING
        return _MatchOutcome.CONTRADICTING

    @staticmethod
    def _context_matches(claim: Claim, evidence_ref: EvidenceRef) -> bool:
        """Check unit/currency/period agreement once a value match is confirmed."""
        unit_ok = not claim.expected_unit or (
            evidence_ref.extracted_unit is not None
            and claim.expected_unit.lower() == evidence_ref.extracted_unit.lower()
        )
        currency_ok = not claim.expected_currency or (
            evidence_ref.extracted_currency is not None
            and claim.expected_currency.lower() == evidence_ref.extracted_currency.lower()
        )
        period_ok = not claim.expected_period or (
            evidence_ref.extracted_period is not None
            and claim.expected_period == evidence_ref.extracted_period
        )
        return unit_ok and currency_ok and period_ok

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "total_evidence": len(self.evidence_refs),
            "supporting": [r.to_dict() for r in self.supporting],
            "contradicting": [r.to_dict() for r in self.contradicting],
            "neutral": [r.to_dict() for r in self.neutral],
        }
