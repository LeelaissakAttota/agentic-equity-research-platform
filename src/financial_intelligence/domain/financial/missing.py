"""Explicit missing-data semantics for financial responses.

Missing must never become 0 / 0.0 / fabricated certainty.
"""

from __future__ import annotations

from enum import StrEnum


class MissingDataSemantics(StrEnum):
    """Why a financial fact or derived metric is absent from a response."""

    UNAVAILABLE = "unavailable"
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    PARTIAL = "partial"
    INCOMPARABLE_PERIOD = "incomparable_period"
    UNIT_MISMATCH = "unit_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    ZERO_DENOMINATOR = "zero_denominator"
    INVALID_INPUT = "invalid_input"
