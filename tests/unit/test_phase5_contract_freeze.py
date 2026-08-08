"""Phase 5 Prompt 3 contract freeze, acceptance regressions, and Prompt 2 verification.

Frozen Phase 5 acceptance (PHASES.md):
- each material qualitative claim cites evidence
- opinion is labeled
- events are time-aware
- general web never overrides authoritative records silently
- incomplete coverage is disclosed

Live qualitative HTTP and LLM sentiment are deferred by design (ADR-034/037/038),
not blocking gaps for the authorized Phase 5 foundation release.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.financial_contracts import FinancialSnapshotQuery
from financial_intelligence.application.financial_snapshot import GetFinancialSnapshot
from financial_intelligence.application.industry_contracts import IndustrySnapshotQuery
from financial_intelligence.application.industry_snapshot import GetIndustryContextSnapshot
from financial_intelligence.application.market_contracts import MarketSnapshotQuery
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.news_event_contracts import NewsEventSnapshotQuery
from financial_intelligence.application.news_event_snapshot import GetNewsEventSnapshot
from financial_intelligence.application.regulatory_contracts import RegulatorySnapshotQuery
from financial_intelligence.application.regulatory_snapshot import GetRegulatorySnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.news import (
    CompanyEventPackage,
    EventConflictState,
    EventEvidenceRef,
    EventId,
    EventType,
    InformationClass,
    NewsEventAvailability,
    QualitativeEvent,
    deduplicate_events,
    process_events,
)
from financial_intelligence.domain.regulatory import (
    RegulatorCode,
    RegulatoryActionType,
    RegulatoryEvent,
    RegulatoryStatus,
    deduplicate_regulatory_events,
)
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId
from financial_intelligence.infrastructure.company import (
    InMemoryCompanyCatalog,
    build_reference_companies,
)
from financial_intelligence.infrastructure.financial import InMemoryFinancialDataAdapter
from financial_intelligence.infrastructure.industry import (
    CachingIndustryAdapter,
    InMemoryIndustryAdapter,
)
from financial_intelligence.infrastructure.market import InMemoryMarketDataAdapter
from financial_intelligence.infrastructure.news import (
    CachingNewsEventAdapter,
    InMemoryNewsEventAdapter,
)
from financial_intelligence.infrastructure.news.reference_dataset import (
    APPLE_ID,
    RELIANCE_ID,
    build_reference_event_packages,
)
from financial_intelligence.infrastructure.regulatory import (
    CachingRegulatoryAdapter,
    InMemoryRegulatoryAdapter,
)


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _ev(
    *,
    event_id: str,
    title: str = "Shared title",
    authority: SourceAuthorityTier = SourceAuthorityTier.TIER_1_AUTHORITATIVE,
    information_class: InformationClass = InformationClass.FACT,
    summary: str = "Shared material summary.",
    event_date: date | None = None,
    retrieved_hour: int = 12,
    sentiment: str | None = None,
    company_id: CompanyId | None = None,
) -> QualitativeEvent:
    return QualitativeEvent(
        event_id=EventId.from_string(event_id),
        company_id=company_id or APPLE_ID,
        event_type=EventType.PRODUCT,
        title=title,
        summary=summary,
        event_date=event_date or date(2024, 9, 9),
        information_class=information_class,
        sentiment_label=sentiment,
        evidence=EventEvidenceRef(
            source_id=SourceId.new(),
            authority_tier=authority,
            locator=f"fixture:{event_id}",
            retrieved_at=datetime(2026, 8, 8, retrieved_hour, tzinfo=UTC),
            published_at=event_date or date(2024, 9, 9),
            provider_name="fixture",
        ),
    )


class Prompt2VerificationTests(TestCase):
    def test_fixture_packages_expose_conflicts_and_fixture_origin(self) -> None:
        packages = build_reference_event_packages()
        apple = packages[APPLE_ID.as_text()]
        self.assertEqual(apple.data_origin, DataOrigin.FIXTURE)
        self.assertTrue(apple.conflicts)
        states = {c.state for c in apple.conflicts}
        self.assertTrue(states & {EventConflictState.SUPERSEDED, EventConflictState.CONFLICTING})

    def test_limit_does_not_drop_relevant_conflicts(self) -> None:
        adapter = InMemoryNewsEventAdapter()
        package = adapter.get_event_package(APPLE_ID, limit=20)
        assert package is not None
        self.assertTrue(package.conflicts)
        payload = package.to_dict()
        self.assertGreater(int(payload["conflict_count"]), 0)


class DeduplicationAndConflictFreezeTests(TestCase):
    def test_insertion_order_independent_and_no_last_write_wins(self) -> None:
        low = _ev(
            event_id="93333333-3333-4333-8333-333333333701",
            authority=SourceAuthorityTier.TIER_4_GENERAL_WEB,
            information_class=InformationClass.OPINION,
            summary="Web rewrite",
            sentiment="positive",
            retrieved_hour=20,
        )
        high = _ev(
            event_id="93333333-3333-4333-8333-333333333702",
            authority=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            summary="Official rewrite",
            retrieved_hour=8,
        )
        a, ca = process_events((low, high))
        b, cb = process_events((high, low))
        self.assertEqual(a[0].event_id, high.event_id)
        self.assertEqual(b[0].event_id, high.event_id)
        self.assertEqual(a[0].event_id, b[0].event_id)
        self.assertEqual(ca[0].state, EventConflictState.SUPERSEDED)
        self.assertEqual(cb[0].state, EventConflictState.SUPERSEDED)

    def test_same_title_alone_does_not_merge_different_dates(self) -> None:
        a = _ev(
            event_id="93333333-3333-4333-8333-333333333703",
            event_date=date(2024, 9, 9),
            summary="Date A",
            authority=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            information_class=InformationClass.OPINION,
            sentiment="neutral",
        )
        b = _ev(
            event_id="93333333-3333-4333-8333-333333333704",
            event_date=date(2024, 9, 10),
            summary="Date B",
            authority=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            information_class=InformationClass.OPINION,
            sentiment="neutral",
        )
        survivors, conflicts = process_events((a, b))
        self.assertEqual(len(survivors), 2)
        self.assertTrue(any(c.state is EventConflictState.CONFLICTING for c in conflicts))

    def test_same_tier_material_disagreement_unresolved_keeps_both(self) -> None:
        a = _ev(
            event_id="93333333-3333-4333-8333-333333333705",
            summary="Claim A",
            authority=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            information_class=InformationClass.OPINION,
            sentiment="positive",
        )
        b = _ev(
            event_id="93333333-3333-4333-8333-333333333706",
            summary="Claim B",
            authority=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            information_class=InformationClass.OPINION,
            sentiment="negative",
        )
        survivors, conflicts = process_events((a, b))
        self.assertEqual(len(survivors), 2)
        self.assertEqual(conflicts[0].state, EventConflictState.UNRESOLVED)
        self.assertIsNone(conflicts[0].selected)

    def test_cross_company_same_title_not_merged(self) -> None:
        a = _ev(event_id="93333333-3333-4333-8333-333333333707", company_id=APPLE_ID)
        b = _ev(event_id="93333333-3333-4333-8333-333333333708", company_id=RELIANCE_ID)
        result = deduplicate_events((a, b))
        self.assertEqual(len(result), 2)


class ClassificationAndTimeFreezeTests(TestCase):
    def test_tier4_and_directional_sentiment_cannot_be_fact(self) -> None:
        with self.assertRaises(ValueError):
            _ev(
                event_id="93333333-3333-4333-8333-333333333709",
                authority=SourceAuthorityTier.TIER_4_GENERAL_WEB,
                information_class=InformationClass.FACT,
            )
        with self.assertRaises(ValueError):
            _ev(
                event_id="93333333-3333-4333-8333-333333333710",
                sentiment="positive",
                information_class=InformationClass.FACT,
            )

    def test_model_interpretation_remains_distinct_from_fact(self) -> None:
        event = _ev(
            event_id="93333333-3333-4333-8333-333333333711",
            information_class=InformationClass.MODEL_INTERPRETATION,
            authority=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
            sentiment="mixed",
            summary="Interpretation only.",
        )
        self.assertEqual(event.information_class, InformationClass.MODEL_INTERPRETATION)
        self.assertNotEqual(event.information_class, InformationClass.FACT)

    def test_late_reporting_and_publication_boundary(self) -> None:
        event = _ev(
            event_id="93333333-3333-4333-8333-333333333712",
            event_date=date(2024, 1, 1),
        )
        # published after event is allowed (late reporting) via evidence published_at
        evidence = EventEvidenceRef(
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            locator="late",
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
            published_at=date(2024, 1, 15),
            provider_name="fixture",
        )
        late = QualitativeEvent(
            event_id=EventId.from_string("93333333-3333-4333-8333-333333333713"),
            company_id=APPLE_ID,
            event_type=EventType.EARNINGS,
            title="Late report",
            summary="Reported later than event date.",
            event_date=date(2024, 1, 1),
            information_class=InformationClass.FACT,
            evidence=evidence,
        )
        self.assertLess(late.event_date, late.evidence.published_at)
        self.assertIsNotNone(event.age_metadata(as_of=datetime(2026, 8, 9, tzinfo=UTC)))


class RegulatoryFreezeTests(TestCase):
    def test_secondary_allegation_cannot_masquerade_as_official_fact(self) -> None:
        with self.assertRaises(ValueError):
            RegulatoryEvent(
                event_id="reg-bad",
                company_id=APPLE_ID,
                regulator=RegulatorCode.SEC,
                jurisdiction="US",
                action_type=RegulatoryActionType.INQUIRY,
                status=RegulatoryStatus.ACTIVE,
                title="Bad upgrade",
                summary="Secondary only",
                event_date=date(2024, 1, 1),
                information_class=InformationClass.FACT,
                evidence=EventEvidenceRef(
                    source_id=SourceId.new(),
                    authority_tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
                    locator="x",
                    retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                    published_at=date(2024, 1, 1),
                    provider_name="fixture",
                ),
            )

    def test_amended_and_active_same_case_remain_distinct(self) -> None:
        def _reg(status: RegulatoryStatus, eid: str) -> RegulatoryEvent:
            return RegulatoryEvent(
                event_id=eid,
                company_id=APPLE_ID,
                regulator=RegulatorCode.SEC,
                jurisdiction="US",
                action_type=RegulatoryActionType.NOTICE,
                status=status,
                title="Case notice",
                summary=f"Status {status.value}",
                event_date=date(2024, 5, 1),
                published_at=date(2024, 5, 2),
                information_class=InformationClass.FACT,
                case_reference="FIXTURE-CASE-1",
                evidence=EventEvidenceRef(
                    source_id=SourceId.new(),
                    authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                    locator=eid,
                    retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                    published_at=date(2024, 5, 2),
                    provider_name="fixture",
                ),
            )

        active = _reg(RegulatoryStatus.ACTIVE, "reg-a")
        amended = _reg(RegulatoryStatus.AMENDED, "reg-b")
        result = deduplicate_regulatory_events((active, amended))
        self.assertEqual(len(result), 2)
        self.assertEqual({e.case_reference for e in result}, {"FIXTURE-CASE-1"})


class CrossCapabilityIdentityTests(TestCase):
    def test_apple_and_reliance_share_canonical_ids_across_capabilities(self) -> None:
        catalog = InMemoryCompanyCatalog()
        resolve = ResolveCompany(catalog)

        def clock() -> datetime:
            return datetime(2026, 8, 8, 20, tzinfo=UTC)

        news = GetNewsEventSnapshot(resolve, InMemoryNewsEventAdapter(), clock=clock)
        industry = GetIndustryContextSnapshot(resolve, InMemoryIndustryAdapter(), clock=clock)
        regulatory = GetRegulatorySnapshot(resolve, InMemoryRegulatoryAdapter(), clock=clock)
        market = GetMarketSnapshot(
            resolve,
            InMemoryMarketDataAdapter(),
            freshness_policy=MarketFreshnessPolicy(stale_after=timedelta(hours=72)),
            clock=clock,
        )
        financial = GetFinancialSnapshot(resolve, InMemoryFinancialDataAdapter(), clock=clock)

        for query, expected in (
            (CompanyQuery(raw_query="Apple"), APPLE_ID),
            (CompanyQuery(raw_query="Reliance"), RELIANCE_ID),
        ):
            n = news.execute(NewsEventSnapshotQuery(company_query=query))
            i = industry.execute(IndustrySnapshotQuery(company_query=query))
            r = regulatory.execute(RegulatorySnapshotQuery(company_query=query))
            m = market.execute(MarketSnapshotQuery(company_query=query))
            f = financial.execute(FinancialSnapshotQuery(company_query=query))
            for result in (n, i, r, m, f):
                assert result.resolution is not None and result.resolution.company is not None
                self.assertEqual(result.resolution.company.company_id, expected)
            assert n.package is not None and i.package is not None and r.package is not None
            self.assertEqual(n.package.company_id, expected)
            self.assertEqual(i.package.company_id, expected)
            self.assertEqual(r.package.company_id, expected)
            # Evidence present on qualitative artifacts
            self.assertTrue(all(e.evidence.source_id for e in n.package.events))
            self.assertTrue(i.package.industry is not None)
            self.assertTrue(all(e.evidence.source_id for e in r.package.events))

    def test_reference_company_ids_match_phase2_catalog(self) -> None:
        companies = {c.company_id.as_text(): c for c in build_reference_companies()}
        self.assertIn(APPLE_ID.as_text(), companies)
        self.assertIn(RELIANCE_ID.as_text(), companies)
        self.assertEqual(companies[APPLE_ID.as_text()].display_name, "Apple")
        self.assertEqual(companies[RELIANCE_ID.as_text()].display_name, "Reliance Industries")


class CacheStabilizationTests(TestCase):
    def test_news_industry_regulatory_cache_isolation_and_concurrency(self) -> None:
        clock = {"now": datetime(2026, 8, 8, 12, 0, tzinfo=UTC)}

        def _clock() -> datetime:
            return clock["now"]

        news = CachingNewsEventAdapter(
            InMemoryNewsEventAdapter(), ttl=timedelta(seconds=30), clock=_clock
        )
        industry = CachingIndustryAdapter(
            InMemoryIndustryAdapter(), ttl=timedelta(seconds=30), clock=_clock
        )
        regulatory = CachingRegulatoryAdapter(
            InMemoryRegulatoryAdapter(), ttl=timedelta(seconds=30), clock=_clock
        )

        def _hit(_: int) -> str:
            n = news.get_event_package(APPLE_ID)
            i = industry.get_industry_package(APPLE_ID)
            r = regulatory.get_regulatory_package(RELIANCE_ID)
            assert n and i and r
            return n.data_origin.value + i.data_origin.value + r.data_origin.value

        with ThreadPoolExecutor(max_workers=8) as pool:
            origins = list(pool.map(_hit, range(16)))
        self.assertTrue(all(o == "fixturefixturefixture" for o in origins))
        # company isolation
        self.assertIsNone(
            news.get_event_package(CompanyId.from_string("22222222-2222-4222-8222-222222222099"))
        )
        # TTL expiry boundary (expires_at = now+30; at +30 miss-refetch)
        clock["now"] = datetime(2026, 8, 8, 12, 0, 30, tzinfo=UTC)
        again = news.get_event_package(APPLE_ID)
        assert again is not None
        self.assertEqual(again.data_origin, DataOrigin.FIXTURE)


class ApiContractFreezeTests(TestCase):
    def test_phase5_endpoints_apple_reliance_and_adversarial(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            apple_news = client.get("/news/events/snapshot?q=Apple&exchange=NASDAQ")
            reliance_reg = client.get("/regulatory/events/snapshot?q=Reliance&exchange=NSE")
            apple_ind = client.get("/industry/context/snapshot?q=Apple&exchange=NASDAQ")
            unknown = client.get("/news/events/snapshot?q=ZZZZNOTACOMPANY")
            ambiguous = client.get("/industry/context/snapshot?q=COLLIDE")
            wrong_ex = client.get("/regulatory/events/snapshot?q=Apple&exchange=NSE")
            control = client.get("/news/events/snapshot?q=Apple%0AInject")
            oversized = client.get("/news/events/snapshot?q=" + ("A" * 500))
            injection = client.get("/news/events/snapshot?q=Apple&exchange=NASDAQ")

        for response in (apple_news, reliance_reg, apple_ind):
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "ok")
            self.assertEqual(body["data_origin"], "fixture")
            self.assertTrue(response.headers.get("X-Correlation-ID"))
            self.assertNotIn("traceback", json.dumps(body).lower())

        self.assertTrue(apple_news.json()["conflicts"])
        self.assertEqual(unknown.json()["status"], "resolution_blocked")
        self.assertEqual(ambiguous.json()["status"], "resolution_blocked")
        self.assertEqual(wrong_ex.json()["status"], "resolution_blocked")
        self.assertIn(control.status_code, {200, 400})
        self.assertIn(oversized.status_code, {200, 400, 422})
        blob = json.dumps(injection.json()).lower()
        self.assertIn("ignore previous instructions", blob)
        self.assertNotIn("openrouter_api_key", blob)

    def test_phase1_to_4_and_identity_protections(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            for path in (
                "/health",
                "/ready",
                "/version",
                "/companies/resolve?q=Apple",
                "/market/snapshot?q=Apple&exchange=NASDAQ",
                "/financials/snapshot?q=Apple&exchange=NASDAQ",
                "/news/events/snapshot?q=Apple&exchange=NASDAQ",
                "/industry/context/snapshot?q=Apple&exchange=NASDAQ",
                "/regulatory/events/snapshot?q=Reliance&exchange=NSE",
            ):
                self.assertEqual(client.get(path).status_code, 200)

            reliance_nasdaq = client.get("/companies/resolve?q=RELIANCE&exchange=NASDAQ")
            self.assertNotEqual(reliance_nasdaq.json()["status"], "RESOLVED")
            goog = client.get("/companies/resolve?ticker=GOOG").json()
            googl = client.get("/companies/resolve?ticker=GOOGL").json()
            self.assertEqual(goog["status"], "RESOLVED")
            self.assertEqual(googl["status"], "RESOLVED")
            nse = client.get("/companies/resolve?q=Reliance&exchange=NSE").json()
            bse = client.get("/companies/resolve?q=Reliance&exchange=BSE").json()
            self.assertEqual(nse["status"], "RESOLVED")
            self.assertEqual(bse["status"], "RESOLVED")
            self.assertEqual(nse["company"]["company_id"], bse["company"]["company_id"])

    def test_openapi_phase5_paths_only(self) -> None:
        app = create_app(settings=_settings())
        paths = set(app.openapi()["paths"])
        self.assertTrue(
            {
                "/news/events/snapshot",
                "/industry/context/snapshot",
                "/regulatory/events/snapshot",
            }.issubset(paths)
        )
        self.assertTrue(paths.isdisjoint({"/agents", "/research", "/mcp", "/chat"}))

    def test_composition_wires_phase5_without_network_import(self) -> None:
        container = build_container(_settings())
        self.assertFalse(container.settings.allow_paid_models)
        self.assertIsNotNone(container.get_news_event_snapshot)
        self.assertIsNotNone(container.get_industry_snapshot)
        self.assertIsNotNone(container.get_regulatory_snapshot)


class ProvenanceSerializationFreezeTests(TestCase):
    def test_event_package_json_roundtrip_fields(self) -> None:
        package = build_reference_event_packages()[APPLE_ID.as_text()]
        payload = package.to_dict()
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["data_origin"], "fixture")
        self.assertGreater(decoded["event_count"], 0)
        self.assertGreater(decoded["conflict_count"], 0)
        first = decoded["events"][0]
        self.assertIn("evidence", first)
        self.assertIn("authority_tier", first["evidence"])
        self.assertIn("retrieved_at", first["evidence"])
        self.assertIn("information_class", first)

    def test_unavailable_package_rejects_events(self) -> None:
        with self.assertRaises(ValueError):
            CompanyEventPackage(
                company_id=APPLE_ID,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                events=(_ev(event_id="93333333-3333-4333-8333-333333333799"),),
                availability=NewsEventAvailability.AVAILABLE,
                data_origin=DataOrigin.UNAVAILABLE,
            )
