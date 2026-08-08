"""Small deterministic India/US reference company dataset for Phase 2 foundation.

This is a REFERENCE / TEST fixture only:

- not complete India or US market coverage
- not live exchange data
- not an investment-grade security master
- provider identifiers are omitted unless confidently known and required

Production company universes and live adapters are intentionally out of scope.
"""

from __future__ import annotations

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
    ListingStatus,
    SecurityId,
    SecurityIdentity,
    SecurityType,
    TickerSymbol,
)


def _listing(
    *,
    listing_id: str,
    security_id: SecurityId,
    exchange: str,
    ticker: str,
    currency: str,
    country: str,
    is_primary: bool = True,
) -> ListingIdentity:
    return ListingIdentity(
        listing_id=ListingId.from_string(listing_id),
        security_id=security_id,
        exchange=ExchangeCode(exchange),
        ticker=TickerSymbol(ticker),
        currency=CurrencyCode(currency),
        country=CountryCode(country),
        is_primary=is_primary,
        status=ListingStatus.ACTIVE,
    )


def build_reference_companies() -> tuple[CompanyIdentity, ...]:
    """Return the Phase 2 Prompt 1 reference catalog (immutable tuple)."""

    in_country = CountryCode("IN")
    us_country = CountryCode("US")

    reliance_id = CompanyId.from_string("11111111-1111-4111-8111-111111111001")
    tcs_id = CompanyId.from_string("11111111-1111-4111-8111-111111111002")
    infosys_id = CompanyId.from_string("11111111-1111-4111-8111-111111111003")
    hdfc_id = CompanyId.from_string("11111111-1111-4111-8111-111111111004")

    apple_id = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
    microsoft_id = CompanyId.from_string("22222222-2222-4222-8222-222222222002")
    alphabet_id = CompanyId.from_string("22222222-2222-4222-8222-222222222003")
    amazon_id = CompanyId.from_string("22222222-2222-4222-8222-222222222004")
    tesla_id = CompanyId.from_string("22222222-2222-4222-8222-222222222005")

    reliance_sec = SecurityId.from_string("31111111-1111-4111-8111-111111111001")
    tcs_sec = SecurityId.from_string("31111111-1111-4111-8111-111111111002")
    infosys_sec = SecurityId.from_string("31111111-1111-4111-8111-111111111003")
    hdfc_sec = SecurityId.from_string("31111111-1111-4111-8111-111111111004")
    apple_sec = SecurityId.from_string("32222222-2222-4222-8222-222222222001")
    microsoft_sec = SecurityId.from_string("32222222-2222-4222-8222-222222222002")
    alphabet_a = SecurityId.from_string("32222222-2222-4222-8222-222222222003")
    alphabet_c = SecurityId.from_string("32222222-2222-4222-8222-222222222004")
    amazon_sec = SecurityId.from_string("32222222-2222-4222-8222-222222222005")
    tesla_sec = SecurityId.from_string("32222222-2222-4222-8222-222222222006")

    companies = (
        CompanyIdentity(
            company_id=reliance_id,
            legal_name="Reliance Industries Limited",
            display_name="Reliance Industries",
            country=in_country,
            aliases=(
                CompanyAlias.create("Reliance", AliasType.SHORT_NAME),
                CompanyAlias.create("Reliance Industries", AliasType.COMMON_NAME),
            ),
            securities=(
                SecurityIdentity(
                    security_id=reliance_sec,
                    company_id=reliance_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Reliance Industries Common Share",
                    listings=(
                        _listing(
                            listing_id="41111111-1111-4111-8111-111111111001",
                            security_id=reliance_sec,
                            exchange="NSE",
                            ticker="RELIANCE",
                            currency="INR",
                            country="IN",
                        ),
                        _listing(
                            listing_id="41111111-1111-4111-8111-111111111011",
                            security_id=reliance_sec,
                            exchange="BSE",
                            ticker="RELIANCE",
                            currency="INR",
                            country="IN",
                            is_primary=False,
                        ),
                    ),
                ),
            ),
            sector="Energy",
            industry="Oil & Gas Refining",
        ),
        CompanyIdentity(
            company_id=tcs_id,
            legal_name="Tata Consultancy Services Limited",
            display_name="Tata Consultancy Services",
            country=in_country,
            aliases=(
                CompanyAlias.create("TCS", AliasType.SHORT_NAME),
                CompanyAlias.create("Tata Consultancy Services", AliasType.COMMON_NAME),
            ),
            securities=(
                SecurityIdentity(
                    security_id=tcs_sec,
                    company_id=tcs_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="TCS Common Share",
                    listings=(
                        _listing(
                            listing_id="41111111-1111-4111-8111-111111111002",
                            security_id=tcs_sec,
                            exchange="NSE",
                            ticker="TCS",
                            currency="INR",
                            country="IN",
                        ),
                    ),
                ),
            ),
            sector="Information Technology",
            industry="IT Services",
        ),
        CompanyIdentity(
            company_id=infosys_id,
            legal_name="Infosys Limited",
            display_name="Infosys",
            country=in_country,
            aliases=(CompanyAlias.create("Infosys", AliasType.SHORT_NAME),),
            securities=(
                SecurityIdentity(
                    security_id=infosys_sec,
                    company_id=infosys_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Infosys Common Share",
                    listings=(
                        _listing(
                            listing_id="41111111-1111-4111-8111-111111111003",
                            security_id=infosys_sec,
                            exchange="NSE",
                            ticker="INFY",
                            currency="INR",
                            country="IN",
                        ),
                    ),
                ),
            ),
            sector="Information Technology",
            industry="IT Services",
        ),
        CompanyIdentity(
            company_id=hdfc_id,
            legal_name="HDFC Bank Limited",
            display_name="HDFC Bank",
            country=in_country,
            aliases=(
                CompanyAlias.create("HDFC Bank", AliasType.COMMON_NAME),
                CompanyAlias.create("HDFC", AliasType.SHORT_NAME),
            ),
            securities=(
                SecurityIdentity(
                    security_id=hdfc_sec,
                    company_id=hdfc_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="HDFC Bank Common Share",
                    listings=(
                        _listing(
                            listing_id="41111111-1111-4111-8111-111111111004",
                            security_id=hdfc_sec,
                            exchange="NSE",
                            ticker="HDFCBANK",
                            currency="INR",
                            country="IN",
                        ),
                    ),
                ),
            ),
            sector="Financials",
            industry="Banks",
        ),
        CompanyIdentity(
            company_id=apple_id,
            legal_name="Apple Inc.",
            display_name="Apple",
            country=us_country,
            aliases=(
                CompanyAlias.create("Apple", AliasType.SHORT_NAME),
                CompanyAlias.create("Apple Inc", AliasType.COMMON_NAME),
            ),
            securities=(
                SecurityIdentity(
                    security_id=apple_sec,
                    company_id=apple_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Apple Common Share",
                    listings=(
                        _listing(
                            listing_id="42222222-2222-4222-8222-222222222001",
                            security_id=apple_sec,
                            exchange="NASDAQ",
                            ticker="AAPL",
                            currency="USD",
                            country="US",
                        ),
                    ),
                ),
            ),
            sector="Information Technology",
            industry="Consumer Electronics",
        ),
        CompanyIdentity(
            company_id=microsoft_id,
            legal_name="Microsoft Corporation",
            display_name="Microsoft",
            country=us_country,
            aliases=(CompanyAlias.create("Microsoft", AliasType.SHORT_NAME),),
            securities=(
                SecurityIdentity(
                    security_id=microsoft_sec,
                    company_id=microsoft_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Microsoft Common Share",
                    listings=(
                        _listing(
                            listing_id="42222222-2222-4222-8222-222222222002",
                            security_id=microsoft_sec,
                            exchange="NASDAQ",
                            ticker="MSFT",
                            currency="USD",
                            country="US",
                        ),
                    ),
                ),
            ),
            sector="Information Technology",
            industry="Software",
        ),
        CompanyIdentity(
            company_id=alphabet_id,
            legal_name="Alphabet Inc.",
            display_name="Alphabet",
            country=us_country,
            aliases=(
                CompanyAlias.create("Alphabet", AliasType.SHORT_NAME),
                CompanyAlias.create("Google", AliasType.BRAND),
                CompanyAlias.create("Alphabet Inc", AliasType.COMMON_NAME),
            ),
            securities=(
                SecurityIdentity(
                    security_id=alphabet_a,
                    company_id=alphabet_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Alphabet Class A",
                    share_class="A",
                    listings=(
                        _listing(
                            listing_id="42222222-2222-4222-8222-222222222003",
                            security_id=alphabet_a,
                            exchange="NASDAQ",
                            ticker="GOOGL",
                            currency="USD",
                            country="US",
                        ),
                    ),
                ),
                SecurityIdentity(
                    security_id=alphabet_c,
                    company_id=alphabet_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Alphabet Class C",
                    share_class="C",
                    listings=(
                        _listing(
                            listing_id="42222222-2222-4222-8222-222222222004",
                            security_id=alphabet_c,
                            exchange="NASDAQ",
                            ticker="GOOG",
                            currency="USD",
                            country="US",
                            is_primary=False,
                        ),
                    ),
                ),
            ),
            sector="Communication Services",
            industry="Internet Content",
        ),
        CompanyIdentity(
            company_id=amazon_id,
            legal_name="Amazon.com, Inc.",
            display_name="Amazon",
            country=us_country,
            aliases=(
                CompanyAlias.create("Amazon", AliasType.SHORT_NAME),
                CompanyAlias.create("Amazon.com", AliasType.BRAND),
            ),
            securities=(
                SecurityIdentity(
                    security_id=amazon_sec,
                    company_id=amazon_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Amazon Common Share",
                    listings=(
                        _listing(
                            listing_id="42222222-2222-4222-8222-222222222005",
                            security_id=amazon_sec,
                            exchange="NASDAQ",
                            ticker="AMZN",
                            currency="USD",
                            country="US",
                        ),
                    ),
                ),
            ),
            sector="Consumer Discretionary",
            industry="Internet Retail",
        ),
        CompanyIdentity(
            company_id=tesla_id,
            legal_name="Tesla, Inc.",
            display_name="Tesla",
            country=us_country,
            aliases=(CompanyAlias.create("Tesla", AliasType.SHORT_NAME),),
            securities=(
                SecurityIdentity(
                    security_id=tesla_sec,
                    company_id=tesla_id,
                    security_type=SecurityType.COMMON_SHARE,
                    display_name="Tesla Common Share",
                    listings=(
                        _listing(
                            listing_id="42222222-2222-4222-8222-222222222006",
                            security_id=tesla_sec,
                            exchange="NASDAQ",
                            ticker="TSLA",
                            currency="USD",
                            country="US",
                        ),
                    ),
                ),
            ),
            sector="Consumer Discretionary",
            industry="Automobiles",
        ),
    )
    return companies
