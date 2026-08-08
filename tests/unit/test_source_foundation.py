"""Source metadata foundation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceId,
    SourceMetadata,
    SourceType,
    validate_source_url,
)


class SourceFoundationTests(TestCase):
    def test_authority_tiers_match_frozen_policy(self) -> None:
        self.assertEqual(int(SourceAuthorityTier.TIER_1_AUTHORITATIVE), 1)
        self.assertEqual(int(SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL), 2)
        self.assertEqual(int(SourceAuthorityTier.TIER_3_REPUTABLE_NEWS), 3)
        self.assertEqual(int(SourceAuthorityTier.TIER_4_GENERAL_WEB), 4)

    def test_source_metadata_with_company_linkage(self) -> None:
        company_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        source = SourceMetadata(
            source_id=SourceId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            name="SEC EDGAR Filing",
            source_type=SourceType.REGULATORY_FILING,
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            url="https://www.sec.gov/Archives/example",
            published_at=datetime(2024, 1, 15, tzinfo=UTC),
            retrieved_at=datetime(2024, 1, 16, tzinfo=UTC),
            company_id=company_id,
        )
        payload = source.to_dict()
        self.assertEqual(payload["authority_tier"], 1)
        self.assertEqual(payload["company_id"], company_id.as_text())
        self.assertEqual(payload["source_type"], "regulatory_filing")

    def test_url_validation_bounds_and_schemes(self) -> None:
        self.assertEqual(
            validate_source_url("https://example.com/path"),
            "https://example.com/path",
        )
        with self.assertRaises(ValueError):
            validate_source_url("javascript:alert(1)")
        with self.assertRaises(ValueError):
            validate_source_url("file:///etc/passwd")
        with self.assertRaises(ValueError):
            validate_source_url("https://" + ("a" * 2100))

    def test_naive_timestamps_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SourceMetadata(
                source_id=SourceId.new(),
                name="News Item",
                source_type=SourceType.NEWS,
                authority_tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
                published_at=datetime(2024, 1, 1),
            )

    def test_source_id_requires_uuid_v4(self) -> None:
        with self.assertRaises(ValueError):
            SourceId.from_string("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")
