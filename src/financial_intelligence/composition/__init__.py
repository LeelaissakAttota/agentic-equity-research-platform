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
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.ports import CompanyCatalogPort, MarketDataPort
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
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


def build_container(
    settings: Settings | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    market_data: MarketDataPort | None = None,
) -> AppContainer:
    """Wire settings, readiness, company resolution, and market intelligence.

    Optional ``clock`` freezes evaluation time for deterministic tests.
    Optional ``market_data`` injects a fully wired adapter (tests).

    Live Yahoo chart acquisition is opt-in via ``MARKET_DATA_LIVE_ENABLED``.
    Absence of live mode does not affect readiness (optional provider).
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
        fixture = InMemoryMarketDataAdapter()
        if (
            resolved.market_data_live_enabled
            and resolved.market_data_primary_provider == "yahoo_finance_chart"
        ):
            http = BoundedHttpClient(
                UrlLibHttpTransport(max_response_bytes=resolved.market_data_max_response_bytes),
                timeout_seconds=float(resolved.market_data_timeout_seconds),
                max_retries=resolved.market_data_max_retries,
                user_agent=(
                    "agentic-financial-intelligence/0.1 "
                    "(research; contact=local-dev; +https://github.com/"
                    "LeelaissakAttota/agentic-equity-research-platform)"
                ),
            )
            live = YahooChartMarketDataAdapter(
                http,
                history_days=resolved.market_data_history_days,
                clock=clock,
            )
            # Primary live, secondary fixture — provenance stays with the winner.
            stacked: MarketDataPort = FallbackMarketDataAdapter(live, fixture)
        else:
            stacked = fixture
        market_data = CachingMarketDataAdapter(
            stacked,
            ttl=timedelta(seconds=resolved.market_cache_ttl_seconds),
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
    return AppContainer(
        settings=resolved,
        readiness=readiness,
        metadata=metadata,
        company_catalog=catalog,
        resolve_company=resolve_company,
        market_data=market_data,
        get_market_snapshot=get_market_snapshot,
    )
