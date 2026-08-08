"""Watchlist and explicit monitoring-check use cases."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.create_research_workflow import CreateResearchWorkflow
from financial_intelligence.application.ports import NotificationPort, WatchlistStorePort
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.application.workflow_contracts import (
    CreateResearchWorkflowQuery,
    WorkflowOperationResult,
)
from financial_intelligence.domain.identity import ExchangeCode
from financial_intelligence.domain.notification import (
    NotificationEvent,
    NotificationId,
    NotificationType,
)
from financial_intelligence.domain.orchestration import ResearchObjective
from financial_intelligence.domain.watchlist import (
    MonitoringCapability,
    MonitoringPolicy,
    Watchlist,
    WatchlistEntry,
    WatchlistId,
)


class WatchlistOperationStatus(StrEnum):
    OK = "ok"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WatchlistEntryInput:
    q: str
    exchange: str | None = None


@dataclass(frozen=True, slots=True)
class CreateWatchlistQuery:
    name: str
    entries: tuple[WatchlistEntryInput, ...] = ()
    capabilities: tuple[str, ...] = ("market",)
    interval_hours: int = 24


@dataclass(frozen=True, slots=True)
class WatchlistOperationResult:
    status: WatchlistOperationStatus
    message: str
    watchlist: Watchlist | None = None
    workflows: tuple[WorkflowOperationResult, ...] = ()
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "watchlist": self.watchlist.to_dict() if self.watchlist else None,
            "workflows": [w.to_dict() for w in self.workflows],
            "evaluated_at": (
                self.evaluated_at.isoformat().replace("+00:00", "Z") if self.evaluated_at else None
            ),
            "kind": "watchlist_operation_result",
        }


class ManageWatchlist:
    def __init__(
        self,
        watchlist_store: WatchlistStorePort,
        resolve_company: ResolveCompany,
        create_research_workflow: CreateResearchWorkflow,
        *,
        notifications: NotificationPort | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = watchlist_store
        self._resolve = resolve_company
        self._create_workflow = create_research_workflow
        self._notifications = notifications
        self._clock = clock or (lambda: datetime.now(UTC))

    def create(self, query: CreateWatchlistQuery) -> WatchlistOperationResult:
        now = self._clock()
        try:
            caps = tuple(MonitoringCapability(c) for c in query.capabilities)
            policy = MonitoringPolicy(capabilities=caps, interval_hours=query.interval_hours)
            entries: list[WatchlistEntry] = []
            for item in query.entries:
                resolution = self._resolve.execute(
                    CompanyQuery(
                        raw_query=item.q,
                        exchange=ExchangeCode(item.exchange) if item.exchange else None,
                    )
                )
                if resolution.company is None:
                    msg = f"cannot resolve watchlist entry q={item.q!r}"
                    raise ValueError(msg)
                entries.append(
                    WatchlistEntry(
                        company_id=resolution.company.company_id,
                        raw_query=item.q,
                        exchange=ExchangeCode(item.exchange) if item.exchange else None,
                    )
                )
            watchlist = Watchlist(
                watchlist_id=WatchlistId.new(),
                name=query.name,
                created_at=now,
                updated_at=now,
                entries=tuple(entries),
                policy=policy,
            )
        except ValueError as exc:
            return WatchlistOperationResult(
                status=WatchlistOperationStatus.INVALID,
                message=str(exc),
                evaluated_at=now,
            )
        self._store.save(watchlist)
        return WatchlistOperationResult(
            status=WatchlistOperationStatus.OK,
            message="watchlist created",
            watchlist=watchlist,
            evaluated_at=now,
        )

    def get(self, watchlist_id: WatchlistId) -> WatchlistOperationResult:
        now = self._clock()
        watchlist = self._store.get(watchlist_id)
        if watchlist is None:
            return WatchlistOperationResult(
                status=WatchlistOperationStatus.NOT_FOUND,
                message="watchlist not found",
                evaluated_at=now,
            )
        return WatchlistOperationResult(
            status=WatchlistOperationStatus.OK,
            message="watchlist loaded",
            watchlist=watchlist,
            evaluated_at=now,
        )

    def evaluate(self, watchlist_id: WatchlistId) -> WatchlistOperationResult:
        """Explicit monitoring check: create bounded workflows for each entry.

        Does not schedule, poll, or loop. One invocation → finite workflow creates.
        """

        now = self._clock()
        watchlist = self._store.get(watchlist_id)
        if watchlist is None:
            return WatchlistOperationResult(
                status=WatchlistOperationStatus.NOT_FOUND,
                message="watchlist not found",
                evaluated_at=now,
            )
        if watchlist.policy is None or not watchlist.policy.enabled:
            return WatchlistOperationResult(
                status=WatchlistOperationStatus.CONFLICT,
                message="monitoring policy disabled",
                watchlist=watchlist,
                evaluated_at=now,
            )
        created: list[WorkflowOperationResult] = []
        for entry in watchlist.entries:
            result = self._create_workflow.execute(
                CreateResearchWorkflowQuery(
                    company_query=CompanyQuery(
                        raw_query=entry.raw_query,
                        exchange=entry.exchange,
                    ),
                    objective=ResearchObjective.MARKET_ANALYSIS,
                )
            )
            created.append(result)
        if self._notifications is not None:
            with suppress(Exception):
                self._notifications.publish(
                    NotificationEvent(
                        notification_id=NotificationId.new(),
                        notification_type=NotificationType.MONITORING_CHECK_CREATED,
                        created_at=now,
                        message="explicit monitoring check created workflows",
                        metadata=(
                            ("watchlist_id", watchlist.watchlist_id.as_text()),
                            ("workflow_count", str(len(created))),
                        ),
                    )
                )
        return WatchlistOperationResult(
            status=WatchlistOperationStatus.OK,
            message="monitoring check created workflows",
            watchlist=watchlist,
            workflows=tuple(created),
            evaluated_at=now,
        )
