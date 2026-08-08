"""Calendar helper tests for Phase 3 market intelligence."""

from __future__ import annotations

from datetime import date
from unittest import TestCase
from zoneinfo import ZoneInfo

from financial_intelligence.domain.identity import ExchangeCode
from financial_intelligence.domain.market import (
    country_for_exchange,
    exchange_timezone,
    is_weekday_calendar_day,
)


class MarketCalendarTests(TestCase):
    def test_exchange_timezones(self) -> None:
        self.assertEqual(exchange_timezone(ExchangeCode("NSE")), ZoneInfo("Asia/Kolkata"))
        self.assertEqual(exchange_timezone(ExchangeCode("NASDAQ")), ZoneInfo("America/New_York"))

    def test_weekday_session_helper(self) -> None:
        self.assertTrue(is_weekday_calendar_day(date(2026, 8, 7)))  # Friday
        self.assertFalse(is_weekday_calendar_day(date(2026, 8, 8)))  # Saturday

    def test_country_mapping(self) -> None:
        self.assertEqual(country_for_exchange(ExchangeCode("BSE")).as_text(), "IN")
        self.assertEqual(country_for_exchange(ExchangeCode("NYSE")).as_text(), "US")
