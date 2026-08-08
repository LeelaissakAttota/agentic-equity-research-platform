"""Provider-specific identifiers that never become CompanyId."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_PROVIDER_ID_RE = re.compile(r"^[\w./:-]{1,64}$", re.UNICODE)


class ProviderKind(StrEnum):
    """Known provider namespaces; extensible via string enum members later."""

    YAHOO_FINANCE = "yahoo_finance"
    ALPHA_VANTAGE = "alpha_vantage"
    FINNHUB = "finnhub"
    SEC_CIK = "sec_cik"
    NSE = "nse"
    BSE = "bse"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ProviderIdentifier:
    """External system identifier scoped by provider kind."""

    provider: ProviderKind
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized or not _PROVIDER_ID_RE.fullmatch(normalized):
            msg = "provider identifier is empty, invalid, or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "value", normalized)
