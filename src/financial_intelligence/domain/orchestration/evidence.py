"""Deterministic evidence-reference aggregation for orchestration runs."""

from __future__ import annotations

from financial_intelligence.domain.orchestration.results import TaskEvidenceRef


def evidence_dedupe_key(ref: TaskEvidenceRef) -> tuple[object, ...]:
    """Stable key for evidence deduplication (never upgrades tiers/origins)."""

    def _s(value: object | None) -> str:
        return "" if value is None else str(value)

    return (
        ref.company_id.as_text(),
        _s(ref.source_id.as_text() if ref.source_id is not None else None),
        _s(int(ref.authority_tier) if ref.authority_tier is not None else None),
        _s(ref.data_origin.value if ref.data_origin is not None else None),
        _s(ref.security_id.as_text() if ref.security_id is not None else None),
        _s(ref.listing_id.as_text() if ref.listing_id is not None else None),
        _s(ref.as_of.isoformat() if ref.as_of is not None else None),
        _s(ref.retrieved_at.isoformat() if ref.retrieved_at is not None else None),
        _s(ref.locator),
    )


def dedupe_evidence_refs(refs: tuple[TaskEvidenceRef, ...]) -> tuple[TaskEvidenceRef, ...]:
    """Deduplicate evidence refs with stable sort order."""

    seen: set[tuple[object, ...]] = set()
    unique: list[TaskEvidenceRef] = []
    for ref in sorted(refs, key=evidence_dedupe_key):
        key = evidence_dedupe_key(ref)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return tuple(unique)
