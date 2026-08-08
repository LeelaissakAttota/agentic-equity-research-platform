"""Explicit news/event conflict handling (no last-write-wins).

Authority may supersede only under documented compatible rules.
Material disagreements remain visible as CONFLICTING / UNRESOLVED.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.news.events import QualitativeEvent


class EventConflictState(StrEnum):
    """Deterministic qualitative conflict outcomes."""

    AGREES = "agrees"
    CONFLICTING = "conflicting"
    SUPERSEDED = "superseded"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class EventConflict:
    """Record of multi-source event agreement or disagreement."""

    state: EventConflictState
    candidates: tuple[QualitativeEvent, ...]
    selected: QualitativeEvent | None
    reason: str

    def __post_init__(self) -> None:
        if len(self.candidates) < 2:
            msg = "event conflict requires at least two candidates"
            raise ValueError(msg)
        if self.state is EventConflictState.UNRESOLVED and self.selected is not None:
            msg = "unresolved conflicts must not select an event"
            raise ValueError(msg)
        if self.state is EventConflictState.CONFLICTING and self.selected is not None:
            msg = "conflicting state must not select a single winner"
            raise ValueError(msg)
        if self.state is EventConflictState.AGREES and self.selected is None:
            msg = "agrees requires a selected event"
            raise ValueError(msg)
        if self.state is EventConflictState.SUPERSEDED and self.selected is None:
            msg = "superseded groups require a selected surviving event"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "reason": self.reason,
            "selected_event_id": (
                self.selected.event_id.as_text() if self.selected is not None else None
            ),
            "candidate_event_ids": [e.event_id.as_text() for e in self.candidates],
            "kind": "event_conflict",
        }


def material_fingerprint(event: QualitativeEvent) -> tuple[str, str, str | None]:
    """Comparable material fields for agreement detection (deterministic)."""

    return (
        event.summary.casefold(),
        event.information_class.value,
        event.sentiment_label,
    )


def _soft_key(event: QualitativeEvent) -> tuple[str, str, str]:
    """Company + type + title without date — surfaces date disagreements."""

    return (
        event.company_id.as_text(),
        event.event_type.value,
        event.title.casefold(),
    )


def _pick_by_authority(events: Sequence[QualitativeEvent]) -> QualitativeEvent:
    """Prefer higher authority (lower tier int), then earlier retrieval, then event_id."""

    return sorted(
        events,
        key=lambda e: (
            int(e.evidence.authority_tier),
            e.evidence.retrieved_at,
            e.event_id.as_text(),
        ),
    )[0]


def resolve_exact_dedupe_group(candidates: Sequence[QualitativeEvent]) -> EventConflict:
    """Resolve events that share an exact dedupe key (company/type/date/title)."""

    if len(candidates) < 2:
        msg = "resolve_exact_dedupe_group requires at least two candidates"
        raise ValueError(msg)
    first = candidates[0]
    if any(c.dedupe_key() != first.dedupe_key() for c in candidates):
        msg = "candidates must share an exact dedupe key"
        raise ValueError(msg)

    fingerprints = {material_fingerprint(c) for c in candidates}
    if len(fingerprints) == 1:
        selected = _pick_by_authority(candidates)
        return EventConflict(
            state=EventConflictState.AGREES,
            candidates=tuple(candidates),
            selected=selected,
            reason=(
                "exact duplicates agree on material fields; "
                "higher authority / earlier retrieval wins"
            ),
        )

    by_tier: dict[int, list[QualitativeEvent]] = {}
    for event in candidates:
        by_tier.setdefault(int(event.evidence.authority_tier), []).append(event)
    best_tier = min(by_tier)
    best = by_tier[best_tier]
    best_fps = {material_fingerprint(e) for e in best}
    if len(best_fps) == 1 and len(by_tier) > 1:
        selected = _pick_by_authority(best)
        return EventConflict(
            state=EventConflictState.SUPERSEDED,
            candidates=tuple(candidates),
            selected=selected,
            reason=(
                "unique higher-authority tier agrees internally; "
                "lower-authority duplicates are superseded"
            ),
        )

    return EventConflict(
        state=EventConflictState.UNRESOLVED,
        candidates=tuple(candidates),
        selected=None,
        reason=(
            "material disagreement without a unique higher-authority agreeing winner; "
            "authority alone does not erase the contradiction"
        ),
    )


def detect_soft_date_conflicts(
    events: Sequence[QualitativeEvent],
) -> tuple[EventConflict, ...]:
    """Flag same company/type/title with disagreeing event dates."""

    buckets: dict[tuple[str, str, str], list[QualitativeEvent]] = {}
    for event in events:
        buckets.setdefault(_soft_key(event), []).append(event)

    conflicts: list[EventConflict] = []
    for group in buckets.values():
        if len(group) < 2:
            continue
        dates = {e.event_date for e in group}
        if len(dates) <= 1:
            continue
        conflicts.append(
            EventConflict(
                state=EventConflictState.CONFLICTING,
                candidates=tuple(group),
                selected=None,
                reason="same company/type/title reported with conflicting event dates",
            )
        )
    return tuple(conflicts)


def process_events(
    events: Sequence[QualitativeEvent],
) -> tuple[tuple[QualitativeEvent, ...], tuple[EventConflict, ...]]:
    """Deduplicate with explicit conflict records.

    - Exact-key AGREES / SUPERSEDED → keep selected only.
    - Exact-key UNRESOLVED → keep all candidates visible.
    - Soft-key date CONFLICTING → keep all; attach conflict record.
    Output order: event_date desc, title asc, event_id asc.
    """

    exact_buckets: dict[tuple[str, str, str, str], list[QualitativeEvent]] = {}
    for event in events:
        exact_buckets.setdefault(event.dedupe_key(), []).append(event)

    survivors: list[QualitativeEvent] = []
    conflicts: list[EventConflict] = []

    for group in exact_buckets.values():
        if len(group) == 1:
            survivors.append(group[0])
            continue
        conflict = resolve_exact_dedupe_group(group)
        conflicts.append(conflict)
        if conflict.selected is not None:
            survivors.append(conflict.selected)
        else:
            survivors.extend(group)

    soft_conflicts = detect_soft_date_conflicts(survivors)
    conflicts.extend(soft_conflicts)

    ordered = _order_events(survivors)
    return ordered, tuple(conflicts)


def _order_events(events: Sequence[QualitativeEvent]) -> tuple[QualitativeEvent, ...]:
    by_date: dict[str, list[QualitativeEvent]] = {}
    for event in events:
        by_date.setdefault(event.event_date.isoformat(), []).append(event)
    result: list[QualitativeEvent] = []
    for day in sorted(by_date.keys(), reverse=True):
        day_events = sorted(
            by_date[day],
            key=lambda e: (e.title.casefold(), e.event_id.as_text()),
        )
        result.extend(day_events)
    return tuple(result)
