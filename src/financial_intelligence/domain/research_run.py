"""UUIDv4 Research Run identity primitive (ADR-018)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ResearchRunId:
    """Canonical Research Run identity.

    The primary key is a UUIDv4. Ordering uses ``created_at``. A derived
    ``RES-...`` label is display-only and is never the primary key.
    """

    value: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        if self.value.version != 4:
            msg = "research_run_id must be a UUIDv4"
            raise ValueError(msg)
        if self.created_at.tzinfo is None:
            msg = "created_at must be timezone-aware"
            raise ValueError(msg)

    @classmethod
    def new(cls, *, created_at: datetime | None = None) -> ResearchRunId:
        """Create a new Research Run identity with UUIDv4 and UTC timestamp."""

        timestamp = created_at if created_at is not None else datetime.now(UTC)
        if timestamp.tzinfo is None:
            msg = "created_at must be timezone-aware"
            raise ValueError(msg)
        return cls(value=uuid4(), created_at=timestamp.astimezone(UTC))

    @classmethod
    def from_string(cls, raw: str, *, created_at: datetime | None = None) -> ResearchRunId:
        """Parse a lowercase UUID text form into a Research Run identity."""

        parsed = UUID(raw)
        if parsed.version != 4:
            msg = "research_run_id must be a UUIDv4"
            raise ValueError(msg)
        timestamp = created_at if created_at is not None else datetime.now(UTC)
        if timestamp.tzinfo is None:
            msg = "created_at must be timezone-aware"
            raise ValueError(msg)
        return cls(value=parsed, created_at=timestamp.astimezone(UTC))

    def as_text(self) -> str:
        """Return the canonical lowercase UUID text form."""

        return str(self.value)

    def display_label(self) -> str:
        """Return a human-friendly label that is never the primary key."""

        return f"RES-{self.as_text()}"

    def to_dict(self) -> dict[str, str]:
        """Serialize to a deterministic JSON-friendly mapping."""

        return {
            "research_run_id": self.as_text(),
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "display_label": self.display_label(),
        }
