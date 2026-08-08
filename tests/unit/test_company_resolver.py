"""Company resolver tests for India, US, ambiguity, and invalid input."""

from __future__ import annotations

from unittest import TestCase

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    MatchMethod,
    ResolutionStatus,
)
from financial_intelligence.application.resolve_company import ResolveCompany
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
    SecurityId,
    SecurityIdentity,
    SecurityType,
    TickerSymbol,
)
from financial_intelligence.infrastructure.company import (
    InMemoryCompanyCatalog,
    build_reference_companies,
)


class CompanyResolverTests(TestCase):
    def setUp(self) -> None:
        self.resolver = ResolveCompany(InMemoryCompanyCatalog(build_reference_companies()))

    def _resolve(self, q: str, **kwargs: object) -> object:
        country = kwargs.get("country")
        exchange = kwargs.get("exchange")
        ticker = kwargs.get("ticker")
        return self.resolver.execute(
            CompanyQuery(
                raw_query=q,
                country=CountryCode(str(country)) if country else None,
                exchange=ExchangeCode(str(exchange)) if exchange else None,
                ticker=TickerSymbol(str(ticker)) if ticker else None,
            )
        )

    def test_india_resolution_examples(self) -> None:
        cases = [
            ("Reliance Industries", "Reliance Industries Limited"),
            ("Reliance", "Reliance Industries Limited"),
            ("RELIANCE", "Reliance Industries Limited"),
            ("Tata Consultancy Services", "Tata Consultancy Services Limited"),
            ("TCS", "Tata Consultancy Services Limited"),
            ("Infosys", "Infosys Limited"),
            ("INFY", "Infosys Limited"),
            ("HDFC Bank", "HDFC Bank Limited"),
        ]
        for query, legal in cases:
            with self.subTest(query=query):
                result = self._resolve(query)
                self.assertEqual(result.status, ResolutionStatus.RESOLVED)
                assert result.company is not None
                self.assertEqual(result.company.legal_name, legal)
                self.assertEqual(result.company.country.as_text(), "IN")

    def test_us_resolution_examples(self) -> None:
        cases = [
            ("Apple", "Apple Inc."),
            ("Apple Inc.", "Apple Inc."),
            ("AAPL", "Apple Inc."),
            ("Microsoft", "Microsoft Corporation"),
            ("MSFT", "Microsoft Corporation"),
            ("Google", "Alphabet Inc."),
            ("Alphabet", "Alphabet Inc."),
            ("GOOGL", "Alphabet Inc."),
            ("GOOG", "Alphabet Inc."),
            ("Amazon", "Amazon.com, Inc."),
            ("AMZN", "Amazon.com, Inc."),
            ("Tesla", "Tesla, Inc."),
            ("TSLA", "Tesla, Inc."),
        ]
        for query, legal in cases:
            with self.subTest(query=query):
                result = self._resolve(query)
                self.assertEqual(result.status, ResolutionStatus.RESOLVED)
                assert result.company is not None
                self.assertEqual(result.company.legal_name, legal)
                self.assertEqual(result.company.country.as_text(), "US")

    def test_alphabet_share_classes_remain_distinct(self) -> None:
        googl = self._resolve("GOOGL")
        goog = self._resolve("GOOG")
        self.assertEqual(googl.status, ResolutionStatus.RESOLVED)
        self.assertEqual(goog.status, ResolutionStatus.RESOLVED)
        assert googl.company is not None and goog.company is not None
        self.assertEqual(googl.company.company_id, goog.company.company_id)
        googl_tickers = {
            listing.ticker.as_text() for listing in googl.candidates[0].matched_listings
        }
        goog_tickers = {listing.ticker.as_text() for listing in goog.candidates[0].matched_listings}
        self.assertEqual(googl_tickers, {"GOOGL"})
        self.assertEqual(goog_tickers, {"GOOG"})
        classes = {security.share_class for security in googl.company.securities}
        self.assertEqual(classes, {"A", "C"})

    def test_case_and_whitespace_normalization(self) -> None:
        result = self._resolve("  apple   inc.  ")
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        assert result.company is not None
        self.assertEqual(result.company.display_name, "Apple")

    def test_ticker_plus_exchange(self) -> None:
        result = self._resolve("", ticker="RELIANCE", exchange="NSE")
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.matched_by, MatchMethod.EXACT_TICKER_EXCHANGE)

    def test_unknown_and_invalid_queries(self) -> None:
        missing = self._resolve("DefinitelyNotAListedCompanyXYZ")
        self.assertEqual(missing.status, ResolutionStatus.NOT_FOUND)
        empty = self._resolve("   ")
        self.assertEqual(empty.status, ResolutionStatus.INVALID)
        oversized = self._resolve("x" * 201)
        self.assertEqual(oversized.status, ResolutionStatus.INVALID)

    def test_malformed_country_rejected_by_value_object(self) -> None:
        with self.assertRaises(ValueError):
            CompanyQuery(raw_query="Apple", country=CountryCode("USA"))

    def test_ambiguous_ticker_collision_is_first_class(self) -> None:
        company_a_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01")
        company_b_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02")
        sec_a = SecurityId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb01")
        sec_b = SecurityId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb02")
        company_a = CompanyIdentity(
            company_id=company_a_id,
            legal_name="Alpha Collision Corp",
            display_name="Alpha Collision",
            country=CountryCode("US"),
            securities=(
                SecurityIdentity(
                    security_id=sec_a,
                    company_id=company_a_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Alpha Collision Common",
                    listings=(
                        ListingIdentity(
                            listing_id=ListingId.from_string(
                                "cccccccc-cccc-4ccc-8ccc-cccccccccc01"
                            ),
                            security_id=sec_a,
                            exchange=ExchangeCode("NYSE"),
                            ticker=TickerSymbol("COLLIDE"),
                            currency=CurrencyCode("USD"),
                            country=CountryCode("US"),
                        ),
                    ),
                ),
            ),
        )
        company_b = CompanyIdentity(
            company_id=company_b_id,
            legal_name="Beta Collision Limited",
            display_name="Beta Collision",
            country=CountryCode("IN"),
            aliases=(CompanyAlias.create("Beta Collision", AliasType.COMMON_NAME),),
            securities=(
                SecurityIdentity(
                    security_id=sec_b,
                    company_id=company_b_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Beta Collision Common",
                    listings=(
                        ListingIdentity(
                            listing_id=ListingId.from_string(
                                "cccccccc-cccc-4ccc-8ccc-cccccccccc02"
                            ),
                            security_id=sec_b,
                            exchange=ExchangeCode("NSE"),
                            ticker=TickerSymbol("COLLIDE"),
                            currency=CurrencyCode("INR"),
                            country=CountryCode("IN"),
                        ),
                    ),
                ),
            ),
        )
        resolver = ResolveCompany(InMemoryCompanyCatalog((company_a, company_b)))
        result = resolver.execute(CompanyQuery(raw_query="COLLIDE"))
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertEqual(len(result.candidates), 2)

    def test_weak_fuzzy_match_is_ambiguous_not_resolved(self) -> None:
        # Near-miss against Infosys should never auto-resolve.
        result = self._resolve("Infosyss")
        self.assertIn(
            result.status,
            {ResolutionStatus.AMBIGUOUS, ResolutionStatus.NOT_FOUND},
        )
        if result.status is ResolutionStatus.AMBIGUOUS:
            self.assertEqual(result.matched_by, MatchMethod.FUZZY_CANDIDATE)
            self.assertIsNone(result.company)
