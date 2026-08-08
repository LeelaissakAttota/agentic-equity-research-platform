"""Composition root: wires concrete adapters to application ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from financial_intelligence import __version__
from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
)
from financial_intelligence.application.financial_snapshot import GetFinancialSnapshot
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.ports import (
    CompanyCatalogPort,
    FinancialDataPort,
    MarketDataPort,
)
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.financial import (
    CachingFinancialDataAdapter,
    FallbackFinancialDataAdapter,
    InMemoryFinancialDataAdapter,
    SecCompanyFactsFinancialDataAdapter,
)
from financial_intelligence.infrastructure.http import BoundedHttpClient, UrlLibHttpTransport
from financial_intelligence.infrastructure.market import (
    CachingMarketDataAdapter,
    FallbackMarketDataAdapter,
    InMemoryMarketDataAdapter,
    YahooChartMarketDataAdapter,
)


@dataclass(slots=True)
class AppContainer:
    """Application composition container."""

    settings: Settings
    readiness: ReadinessRegistry
    metadata: ApplicationMetadata
    company_catalog: CompanyCatalogPort
    resolve_company: ResolveCompany
    market_data: MarketDataPort
    get_market_snapshot: GetMarketSnapshot
    financial_data: FinancialDataPort
    get_financial_snapshot: GetFinancialSnapshot


def _sec_user_agent() -> str:
    return (
        "agentic-financial-intelligence/0.1 "
        "(research; contact=local-dev; +https://github.com/"
        "LeelaissakAttota/agentic-equity-research-platform)"
    )


def build_container(
    settings: Settings | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    market_data: MarketDataPort | None = None,
    financial_data: FinancialDataPort | None = None,
) -> AppContainer:
    """Wire settings, readiness, company resolution, market and financial intelligence.

    Optional ``clock`` freezes evaluation time for deterministic tests.
    Optional ``market_data`` / ``financial_data`` inject fully wired adapters (tests).

    Live Yahoo chart and SEC companyfacts acquisition are opt-in via settings.
    Absence of live mode does not affect readiness (optional providers).
    Fixture data is never labeled as live.
    """

    resolved = settings if settings is not None else Settings()
    metadata = ApplicationMetadata(
        service=resolved.service_name,
        version=__version__,
        environment=resolved.app_env,
    )
    readiness = ReadinessRegistry()
    readiness.register(
        "application",
        lambda: ReadinessCheckResult(
            name="application",
            ready=True,
            detail="application foundation loaded",
        ),
    )
    catalog: CompanyCatalogPort = InMemoryCompanyCatalog()
    resolve_company = ResolveCompany(catalog)

    if market_data is None:
        fixture_market = InMemoryMarketDataAdapter()
        if (
            resolved.market_data_live_enabled
            and resolved.market_data_primary_provider == "yahoo_finance_chart"
        ):
            http = BoundedHttpClient(
                UrlLibHttpTransport(max_response_bytes=resolved.market_data_max_response_bytes),
                timeout_seconds=float(resolved.market_data_timeout_seconds),
                max_retries=resolved.market_data_max_retries,
                user_agent=_sec_user_agent(),
            )
            live = YahooChartMarketDataAdapter(
                http,
                history_days=resolved.market_data_history_days,
                clock=clock,
            )
            stacked_market: MarketDataPort = FallbackMarketDataAdapter(live, fixture_market)
        else:
            stacked_market = fixture_market
        market_data = CachingMarketDataAdapter(
            stacked_market,
            ttl=timedelta(seconds=resolved.market_cache_ttl_seconds),
            clock=clock,
        )

    if financial_data is None:
        fixture_financial = InMemoryFinancialDataAdapter()
        if (
            resolved.financial_data_live_enabled
            and resolved.financial_data_primary_provider == "sec_company_facts"
        ):
            fin_http = BoundedHttpClient(
                UrlLibHttpTransport(max_response_bytes=resolved.financial_data_max_response_bytes),
                timeout_seconds=float(resolved.financial_data_timeout_seconds),
                max_retries=resolved.financial_data_max_retries,
                user_agent=_sec_user_agent(),
            )
            live_financial = SecCompanyFactsFinancialDataAdapter(fin_http, clock=clock)
            stacked_financial: FinancialDataPort = FallbackFinancialDataAdapter(
                live_financial,
                fixture_financial,
            )
        else:
            stacked_financial = fixture_financial
        financial_data = CachingFinancialDataAdapter(
            stacked_financial,
            ttl=timedelta(seconds=resolved.financial_cache_ttl_seconds),
            clock=clock,
        )

    freshness = MarketFreshnessPolicy(
        stale_after=timedelta(hours=resolved.market_stale_after_hours),
    )
    get_market_snapshot = GetMarketSnapshot(
        resolve_company=resolve_company,
        market_data=market_data,
        freshness_policy=freshness,
        clock=clock,
    )
    get_financial_snapshot = GetFinancialSnapshot(
        resolve_company=resolve_company,
        financial_data=financial_data,
        clock=clock,
    )
    return AppContainer(
        settings=resolved,
        readiness=readiness,
        metadata=metadata,
        company_catalog=catalog,
        resolve_company=resolve_company,
        market_data=market_data,
        get_market_snapshot=get_market_snapshot,
        financial_data=financial_data,
        get_financial_snapshot=get_financial_snapshot,
    )
