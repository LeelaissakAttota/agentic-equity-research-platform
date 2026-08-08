"""Deterministic ticker and company-name normalization (no LLM)."""

from __future__ import annotations

import re
import unicodedata

from financial_intelligence.domain.identity.codes import TickerSymbol

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s&/+.-]", re.UNICODE)
_CORPORATE_SUFFIX_RE = re.compile(
    r"""
    \s+(
        limited|ltd\.?|
        incorporated|inc\.?|
        corporation|corp\.?|
        company|co\.?|
        plc|llc|
        private\s+limited|pvt\.?\s*ltd\.?|
        \.com
    )\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

MAX_COMPANY_NAME_LENGTH = 256
MAX_QUERY_LENGTH = 200


def normalize_ticker(raw: str) -> TickerSymbol:
    """Trim and uppercase a ticker into a bounded value object."""

    return TickerSymbol(raw)


def normalize_company_display_name(raw: str) -> str:
    """Conservative display-oriented normalization preserving meaning."""

    if len(raw) > MAX_COMPANY_NAME_LENGTH:
        msg = "company name exceeds length bounds"
        raise ValueError(msg)
    # Tabs are treated as whitespace; other C0 controls (including newlines) rejected.
    if any(ord(ch) < 32 and ch != "\t" for ch in raw):
        msg = "company name contains control characters"
        raise ValueError(msg)
    text = unicodedata.normalize("NFKC", raw).replace("\t", " ").strip()
    text = _WHITESPACE_RE.sub(" ", text)
    if not text:
        msg = "company name is empty"
        raise ValueError(msg)
    return text


def company_match_key(raw: str) -> str:
    """Case-insensitive match key with controlled punctuation and suffix handling.

    Display/legal names remain separate; this key is for deterministic matching only.
    """

    display = normalize_company_display_name(raw)
    lowered = display.casefold()
    lowered = _PUNCT_RE.sub(" ", lowered)
    lowered = _WHITESPACE_RE.sub(" ", lowered).strip()
    without_suffix = _CORPORATE_SUFFIX_RE.sub("", lowered).strip()
    return without_suffix or lowered
