"""Unit tests for deterministic market calculation library."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.identity import CurrencyCode
from financial_intelligence.domain.market import (
    CALCULATION_LIBRARY_VERSION,
    OhlcvBar,
    adjusted_last_close,
    compute_standard_metrics,
    last_close,
    simple_moving_average,
    simple_return,
    volume_sum,
)


def _bars() -> tuple[OhlcvBar, ...]:
    currency = CurrencyCode("USD")
    return (
        OhlcvBar(
            session_date=date(2026, 8, 5),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=Decimal("10"),
            currency=currency,
        ),
        OhlcvBar(
            session_date=date(2026, 8, 6),
            open=Decimal("100"),
            high=Decimal("120"),
            low=Decimal("99"),
            close=Decimal("110"),
            volume=Decimal("20"),
            currency=currency,
        ),
        OhlcvBar(
            session_date=date(2026, 8, 7),
            open=Decimal("110"),
            high=Decimal("130"),
            low=Decimal("108"),
            close=Decimal("121"),
            volume=Decimal("30"),
            currency=currency,
            adjustment_factor=Decimal("1"),
        ),
    )


class MarketCalculationTests(TestCase):
    def test_last_close_and_simple_return_are_deterministic(self) -> None:
        bars = _bars()
        self.assertEqual(last_close(bars).value, Decimal("121.0000"))
        self.assertEqual(simple_return(bars).value, Decimal("0.100000"))
        self.assertIn(CALCULATION_LIBRARY_VERSION, last_close(bars).formula_version)

    def test_sma_and_volume_sum_window(self) -> None:
        bars = _bars()
        self.assertEqual(simple_moving_average(bars, window=3).value, Decimal("110.3333"))
        self.assertEqual(volume_sum(bars, window=3).value, Decimal("60"))

    def test_adjusted_close_respects_factor(self) -> None:
        currency = CurrencyCode("INR")
        bars = (
            OhlcvBar(
                session_date=date(2026, 8, 6),
                open=Decimal("2000"),
                high=Decimal("2010"),
                low=Decimal("1990"),
                close=Decimal("2000"),
                volume=Decimal("1"),
                currency=currency,
                adjustment_factor=Decimal("0.5"),
            ),
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("1000"),
                high=Decimal("1010"),
                low=Decimal("990"),
                close=Decimal("1000"),
                volume=Decimal("1"),
                currency=currency,
            ),
        )
        self.assertEqual(adjusted_last_close(bars).value, Decimal("1000.0000"))
        # Previous adjusted close = 2000 * 0.5 = 1000; return = 0
        self.assertEqual(simple_return(bars).value, Decimal("0.000000"))

    def test_standard_metrics_skip_unavailable_windows(self) -> None:
        bars = _bars()[:1]
        metrics = compute_standard_metrics(bars, sma_window=3)
        names = {metric.name.value for metric in metrics}
        self.assertEqual(names, {"last_close", "adjusted_last_close"})

    def test_invalid_ohlcv_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OhlcvBar(
                session_date=date(2026, 8, 7),
                open=Decimal("10"),
                high=Decimal("9"),
                low=Decimal("8"),
                close=Decimal("9"),
                volume=Decimal("1"),
                currency=CurrencyCode("USD"),
            )
