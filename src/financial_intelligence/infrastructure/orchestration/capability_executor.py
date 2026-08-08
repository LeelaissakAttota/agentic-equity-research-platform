"""Infrastructure adapter: map Phase 6 capability IDs to Phase 2-5 use cases."""

from __future__ import annotations

from financial_intelligence.application.capability_result_adapters import (
    adapt_financial_result,
    adapt_industry_result,
    adapt_market_result,
    adapt_news_result,
    adapt_regulatory_result,
    adapt_resolution_result,
)
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.financial_contracts import FinancialSnapshotQuery
from financial_intelligence.application.financial_snapshot import GetFinancialSnapshot
from financial_intelligence.application.industry_contracts import IndustrySnapshotQuery
from financial_intelligence.application.industry_snapshot import GetIndustryContextSnapshot
from financial_intelligence.application.market_contracts import MarketSnapshotQuery
from financial_intelligence.application.market_snapshot import GetMarketSnapshot
from financial_intelligence.application.news_event_contracts import NewsEventSnapshotQuery
from financial_intelligence.application.news_event_snapshot import GetNewsEventSnapshot
from financial_intelligence.application.regulatory_contracts import RegulatorySnapshotQuery
from financial_intelligence.application.regulatory_snapshot import GetRegulatorySnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.orchestration import (
    ResearchTask,
    TaskExecutionResult,
    TaskResultStatus,
    TaskType,
)


class Phase6CapabilityExecutor:
    """Orchestration bridge only - does not duplicate Phase 2-5 business logic."""

    def __init__(
        self,
        *,
        resolve_company: ResolveCompany,
        get_market_snapshot: GetMarketSnapshot,
        get_financial_snapshot: GetFinancialSnapshot,
        get_news_event_snapshot: GetNewsEventSnapshot,
        get_industry_snapshot: GetIndustryContextSnapshot,
        get_regulatory_snapshot: GetRegulatorySnapshot,
    ) -> None:
        self._resolve_company = resolve_company
        self._market = get_market_snapshot
        self._financial = get_financial_snapshot
        self._news = get_news_event_snapshot
        self._industry = get_industry_snapshot
        self._regulatory = get_regulatory_snapshot

    def execute_task(
        self,
        task: ResearchTask,
        *,
        company: CompanyIdentity,
        company_query: CompanyQuery,
    ) -> TaskExecutionResult:
        try:
            return self._dispatch(task, company=company, company_query=company_query)
        except Exception as exc:
            return TaskExecutionResult(
                task_id=task.task_id,
                status=TaskResultStatus.FAILED,
                message=f"capability executor exception: {exc.__class__.__name__}: {exc}",
                retryable=True,
                error_code="executor_exception",
            )

    def _dispatch(
        self,
        task: ResearchTask,
        *,
        company: CompanyIdentity,
        company_query: CompanyQuery,
    ) -> TaskExecutionResult:
        expected = company.company_id
        capability = task.capability_id
        if capability == "company_resolution" or task.task_type is TaskType.COMPANY_RESOLUTION:
            resolution = self._resolve_company.execute(company_query)
            return adapt_resolution_result(
                task.task_id,
                expected=expected,
                resolution=resolution,
                company=company,
            )
        if capability == "market_intelligence" or task.task_type is TaskType.MARKET_INTELLIGENCE:
            market = self._market.execute(MarketSnapshotQuery(company_query=company_query))
            return adapt_market_result(task.task_id, expected=expected, result=market)
        if (
            capability == "financial_intelligence"
            or task.task_type is TaskType.FINANCIAL_INTELLIGENCE
        ):
            financial = self._financial.execute(FinancialSnapshotQuery(company_query=company_query))
            return adapt_financial_result(task.task_id, expected=expected, result=financial)
        if (
            capability == "news_event_intelligence"
            or task.task_type is TaskType.NEWS_EVENT_INTELLIGENCE
        ):
            news = self._news.execute(NewsEventSnapshotQuery(company_query=company_query))
            return adapt_news_result(task.task_id, expected=expected, result=news)
        if (
            capability == "industry_intelligence"
            or task.task_type is TaskType.INDUSTRY_INTELLIGENCE
        ):
            industry = self._industry.execute(IndustrySnapshotQuery(company_query=company_query))
            return adapt_industry_result(task.task_id, expected=expected, result=industry)
        if (
            capability == "regulatory_intelligence"
            or task.task_type is TaskType.REGULATORY_INTELLIGENCE
        ):
            regulatory = self._regulatory.execute(
                RegulatorySnapshotQuery(company_query=company_query)
            )
            return adapt_regulatory_result(task.task_id, expected=expected, result=regulatory)
        return TaskExecutionResult(
            task_id=task.task_id,
            status=TaskResultStatus.FAILED,
            message=f"unknown capability_id={capability}",
            retryable=False,
            error_code="unknown_capability",
        )
