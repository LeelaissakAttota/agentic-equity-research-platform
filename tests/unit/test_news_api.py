"""Use-case and API tests for Phase 5 news/event snapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.news_event_contracts import (
    NewsEventSnapshotQuery,
    NewsEventSnapshotStatus,
)
from financial_intelligence.application.news_event_snapshot import GetNewsEventSnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.news import EventType
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.news import InMemoryNewsEventAdapter


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class NewsEventSnapshotTests(TestCase):
    def _use_case(self) -> GetNewsEventSnapshot:
        return GetNewsEventSnapshot(
            resolve_company=ResolveCompany(InMemoryCompanyCatalog()),
            news_events=InMemoryNewsEventAdapter(),
            clock=lambda: datetime(2026, 8, 8, 20, tzinfo=UTC),
        )

    def test_apple_ok_fixture_origin(self) -> None:
        result = self._use_case().execute(
            NewsEventSnapshotQuery(company_query=CompanyQuery(raw_query="Apple"))
        )
        self.assertEqual(result.status, NewsEventSnapshotStatus.OK)
        assert result.package is not None
        self.assertEqual(result.package.data_origin, DataOrigin.FIXTURE)
        self.assertGreater(len(result.package.events), 0)
        # Dedupe should keep Tier-1 earnings over Tier-4 rewrite.
        earnings = [e for e in result.package.events if e.event_type is EventType.EARNINGS]
        self.assertEqual(len(earnings), 1)
        self.assertEqual(int(earnings[0].evidence.authority_tier), 1)

    def test_reliance_india_ok(self) -> None:
        result = self._use_case().execute(
            NewsEventSnapshotQuery(company_query=CompanyQuery(raw_query="Reliance"))
        )
        self.assertEqual(result.status, NewsEventSnapshotStatus.OK)
        assert result.package is not None
        self.assertTrue(any(e.jurisdiction == "IN" for e in result.package.events))

    def test_ambiguous_blocks(self) -> None:
        result = self._use_case().execute(
            NewsEventSnapshotQuery(company_query=CompanyQuery(raw_query="COLLIDE"))
        )
        self.assertEqual(result.status, NewsEventSnapshotStatus.RESOLUTION_BLOCKED)
        self.assertIsNone(result.package)

    def test_unknown_blocks(self) -> None:
        result = self._use_case().execute(
            NewsEventSnapshotQuery(company_query=CompanyQuery(raw_query="ZZZZNOTACOMPANY"))
        )
        self.assertEqual(result.status, NewsEventSnapshotStatus.RESOLUTION_BLOCKED)

    def test_event_type_filter(self) -> None:
        result = self._use_case().execute(
            NewsEventSnapshotQuery(
                company_query=CompanyQuery(raw_query="Apple"),
                event_type=EventType.PRODUCT,
            )
        )
        self.assertEqual(result.status, NewsEventSnapshotStatus.OK)
        assert result.package is not None
        self.assertTrue(all(e.event_type is EventType.PRODUCT for e in result.package.events))


class NewsEventApiTests(TestCase):
    def test_apple_api_ok(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/news/events/snapshot?q=Apple&exchange=NASDAQ")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertTrue(payload["events"])
        self.assertTrue(response.headers.get("X-Correlation-ID"))
        self.assertNotIn("traceback", str(payload).lower())

    def test_reliance_api_ok(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/news/events/snapshot?q=Reliance&exchange=NSE")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["data_origin"], "fixture")

    def test_ambiguous_api_blocked(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/news/events/snapshot?q=COLLIDE")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "resolution_blocked")
        self.assertEqual(response.json()["events"], [])

    def test_invalid_event_type_400(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/news/events/snapshot?q=Apple&event_type=not_a_type")
        self.assertEqual(response.status_code, 400)

    def test_phase1_4_endpoints_still_ok(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/ready").status_code, 200)
            self.assertEqual(client.get("/version").status_code, 200)
            self.assertEqual(client.get("/companies/resolve?q=Apple").status_code, 200)
            self.assertEqual(
                client.get("/market/snapshot?q=Apple&exchange=NASDAQ").status_code, 200
            )
            self.assertEqual(
                client.get("/financials/snapshot?q=Apple&exchange=NASDAQ").status_code, 200
            )
