"""Infrastructure-neutral ports owned by the application layer.

Concrete adapters are wired only in the composition root.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.domain.financial import CompanyFinancialPackage
from financial_intelligence.domain.identity import (
    CompanyId,
    CompanyIdentity,
    CountryCode,
    ExchangeCode,
    ListingIdentity,
    TickerSymbol,
)
from financial_intelligence.domain.industry import CompanyIndustryPackage
from financial_intelligence.domain.market import MarketObservationSeries
from financial_intelligence.domain.memory import MemoryRecordId, ResearchMemoryRecord
from financial_intelligence.domain.news import CompanyEventPackage
from financial_intelligence.domain.notification import NotificationEvent
from financial_intelligence.domain.orchestration import ResearchTask, TaskExecutionResult
from financial_intelligence.domain.regulatory import CompanyRegulatoryPackage
from financial_intelligence.domain.watchlist import Watchlist, WatchlistId
from financial_intelligence.domain.workflow import (
    ResearchWorkflow,
    WorkflowCheckpoint,
    WorkflowId,
    WorkflowStatus,
)


@runtime_checkable
class PersistencePort(Protocol):
    """Future durable persistence boundary (PostgreSQL in later phases)."""

    def ping(self) -> bool:
        """Return True when the persistence dependency can accept work."""


@runtime_checkable
class ResearchWorkflowStorePort(Protocol):
    """Application-owned workflow persistence boundary.

    Prompt 1 uses an in-memory adapter. Durable DB persistence is deferred.
    """

    def save_workflow(self, workflow: ResearchWorkflow) -> None:
        """Create or replace a workflow aggregate."""

    def get_workflow(self, workflow_id: WorkflowId) -> ResearchWorkflow | None:
        """Return workflow or None when unknown."""

    def save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> None:
        """Persist a checkpoint for a workflow."""

    def get_latest_checkpoint(self, workflow_id: WorkflowId) -> WorkflowCheckpoint | None:
        """Return latest checkpoint or None."""

    def list_workflows(
        self,
        *,
        status: WorkflowStatus | None = None,
        company_id_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[ResearchWorkflow, ...]:
        """Return a bounded, deterministically ordered workflow list."""


@runtime_checkable
class ResearchMemoryPort(Protocol):
    """Structured research-memory boundary (not vector/RAG)."""

    def append(self, record: ResearchMemoryRecord) -> None:
        """Append an immutable memory record."""

    def get_record(self, record_id: MemoryRecordId) -> ResearchMemoryRecord | None:
        """Return one record or None."""

    def list_for_workflow(
        self, workflow_id: WorkflowId, *, limit: int = 100
    ) -> tuple[ResearchMemoryRecord, ...]:
        """List records for a workflow (deterministic order)."""

    def list_for_company(
        self, company_id: CompanyId, *, limit: int = 100
    ) -> tuple[ResearchMemoryRecord, ...]:
        """List records for a company (deterministic order)."""


@runtime_checkable
class WatchlistStorePort(Protocol):
    """Watchlist persistence boundary."""

    def save(self, watchlist: Watchlist) -> None:
        """Create or replace a watchlist."""

    def get(self, watchlist_id: WatchlistId) -> Watchlist | None:
        """Return watchlist or None."""

    def list_all(self, *, limit: int = 50, offset: int = 0) -> tuple[Watchlist, ...]:
        """Bounded watchlist listing."""


@runtime_checkable
class NotificationPort(Protocol):
    """Outbound notification boundary (in-memory / test adapters in Prompt 2)."""

    def publish(self, event: NotificationEvent) -> None:
        """Publish a notification event. May raise on adapter failure."""

    def list_events(self, *, limit: int = 100) -> tuple[NotificationEvent, ...]:
        """List published events for tests/dashboard foundation."""


@runtime_checkable
class CachePort(Protocol):
    """Future cache/coordination boundary (Redis in later phases)."""

    def ping(self) -> bool:
        """Return True when the cache dependency can accept work."""


@runtime_checkable
class CompanyCatalogPort(Protocol):
    """Application-owned catalog abstraction for company identity records.

    Implementations may be in-memory (Phase 2 foundation) or PostgreSQL later.
    """

    def get_by_id(self, company_id: CompanyId) -> CompanyIdentity | None:
        """Return a company by stable canonical id."""

    def find_by_ticker(
        self,
        ticker: TickerSymbol,
        *,
        exchange: ExchangeCode | None = None,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        """Find companies with a matching listing ticker (exchange/country optional)."""

    def find_by_alias(
        self,
        normalized_alias: str,
        *,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        """Find companies by normalized alias key."""

    def find_by_name(
        self,
        normalized_name: str,
        *,
        country: CountryCode | None = None,
    ) -> tuple[CompanyIdentity, ...]:
        """Find companies by normalized legal/display name key."""

    def search_name_candidates(
        self,
        normalized_name: str,
        *,
        country: CountryCode | None = None,
        limit: int = 5,
    ) -> tuple[CompanyIdentity, ...]:
        """Return bounded deterministic fuzzy name candidates (never authoritative alone)."""


@runtime_checkable
class MarketDataPort(Protocol):
    """Application-owned market observation boundary.

    Concrete adapters (fixture / optional live HTTP) are selected in composition.
    Implementations must never invent successful OHLCV when upstream data is missing.
    """

    def get_ohlcv_series(
        self,
        listing: ListingIdentity,
        *,
        company_id: CompanyId,
    ) -> MarketObservationSeries | None:
        """Return normalized OHLCV for a listing, or None when unavailable."""


@runtime_checkable
class FinancialDataPort(Protocol):
    """Application-owned financial/filing data boundary.

    Concrete adapters (fixture / optional SEC companyfacts HTTP) are selected
    in composition. Implementations must never invent financial facts when
    upstream data is missing.
    """

    def get_financial_package(
        self,
        company_id: CompanyId,
        *,
        fiscal_year: int | None = None,
    ) -> CompanyFinancialPackage | None:
        """Return normalized financial package for a company, or None when unavailable."""


@runtime_checkable
class NewsEventPort(Protocol):
    """Application-owned news/event research boundary (Phase 5).

    Concrete adapters (fixture-first) are selected in composition.
    Implementations must never invent events when upstream data is missing.
    """

    def get_event_package(
        self,
        company_id: CompanyId,
        *,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> CompanyEventPackage | None:
        """Return normalized company events, or None when unavailable."""


@runtime_checkable
class IndustryContextPort(Protocol):
    """Application-owned industry/competitor boundary (Phase 5).

    Concrete adapters are fixture-first. Never invent peer identities.
    """

    def get_industry_package(self, company_id: CompanyId) -> CompanyIndustryPackage | None:
        """Return industry/competitor package, or None when unavailable."""


@runtime_checkable
class RegulatoryEventPort(Protocol):
    """Application-owned regulatory intelligence boundary (Phase 5).

    Concrete adapters are fixture-first. Secondary allegations stay labeled.
    """

    def get_regulatory_package(
        self,
        company_id: CompanyId,
    ) -> CompanyRegulatoryPackage | None:
        """Return regulatory package, or None when unavailable."""


@runtime_checkable
class ResearchCapabilityExecutorPort(Protocol):
    """Execute one research task against an existing Phase 2-5 capability.

    Implementations are orchestration bridges only — they must never fabricate
    successful research and must preserve the plan's canonical CompanyId.
    """

    def execute_task(
        self,
        task: ResearchTask,
        *,
        company: CompanyIdentity,
        company_query: CompanyQuery,
    ) -> TaskExecutionResult:
        """Run a single task and return a typed evidence-aware result."""
