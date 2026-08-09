"""Evidence references for verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.verification.claim import Claim, ClaimType

AuthorityTier = SourceAuthorityTier


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
                # Check if the value matches (and unit, currency, period if applicable)
                if cls._values_match(claim, ref):
                    supporting.append(ref)
                else:
                    contradicting.append(ref)
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
    def _values_match(claim: Claim, evidence_ref: EvidenceRef) -> bool:
        """Check if evidence explicitly supports the claim by matching values."""
        # If expected_value is None, we only match for non-numeric claims (text already matched)
        if claim.expected_value is None:
            # For non-numeric claims, we rely on text matching only
            return claim.claim_type != ClaimType.NUMERIC

        if isinstance(claim.expected_value, Decimal) and not claim.expected_value.is_finite():
            return False
        if (
            isinstance(evidence_ref.extracted_value, Decimal)
            and not evidence_ref.extracted_value.is_finite()
        ):
            return False

        # Only check for explicit support when we have extracted values to compare
        comparable_types = (str, int, float, Decimal, datetime)
        if (
            evidence_ref.extracted_value is not None
            and isinstance(evidence_ref.extracted_value, comparable_types)
            and isinstance(claim.expected_value, comparable_types)
        ):
            # Normalize for comparison
            ev_val = str(evidence_ref.extracted_value).strip().lower()
            exp_val = str(claim.expected_value).strip().lower()

            # If values match, check units, currency, and period
            if ev_val == exp_val:
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

        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "total_evidence": len(self.evidence_refs),
            "supporting": [r.to_dict() for r in self.supporting],
            "contradicting": [r.to_dict() for r in self.contradicting],
            "neutral": [r.to_dict() for r in self.neutral],
        }
