"""Explicit multi-source financial fact conflict handling.

Never silently choose a value solely because it arrived last.
Authority-tier resolution is explicit and testable; otherwise conflicts are exposed.

Compatible measurement basis is required before value agreement can resolve a conflict:
unit, currency, and exact reporting period must match. Numeric coincidence across
incompatible bases is never treated as agreement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.financial.concepts import FinancialConcept
from financial_intelligence.domain.financial.facts import FinancialFact
from financial_intelligence.domain.financial.periods import ReportingPeriod
from financial_intelligence.domain.identity import CompanyId


class ConflictResolutionRule(StrEnum):
    """Deterministic conflict outcomes (never silent last-write-wins)."""

    VALUES_AGREE = "values_agree"
    HIGHER_AUTHORITY_TIER = "higher_authority_tier"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class FinancialFactConflict:
    """Two or more candidate facts for the same concept/period/company."""

    company_id: CompanyId
    concept: FinancialConcept
    period: ReportingPeriod
    candidates: tuple[FinancialFact, ...]
    resolution_rule: ConflictResolutionRule
    selected: FinancialFact | None
    detail: str

    def __post_init__(self) -> None:
        if len(self.candidates) < 2:
            msg = "conflict requires at least two candidate facts"
            raise ValueError(msg)
        for fact in self.candidates:
            if fact.company_id != self.company_id:
                msg = "candidate company_id mismatch"
                raise ValueError(msg)
            if fact.concept is not self.concept:
                msg = "candidate concept mismatch"
                raise ValueError(msg)
            # Label grouping is the conflict key; exact period equality is enforced
            # by resolve_fact_conflict before selecting a winner.
            if fact.period.display_label() != self.period.display_label():
                msg = "candidate period label mismatch"
                raise ValueError(msg)
        if self.resolution_rule is ConflictResolutionRule.UNRESOLVED and self.selected is not None:
            msg = "unresolved conflicts must not select a fact"
            raise ValueError(msg)
        if self.resolution_rule is not ConflictResolutionRule.UNRESOLVED and self.selected is None:
            msg = "resolved conflicts require a selected fact"
            raise ValueError(msg)
        if self.resolution_rule is not ConflictResolutionRule.UNRESOLVED:
            for fact in self.candidates:
                if fact.period != self.period:
                    msg = "resolved conflicts require exact period equality"
                    raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "company_id": self.company_id.as_text(),
            "concept": self.concept.value,
            "period": self.period.to_dict(),
            "resolution_rule": self.resolution_rule.value,
            "selected_source_id": (
                self.selected.source_id.as_text() if self.selected is not None else None
            ),
            "selected_authority_tier": (
                int(self.selected.authority_tier) if self.selected is not None else None
            ),
            "detail": self.detail,
            "candidates": [
                {
                    "source_id": fact.source_id.as_text(),
                    "authority_tier": int(fact.authority_tier),
                    "filing_id": fact.filing_id.as_text() if fact.filing_id else None,
                    "retrieved_at": fact.retrieved_at.isoformat().replace("+00:00", "Z"),
                    "normalized_value": str(fact.normalized_value),
                    "currency": fact.currency.as_text() if fact.currency else None,
                    "unit": fact.unit.value,
                    "scale": int(fact.scale),
                    "provider_concept": fact.provider_concept,
                }
                for fact in self.candidates
            ],
            "kind": "financial_fact_conflict",
        }


def _conflict_key(fact: FinancialFact) -> tuple[str, str, str]:
    return (fact.company_id.as_text(), fact.concept.value, fact.period.display_label())


def resolve_fact_conflict(candidates: Sequence[FinancialFact]) -> FinancialFactConflict:
    """Apply explicit authority rules; expose unresolved disagreements.

    Never resolves by retrieval timestamp alone. Never treats numeric coincidence
    across mismatched unit/currency/exact-period as agreement.
    """

    if len(candidates) < 2:
        msg = "resolve_fact_conflict requires at least two candidates"
        raise ValueError(msg)
    first = candidates[0]
    for fact in candidates[1:]:
        if _conflict_key(fact) != _conflict_key(first):
            msg = "candidates must share company, concept, and period label"
            raise ValueError(msg)

    ordered = tuple(candidates)
    units = {fact.unit for fact in ordered}
    currencies = {fact.currency for fact in ordered}
    periods_equal = all(fact.period == first.period for fact in ordered)
    if len(units) > 1 or len(currencies) > 1 or not periods_equal:
        reasons: list[str] = []
        if len(units) > 1:
            reasons.append("unit mismatch")
        if len(currencies) > 1:
            reasons.append("currency mismatch")
        if not periods_equal:
            reasons.append("exact period mismatch")
        return FinancialFactConflict(
            company_id=first.company_id,
            concept=first.concept,
            period=first.period,
            candidates=ordered,
            resolution_rule=ConflictResolutionRule.UNRESOLVED,
            selected=None,
            detail=(
                f"{', '.join(reasons)}; not resolved by numeric coincidence or retrieval order"
            ),
        )

    values = {fact.normalized_value for fact in ordered}
    if len(values) == 1:
        selected = min(ordered, key=lambda f: (int(f.authority_tier),))
        return FinancialFactConflict(
            company_id=first.company_id,
            concept=first.concept,
            period=first.period,
            candidates=ordered,
            resolution_rule=ConflictResolutionRule.VALUES_AGREE,
            selected=selected,
            detail="candidate normalized values agree; higher authority tier preferred on ties",
        )

    tiers = {int(fact.authority_tier) for fact in ordered}
    if len(tiers) > 1:
        best_tier = min(tiers)
        winners = [fact for fact in ordered if int(fact.authority_tier) == best_tier]
        winner_values = {fact.normalized_value for fact in winners}
        if len(winner_values) == 1:
            selected = winners[0]
            return FinancialFactConflict(
                company_id=first.company_id,
                concept=first.concept,
                period=first.period,
                candidates=ordered,
                resolution_rule=ConflictResolutionRule.HIGHER_AUTHORITY_TIER,
                selected=selected,
                detail=(
                    f"selected tier-{best_tier} authoritative value; "
                    "lower-authority disagreeing candidates retained for audit"
                ),
            )

    return FinancialFactConflict(
        company_id=first.company_id,
        concept=first.concept,
        period=first.period,
        candidates=ordered,
        resolution_rule=ConflictResolutionRule.UNRESOLVED,
        selected=None,
        detail=(
            "conflicting normalized values without a unique higher-authority winner; "
            "not silently resolved by retrieval order"
        ),
    )


def detect_fact_conflicts(
    facts: Sequence[FinancialFact],
) -> tuple[tuple[FinancialFact, ...], tuple[FinancialFactConflict, ...]]:
    """Group facts by company/concept/period; return survivors plus explicit conflicts.

    Survivors exclude members of UNRESOLVED conflicts. Resolved conflicts contribute
    only the selected fact.
    """

    buckets: dict[tuple[str, str, str], list[FinancialFact]] = {}
    for fact in facts:
        buckets.setdefault(_conflict_key(fact), []).append(fact)

    survivors: list[FinancialFact] = []
    conflicts: list[FinancialFactConflict] = []
    for group in buckets.values():
        if len(group) == 1:
            survivors.append(group[0])
            continue
        conflict = resolve_fact_conflict(group)
        conflicts.append(conflict)
        if conflict.selected is not None:
            survivors.append(conflict.selected)
    return tuple(survivors), tuple(conflicts)
