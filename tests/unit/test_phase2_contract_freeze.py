"""Phase 2 Prompt 3 contract-freeze and false-positive safety regressions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionStatus,
)
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import (
    CompanyId,
    CompanyIdentity,
    CountryCode,
    CurrencyCode,
    ExchangeCode,
    ListingId,
    ListingIdentity,
    SecurityId,
    SecurityIdentity,
    SecurityType,
    TickerSymbol,
)
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceId,
    SourceMetadata,
    SourceType,
)
from financial_intelligence.infrastructure.company import (
    InMemoryCompanyCatalog,
    build_reference_companies,
)


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


class Prompt2FixVerificationTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog())

    def test_reliance_plus_nasdaq_is_not_found(self) -> None:
        result = self.resolver.execute(
            CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NASDAQ"))
        )
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)
        self.assertIsNone(result.company)

    def test_explicit_ticker_miss_does_not_fall_through(self) -> None:
        # Explicit ticker that misses must not resolve via unconstrained name.
        result = self.resolver.execute(
            CompanyQuery(
                raw_query="Apple",
                ticker=TickerSymbol("NOSUCH"),
                country=CountryCode("US"),
            )
        )
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)
        self.assertIsNone(result.company)

    def test_cross_type_id_inequality(self) -> None:
        shared = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        self.assertNotEqual(CompanyId(shared), SecurityId(shared))
        self.assertNotEqual(CompanyId(shared), ListingId(shared))


class PrimaryListingInvariantTests(TestCase):
    def test_security_rejects_multiple_primary_listings(self) -> None:
        company_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaae01")
        security_id = SecurityId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbe01")
        with self.assertRaises(ValueError):
            SecurityIdentity(
                security_id=security_id,
                company_id=company_id,
                security_type=SecurityType.COMMON_SHARE,
                display_name="Dual Primary",
                listings=(
                    ListingIdentity(
                        listing_id=ListingId.from_string("cccccccc-cccc-4ccc-8ccc-ccccccccce01"),
                        security_id=security_id,
                        exchange=ExchangeCode("NSE"),
                        ticker=TickerSymbol("DUAL"),
                        currency=CurrencyCode("INR"),
                        country=CountryCode("IN"),
                        is_primary=True,
                    ),
                    ListingIdentity(
                        listing_id=ListingId.from_string("cccccccc-cccc-4ccc-8ccc-ccccccccce02"),
                        security_id=security_id,
                        exchange=ExchangeCode("BSE"),
                        ticker=TickerSymbol("DUAL"),
                        currency=CurrencyCode("INR"),
                        country=CountryCode("IN"),
                        is_primary=True,
                    ),
                ),
            )

    def test_company_may_have_primary_on_each_security(self) -> None:
        company_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaf01")
        sec_a = SecurityId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbf01")
        sec_b = SecurityId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbf02")
        company = CompanyIdentity(
            company_id=company_id,
            legal_name="Multi Class Corp",
            display_name="Multi Class",
            country=CountryCode("US"),
            securities=(
                SecurityIdentity(
                    security_id=sec_a,
                    company_id=company_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Class A",
                    share_class="A",
                    listings=(
                        ListingIdentity(
                            listing_id=ListingId.from_string(
                                "cccccccc-cccc-4ccc-8ccc-cccccccccf01"
                            ),
                            security_id=sec_a,
                            exchange=ExchangeCode("NASDAQ"),
                            ticker=TickerSymbol("MULTA"),
                            currency=CurrencyCode("USD"),
                            country=CountryCode("US"),
                            is_primary=True,
                        ),
                    ),
                ),
                SecurityIdentity(
                    security_id=sec_b,
                    company_id=company_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Class B",
                    share_class="B",
                    listings=(
                        ListingIdentity(
                            listing_id=ListingId.from_string(
                                "cccccccc-cccc-4ccc-8ccc-cccccccccf02"
                            ),
                            security_id=sec_b,
                            exchange=ExchangeCode("NASDAQ"),
                            ticker=TickerSymbol("MULTB"),
                            currency=CurrencyCode("USD"),
                            country=CountryCode("US"),
                            is_primary=True,
                        ),
                    ),
                ),
            ),
        )
        primaries = [
            listing
            for security in company.securities
            for listing in security.listings
            if listing.is_primary
        ]
        self.assertEqual(len(primaries), 2)

    def test_alphabet_fixture_marks_googl_primary_only(self) -> None:
        alphabet = next(
            company
            for company in build_reference_companies()
            if company.legal_name == "Alphabet Inc."
        )
        primaries = [
            listing
            for security in alphabet.securities
            for listing in security.listings
            if listing.is_primary
        ]
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0].ticker.as_text(), "GOOGL")


class AlphabetContractFreezeTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog())
        self.alphabet = next(
            company
            for company in build_reference_companies()
            if company.legal_name == "Alphabet Inc."
        )

    def test_company_queries_share_company_id(self) -> None:
        for query in ("Alphabet", "Google"):
            with self.subTest(query=query):
                result = self.resolver.execute(CompanyQuery(raw_query=query))
                self.assertEqual(result.status, ResolutionStatus.RESOLVED)
                assert result.company is not None
                self.assertEqual(result.company.company_id, self.alphabet.company_id)

    def test_googl_and_goog_preserve_distinct_security_and_listing(self) -> None:
        googl = self.resolver.execute(CompanyQuery(raw_query="GOOGL"))
        goog = self.resolver.execute(CompanyQuery(raw_query="GOOG"))
        self.assertEqual(googl.status, ResolutionStatus.RESOLVED)
        self.assertEqual(goog.status, ResolutionStatus.RESOLVED)
        assert googl.company is not None and goog.company is not None
        self.assertEqual(googl.company.company_id, goog.company.company_id)
        googl_listing = googl.candidates[0].matched_listings[0]
        goog_listing = goog.candidates[0].matched_listings[0]
        self.assertNotEqual(googl_listing.listing_id, goog_listing.listing_id)
        self.assertNotEqual(googl_listing.security_id, goog_listing.security_id)
        self.assertEqual(googl_listing.ticker.as_text(), "GOOGL")
        self.assertEqual(goog_listing.ticker.as_text(), "GOOG")
        classes = {security.share_class for security in googl.company.securities}
        self.assertEqual(classes, {"A", "C"})


class RelianceContractFreezeTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog())

    def test_reliance_company_and_listings(self) -> None:
        company = self.resolver.execute(CompanyQuery(raw_query="Reliance"))
        self.assertEqual(company.status, ResolutionStatus.RESOLVED)
        assert company.company is not None
        self.assertEqual(company.company.legal_name, "Reliance Industries Limited")
        listings = company.company.all_listings()
        exchanges = {listing.exchange.as_text() for listing in listings}
        self.assertEqual(exchanges, {"NSE", "BSE"})
        listing_ids = {listing.listing_id.as_text() for listing in listings}
        self.assertEqual(len(listing_ids), 2)

        nse = self.resolver.execute(
            CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NSE"))
        )
        self.assertEqual(nse.status, ResolutionStatus.RESOLVED)
        self.assertEqual(
            {item.exchange.as_text() for item in nse.candidates[0].matched_listings},
            {"NSE"},
        )
        conflict = self.resolver.execute(
            CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NASDAQ"))
        )
        self.assertEqual(conflict.status, ResolutionStatus.NOT_FOUND)


class FalsePositiveSafetyTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog())

    def test_wrong_country_and_exchange(self) -> None:
        cases = [
            CompanyQuery(raw_query="Apple", country=CountryCode("IN")),
            CompanyQuery(raw_query="AAPL", exchange=ExchangeCode("NSE")),
            CompanyQuery(raw_query="Microsoft", exchange=ExchangeCode("BSE")),
            CompanyQuery(raw_query="TCS", country=CountryCode("US")),
            CompanyQuery(raw_query="Infosys", exchange=ExchangeCode("NYSE")),
        ]
        for query in cases:
            with self.subTest(query=query):
                result = self.resolver.execute(query)
                self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)
                self.assertIsNone(result.company)

    def test_alias_with_wrong_exchange(self) -> None:
        result = self.resolver.execute(
            CompanyQuery(raw_query="Google", exchange=ExchangeCode("NSE"))
        )
        self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)

    def test_fuzzy_typo_never_resolves(self) -> None:
        result = self.resolver.execute(CompanyQuery(raw_query="Aple"))
        self.assertIn(
            result.status,
            {ResolutionStatus.AMBIGUOUS, ResolutionStatus.NOT_FOUND},
        )
        self.assertIsNone(result.company)

    def test_determinism_across_repeated_calls(self) -> None:
        payloads = [
            self.resolver.execute(CompanyQuery(raw_query="RELIANCE")).to_dict() for _ in range(5)
        ]
        encoded = [json.dumps(payload, sort_keys=True) for payload in payloads]
        self.assertEqual(len(set(encoded)), 1)


class SerializationContractTests(TestCase):
    def test_identity_and_source_serialize_stably(self) -> None:
        company = next(
            item for item in build_reference_companies() if item.legal_name == "Apple Inc."
        )
        payload = company.to_dict()
        self.assertEqual(payload["company_id"], company.company_id.as_text())
        self.assertIsInstance(payload["aliases"], list)
        self.assertIsInstance(payload["securities"], list)
        first = json.dumps(payload, sort_keys=True)
        second = json.dumps(company.to_dict(), sort_keys=True)
        self.assertEqual(first, second)

        source = SourceMetadata(
            source_id=SourceId.from_string("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
            name="Example Filing",
            source_type=SourceType.REGULATORY_FILING,
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            url="https://example.com/filing",
            published_at=datetime(2024, 1, 2, tzinfo=UTC),
            retrieved_at=datetime(2024, 1, 3, tzinfo=UTC),
            company_id=company.company_id,
        )
        source_payload = source.to_dict()
        self.assertEqual(source_payload["authority_tier"], 1)
        self.assertEqual(source_payload["published_at"], "2024-01-02T00:00:00Z")
        self.assertEqual(
            json.dumps(source_payload, sort_keys=True),
            json.dumps(source.to_dict(), sort_keys=True),
        )


class ApiContractFreezeTests(TestCase):
    def test_representative_resolutions_and_http_semantics(self) -> None:
        cases = {
            "Apple": "Apple Inc.",
            "AAPL": "Apple Inc.",
            "Microsoft": "Microsoft Corporation",
            "MSFT": "Microsoft Corporation",
            "Google": "Alphabet Inc.",
            "Alphabet": "Alphabet Inc.",
            "GOOGL": "Alphabet Inc.",
            "GOOG": "Alphabet Inc.",
            "Reliance": "Reliance Industries Limited",
            "RELIANCE": "Reliance Industries Limited",
            "TCS": "Tata Consultancy Services Limited",
            "Infosys": "Infosys Limited",
            "HDFC Bank": "HDFC Bank Limited",
        }
        with TestClient(create_app(settings=_settings())) as client:
            for query, legal in cases.items():
                with self.subTest(query=query):
                    response = client.get("/companies/resolve", params={"q": query})
                    self.assertEqual(response.status_code, 200)
                    payload = response.json()
                    self.assertEqual(payload["status"], "RESOLVED")
                    self.assertEqual(payload["company"]["legal_name"], legal)
                    self.assertIn("X-Correlation-ID", response.headers)

            missing = client.get("/companies/resolve", params={"q": "NoSuchIssuerZZZ"})
            invalid = client.get("/companies/resolve", params={"q": "   "})
            conflict = client.get(
                "/companies/resolve",
                params={"q": "RELIANCE", "exchange": "NASDAQ"},
            )
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json()["status"], "NOT_FOUND")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(conflict.status_code, 200)
        self.assertEqual(conflict.json()["status"], "NOT_FOUND")

    def test_openapi_paths_include_phase3_to_phase5_snapshots(self) -> None:
        app = create_app(settings=_settings())
        self.assertEqual(
            set(app.openapi()["paths"]),
            {
                "/health",
                "/ready",
                "/version",
                "/companies/resolve",
                "/market/snapshot",
                "/financials/snapshot",
                "/news/events/snapshot",
                "/industry/context/snapshot",
                "/regulatory/events/snapshot",
            },
        )
