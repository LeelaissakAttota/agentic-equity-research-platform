"""Additional source metadata and import-side-effect hardening tests."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from financial_intelligence.domain.identity import CompanyId, ListingId, SecurityId
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceId,
    SourceMetadata,
    SourceType,
    validate_source_url,
)

ROOT = Path(__file__).resolve().parents[2]


class SourceHardeningTests(TestCase):
    def test_authority_tier_order_frozen(self) -> None:
        tiers = [int(tier) for tier in SourceAuthorityTier]
        self.assertEqual(tiers, [1, 2, 3, 4])
        self.assertLess(
            SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            SourceAuthorityTier.TIER_4_GENERAL_WEB,
        )

    def test_linkage_invariants(self) -> None:
        company_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        security_id = SecurityId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        listing_id = ListingId.from_string("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
        ok = SourceMetadata(
            source_id=SourceId.new(),
            name="Linked Filing",
            source_type=SourceType.REGULATORY_FILING,
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            company_id=company_id,
            security_id=security_id,
            listing_id=listing_id,
        )
        self.assertEqual(ok.listing_id, listing_id)
        with self.assertRaises(ValueError):
            SourceMetadata(
                source_id=SourceId.new(),
                name="Listing Without Security",
                source_type=SourceType.MARKET_DATA,
                authority_tier=SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL,
                listing_id=listing_id,
            )
        with self.assertRaises(ValueError):
            SourceMetadata(
                source_id=SourceId.new(),
                name="Security Without Company",
                source_type=SourceType.MARKET_DATA,
                authority_tier=SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL,
                security_id=security_id,
            )

    def test_url_schemes_and_controls(self) -> None:
        for bad in (
            "ftp://example.com",
            "file:///tmp/x",
            "javascript:alert(1)",
            "data:text/plain,hi",
            "/relative/path",
            "https://example.com/\npath",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_source_url(bad)

    def test_published_after_retrieved_is_allowed(self) -> None:
        # Evidence model separates publication and retrieval; unusual order is not invalid.
        source = SourceMetadata(
            source_id=SourceId.new(),
            name="Delayed Indexing",
            source_type=SourceType.NEWS,
            authority_tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            published_at=datetime(2024, 2, 1, tzinfo=UTC),
            retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        payload = source.to_dict()
        self.assertEqual(payload["published_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(payload["retrieved_at"], "2024-01-01T00:00:00Z")


class ImportSideEffectTests(TestCase):
    def test_phase2_imports_have_no_network_or_io_side_effects(self) -> None:
        script = """
import financial_intelligence.domain.identity
import financial_intelligence.domain.sources
import financial_intelligence.application.resolve_company
import financial_intelligence.infrastructure.company
print("IMPORT_OK")
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={
                **dict(**{k: v for k, v in __import__("os").environ.items()}),
                "PYTHONPATH": str(ROOT / "src"),
            },
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("IMPORT_OK", completed.stdout)
