"""Composition root: wires concrete adapters to application ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from financial_intelligence import __version__
from financial_intelligence.application.approval_policy import DeterministicApprovalPolicy
from financial_intelligence.application.capability_registry import CapabilityRegistry
from financial_intelligence.application.contracts import (
    ApplicationMetadata,
    ReadinessCheckResult,
)
from financial_intelligence.application.create_research_plan import CreateResearchPlan
from financial_intelligence.application.create_research_workflow import CreateResearchWorkflow
from financial_intelligence.application.deterministic_planner import DeterministicPlanner
from financial_intelligence.application.execute_research_plan import ExecuteResearchPlan
from financial_intelligence.application.financial_snapshot import GetFinancialSnapshot
from financial_intelligence.application.industry_snapshot import GetIndustryContextSnapshot
from financial_intelligence.application.manage_research_workflow import ManageResearchWorkflow
from financial_intelligence.application.manage_watchlist import ManageWatchlist
from financial_intelligence.application.market_freshness import MarketFreshnessPolicy
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.news_event_snapshot import GetNewsEventSnapshot
from financial_intelligence.application.ports import (
    CompanyCatalogPort,
    FinancialDataPort,
    IndustryContextPort,
    MarketDataPort,
    NewsEventPort,
    NotificationPort,
    RegulatoryEventPort,
    ResearchMemoryPort,
    ResearchWorkflowStorePort,
    WatchlistStorePort,
)
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.application.regulatory_snapshot import GetRegulatorySnapshot
from financial_intelligence.application.request_research_report import RequestResearchReport
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.application.verify_claims import VerifyClaimUseCase
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.orchestration import ResearchExecutionBudget
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.financial import (
    CachingFinancialDataAdapter,
    FallbackFinancialDataAdapter,
    InMemoryFinancialDataAdapter,
    SecCompanyFactsFinancialDataAdapter,
)
from financial_intelligence.infrastructure.http import BoundedHttpClient, UrlLibHttpTransport
from financial_intelligence.infrastructure.industry import (
    CachingIndustryAdapter,
    InMemoryIndustryAdapter,
)
from financial_intelligence.infrastructure.market import (
    CachingMarketDataAdapter,
    FallbackMarketDataAdapter,
    InMemoryMarketDataAdapter,
    YahooChartMarketDataAdapter,
)
from financial_intelligence.infrastructure.memory import InMemoryResearchMemoryStore
from financial_intelligence.infrastructure.news import (
    CachingNewsEventAdapter,
    InMemoryNewsEventAdapter,
)
from financial_intelligence.infrastructure.notification import InMemoryNotificationAdapter
from financial_intelligence.infrastructure.orchestration import Phase6CapabilityExecutor
from financial_intelligence.infrastructure.regulatory import (
    CachingRegulatoryAdapter,
    InMemoryRegulatoryAdapter,
)
from financial_intelligence.infrastructure.watchlist import InMemoryWatchlistStore
from financial_intelligence.infrastructure.workflow import InMemoryResearchWorkflowStore


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
    news_events: NewsEventPort
    get_news_event_snapshot: GetNewsEventSnapshot
    industry: IndustryContextPort
    get_industry_snapshot: GetIndustryContextSnapshot
    regulatory: RegulatoryEventPort
    get_regulatory_snapshot: GetRegulatorySnapshot
    capability_registry: CapabilityRegistry
    create_research_plan: CreateResearchPlan
    capability_executor: Phase6CapabilityExecutor
    execute_research_plan: ExecuteResearchPlan
    workflow_store: ResearchWorkflowStorePort
    create_research_workflow: CreateResearchWorkflow
    manage_research_workflow: ManageResearchWorkflow
    research_memory: ResearchMemoryPort
    watchlist_store: WatchlistStorePort
    manage_watchlist: ManageWatchlist
    notifications: NotificationPort
    request_research_report: RequestResearchReport
    verification_engine: VerificationEngine
    verify_claim: VerifyClaimUseCase


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
    news_events: NewsEventPort | None = None,
    industry: IndustryContextPort | None = None,
    regulatory: RegulatoryEventPort | None = None,
) -> AppContainer:
    """Wire settings, readiness, Phase 2-6 intelligence, and Phase 7 workflow foundation.

    Optional ``clock`` freezes evaluation time for deterministic tests.
    Optional adapters inject fully wired ports (tests).

    Live Yahoo chart and SEC companyfacts acquisition are opt-in via settings.
    Phase 5 qualitative intelligence remains fixture-first.
    Phase 6 executes deterministic plans synchronously through existing
    Phase 2-5 use cases (no LLM planner, no external workflow-engine dependency).
    Phase 7 Prompt 1 adds in-memory workflow persistence / approval / pause-resume
    coordination on top of Phase 6 (not durable DB; not RAG or vector memory).
    Phase 8 Prompt 1 adds deterministic verification engine (no LLM, no RAG).
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

    if news_events is None:
        news_events = CachingNewsEventAdapter(
            InMemoryNewsEventAdapter(),
            ttl=timedelta(seconds=resolved.news_cache_ttl_seconds),
            clock=clock,
        )

    if industry is None:
        industry = CachingIndustryAdapter(
            InMemoryIndustryAdapter(),
            ttl=timedelta(seconds=resolved.industry_cache_ttl_seconds),
            clock=clock,
        )

    if regulatory is None:
        regulatory = CachingRegulatoryAdapter(
            InMemoryRegulatoryAdapter(),
            ttl=timedelta(seconds=resolved.regulatory_cache_ttl_seconds),
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
    get_news_event_snapshot = GetNewsEventSnapshot(
        resolve_company=resolve_company,
        news_events=news_events,
        clock=clock,
    )
    get_industry_snapshot = GetIndustryContextSnapshot(
        resolve_company=resolve_company,
        industry=industry,
        clock=clock,
    )
    get_regulatory_snapshot = GetRegulatorySnapshot(
        resolve_company=resolve_company,
        regulatory=regulatory,
        clock=clock,
    )
    capability_registry = CapabilityRegistry()
    budget = ResearchExecutionBudget()
    planner = DeterministicPlanner(capability_registry, budget=budget)
    create_research_plan = CreateResearchPlan(
        resolve_company=resolve_company,
        planner=planner,
        budget=budget,
        clock=clock,
    )
    capability_executor = Phase6CapabilityExecutor(
        resolve_company=resolve_company,
        get_market_snapshot=get_market_snapshot,
        get_financial_snapshot=get_financial_snapshot,
        get_news_event_snapshot=get_news_event_snapshot,
        get_industry_snapshot=get_industry_snapshot,
        get_regulatory_snapshot=get_regulatory_snapshot,
    )
    execute_research_plan = ExecuteResearchPlan(
        create_research_plan=create_research_plan,
        capability_executor=capability_executor,
        budget=budget,
        clock=clock,
    )
    workflow_store: ResearchWorkflowStorePort = InMemoryResearchWorkflowStore()
    research_memory: ResearchMemoryPort = InMemoryResearchMemoryStore()
    watchlist_store: WatchlistStorePort = InMemoryWatchlistStore()
    notifications: NotificationPort = InMemoryNotificationAdapter()
    create_research_workflow = CreateResearchWorkflow(
        create_research_plan=create_research_plan,
        workflow_store=workflow_store,
        approval_policy=DeterministicApprovalPolicy(),
        notifications=notifications,
        clock=clock,
    )
    manage_research_workflow = ManageResearchWorkflow(
        workflow_store=workflow_store,
        execute_research_plan=execute_research_plan,
        resolve_company=resolve_company,
        research_memory=research_memory,
        notifications=notifications,
        clock=clock,
    )
    manage_watchlist = ManageWatchlist(
        watchlist_store=watchlist_store,
        resolve_company=resolve_company,
        create_research_workflow=create_research_workflow,
        notifications=notifications,
        clock=clock,
    )
    request_research_report = RequestResearchReport(
        workflow_store=workflow_store,
        clock=clock,
    )

    verification_engine = VerificationEngine()
    verify_claim = VerifyClaimUseCase(engine=verification_engine)

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
        news_events=news_events,
        get_news_event_snapshot=get_news_event_snapshot,
        industry=industry,
        get_industry_snapshot=get_industry_snapshot,
        regulatory=regulatory,
        get_regulatory_snapshot=get_regulatory_snapshot,
        capability_registry=capability_registry,
        create_research_plan=create_research_plan,
        capability_executor=capability_executor,
        execute_research_plan=execute_research_plan,
        workflow_store=workflow_store,
        create_research_workflow=create_research_workflow,
        manage_research_workflow=manage_research_workflow,
        research_memory=research_memory,
        watchlist_store=watchlist_store,
        manage_watchlist=manage_watchlist,
        notifications=notifications,
        request_research_report=request_research_report,
        verification_engine=verification_engine,
        verify_claim=verify_claim,
    )
