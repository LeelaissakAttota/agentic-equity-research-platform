"""Research Run identity primitive tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase
from uuid import UUID

from financial_intelligence.domain.research_run import ResearchRunId


class ResearchRunIdTests(TestCase):
    """Verify UUIDv4 Research Run identity contracts."""

    def test_new_creates_uuidv4_and_timestamp(self) -> None:
        created_at = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
        run_id = ResearchRunId.new(created_at=created_at)
        self.assertEqual(run_id.value.version, 4)
        self.assertEqual(run_id.created_at, created_at)
        self.assertEqual(run_id.as_text(), str(run_id.value))
        self.assertTrue(run_id.display_label().startswith("RES-"))

    def test_uniqueness(self) -> None:
        first = ResearchRunId.new()
        second = ResearchRunId.new()
        self.assertNotEqual(first.value, second.value)

    def test_immutability(self) -> None:
        run_id = ResearchRunId.new()
        with self.assertRaises(AttributeError):
            run_id.value = UUID("00000000-0000-4000-8000-000000000000")  # type: ignore[misc]

    def test_serialization(self) -> None:
        created_at = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
        run_id = ResearchRunId.new(created_at=created_at)
        payload = run_id.to_dict()
        self.assertEqual(payload["research_run_id"], run_id.as_text())
        self.assertEqual(payload["created_at"], "2026-08-08T12:00:00Z")
        self.assertEqual(payload["display_label"], run_id.display_label())

    def test_from_string_rejects_non_uuidv4(self) -> None:
        with self.assertRaises(ValueError):
            ResearchRunId.from_string("00000000-0000-1000-8000-000000000000")

    def test_naive_timestamp_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ResearchRunId.new(created_at=datetime(2026, 8, 8, 12, 0))

    def test_equality_and_hash(self) -> None:
        created_at = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
        first = ResearchRunId.from_string(
            "11111111-1111-4111-8111-111111111111",
            created_at=created_at,
        )
        second = ResearchRunId.from_string(
            "11111111-1111-4111-8111-111111111111",
            created_at=created_at,
        )
        third = ResearchRunId.new(created_at=created_at)
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        self.assertNotEqual(first, third)
        as_set = {first, second, third}
        self.assertEqual(len(as_set), 2)
