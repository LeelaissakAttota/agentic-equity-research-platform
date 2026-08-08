"""Reporting-period semantics for financial facts and statements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class PeriodBasis(StrEnum):
    """Temporal basis of a reporting period."""

    FISCAL_YEAR = "fy"
    FISCAL_QUARTER = "quarter"
    YEAR_TO_DATE = "ytd"
    INSTANT = "instant"


class PeriodIncomparabilityReason(StrEnum):
    """Explainable reason when two reporting periods must not be compared."""

    BASIS_MISMATCH = "basis_mismatch"
    INSTANT_NOT_COMPARABLE = "instant_not_comparable"
    QUARTER_MISMATCH = "quarter_mismatch"
    DURATION_MISMATCH = "duration_mismatch"
    MISSING_DURATION = "missing_duration"


# Allow small calendar drift between fiscal year ends (e.g. 52/53-week years).
_MAX_DURATION_DRIFT_DAYS = 8


@dataclass(frozen=True, slots=True)
class ReportingPeriod:
    """Explicit reporting period — incompatible periods must not be compared silently."""

    basis: PeriodBasis
    fiscal_year: int
    period_end: date
    period_start: date | None = None
    fiscal_quarter: int | None = None
    as_of: date | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if self.fiscal_year < 1900 or self.fiscal_year > 2100:
            msg = "fiscal_year out of supported bounds"
            raise ValueError(msg)
        if self.fiscal_quarter is not None and self.fiscal_quarter not in {1, 2, 3, 4}:
            msg = "fiscal_quarter must be 1..4 when set"
            raise ValueError(msg)
        if self.basis is PeriodBasis.FISCAL_QUARTER and self.fiscal_quarter is None:
            msg = "quarter basis requires fiscal_quarter"
            raise ValueError(msg)
        if self.basis is PeriodBasis.INSTANT:
            if self.as_of is None:
                msg = "instant basis requires as_of"
                raise ValueError(msg)
            if self.period_start is not None:
                msg = "instant basis must not set period_start"
                raise ValueError(msg)
        elif self.basis in {
            PeriodBasis.FISCAL_YEAR,
            PeriodBasis.FISCAL_QUARTER,
            PeriodBasis.YEAR_TO_DATE,
        }:
            if self.period_start is None:
                msg = f"{self.basis.value} basis requires period_start"
                raise ValueError(msg)
            if self.period_start > self.period_end:
                msg = "period_start must be <= period_end"
                raise ValueError(msg)
        if self.label is not None:
            cleaned = self.label.strip()
            if not cleaned or len(cleaned) > 64:
                msg = "period label empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "label", cleaned)

    def duration_days(self) -> int | None:
        """Inclusive duration in calendar days for duration-based periods."""

        if self.basis is PeriodBasis.INSTANT or self.period_start is None:
            return None
        return (self.period_end - self.period_start).days + 1

    def incomparability_reason(self, other: ReportingPeriod) -> PeriodIncomparabilityReason | None:
        """Return why ``other`` is not comparable, or None when comparison is safe."""

        if self.basis is PeriodBasis.INSTANT or other.basis is PeriodBasis.INSTANT:
            return PeriodIncomparabilityReason.INSTANT_NOT_COMPARABLE
        if self.basis != other.basis:
            return PeriodIncomparabilityReason.BASIS_MISMATCH
        if self.basis is PeriodBasis.FISCAL_QUARTER and self.fiscal_quarter != other.fiscal_quarter:
            return PeriodIncomparabilityReason.QUARTER_MISMATCH
        left = self.duration_days()
        right = other.duration_days()
        if left is None or right is None:
            return PeriodIncomparabilityReason.MISSING_DURATION
        if abs(left - right) > _MAX_DURATION_DRIFT_DAYS:
            return PeriodIncomparabilityReason.DURATION_MISMATCH
        return None

    def is_comparable_to(self, other: ReportingPeriod) -> bool:
        """True when growth/margin cross-period math is semantically safe."""

        return self.incomparability_reason(other) is None

    def selection_key(self) -> tuple[object, ...]:
        """Deterministic ordering key: prefer later period_end, then fiscal year."""

        return (self.period_end, self.fiscal_year, self.basis.value, self.fiscal_quarter or 0)

    def display_label(self) -> str:
        if self.label:
            return self.label
        if self.basis is PeriodBasis.FISCAL_YEAR:
            return f"FY{self.fiscal_year}"
        if self.basis is PeriodBasis.FISCAL_QUARTER:
            return f"FY{self.fiscal_year}Q{self.fiscal_quarter}"
        if self.basis is PeriodBasis.YEAR_TO_DATE:
            return f"FY{self.fiscal_year}YTD"
        return f"INSTANT:{self.as_of.isoformat() if self.as_of else self.period_end.isoformat()}"

    def to_dict(self) -> dict[str, object]:
        return {
            "basis": self.basis.value,
            "fiscal_year": self.fiscal_year,
            "fiscal_quarter": self.fiscal_quarter,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat(),
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "label": self.display_label(),
            "duration_days": self.duration_days(),
        }
