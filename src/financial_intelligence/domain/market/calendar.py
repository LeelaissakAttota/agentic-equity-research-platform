"""Market calendar helpers (weekday calendar days; holiday calendars deferred).

``is_weekday_calendar_day`` only answers Monday-Friday. It does **not** assert
that an exchange was open (holidays/early closes are unknown here).
"""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from financial_intelligence.domain.identity import CountryCode, ExchangeCode

_EXCHANGE_TZ: dict[str, str] = {
    "NSE": "Asia/Kolkata",
    "BSE": "Asia/Kolkata",
    "NASDAQ": "America/New_York",
    "NYSE": "America/New_York",
}


def exchange_timezone(exchange: ExchangeCode) -> ZoneInfo:
    """Return the conventional IANA timezone for a supported exchange."""

    name = _EXCHANGE_TZ.get(exchange.as_text())
    if name is None:
        msg = f"no timezone mapping for exchange {exchange.as_text()}"
        raise ValueError(msg)
    return ZoneInfo(name)


def is_weekday_calendar_day(session_date: date) -> bool:
    """True for Monday-Friday calendar days.

    This is **not** confirmation of an exchange trading session. Exchange
    holidays and special sessions are intentionally out of scope.
    """

    return session_date.weekday() < 5


# Backward-compatible alias used by Prompt 1 call sites/tests.
def is_weekday_session(session_date: date) -> bool:
    """Alias for :func:`is_weekday_calendar_day` (does not imply market open)."""

    return is_weekday_calendar_day(session_date)


def country_for_exchange(exchange: ExchangeCode) -> CountryCode:
    if exchange.as_text() in {"NSE", "BSE"}:
        return CountryCode("IN")
    if exchange.as_text() in {"NASDAQ", "NYSE"}:
        return CountryCode("US")
    msg = f"no country mapping for exchange {exchange.as_text()}"
    raise ValueError(msg)
