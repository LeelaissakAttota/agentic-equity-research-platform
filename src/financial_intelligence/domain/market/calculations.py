"""Deterministic market calculation library (ADR-017).

Formulas are explicit and versioned. LLMs must not perform these calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from financial_intelligence.domain.market.observations import OhlcvBar

CALCULATION_LIBRARY_VERSION = "market-calc-1"
_MONEY = Decimal("0.0001")
_RATIO = Decimal("0.000001")


class MetricName(StrEnum):
    """Supported Phase 3 Prompt 1 market metrics."""

    LAST_CLOSE = "last_close"
    ADJUSTED_LAST_CLOSE = "adjusted_last_close"
    SIMPLE_RETURN = "simple_return"
    SMA = "sma"
    VOLUME_SUM = "volume_sum"


@dataclass(frozen=True, slots=True)
class MarketMetric:
    """One reproducible calculated market figure with formula identity."""

    name: MetricName
    value: Decimal
    unit: str
    formula_version: str
    window: int | None = None
    inputs_as_of: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "value": str(self.value),
            "unit": self.unit,
            "formula_version": self.formula_version,
            "window": self.window,
            "inputs_as_of": self.inputs_as_of,
        }


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def last_close(bars: tuple[OhlcvBar, ...]) -> MarketMetric:
    if not bars:
        msg = "last_close requires at least one bar"
        raise ValueError(msg)
    bar = bars[-1]
    return MarketMetric(
        name=MetricName.LAST_CLOSE,
        value=_quantize(bar.close, _MONEY),
        unit=bar.currency.as_text(),
        formula_version=f"{CALCULATION_LIBRARY_VERSION}:last_close=close[-1]",
        inputs_as_of=bar.session_date.isoformat(),
    )


def adjusted_last_close(bars: tuple[OhlcvBar, ...]) -> MarketMetric:
    if not bars:
        msg = "adjusted_last_close requires at least one bar"
        raise ValueError(msg)
    bar = bars[-1]
    return MarketMetric(
        name=MetricName.ADJUSTED_LAST_CLOSE,
        value=_quantize(bar.adjusted_close, _MONEY),
        unit=bar.currency.as_text(),
        formula_version=(
            f"{CALCULATION_LIBRARY_VERSION}:adjusted_last_close=close[-1]*adjustment_factor[-1]"
        ),
        inputs_as_of=bar.session_date.isoformat(),
    )


def simple_return(bars: tuple[OhlcvBar, ...]) -> MarketMetric:
    """Simple return as a **ratio** between previous and last adjusted closes.

    Formula (equivalent forms)::

        (adj_close[-1] - adj_close[-2]) / adj_close[-2]
        adj_close[-1] / adj_close[-2] - 1

    Unit is ``ratio`` (example: ``0.050000`` means +5%, not ``5.0``).
    """

    if len(bars) < 2:
        msg = "simple_return requires at least two bars"
        raise ValueError(msg)
    previous = bars[-2].adjusted_close
    current = bars[-1].adjusted_close
    if previous == 0:
        msg = "simple_return previous adjusted close cannot be zero"
        raise ValueError(msg)
    value = (current / previous) - Decimal("1")
    return MarketMetric(
        name=MetricName.SIMPLE_RETURN,
        value=_quantize(value, _RATIO),
        unit="ratio",
        formula_version=(
            f"{CALCULATION_LIBRARY_VERSION}:simple_return=(adj_close[-1]/adj_close[-2])-1"
        ),
        inputs_as_of=bars[-1].session_date.isoformat(),
    )


def simple_moving_average(bars: tuple[OhlcvBar, ...], *, window: int) -> MarketMetric:
    if window < 1:
        msg = "sma window must be >= 1"
        raise ValueError(msg)
    if len(bars) < window:
        msg = f"sma requires at least {window} bars"
        raise ValueError(msg)
    sample = bars[-window:]
    total = sum((bar.adjusted_close for bar in sample), Decimal("0"))
    value = total / Decimal(window)
    return MarketMetric(
        name=MetricName.SMA,
        value=_quantize(value, _MONEY),
        unit=sample[-1].currency.as_text(),
        formula_version=(f"{CALCULATION_LIBRARY_VERSION}:sma=mean(adj_close[-{window}:])"),
        window=window,
        inputs_as_of=sample[-1].session_date.isoformat(),
    )


def volume_sum(bars: tuple[OhlcvBar, ...], *, window: int) -> MarketMetric:
    if window < 1:
        msg = "volume_sum window must be >= 1"
        raise ValueError(msg)
    if len(bars) < window:
        msg = f"volume_sum requires at least {window} bars"
        raise ValueError(msg)
    sample = bars[-window:]
    total = sum((bar.volume for bar in sample), Decimal("0"))
    return MarketMetric(
        name=MetricName.VOLUME_SUM,
        value=_quantize(total, Decimal("1")),
        unit="shares",
        formula_version=f"{CALCULATION_LIBRARY_VERSION}:volume_sum=sum(volume[-{window}:])",
        window=window,
        inputs_as_of=sample[-1].session_date.isoformat(),
    )


def compute_standard_metrics(
    bars: tuple[OhlcvBar, ...],
    *,
    sma_window: int = 3,
) -> tuple[MarketMetric, ...]:
    """Compute the Phase 3 Prompt 1 standard metric set where inputs allow."""

    metrics: list[MarketMetric] = [last_close(bars), adjusted_last_close(bars)]
    if len(bars) >= 2:
        metrics.append(simple_return(bars))
    if len(bars) >= sma_window:
        metrics.append(simple_moving_average(bars, window=sma_window))
        metrics.append(volume_sum(bars, window=sma_window))
    return tuple(metrics)
