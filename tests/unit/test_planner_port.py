"""Tests for PlannerPort, PlannerOutcome, and the UnavailablePlannerAdapter stub."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from financial_intelligence.application.ports import LlmRouterPort, PlannerPort
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.orchestration import (
    PLANNER_VERSION,
    PlanId,
    PlannerOutcome,
    PlannerOutcomeStatus,
    PlanStatus,
    RequestId,
    ResearchObjective,
    ResearchPlan,
    ResearchRequest,
    ResearchTask,
    TaskId,
    TaskType,
)
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.infrastructure.orchestration import UnavailablePlannerAdapter


def _clock() -> datetime:
    return datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _request() -> ResearchRequest:
    return ResearchRequest(
        request_id=RequestId.new(),
        research_run_id=ResearchRunId.new(created_at=_clock()),
        objective=ResearchObjective.MARKET_ANALYSIS,
        raw_query="Apple",
        created_at=_clock(),
    )


def _plan() -> ResearchPlan:
    task = ResearchTask(
        task_id=TaskId.new(),
        task_type=TaskType.MARKET_INTELLIGENCE,
        capability_id="market_intelligence",
        description="fetch market snapshot",
        created_at=_clock(),
    )
    return ResearchPlan(
        plan_id=PlanId.new(),
        research_run_id=ResearchRunId.new(created_at=_clock()),
        objective=ResearchObjective.MARKET_ANALYSIS,
        company_id=CompanyId.new(),
        tasks=(task,),
        created_at=_clock(),
        planner_version=PLANNER_VERSION,
        status=PlanStatus.READY,
    )


class _FakePlanner:
    """Test-only PlannerPort implementation — not production intelligence."""

    def __init__(self, outcome: PlannerOutcome) -> None:
        self._outcome = outcome
        self.received_requests: list[ResearchRequest] = []

    def create_plan(self, request: ResearchRequest) -> PlannerOutcome:
        self.received_requests.append(request)
        return self._outcome


class PlannerOutcomeValidationTests(TestCase):
    def test_ok_requires_a_plan(self) -> None:
        with self.assertRaises(ValueError):
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="ok but no plan")

    def test_non_ok_forbids_a_plan(self) -> None:
        with self.assertRaises(ValueError):
            PlannerOutcome(
                status=PlannerOutcomeStatus.UNAVAILABLE,
                message="unavailable",
                plan=_plan(),
            )

    def test_ok_with_plan_is_valid(self) -> None:
        outcome = PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        self.assertIs(outcome.plan.__class__, ResearchPlan)

    def test_rejects_empty_message(self) -> None:
        with self.assertRaises(ValueError):
            PlannerOutcome(status=PlannerOutcomeStatus.FAILED, message="   ")

    def test_to_dict_shape(self) -> None:
        outcome = PlannerOutcome(
            status=PlannerOutcomeStatus.UNAVAILABLE, message="planner not implemented"
        )
        payload = outcome.to_dict()
        self.assertEqual(payload["status"], "unavailable")
        self.assertIsNone(payload["plan"])
        self.assertEqual(payload["kind"], "planner_outcome")


class PlannerPortProtocolTests(TestCase):
    def test_planner_port_is_runtime_checkable_and_provider_neutral(self) -> None:
        planner = UnavailablePlannerAdapter()
        self.assertIsInstance(planner, PlannerPort)
        # PlannerPort must not be the same protocol as LlmRouterPort — it sits
        # above it, it does not duplicate it.
        self.assertIsNot(PlannerPort, LlmRouterPort)

    def test_fake_planner_satisfies_the_protocol(self) -> None:
        fake = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        self.assertIsInstance(fake, PlannerPort)


class UnavailablePlannerAdapterTests(TestCase):
    def test_always_returns_typed_unavailable_outcome(self) -> None:
        adapter = UnavailablePlannerAdapter()
        outcome = adapter.create_plan(_request())
        self.assertEqual(outcome.status, PlannerOutcomeStatus.UNAVAILABLE)
        self.assertIsNone(outcome.plan)

    def test_never_fabricates_a_plan_across_repeated_calls(self) -> None:
        adapter = UnavailablePlannerAdapter()
        for _ in range(3):
            outcome = adapter.create_plan(_request())
            self.assertIsNone(outcome.plan)
            self.assertEqual(outcome.status, PlannerOutcomeStatus.UNAVAILABLE)


class PlannerFailurePropagationTests(TestCase):
    def test_failed_outcome_carries_no_plan(self) -> None:
        fake = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.FAILED, message="model call failed")
        )
        outcome = fake.create_plan(_request())
        self.assertEqual(outcome.status, PlannerOutcomeStatus.FAILED)
        self.assertIsNone(outcome.plan)

    def test_planner_receives_the_research_request(self) -> None:
        fake = _FakePlanner(
            PlannerOutcome(status=PlannerOutcomeStatus.OK, message="planned", plan=_plan())
        )
        request = _request()
        fake.create_plan(request)
        self.assertEqual(fake.received_requests, [request])
