"""In-memory CompanyCatalogPort adapter for deterministic foundation/testing."""

from __future__ import annotations

from difflib import SequenceMatcher

from financial_intelligence.domain.identity import (
    CompanyId,
    CompanyIdentity,
    CountryCode,
    ExchangeCode,
    TickerSymbol,
)
from financial_intelligence.infrastructure.company.reference_dataset import (
    build_reference_companies,
)

# Bounded fuzzy threshold: candidates only; never auto-resolve.
# SequenceMatcher ratios are similarity scores, not probabilities.
FUZZY_RATIO_FLOOR = 0.88


class InMemoryCompanyCatalog:
    """Replaceable in-memory catalog implementing CompanyCatalogPort."""

    def __init__(self, companies: tuple[CompanyIdentity, ...] | None = None) -> None:
        source = companies if companies is not None else build_reference_companies()
        self._companies = self._validated_snapshot(source)
        self._by_id = {company.company_id.as_text(): company for company in self._companies}

    @staticmethod
    def _validated_snapshot(
        companies: tuple[CompanyIdentity, ...],
    ) -> tuple[CompanyIdentity, ...]:
        company_ids: set[str] = set()
        security_ids: set[str] = set()
        listing_ids: set[str] = set()
        listing_keys: set[tuple[str, str]] = set()
        for company in companies:
            cid = company.company_id.as_text()
            if cid in company_ids:
                msg = f"duplicate CompanyId in catalog: {cid}"
                raise ValueError(msg)
            company_ids.add(cid)
            for security in company.securities:
                sid = security.security_id.as_text()
                if sid in security_ids:
                    msg = f"duplicate SecurityId in catalog: {sid}"
                    raise ValueError(msg)
                security_ids.add(sid)
                for listing in security.listings:
                    lid = listing.listing_id.as_text()
                    if lid in listing_ids:
                        msg = f"duplicate ListingId in catalog: {lid}"
                        raise ValueError(msg)
                    listing_ids.add(lid)
                    key = (listing.exchange.as_text(), listing.ticker.as_text())
                    if key in listing_keys:
                        msg = f"duplicate exchange+ticker listing in catalog: {key[0]}:{key[1]}"
                        raise ValueError(msg)
                    listing_keys.add(key)
        # Freeze as a new tuple so callers cannot mutate the catalog via the
        # input sequence reference (input may be a list cast by mistake).
        return tuple(companies)

    def get_by_id(self, company_id: CompanyId) -> CompanyIdentity | None:
        return self._by_id.get(company_id.as_text())

    def find_by_ticker(
        self,
        ticker: TickerSymbol,
        *,
        exchange: ExchangeCode | None = None,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        matches: list[CompanyIdentity] = []
        for company in self._companies:
            if country is not None and company.country != country:
                continue
            for listing in company.all_listings():
                if listing.ticker != ticker:
                    continue
                if exchange is not None and listing.exchange.value != exchange.value:
                    continue
                matches.append(company)
                break
        # Deterministic order by company id, not insertion order.
        matches.sort(key=lambda company: company.company_id.as_text())
        return tuple(matches)

    def find_by_alias(
        self,
        normalized_alias: str,
        *,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        matches: list[CompanyIdentity] = []
        for company in self._companies:
            if country is not None and company.country != country:
                continue
            if any(alias.normalized == normalized_alias for alias in company.aliases):
                matches.append(company)
        matches.sort(key=lambda company: company.company_id.as_text())
        return tuple(matches)

    def find_by_name(
        self,
        normalized_name: str,
        *,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        matches: list[CompanyIdentity] = []
        for company in self._companies:
            if country is not None and company.country != country:
                continue
            if (
                company.legal_name_key == normalized_name
                or company.display_name_key == normalized_name
            ):
                matches.append(company)
        matches.sort(key=lambda company: company.company_id.as_text())
        return tuple(matches)

    def search_name_candidates(
        self,
        normalized_name: str,
        *,
        country: CountryCode | None = None,
        limit: int = 5,
    ) -> tuple[CompanyIdentity, ...]:
        scored: list[tuple[float, CompanyIdentity]] = []
        for company in self._companies:
            if country is not None and company.country != country:
                continue
            keys = {
                company.legal_name_key,
                company.display_name_key,
                *(alias.normalized for alias in company.aliases),
            }
            best = max(
                (SequenceMatcher(a=normalized_name, b=key).ratio() for key in keys),
                default=0.0,
            )
            if best >= FUZZY_RATIO_FLOOR and best < 1.0:
                scored.append((best, company))
        scored.sort(key=lambda item: (-item[0], item[1].company_id.as_text()))
        return tuple(company for _, company in scored[: max(limit, 0)])
