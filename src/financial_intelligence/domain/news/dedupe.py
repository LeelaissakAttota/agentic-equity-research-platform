"""Deterministic event deduplication and ordering (no LLM)."""

from __future__ import annotations

from collections.abc import Sequence

from financial_intelligence.domain.news.conflicts import EventConflict, process_events
from financial_intelligence.domain.news.events import QualitativeEvent
from financial_intelligence.domain.sources import SourceAuthorityTier


def deduplicate_events(events: Sequence[QualitativeEvent]) -> tuple[QualitativeEvent, ...]:
    """Collapse exact duplicates with authority preference; expose survivors only.

    For conflict-aware processing that retains UNRESOLVED duplicates and conflict
    records, use ``process_events``.
    """

    survivors, _conflicts = process_events(events)
    return survivors


def deduplicate_events_with_conflicts(
    events: Sequence[QualitativeEvent],
) -> tuple[tuple[QualitativeEvent, ...], tuple[EventConflict, ...]]:
    """Return survivors plus explicit conflict records (never last-write-wins)."""

    return process_events(events)


def tier_may_override(lower: SourceAuthorityTier, higher: SourceAuthorityTier) -> bool:
    """True when ``higher`` (lower numeric tier) may outrank ``lower``."""

    return int(higher) < int(lower)
