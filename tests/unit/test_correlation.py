"""Correlation ID helper tests."""

from __future__ import annotations

from unittest import TestCase
from uuid import UUID

from financial_intelligence.observability.correlation import (
    generate_correlation_id,
    resolve_correlation_id,
)


class CorrelationIdTests(TestCase):
    """Validate correlation ID generation and inbound sanitization."""

    def test_generate_uuid(self) -> None:
        correlation = generate_correlation_id()
        self.assertEqual(UUID(correlation.value).version, 4)

    def test_accepts_safe_inbound_value(self) -> None:
        correlation = resolve_correlation_id("client-request-123")
        self.assertEqual(correlation.value, "client-request-123")

    def test_rejects_oversized_inbound_value(self) -> None:
        oversized = "a" * 65
        correlation = resolve_correlation_id(oversized)
        self.assertNotEqual(correlation.value, oversized)
        self.assertEqual(UUID(correlation.value).version, 4)

    def test_rejects_unsafe_characters(self) -> None:
        correlation = resolve_correlation_id("bad id with spaces!")
        self.assertNotEqual(correlation.value, "bad id with spaces!")
        self.assertEqual(UUID(correlation.value).version, 4)
