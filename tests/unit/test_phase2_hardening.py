"""Adversarial hardening tests for Phase 2 company identity/resolution."""

from __future__ import annotations

from difflib import SequenceMatcher
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ConfidenceBand,
    MatchMethod,
    ResolutionResult,
    ResolutionStatus,
)
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.composition import build_container
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.identity import (
    AliasType,
    CompanyAlias,
    CompanyId,
    CompanyIdentity,
    CountryCode,
    CurrencyCode,
    ExchangeCode,
    ListingId,
    ListingIdentity,
    ProviderIdentifier,
    ProviderKind,
    SecurityId,
    SecurityIdentity,
    SecurityType,
    TickerSymbol,
    company_match_key,
    normalize_company_display_name,
    normalize_ticker,
)
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.company.in_memory_catalog import FUZZY_RATIO_FLOOR
from financial_intelligence.infrastructure.company.reference_dataset import (
    build_reference_companies,
)


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


_COUNTER = 0


def _company(
    *,
    company_id: str,
    legal: str,
    display: str,
    country: str,
    aliases: tuple[tuple[str, AliasType], ...] = (),
    listings: tuple[tuple[str, str, str, str], ...] = (),
) -> CompanyIdentity:
    global _COUNTER
    cid = CompanyId.from_string(company_id)
    securities: list[SecurityIdentity] = []
    for index, (exchange, ticker, currency, listing_country) in enumerate(listings):
        _COUNTER += 1
        sid = SecurityId.from_string(f"c{_COUNTER:07d}-cccc-4ccc-8ccc-{_COUNTER:012d}")
        lid = ListingId.from_string(f"d{_COUNTER:07d}-dddd-4ddd-8ddd-{_COUNTER:012d}")
        securities.append(
            SecurityIdentity(
                security_id=sid,
                company_id=cid,
                security_type=SecurityType.COMMON_SHARE,
                display_name=f"{display} Common",
                listings=(
                    ListingIdentity(
                        listing_id=lid,
                        security_id=sid,
                        exchange=ExchangeCode(exchange),
                        ticker=TickerSymbol(ticker),
                        currency=CurrencyCode(currency),
                        country=CountryCode(listing_country),
                        is_primary=index == 0,
                    ),
                ),
            )
        )
    return CompanyIdentity(
        company_id=cid,
        legal_name=legal,
        display_name=display,
        country=CountryCode(country),
        aliases=tuple(CompanyAlias.create(name, alias_type) for name, alias_type in aliases),
        securities=tuple(securities),
    )


class StableIdHardeningTests(TestCase):
    def test_cross_type_ids_never_compare_equal(self) -> None:
        shared = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        company_id = CompanyId(shared)
        security_id = SecurityId(shared)
        listing_id = ListingId(shared)
        self.assertNotEqual(company_id, security_id)
        self.assertNotEqual(company_id, listing_id)
        self.assertNotEqual(security_id, listing_id)
        self.assertEqual(hash(company_id), hash(CompanyId(shared)))
        self.assertNotEqual(hash(company_id), hash(security_id))

    def test_id_immutability_and_invalid_version(self) -> None:
        company_id = CompanyId.new()
        with self.assertRaises(AttributeError):
            company_id.value = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")  # type: ignore[misc]
        with self.assertRaises(ValueError):
            CompanyId.from_string("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")


class NormalizationHardeningTests(TestCase):
    def test_code_normalization_and_rejects(self) -> None:
        self.assertEqual(CountryCode(" us ").as_text(), "US")
        self.assertEqual(CurrencyCode("inr").as_text(), "INR")
        self.assertEqual(ExchangeCode(" nasdaq ").as_text(), "NASDAQ")
        self.assertEqual(normalize_ticker("  aapl\t").as_text(), "AAPL")
        for factory, bad in (
            (CountryCode, ""),
            (CountryCode, "USA"),
            (CountryCode, "U\n"),
            (CurrencyCode, "US"),
            (ExchangeCode, ""),
            (ExchangeCode, "X" * 40),
            (TickerSymbol, ""),
            (TickerSymbol, "BAD TICKER"),
            (TickerSymbol, "A\rAPL"),
        ):
            with (
                self.subTest(factory=factory.__name__, bad=repr(bad)),
                self.assertRaises(ValueError),
            ):
                factory(bad)

    def test_company_name_normalization_preserves_meaning(self) -> None:
        self.assertEqual(normalize_company_display_name("  Apple   Inc.  "), "Apple Inc.")
        self.assertEqual(company_match_key("Apple Inc."), "apple")
        self.assertEqual(company_match_key("Amazon.com, Inc."), "amazon.com")
        self.assertEqual(
            company_match_key("Tata Consultancy Services Limited"),
            "tata consultancy services",
        )
        with self.assertRaises(ValueError):
            normalize_company_display_name("Apple\nInc.")
        self.assertEqual(normalize_company_display_name("Apple\tInc."), "Apple Inc.")


class ConstraintAndCollisionTests(TestCase):
    def setUp(self) -> None:
        self.reference = ResolveCompany(InMemoryCompanyCatalog())
        self.collision_catalog = InMemoryCompanyCatalog(
            (
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01",
                    legal="Alpha Collision Corp",
                    display="Alpha Collision",
                    country="US",
                    aliases=(("Alpha Collision", AliasType.COMMON_NAME),),
                    listings=(("NYSE", "COLLIDE", "USD", "US"),),
                ),
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02",
                    legal="Beta Collision Limited",
                    display="Beta Collision",
                    country="IN",
                    aliases=(("Beta Collision", AliasType.COMMON_NAME),),
                    listings=(("NSE", "COLLIDE", "INR", "IN"),),
                ),
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa03",
                    legal="Shared Alias One Inc.",
                    display="Shared Alias One",
                    country="US",
                    aliases=(("TwinBrand", AliasType.BRAND),),
                    listings=(("NASDAQ", "ONE", "USD", "US"),),
                ),
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa04",
                    legal="Shared Alias Two Inc.",
                    display="Shared Alias Two",
                    country="US",
                    aliases=(("TwinBrand", AliasType.BRAND),),
                    listings=(("NYSE", "TWO", "USD", "US"),),
                ),
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa05",
                    legal="Name Victim Inc.",
                    display="Name Victim",
                    country="US",
                    aliases=(("SHADOW", AliasType.SHORT_NAME),),
                    listings=(("NASDAQ", "VICTIM", "USD", "US"),),
                ),
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa06",
                    legal="Ticker Holder Inc.",
                    display="Ticker Holder",
                    country="US",
                    aliases=(("Ticker Holder", AliasType.COMMON_NAME),),
                    listings=(("NYSE", "SHADOW", "USD", "US"),),
                ),
            )
        )
        self.collision_resolver = ResolveCompany(self.collision_catalog)

    def test_contradictory_constraints_are_not_found(self) -> None:
        cases = [
            CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NASDAQ")),
            CompanyQuery(raw_query="Apple", country=CountryCode("IN")),
            CompanyQuery(raw_query="AAPL", country=CountryCode("IN")),
            CompanyQuery(raw_query="MSFT", exchange=ExchangeCode("NSE")),
            CompanyQuery(
                raw_query="",
                ticker=TickerSymbol("RELIANCE"),
                exchange=ExchangeCode("NASDAQ"),
            ),
        ]
        for query in cases:
            with self.subTest(query=query):
                result = self.reference.execute(query)
                self.assertEqual(result.status, ResolutionStatus.NOT_FOUND)
                self.assertIsNone(result.company)

    def test_ticker_only_collision_is_ambiguous_context_resolves(self) -> None:
        ambiguous = self.collision_resolver.execute(CompanyQuery(raw_query="COLLIDE"))
        self.assertEqual(ambiguous.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(ambiguous.company)
        self.assertEqual(len(ambiguous.candidates), 2)

        nyse = self.collision_resolver.execute(
            CompanyQuery(raw_query="COLLIDE", exchange=ExchangeCode("NYSE"))
        )
        self.assertEqual(nyse.status, ResolutionStatus.RESOLVED)
        assert nyse.company is not None
        self.assertEqual(nyse.company.legal_name, "Alpha Collision Corp")

        india = self.collision_resolver.execute(
            CompanyQuery(raw_query="COLLIDE", country=CountryCode("IN"))
        )
        self.assertEqual(india.status, ResolutionStatus.RESOLVED)
        assert india.company is not None
        self.assertEqual(india.company.legal_name, "Beta Collision Limited")

    def test_alias_collision_is_ambiguous(self) -> None:
        result = self.collision_resolver.execute(CompanyQuery(raw_query="TwinBrand"))
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(result.company)
        self.assertEqual(len(result.candidates), 2)

    def test_ticker_precedes_conflicting_alias_intentionally(self) -> None:
        # "SHADOW" is an alias for Name Victim and a ticker for Ticker Holder.
        # Ticker-first policy resolves to the listing owner, not the alias owner.
        result = self.collision_resolver.execute(CompanyQuery(raw_query="SHADOW"))
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        assert result.company is not None
        self.assertEqual(result.company.legal_name, "Ticker Holder Inc.")
        self.assertEqual(result.matched_by, MatchMethod.EXACT_TICKER)

    def test_fixture_order_does_not_change_ambiguous_set(self) -> None:
        first = self.collision_catalog.find_by_ticker(TickerSymbol("COLLIDE"))
        reversed_catalog = InMemoryCompanyCatalog(
            tuple(reversed(self.collision_catalog._companies))
        )
        second = reversed_catalog.find_by_ticker(TickerSymbol("COLLIDE"))
        self.assertEqual(
            [company.company_id.as_text() for company in first],
            [company.company_id.as_text() for company in second],
        )


class AlphabetAndListingTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog())

    def test_alphabet_share_classes_and_reliance_listings(self) -> None:
        alphabet = self.resolver.execute(CompanyQuery(raw_query="Google"))
        self.assertEqual(alphabet.status, ResolutionStatus.RESOLVED)
        assert alphabet.company is not None
        self.assertEqual(len(alphabet.company.securities), 2)

        googl = self.resolver.execute(CompanyQuery(raw_query="GOOGL"))
        goog = self.resolver.execute(CompanyQuery(raw_query="GOOG"))
        assert googl.company is not None and goog.company is not None
        self.assertEqual(googl.company.company_id, goog.company.company_id)
        self.assertNotEqual(
            googl.candidates[0].matched_listings[0].listing_id,
            goog.candidates[0].matched_listings[0].listing_id,
        )

        reliance = self.resolver.execute(CompanyQuery(raw_query="Reliance"))
        self.assertEqual(reliance.status, ResolutionStatus.RESOLVED)
        assert reliance.company is not None
        exchanges = {listing.exchange.as_text() for listing in reliance.company.all_listings()}
        self.assertEqual(exchanges, {"NSE", "BSE"})
        nse = self.resolver.execute(
            CompanyQuery(raw_query="RELIANCE", exchange=ExchangeCode("NSE"))
        )
        self.assertEqual(nse.status, ResolutionStatus.RESOLVED)
        self.assertEqual(
            {listing.exchange.as_text() for listing in nse.candidates[0].matched_listings},
            {"NSE"},
        )


class FuzzyAndBoundsTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog())

    def test_typos_never_auto_resolve(self) -> None:
        for query in ("Aple", "Microsft", "Relaince", "Infossys", "Teslla"):
            with self.subTest(query=query):
                result = self.resolver.execute(CompanyQuery(raw_query=query))
                self.assertIn(
                    result.status,
                    {ResolutionStatus.AMBIGUOUS, ResolutionStatus.NOT_FOUND},
                )
                self.assertIsNone(result.company)
                if result.status is ResolutionStatus.AMBIGUOUS:
                    self.assertEqual(result.matched_by, MatchMethod.FUZZY_CANDIDATE)
                    self.assertEqual(result.confidence, ConfidenceBand.CANDIDATE)

    def test_fuzzy_threshold_boundary_semantics(self) -> None:
        self.assertEqual(FUZZY_RATIO_FLOOR, 0.88)
        ratio = SequenceMatcher(a="infosys", b="infosyss").ratio()
        self.assertGreaterEqual(ratio, 0.0)
        self.assertLessEqual(ratio, 1.0)

    def test_oversized_query_rejected_before_matching(self) -> None:
        result = self.resolver.execute(CompanyQuery(raw_query="x" * 201))
        self.assertEqual(result.status, ResolutionStatus.INVALID)
        result_ctrl = self.resolver.execute(CompanyQuery(raw_query="Apple\nInc"))
        self.assertEqual(result_ctrl.status, ResolutionStatus.INVALID)


class CatalogHardeningTests(TestCase):
    def test_duplicate_ids_and_listings_rejected(self) -> None:
        base = build_reference_companies()[0]
        with self.assertRaises(ValueError):
            InMemoryCompanyCatalog((base, base))

        left = _company(
            company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaab01",
            legal="Dup Listing A Inc.",
            display="Dup A",
            country="US",
            listings=(("NASDAQ", "DUPED", "USD", "US"),),
        )
        right = _company(
            company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaab02",
            legal="Dup Listing B Inc.",
            display="Dup B",
            country="US",
            listings=(("NASDAQ", "DUPED", "USD", "US"),),
        )
        with self.assertRaises(ValueError):
            InMemoryCompanyCatalog((left, right))

    def test_resolution_result_invariants(self) -> None:
        query = CompanyQuery(raw_query="Apple")
        with self.assertRaises(ValueError):
            ResolutionResult(
                query=query,
                status=ResolutionStatus.RESOLVED,
                matched_by=MatchMethod.EXACT_ALIAS,
                confidence=ConfidenceBand.EXACT,
                company=None,
            )
        with self.assertRaises(ValueError):
            ResolutionResult(
                query=query,
                status=ResolutionStatus.AMBIGUOUS,
                matched_by=MatchMethod.EXACT_ALIAS,
                confidence=ConfidenceBand.EXACT,
                company=build_reference_companies()[0],
                candidates=(),
            )


class ApiHardeningTests(TestCase):
    def test_api_ambiguous_contract_and_filters(self) -> None:
        catalog = InMemoryCompanyCatalog(
            (
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaac01",
                    legal="Api Ambiguous One Inc.",
                    display="Api Ambiguous One",
                    country="US",
                    aliases=(("AmbiguCorp", AliasType.BRAND),),
                    listings=(("NASDAQ", "AMB1", "USD", "US"),),
                ),
                _company(
                    company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaac02",
                    legal="Api Ambiguous Two Inc.",
                    display="Api Ambiguous Two",
                    country="US",
                    aliases=(("AmbiguCorp", AliasType.BRAND),),
                    listings=(("NYSE", "AMB2", "USD", "US"),),
                ),
            )
        )
        container = build_container(_settings())
        container.company_catalog = catalog
        container.resolve_company = ResolveCompany(catalog)
        app = create_app(settings=_settings(), container=container)
        with TestClient(app) as client:
            ambiguous = client.get(
                "/companies/resolve",
                params={"q": "AmbiguCorp"},
                headers={"X-Correlation-ID": "amb-1"},
            )
            conflict = client.get(
                "/companies/resolve",
                params={"q": "RELIANCE", "exchange": "NASDAQ"},
            )
            ok = client.get("/companies/resolve", params={"q": "Apple", "country": "US"})
        self.assertEqual(ambiguous.status_code, 200)
        self.assertEqual(ambiguous.headers["X-Correlation-ID"], "amb-1")
        self.assertEqual(ambiguous.headers["X-Content-Type-Options"], "nosniff")
        payload = ambiguous.json()
        self.assertEqual(payload["status"], "AMBIGUOUS")
        self.assertIsNone(payload["company"])
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertNotIn("InMemoryCompanyCatalog", str(payload))
        self.assertEqual(conflict.status_code, 200)
        self.assertEqual(conflict.json()["status"], "NOT_FOUND")
        # Custom container replaced catalog; Apple is absent → NOT_FOUND.
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "NOT_FOUND")

    def test_api_with_reference_catalog_still_resolves_apple(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/companies/resolve", params={"q": "Apple", "country": "US"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "RESOLVED")
        self.assertEqual(response.json()["company"]["legal_name"], "Apple Inc.")


class ProviderAndAliasTypeTests(TestCase):
    def test_provider_identifier_remains_metadata(self) -> None:
        provider = ProviderIdentifier(ProviderKind.SEC_CIK, "320193")
        self.assertEqual(provider.provider, ProviderKind.SEC_CIK)
        with self.assertRaises(ValueError):
            ProviderIdentifier(ProviderKind.OTHER, "")
        with self.assertRaises(ValueError):
            ProviderIdentifier(ProviderKind.OTHER, "x" * 100)

    def test_alias_types_serialize(self) -> None:
        company = _company(
            company_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaad01",
            legal="Alias Types Inc.",
            display="Alias Types",
            country="US",
            aliases=(
                ("Official Name", AliasType.OFFICIAL),
                ("Short", AliasType.SHORT_NAME),
                ("Former", AliasType.FORMER_NAME),
                ("BrandX", AliasType.BRAND),
                ("Common", AliasType.COMMON_NAME),
                ("ProvAlias", AliasType.PROVIDER_ALIAS),
            ),
            listings=(("NASDAQ", "ATYPE", "USD", "US"),),
        )
        types = {alias["alias_type"] for alias in company.to_dict()["aliases"]}  # type: ignore[index]
        self.assertEqual(
            types,
            {
                "official",
                "short_name",
                "former_name",
                "brand",
                "common_name",
                "provider_alias",
            },
        )
