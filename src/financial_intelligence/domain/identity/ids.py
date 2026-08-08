"""Stable provider-neutral identity primitives for issuers, securities, and listings.

Canonical IDs are UUIDv4 values. Names, tickers, and provider symbols are mutable
attributes and must never redefine the underlying entity.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


def _require_uuid_v4(value: UUID, *, label: str) -> UUID:
    if value.version != 4:
        msg = f"{label} must be a UUIDv4"
        raise ValueError(msg)
    return value


@dataclass(frozen=True, slots=True)
class CompanyId:
    """Opaque canonical issuer identity (provider-neutral)."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid_v4(self.value, label="company_id")

    @classmethod
    def new(cls) -> CompanyId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> CompanyId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CompanyId) and self.value == other.value

    def __hash__(self) -> int:
        return hash((CompanyId, self.value))


@dataclass(frozen=True, slots=True)
class SecurityId:
    """Opaque canonical security / share-class identity."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid_v4(self.value, label="security_id")

    @classmethod
    def new(cls) -> SecurityId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> SecurityId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SecurityId) and self.value == other.value

    def __hash__(self) -> int:
        return hash((SecurityId, self.value))


@dataclass(frozen=True, slots=True)
class ListingId:
    """Opaque canonical exchange listing identity."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid_v4(self.value, label="listing_id")

    @classmethod
    def new(cls) -> ListingId:
        return cls(value=uuid4())

    @classmethod
    def from_string(cls, raw: str) -> ListingId:
        return cls(value=UUID(raw))

    def as_text(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ListingId) and self.value == other.value

    def __hash__(self) -> int:
        return hash((ListingId, self.value))
