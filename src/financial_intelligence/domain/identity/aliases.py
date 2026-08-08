"""Typed company aliases with provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.identity.normalization import (
    MAX_COMPANY_NAME_LENGTH,
    company_match_key,
    normalize_company_display_name,
)


class AliasType(StrEnum):
    """Controlled alias classification."""

    OFFICIAL = "official"
    SHORT_NAME = "short_name"
    FORMER_NAME = "former_name"
    BRAND = "brand"
    COMMON_NAME = "common_name"
    PROVIDER_ALIAS = "provider_alias"


@dataclass(frozen=True, slots=True)
class CompanyAlias:
    """Alias string with type metadata for governed matching."""

    value: str
    alias_type: AliasType
    normalized: str

    def __post_init__(self) -> None:
        display = normalize_company_display_name(self.value)
        if len(display) > MAX_COMPANY_NAME_LENGTH:
            msg = "alias exceeds length bounds"
            raise ValueError(msg)
        object.__setattr__(self, "value", display)
        object.__setattr__(self, "normalized", company_match_key(display))

    @classmethod
    def create(cls, value: str, alias_type: AliasType) -> CompanyAlias:
        display = normalize_company_display_name(value)
        return cls(value=display, alias_type=alias_type, normalized=company_match_key(display))
