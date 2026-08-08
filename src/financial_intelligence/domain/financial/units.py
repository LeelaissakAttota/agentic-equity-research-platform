"""Units and scale for financial facts."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class FinancialUnit(StrEnum):
    """Unit of measure for a financial fact."""

    CURRENCY = "currency"
    SHARES = "shares"
    PER_SHARE = "per_share"
    RATIO = "ratio"
    PERCENT = "percent"


class FinancialScale(IntEnum):
    """Magnitude multiplier applied to ``raw_value`` to obtain ``normalized_value``.

    Example: scale=MILLIONS and raw_value=383 means normalized=383_000_000.
    """

    ONES = 1
    THOUSANDS = 1_000
    MILLIONS = 1_000_000
    BILLIONS = 1_000_000_000
