"""Domain tests for company / security / listing identity."""

from __future__ import annotations

from unittest import TestCase

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


class IdentityPrimitiveTests(TestCase):
    def test_stable_company_id_is_uuid_v4_and_immutable(self) -> None:
        company_id = CompanyId.from_string("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        self.assertEqual(company_id.as_text(), "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        with self.assertRaises(AttributeError):
            company_id.value = CompanyId.new().value  # type: ignore[misc]
        with self.assertRaises(ValueError):
            CompanyId.from_string("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")

    def test_ticker_and_exchange_normalization(self) -> None:
        self.assertEqual(normalize_ticker("  reliance ").as_text(), "RELIANCE")
        self.assertEqual(normalize_ticker("aapl").as_text(), "AAPL")
        exchange = ExchangeCode("nasdaq")
        self.assertEqual(exchange.as_text(), "NASDAQ")
        self.assertEqual(exchange.mic, "XNAS")
        with self.assertRaises(ValueError):
            TickerSymbol("x" * 40)
        with self.assertRaises(ValueError):
            TickerSymbol("")

    def test_country_and_currency(self) -> None:
        self.assertEqual(CountryCode("in").as_text(), "IN")
        self.assertEqual(CurrencyCode("usd").as_text(), "USD")
        with self.assertRaises(ValueError):
            CountryCode("IND")
        with self.assertRaises(ValueError):
            CurrencyCode("US")

    def test_company_name_normalization_is_conservative(self) -> None:
        self.assertEqual(
            normalize_company_display_name("  Apple   Inc.  "),
            "Apple Inc.",
        )
        self.assertEqual(company_match_key("Apple Inc."), "apple")
        self.assertEqual(
            company_match_key("Tata Consultancy Services Limited"),
            "tata consultancy services",
        )
        with self.assertRaises(ValueError):
            normalize_company_display_name("   ")

    def test_aliases_and_provider_identifiers(self) -> None:
        alias = CompanyAlias.create("Google", AliasType.BRAND)
        self.assertEqual(alias.normalized, "google")
        provider = ProviderIdentifier(ProviderKind.SEC_CIK, "1652044")
        self.assertEqual(provider.value, "1652044")
        with self.assertRaises(ValueError):
            ProviderIdentifier(ProviderKind.OTHER, "")

    def test_multiple_listings_and_share_classes(self) -> None:
        company_id = CompanyId.from_string("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        sec_a = SecurityId.from_string("cccccccc-cccc-4ccc-8ccc-ccccccccccc1")
        sec_c = SecurityId.from_string("cccccccc-cccc-4ccc-8ccc-ccccccccccc2")
        listing_a = ListingIdentity(
            listing_id=ListingId.from_string("dddddddd-dddd-4ddd-8ddd-ddddddddddd1"),
            security_id=sec_a,
            exchange=ExchangeCode("NASDAQ"),
            ticker=TickerSymbol("GOOGL"),
            currency=CurrencyCode("USD"),
            country=CountryCode("US"),
            is_primary=True,
        )
        listing_c = ListingIdentity(
            listing_id=ListingId.from_string("dddddddd-dddd-4ddd-8ddd-ddddddddddd2"),
            security_id=sec_c,
            exchange=ExchangeCode("NASDAQ"),
            ticker=TickerSymbol("GOOG"),
            currency=CurrencyCode("USD"),
            country=CountryCode("US"),
        )
        company = CompanyIdentity(
            company_id=company_id,
            legal_name="Alphabet Inc.",
            display_name="Alphabet",
            country=CountryCode("US"),
            aliases=(CompanyAlias.create("Google", AliasType.BRAND),),
            securities=(
                SecurityIdentity(
                    security_id=sec_a,
                    company_id=company_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Alphabet Class A",
                    share_class="A",
                    listings=(listing_a,),
                ),
                SecurityIdentity(
                    security_id=sec_c,
                    company_id=company_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Alphabet Class C",
                    share_class="C",
                    listings=(listing_c,),
                ),
            ),
            provider_identifiers=(ProviderIdentifier(ProviderKind.SEC_CIK, "1652044"),),
        )
        self.assertEqual(len(company.securities), 2)
        self.assertEqual(len(company.all_listings()), 2)
        payload = company.to_dict()
        self.assertEqual(payload["company_id"], company_id.as_text())
        self.assertEqual(payload["aliases"][0]["alias_type"], "brand")
        self.assertEqual(company.securities[0].share_class, "A")
        self.assertEqual(company.securities[1].share_class, "C")

    def test_equality_by_value(self) -> None:
        left = CompanyId.from_string("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
        right = CompanyId.from_string("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
        self.assertEqual(left, right)
        self.assertEqual(TickerSymbol("AAPL"), TickerSymbol("aapl"))
