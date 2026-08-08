"""Shared data-origin vocabulary for acquired structured/qualitative packages.

Consumers must distinguish fixture/demo data from live/authoritative acquisition.
Data origin is independent of source authority tier.
"""

from __future__ import annotations

from enum import StrEnum


class DataOrigin(StrEnum):
    """Explicit origin of acquired structured data (never conflate fixture with live)."""

    LIVE = "live"
    CACHED_LIVE = "cached_live"
    FIXTURE = "fixture"
    UNAVAILABLE = "unavailable"
