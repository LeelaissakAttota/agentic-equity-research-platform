"""Domain tests for Phase 5 news/event models and deduplication."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest import TestCase
from uuid import UUID

from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.news import (
    EventEvidenceRef,
    EventId,
    EventType,
    InformationClass,
    QualitativeEvent,
    deduplicate_events,
)
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId


def _event(
    *,
    event_id: str,
    title: str,
    authority: SourceAuthorityTier,
    retrieved_hour: int,
    information_class: InformationClass = InformationClass.FACT,
    sentiment: str | None = None,
) -> QualitativeEvent:
    return QualitativeEvent(
        event_id=EventId.from_string(event_id),
        company_id=CompanyId.from_string("22222222-2222-4222-8222-222222222001"),
        event_type=EventType.EARNINGS,
        title=title,
        summary="Fixture summary for tests.",
        event_date=date(2024, 10, 31),
        information_class=information_class,
        sentiment_label=sentiment,
        evidence=EventEvidenceRef(
            source_id=SourceId(value=UUID("83333333-3333-4333-8333-333333333001")),
            authority_tier=authority,
            locator=f"fixture:{event_id}",
            retrieved_at=datetime(2026, 8, 8, retrieved_hour, tzinfo=UTC),
            provider_name="fixture",
        ),
    )


class NewsEventDomainTests(TestCase):
    def test_tier4_cannot_be_fact(self) -> None:
        with self.assertRaises(ValueError):
            _event(
                event_id="93333333-3333-4333-8333-333333333001",
                title="Web rewrite",
                authority=SourceAuthorityTier.TIER_4_GENERAL_WEB,
                retrieved_hour=12,
                information_class=InformationClass.FACT,
            )

    def test_directional_sentiment_cannot_be_fact(self) -> None:
        with self.assertRaises(ValueError):
            _event(
                event_id="93333333-3333-4333-8333-333333333002",
                title="Earnings",
                authority=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_hour=12,
                information_class=InformationClass.FACT,
                sentiment="positive",
            )

    def test_dedupe_prefers_higher_authority_not_last_write(self) -> None:
        low = _event(
            event_id="93333333-3333-4333-8333-333333333003",
            title="Apple reports fiscal Q4 results",
            authority=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            retrieved_hour=20,
            information_class=InformationClass.OPINION,
            sentiment="positive",
        )
        high = _event(
            event_id="93333333-3333-4333-8333-333333333004",
            title="Apple reports fiscal Q4 results",
            authority=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_hour=10,
        )
        result = deduplicate_events((low, high))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].event_id, high.event_id)

    def test_javascript_url_rejected(self) -> None:
        with self.assertRaises(ValueError):
            EventEvidenceRef(
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
                locator="x",
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                source_url="javascript:alert(1)",
            )
