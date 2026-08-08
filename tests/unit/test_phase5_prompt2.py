"""Domain and API tests for industry/competitor and regulatory foundations."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.industry_contracts import (
    IndustrySnapshotQuery,
    IndustrySnapshotStatus,
)
from financial_intelligence.application.industry_snapshot import GetIndustryContextSnapshot
from financial_intelligence.application.regulatory_contracts import (
    RegulatorySnapshotQuery,
    RegulatorySnapshotStatus,
)
from financial_intelligence.application.regulatory_snapshot import GetRegulatorySnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.industry import (
    CompetitorRelationship,
    IndustryClassification,
    IndustryTaxonomySource,
    PeerResolutionState,
)
from financial_intelligence.domain.news.events import EventEvidenceRef, InformationClass
from financial_intelligence.domain.regulatory import (
    RegulatorCode,
    RegulatoryActionType,
    RegulatoryEvent,
    RegulatoryStatus,
)
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.industry import InMemoryIndustryAdapter
from financial_intelligence.infrastructure.regulatory import InMemoryRegulatoryAdapter

APPLE = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
MSFT = CompanyId.from_string("22222222-2222-4222-8222-222222222002")


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _ev(
    *,
    tier: SourceAuthorityTier = SourceAuthorityTier.TIER_1_AUTHORITATIVE,
) -> EventEvidenceRef:
    return EventEvidenceRef(
        source_id=SourceId(value=UUID("84333333-3333-4333-8333-333333333001")),
        authority_tier=tier,
        locator="fixture:test",
        retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
        published_at=date(2024, 1, 1),
        provider_name="fixture",
    )


class IndustryDomainTests(TestCase):
    def test_self_competitor_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CompetitorRelationship(
                subject_company_id=APPLE,
                peer_display_name="Apple",
                peer_resolution=PeerResolutionState.RESOLVED,
                peer_company_id=APPLE,
                evidence=_ev(),
                as_of=date(2024, 1, 1),
            )

    def test_unmapped_must_not_invent_canonical(self) -> None:
        with self.assertRaises(ValueError):
            IndustryClassification(
                company_id=APPLE,
                canonical_code="invented",
                canonical_label="Invented",
                provider_label="raw",
                taxonomy_source=IndustryTaxonomySource.UNMAPPED,
                evidence=_ev(),
            )

    def test_unresolved_peer_cannot_attach_id(self) -> None:
        with self.assertRaises(ValueError):
            CompetitorRelationship(
                subject_company_id=APPLE,
                peer_display_name="Someone",
                peer_resolution=PeerResolutionState.UNRESOLVED,
                peer_company_id=MSFT,
                evidence=_ev(tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS),
                as_of=date(2024, 1, 1),
                information_class=InformationClass.OPINION,
            )

    def test_apple_industry_snapshot_ok(self) -> None:
        result = GetIndustryContextSnapshot(
            ResolveCompany(InMemoryCompanyCatalog()),
            InMemoryIndustryAdapter(),
            clock=lambda: datetime(2026, 8, 8, 20, tzinfo=UTC),
        ).execute(IndustrySnapshotQuery(company_query=CompanyQuery(raw_query="Apple")))
        self.assertEqual(result.status, IndustrySnapshotStatus.OK)
        assert result.package is not None
        self.assertEqual(result.package.data_origin, DataOrigin.FIXTURE)
        self.assertIsNotNone(result.package.industry)
        resolved = [c for c in result.package.competitors if c.peer_resolution.value == "resolved"]
        self.assertTrue(resolved)
        self.assertEqual(resolved[0].peer_company_id, MSFT)

    def test_reliance_industry_snapshot_ok(self) -> None:
        result = GetIndustryContextSnapshot(
            ResolveCompany(InMemoryCompanyCatalog()),
            InMemoryIndustryAdapter(),
            clock=lambda: datetime(2026, 8, 8, 20, tzinfo=UTC),
        ).execute(IndustrySnapshotQuery(company_query=CompanyQuery(raw_query="Reliance")))
        self.assertEqual(result.status, IndustrySnapshotStatus.OK)

    def test_ambiguous_blocks_industry(self) -> None:
        result = GetIndustryContextSnapshot(
            ResolveCompany(InMemoryCompanyCatalog()),
            InMemoryIndustryAdapter(),
        ).execute(IndustrySnapshotQuery(company_query=CompanyQuery(raw_query="COLLIDE")))
        self.assertEqual(result.status, IndustrySnapshotStatus.RESOLUTION_BLOCKED)
        self.assertIsNone(result.package)


class RegulatoryDomainTests(TestCase):
    def test_secondary_cannot_be_fact_or_active(self) -> None:
        with self.assertRaises(ValueError):
            RegulatoryEvent(
                event_id="x1",
                company_id=APPLE,
                regulator=RegulatorCode.SEC,
                jurisdiction="US",
                action_type=RegulatoryActionType.INQUIRY,
                status=RegulatoryStatus.ACTIVE,
                title="Secondary",
                summary="News only",
                event_date=date(2024, 1, 1),
                information_class=InformationClass.FACT,
                evidence=_ev(tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS),
            )

    def test_apple_and_reliance_regulatory_snapshots(self) -> None:
        uc = GetRegulatorySnapshot(
            ResolveCompany(InMemoryCompanyCatalog()),
            InMemoryRegulatoryAdapter(),
            clock=lambda: datetime(2026, 8, 8, 20, tzinfo=UTC),
        )
        apple = uc.execute(RegulatorySnapshotQuery(company_query=CompanyQuery(raw_query="Apple")))
        reliance = uc.execute(
            RegulatorySnapshotQuery(company_query=CompanyQuery(raw_query="Reliance"))
        )
        self.assertEqual(apple.status, RegulatorySnapshotStatus.OK)
        self.assertEqual(reliance.status, RegulatorySnapshotStatus.OK)
        assert apple.package is not None and reliance.package is not None
        self.assertTrue(any(e.regulator is RegulatorCode.SEC for e in apple.package.events))
        self.assertTrue(any(e.regulator is RegulatorCode.SEBI for e in reliance.package.events))
        alleged = [e for e in apple.package.events if e.status is RegulatoryStatus.ALLEGED]
        self.assertTrue(alleged)
        self.assertNotEqual(alleged[0].information_class, InformationClass.FACT)


class Phase5ApiHardeningTests(TestCase):
    def test_news_conflicts_and_injection_inert(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/news/events/snapshot?q=Apple&exchange=NASDAQ")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload.get("conflicts"))
        blob = str(payload).lower()
        self.assertIn("ignore previous instructions", blob)
        self.assertNotIn("traceback", blob)

    def test_industry_and_regulatory_endpoints(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            ind = client.get("/industry/context/snapshot?q=Apple&exchange=NASDAQ")
            reg = client.get("/regulatory/events/snapshot?q=Reliance&exchange=NSE")
            blocked = client.get("/industry/context/snapshot?q=COLLIDE")
            unknown = client.get("/regulatory/events/snapshot?q=ZZZZNOTACOMPANY")
            bad_exchange = client.get("/industry/context/snapshot?q=Apple&exchange=NSE")
            reliance_nasdaq = client.get("/companies/resolve?q=RELIANCE&exchange=NASDAQ")
        self.assertEqual(ind.status_code, 200)
        self.assertEqual(ind.json()["status"], "ok")
        self.assertEqual(ind.json()["data_origin"], "fixture")
        self.assertEqual(reg.status_code, 200)
        self.assertEqual(reg.json()["status"], "ok")
        self.assertEqual(blocked.json()["status"], "resolution_blocked")
        self.assertEqual(unknown.json()["status"], "resolution_blocked")
        self.assertEqual(bad_exchange.json()["status"], "resolution_blocked")
        self.assertNotEqual(reliance_nasdaq.json()["status"], "RESOLVED")

    def test_phase1_to_4_regression(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            for path in (
                "/health",
                "/ready",
                "/version",
                "/companies/resolve?q=Apple",
                "/market/snapshot?q=Apple&exchange=NASDAQ",
                "/financials/snapshot?q=Apple&exchange=NASDAQ",
                "/news/events/snapshot?q=Apple&exchange=NASDAQ",
            ):
                self.assertEqual(client.get(path).status_code, 200)
            goog = client.get("/companies/resolve?ticker=GOOG")
            googl = client.get("/companies/resolve?ticker=GOOGL")
            self.assertEqual(goog.status_code, 200)
            self.assertEqual(googl.status_code, 200)
