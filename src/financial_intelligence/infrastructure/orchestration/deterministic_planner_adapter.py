"""Deterministic ``PlannerPort`` adapter (no LLM, no network).

Flow::

    ResearchRequest
        -> ResolveCompany (server-side company identity)
        -> DeterministicPlanner.build_plan(research_run_id, objective, company_id, created_at)
        -> ResearchPlan
        -> PlannerOutcome

This adapter is the default production planner. It only translates between the
``PlannerPort`` contract and the existing ``DeterministicPlanner``: it invents no
planner inputs, builds no tasks of its own, and takes its planner version from the
planner it wraps. Task ids and task types remain server-generated /
registry-derived inside ``DeterministicPlanner``.

It never raises for an ordinary failure. Every outcome message is a fixed string;
exception text, request text, and internal details are never placed in a message.
"""

from __future__ import annotations

from financial_intelligence.application.company_resolution import (
    CompanyQuery,
    ResolutionStatus,
)
from financial_intelligence.application.create_research_plan import (
    PLANNER_BUDGET_EXCEEDED_MESSAGE,
)
from financial_intelligence.application.deterministic_planner import DeterministicPlanner
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.orchestration import (
    BudgetExceededError,
    PlannerOutcome,
    PlannerOutcomeStatus,
    ResearchRequest,
)
from financial_intelligence.observability.logging import get_logger

logger = get_logger(
    "financial_intelligence.infrastructure.orchestration.deterministic_planner_adapter"
)


class DeterministicPlannerAdapter:
    """``PlannerPort`` implementation backed by the existing ``DeterministicPlanner``."""

    def __init__(self, planner: DeterministicPlanner, resolve_company: ResolveCompany) -> None:
        self._planner = planner
        self._resolve_company = resolve_company

    @property
    def planner_version(self) -> str:
        return self._planner.planner_version

    def create_plan(self, request: ResearchRequest) -> PlannerOutcome:
        try:
            resolution = self._resolve_company.execute(
                CompanyQuery(
                    raw_query=request.raw_query,
                    country=request.country,
                    exchange=request.exchange,
                    ticker=request.ticker,
                )
            )
            if resolution.status is ResolutionStatus.INVALID:
                return self._outcome(PlannerOutcomeStatus.INVALID, "company query is invalid")
            if resolution.status is not ResolutionStatus.RESOLVED or resolution.company is None:
                return self._outcome(
                    PlannerOutcomeStatus.INVALID,
                    "company identity could not be uniquely resolved",
                )
            plan = self._planner.build_plan(
                research_run_id=request.research_run_id,
                objective=request.objective,
                company_id=resolution.company.company_id,
                created_at=request.created_at,
            )
        except BudgetExceededError:
            return self._outcome(PlannerOutcomeStatus.FAILED, PLANNER_BUDGET_EXCEEDED_MESSAGE)
        except KeyError:
            # CapabilityRegistry.require raises KeyError for an unknown capability id.
            return self._outcome(
                PlannerOutcomeStatus.UNAVAILABLE, "required capability unavailable"
            )
        except ValueError:
            return self._outcome(PlannerOutcomeStatus.FAILED, "planner validation failed")
        except Exception as exc:
            # PlannerPort must never raise on a planning failure. Only the exception
            # type is logged; its message may carry request content.
            logger.warning(
                "deterministic_planner_unexpected_failure",
                extra={
                    "request_id": request.request_id.as_text(),
                    "error_type": type(exc).__name__,
                },
            )
            return self._outcome(PlannerOutcomeStatus.FAILED, "planner failed unexpectedly")
        return PlannerOutcome(
            status=PlannerOutcomeStatus.OK,
            message="research plan created by deterministic planner",
            plan=plan,
            planner_version=self.planner_version,
        )

    def _outcome(self, status: PlannerOutcomeStatus, message: str) -> PlannerOutcome:
        return PlannerOutcome(status=status, message=message, planner_version=self.planner_version)
