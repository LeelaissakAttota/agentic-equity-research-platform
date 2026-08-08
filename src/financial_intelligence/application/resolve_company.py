"""Deterministic-first ResolveCompany use case."""

from __future__ import annotations

from financial_intelligence.application.company_resolution import (
    QUERY_MAX_LENGTH,
    CompanyQuery,
    ConfidenceBand,
    MatchMethod,
    ResolutionCandidate,
    ResolutionResult,
    ResolutionStatus,
    confidence_for,
)
from financial_intelligence.application.ports import CompanyCatalogPort
from financial_intelligence.domain.identity import (
    company_match_key,
    normalize_ticker,
)
from financial_intelligence.domain.identity.codes import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.domain.identity.company import CompanyIdentity
from financial_intelligence.domain.identity.listing import ListingIdentity


class ResolveCompany:
    """Resolve untrusted company input via the company-catalog port.

    Frozen matching precedence (ADR-025):

    1. Validate and bound the query (reject empty/oversized/control input)
    2. Normalize country/exchange/ticker/name keys
    3. Exact ticker + exchange (when exchange provided)
    4. Exact ticker (AMBIGUOUS on multi-issuer collision)
    5. Exact alias
    6. Exact normalized legal/display name
    7. Bounded fuzzy name candidates → AMBIGUOUS only (never auto-RESOLVE)

    Explicit country/exchange/ticker constraints are never discarded to force a
    match. A false-positive RESOLVED is worse than NOT_FOUND or AMBIGUOUS.

    When a raw token looks like a ticker, ticker matching runs before
    alias/name matching. An explicit ``ticker`` query parameter that misses
    does not fall through to unconstrained name/alias resolution.
    """

    def __init__(self, catalog: CompanyCatalogPort) -> None:
        self._catalog = catalog

    def execute(self, query: CompanyQuery) -> ResolutionResult:
        raw = query.raw_query
        if raw is None or not isinstance(raw, str):
            return self._invalid(query, "query must be a string")
        if len(raw) > QUERY_MAX_LENGTH:
            return self._invalid(query, "query exceeds length bounds")
        if any(ord(ch) < 32 for ch in raw):
            return self._invalid(query, "query contains control characters")
        stripped = raw.strip()
        if not stripped and query.ticker is None:
            return self._invalid(query, "query is empty")

        ticker = query.ticker
        exchange = query.exchange
        country = query.country
        name_key = ""

        try:
            if stripped:
                name_key = company_match_key(stripped)
        except ValueError as exc:
            return self._invalid(query, str(exc))

        # 3-4: ticker paths (explicit ticker param or ticker-like raw query)
        resolved_ticker = ticker
        if resolved_ticker is None and stripped:
            maybe_ticker = stripped.upper()
            if self._looks_like_ticker(maybe_ticker):
                try:
                    resolved_ticker = normalize_ticker(maybe_ticker)
                except ValueError:
                    resolved_ticker = None

        if resolved_ticker is not None:
            ticker_result = self._resolve_ticker(
                query,
                ticker=resolved_ticker,
                exchange=exchange,
                country=country,
                normalized_query=name_key or resolved_ticker.as_text(),
            )
            if ticker_result.status is not ResolutionStatus.NOT_FOUND:
                return ticker_result
            # Explicit ticker parameter that misses must not fall through to
            # unconstrained name matching (prevents false positives).
            if query.ticker is not None:
                return ticker_result

        if not name_key:
            return self._not_found(query, normalized_query="")

        # 5: exact alias
        alias_hits = self._catalog.find_by_alias(name_key, country=country)
        alias_result = self._finalize_exact(
            query,
            hits=alias_hits,
            method=MatchMethod.EXACT_ALIAS,
            normalized_query=name_key,
            exchange=exchange,
            ticker=None,
        )
        if alias_result.status is not ResolutionStatus.NOT_FOUND:
            return alias_result

        # 6: exact normalized name
        name_hits = self._catalog.find_by_name(name_key, country=country)
        name_result = self._finalize_exact(
            query,
            hits=name_hits,
            method=MatchMethod.EXACT_NORMALIZED_NAME,
            normalized_query=name_key,
            exchange=exchange,
            ticker=None,
        )
        if name_result.status is not ResolutionStatus.NOT_FOUND:
            return name_result

        # 7: bounded fuzzy candidates only (never auto-resolve)
        fuzzy_hits = self._catalog.search_name_candidates(
            name_key,
            country=country,
            limit=5,
        )
        candidates = tuple(
            ResolutionCandidate(
                company=company,
                matched_by=MatchMethod.FUZZY_CANDIDATE,
                confidence=ConfidenceBand.CANDIDATE,
                matched_listings=self._matching_listings(company, exchange=exchange, ticker=None),
            )
            for company in fuzzy_hits
            if self._satisfies_exchange(company, exchange=exchange)
        )
        if not candidates:
            return self._not_found(query, normalized_query=name_key)

        return ResolutionResult(
            query=query,
            status=ResolutionStatus.AMBIGUOUS,
            matched_by=MatchMethod.FUZZY_CANDIDATE,
            confidence=ConfidenceBand.CANDIDATE,
            candidates=candidates,
            message="fuzzy matches require explicit disambiguation",
            normalized_query=name_key,
        )

    def _resolve_ticker(
        self,
        query: CompanyQuery,
        *,
        ticker: TickerSymbol,
        exchange: ExchangeCode | None,
        country: CountryCode | None,
        normalized_query: str,
    ) -> ResolutionResult:
        hits = self._catalog.find_by_ticker(
            ticker,
            exchange=exchange,
            country=country,
        )
        if not hits:
            return self._not_found(query, normalized_query=normalized_query)

        method = (
            MatchMethod.EXACT_TICKER_EXCHANGE if exchange is not None else MatchMethod.EXACT_TICKER
        )
        return self._finalize_exact(
            query,
            hits=hits,
            method=method,
            normalized_query=normalized_query,
            exchange=exchange,
            ticker=ticker,
        )

    def _finalize_exact(
        self,
        query: CompanyQuery,
        *,
        hits: tuple[CompanyIdentity, ...],
        method: MatchMethod,
        normalized_query: str,
        exchange: ExchangeCode | None,
        ticker: TickerSymbol | None = None,
    ) -> ResolutionResult:
        if not hits:
            return self._not_found(query, normalized_query=normalized_query)

        # Explicit exchange must be satisfied by at least one listing.
        constrained = tuple(
            company
            for company in hits
            if self._satisfies_exchange(company, exchange=exchange)
            and (
                ticker is None or self._matching_listings(company, exchange=exchange, ticker=ticker)
            )
        )
        if not constrained:
            return self._not_found(query, normalized_query=normalized_query)

        unique: dict[str, CompanyIdentity] = {
            company.company_id.as_text(): company for company in constrained
        }
        # Deterministic ordering independent of catalog insertion order.
        companies = tuple(sorted(unique.values(), key=lambda company: company.company_id.as_text()))
        confidence = confidence_for(method)

        if len(companies) == 1:
            company = companies[0]
            listings = self._matching_listings(company, exchange=exchange, ticker=ticker)
            return ResolutionResult(
                query=query,
                status=ResolutionStatus.RESOLVED,
                matched_by=method,
                confidence=confidence,
                company=company,
                candidates=(
                    ResolutionCandidate(
                        company=company,
                        matched_by=method,
                        confidence=confidence,
                        matched_listings=listings,
                    ),
                ),
                message="company resolved",
                normalized_query=normalized_query,
            )

        candidates = tuple(
            ResolutionCandidate(
                company=company,
                matched_by=method,
                confidence=confidence,
                matched_listings=self._matching_listings(company, exchange=exchange, ticker=ticker),
            )
            for company in companies
        )
        return ResolutionResult(
            query=query,
            status=ResolutionStatus.AMBIGUOUS,
            matched_by=method,
            confidence=confidence,
            candidates=candidates,
            message="multiple companies matched; explicit selection required",
            normalized_query=normalized_query,
        )

    @staticmethod
    def _satisfies_exchange(
        company: CompanyIdentity,
        *,
        exchange: ExchangeCode | None,
    ) -> bool:
        if exchange is None:
            return True
        return any(listing.exchange.value == exchange.value for listing in company.all_listings())

    @staticmethod
    def _matching_listings(
        company: CompanyIdentity,
        *,
        exchange: ExchangeCode | None,
        ticker: TickerSymbol | None,
    ) -> tuple[ListingIdentity, ...]:
        listings: list[ListingIdentity] = []
        for listing in company.all_listings():
            if ticker is not None and listing.ticker != ticker:
                continue
            if exchange is not None and listing.exchange.value != exchange.value:
                continue
            listings.append(listing)
        return tuple(listings)

    @staticmethod
    def _looks_like_ticker(token: str) -> bool:
        if " " in token:
            return False
        if not (1 <= len(token) <= 12):
            return False
        return token.replace(".", "").replace("-", "").isalnum()

    def _invalid(self, query: CompanyQuery, message: str) -> ResolutionResult:
        return ResolutionResult(
            query=query,
            status=ResolutionStatus.INVALID,
            matched_by=MatchMethod.INVALID_INPUT,
            confidence=ConfidenceBand.NONE,
            message=message,
        )

    def _not_found(self, query: CompanyQuery, *, normalized_query: str) -> ResolutionResult:
        return ResolutionResult(
            query=query,
            status=ResolutionStatus.NOT_FOUND,
            matched_by=MatchMethod.NONE,
            confidence=ConfidenceBand.NONE,
            message="no matching company identity",
            normalized_query=normalized_query,
        )
