"""Normalized country, currency, exchange, and ticker value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_EXCHANGE_RE = re.compile(r"^[A-Z0-9._-]{1,32}$")
_TICKER_RE = re.compile(r"^[A-Z0-9./-]{1,32}$")
_MIC_RE = re.compile(r"^[A-Z0-9]{4}$")

# Known initial exchanges; unknown codes remain representable for extensibility.
KNOWN_EXCHANGE_MICS: dict[str, str] = {
    "NSE": "XNSE",
    "BSE": "XBOM",
    "NASDAQ": "XNAS",
    "NYSE": "XNYS",
}


@dataclass(frozen=True, slots=True)
class CountryCode:
    """ISO 3166-1 alpha-2 country code."""

    value: str

    MAX_LENGTH: ClassVar[int] = 2

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if any(ord(ch) < 32 for ch in normalized):
            msg = "country code contains control characters"
            raise ValueError(msg)
        if not _COUNTRY_RE.fullmatch(normalized):
            msg = "country code must be ISO 3166-1 alpha-2"
            raise ValueError(msg)
        object.__setattr__(self, "value", normalized)

    def as_text(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class CurrencyCode:
    """ISO 4217 currency code."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if any(ord(ch) < 32 for ch in normalized):
            msg = "currency code contains control characters"
            raise ValueError(msg)
        if not _CURRENCY_RE.fullmatch(normalized):
            msg = "currency code must be ISO 4217 alpha-3"
            raise ValueError(msg)
        object.__setattr__(self, "value", normalized)

    def as_text(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ExchangeCode:
    """Normalized exchange code with optional ISO 10383 MIC."""

    value: str
    mic: str | None = None

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if any(ord(ch) < 32 for ch in normalized):
            msg = "exchange code contains control characters"
            raise ValueError(msg)
        if not _EXCHANGE_RE.fullmatch(normalized):
            msg = "exchange code is invalid or exceeds length bounds"
            raise ValueError(msg)
        resolved_mic = self.mic
        if resolved_mic is None:
            resolved_mic = KNOWN_EXCHANGE_MICS.get(normalized)
        if resolved_mic is not None:
            mic_normalized = resolved_mic.strip().upper()
            if not _MIC_RE.fullmatch(mic_normalized):
                msg = "MIC must be a 4-character ISO 10383 code"
                raise ValueError(msg)
            object.__setattr__(self, "mic", mic_normalized)
        object.__setattr__(self, "value", normalized)

    def as_text(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TickerSymbol:
    """Exchange-contextual ticker symbol (never globally unique alone)."""

    value: str

    MAX_LENGTH: ClassVar[int] = 32

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if any(ord(ch) < 32 for ch in normalized):
            msg = "ticker contains control characters"
            raise ValueError(msg)
        if not normalized or len(normalized) > self.MAX_LENGTH:
            msg = "ticker is empty or exceeds length bounds"
            raise ValueError(msg)
        if not _TICKER_RE.fullmatch(normalized):
            msg = "ticker contains unsupported characters"
            raise ValueError(msg)
        object.__setattr__(self, "value", normalized)

    def as_text(self) -> str:
        return self.value
