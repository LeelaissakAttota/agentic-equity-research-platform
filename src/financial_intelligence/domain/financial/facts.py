"""Canonical financial facts with units, scale, and provenance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from financial_intelligence.domain.financial.concepts import FinancialConcept
from financial_intelligence.domain.financial.filings import FilingId
from financial_intelligence.domain.financial.periods import ReportingPeriod
from financial_intelligence.domain.financial.units import FinancialScale, FinancialUnit
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId


def _require_finite_decimal(label: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        msg = f"{label} must be Decimal"
        raise TypeError(msg)
    if value.is_nan() or value.is_infinite():
        msg = f"{label} must be a finite Decimal"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class FinancialFact:
    """One provider-neutral financial fact.

    Missing fact ≠ zero: absence is represented by omitting the concept from
    a statement package, never by inventing a zero fact.
    """

    company_id: CompanyId
    concept: FinancialConcept
    period: ReportingPeriod
    raw_value: Decimal
    normalized_value: Decimal
    unit: FinancialUnit
    scale: FinancialScale
    source_id: SourceId
    authority_tier: SourceAuthorityTier
    retrieved_at: datetime
    currency: CurrencyCode | None = None
    filing_id: FilingId | None = None
    provider_concept: str | None = None

    def __post_init__(self) -> None:
        _require_finite_decimal("raw_value", self.raw_value)
        _require_finite_decimal("normalized_value", self.normalized_value)
        if self.retrieved_at.tzinfo is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        expected = self.raw_value * Decimal(int(self.scale))
        if expected != self.normalized_value:
            msg = "normalized_value must equal raw_value * scale"
            raise ValueError(msg)
        if self.unit is FinancialUnit.CURRENCY and self.currency is None:
            msg = "currency unit requires currency"
            raise ValueError(msg)
        if self.unit is FinancialUnit.PER_SHARE and self.currency is None:
            msg = "per_share unit requires currency"
            raise ValueError(msg)
        if self.unit is FinancialUnit.SHARES and self.currency is not None:
            msg = "shares unit must not carry currency"
            raise ValueError(msg)
        if self.unit in {FinancialUnit.RATIO, FinancialUnit.PERCENT} and self.currency is not None:
            msg = "ratio/percent units must not carry currency"
            raise ValueError(msg)
        if self.provider_concept is not None:
            cleaned = self.provider_concept.strip()
            if len(cleaned) > 128:
                msg = "provider_concept exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "provider_concept", cleaned or None)

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "concept": self.concept.value,
            "period": self.period.to_dict(),
            "raw_value": str(self.raw_value),
            "normalized_value": str(self.normalized_value),
            "unit": self.unit.value,
            "scale": int(self.scale),
            "currency": self.currency.as_text() if self.currency else None,
            "source_id": self.source_id.as_text(),
            "authority_tier": int(self.authority_tier),
            "filing_id": self.filing_id.as_text() if self.filing_id else None,
            "retrieved_at": self.retrieved_at.isoformat().replace("+00:00", "Z"),
            "provider_concept": self.provider_concept,
            "kind": "financial_fact",
        }


def build_fact(
    *,
    company_id: CompanyId,
    concept: FinancialConcept,
    period: ReportingPeriod,
    raw_value: Decimal | str,
    unit: FinancialUnit,
    scale: FinancialScale,
    source_id: SourceId,
    authority_tier: SourceAuthorityTier,
    retrieved_at: datetime,
    currency: CurrencyCode | None = None,
    filing_id: FilingId | None = None,
    provider_concept: str | None = None,
) -> FinancialFact:
    """Construct a fact with normalized_value = raw_value * scale."""

    raw = raw_value if isinstance(raw_value, Decimal) else Decimal(raw_value)
    return FinancialFact(
        company_id=company_id,
        concept=concept,
        period=period,
        raw_value=raw,
        normalized_value=raw * Decimal(int(scale)),
        unit=unit,
        scale=scale,
        source_id=source_id,
        authority_tier=authority_tier,
        retrieved_at=retrieved_at,
        currency=currency,
        filing_id=filing_id,
        provider_concept=provider_concept,
    )
