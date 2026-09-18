"""Application tests for LLM Foundation Phase 4 — controlled tool-call execution.

Uses the real ``ResolveCompany`` + reference in-memory catalog (both already
used across the existing test suite) so company resolution behaves exactly
as it does in production, and a lightweight spy in place of
``ResearchCapabilityExecutorPort`` so tests can assert *whether* execution
was ever attempted, not just its result.
"""

from __future__ import annotations

import json
from unittest import TestCase

from financial_intelligence.application.capability_registry import (
    CapabilityAvailability,
    CapabilityDescriptor,
    CapabilityRegistry,
    default_capability_registry,
)
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.application.tool_call_execution import (
    ToolCallExecutionService,
    ToolCallResult,
    ToolCallResultStatus,
    build_company_query,
)
from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.llm.ids import ToolCallId
from financial_intelligence.domain.orchestration import (
    ResearchTask,
    TaskExecutionResult,
    TaskId,
    TaskResultStatus,
    TaskType,
)
from financial_intelligence.infrastructure.company import (
    InMemoryCompanyCatalog,
    build_reference_companies,
)


class _SpyCapabilityExecutor:
    """Stand-in for ``ResearchCapabilityExecutorPort`` that records calls."""

    def __init__(
        self, result: TaskExecutionResult | None = None, *, raises: Exception | None = None
    ) -> None:
        self.calls: list[ResearchTask] = []
        self._result = result
        self._raises = raises

    def execute_task(
        self,
        task: ResearchTask,
        *,
        company: CompanyIdentity,
        company_query: CompanyQuery,
    ) -> TaskExecutionResult:
        self.calls.append(task)
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


def _success_result(task_id: TaskId) -> TaskExecutionResult:
    return TaskExecutionResult(
        task_id=task_id,
        status=TaskResultStatus.SUCCESS,
        message="capability executed successfully",
    )


def _failed_result(task_id: TaskId) -> TaskExecutionResult:
    return TaskExecutionResult(
        task_id=task_id,
        status=TaskResultStatus.FAILED,
        message="capability failed",
        retryable=True,
        error_code="capability_execution_failed",
    )


def _make_service(
    executor: _SpyCapabilityExecutor, *, registry: CapabilityRegistry | None = None
) -> ToolCallExecutionService:
    resolve_company = ResolveCompany(InMemoryCompanyCatalog(build_reference_companies()))
    return ToolCallExecutionService(
        registry=registry or CapabilityRegistry(),
        resolve_company=resolve_company,
        capability_executor=executor,  # type: ignore[arg-type]
    )


def _tool_call_content(tool_name: str, arguments: dict[str, object]) -> str:
    return json.dumps({"type": "tool_call", "tool_name": tool_name, "arguments": arguments})


class FinalAnswerHandlingTests(TestCase):
    def test_final_answer_output_returns_final_answer_status_with_no_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output(
            json.dumps({"type": "final_answer", "text": "Apple trades as AAPL on NASDAQ."})
        )

        self.assertEqual(result.status, ToolCallResultStatus.FINAL_ANSWER)
        self.assertEqual(result.final_text, "Apple trades as AAPL on NASDAQ.")
        self.assertIsNone(result.task_result)
        self.assertEqual(executor.calls, [])


class MalformedOutputTests(TestCase):
    def test_malformed_json_is_rejected_without_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output("{not valid json")

        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "malformed_structured_output")
        self.assertEqual(executor.calls, [])

    def test_missing_required_field_is_rejected_without_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output(json.dumps({"type": "tool_call"}))

        # tool_name missing entirely -> the 'type' matches but required
        # 'tool_name' is absent, so parsing itself rejects it.
        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "malformed_structured_output")
        self.assertEqual(executor.calls, [])

    def test_malformed_output_message_never_leaks_raw_content(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)
        secret_marker = "AUDIT_MARKER_super_secret_internal_detail"

        result = service.handle_model_output(f"{{not valid json {secret_marker}")

        self.assertNotIn(secret_marker, result.message)
        self.assertNotIn(secret_marker, json.dumps(result.to_dict()))


class UnknownToolTests(TestCase):
    def test_unknown_tool_name_is_rejected_without_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content("not_a_real_capability", {"raw_query": "Apple"})
        )

        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "unknown_tool")
        self.assertEqual(executor.calls, [], "unknown tool must never reach the executor")

    def test_arbitrary_dotted_python_name_is_rejected_without_execution(self) -> None:
        """Proves no dynamic getattr/import resolves an LLM-supplied name."""

        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        for hostile_name in ("os.system", "eval", "subprocess.run", "__import__"):
            with self.subTest(hostile_name=hostile_name):
                result = service.handle_model_output(
                    _tool_call_content(hostile_name, {"raw_query": "irrelevant"})
                )
                self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
                self.assertEqual(result.error_code, "unknown_tool")

        self.assertEqual(executor.calls, [], "no hostile name may ever reach the executor")

    def test_unavailable_capability_is_rejected_without_execution(self) -> None:
        unavailable_registry = CapabilityRegistry(
            (
                CapabilityDescriptor(
                    capability_id="market_intelligence",
                    description="disabled for this test",
                    availability=CapabilityAvailability.UNAVAILABLE,
                    required_inputs=("company_id", "listing"),
                    produced_output_type="market_snapshot",
                    task_type=TaskType.MARKET_INTELLIGENCE,
                ),
            )
        )
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor, registry=unavailable_registry)

        result = service.handle_model_output(
            _tool_call_content("market_intelligence", {"raw_query": "Apple"})
        )

        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "capability_unavailable")
        self.assertEqual(executor.calls, [])


class InvalidArgumentTests(TestCase):
    def test_missing_raw_query_is_rejected_without_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output(_tool_call_content("company_resolution", {}))

        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "invalid_arguments")
        self.assertEqual(executor.calls, [])

    def test_unsupported_argument_key_is_rejected_without_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content(
                "company_resolution", {"raw_query": "Apple", "unexpected_field": "x"}
            )
        )

        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "invalid_arguments")
        self.assertEqual(executor.calls, [])

    def test_invalid_country_code_is_rejected_without_execution(self) -> None:
        executor = _SpyCapabilityExecutor()
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content(
                "company_resolution", {"raw_query": "Apple", "country": "not-a-code"}
            )
        )

        self.assertEqual(result.status, ToolCallResultStatus.REJECTED)
        self.assertEqual(result.error_code, "invalid_arguments")
        self.assertEqual(executor.calls, [])

    def test_build_company_query_accepts_valid_arguments(self) -> None:
        query = build_company_query(
            {"raw_query": "Apple", "country": "US", "exchange": "NASDAQ", "ticker": "AAPL"}
        )
        self.assertEqual(query.raw_query, "Apple")
        assert query.country is not None
        self.assertEqual(query.country.as_text(), "US")


class SuccessfulExecutionTests(TestCase):
    def test_registered_capability_executes_end_to_end(self) -> None:
        # The executor is a spy standing in for Phase6CapabilityExecutor; the
        # point under test is the *validation and dispatch path* around it
        # (capability resolution, argument validation, company resolution),
        # which is exercised for real.
        placeholder_task_id = TaskId.new()
        executor = _SpyCapabilityExecutor(result=_success_result(placeholder_task_id))
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content("company_resolution", {"raw_query": "Apple"})
        )

        self.assertEqual(result.status, ToolCallResultStatus.SUCCEEDED)
        self.assertEqual(len(executor.calls), 1)
        dispatched_task = executor.calls[0]
        self.assertEqual(dispatched_task.capability_id, "company_resolution")
        self.assertEqual(dispatched_task.task_type, TaskType.COMPANY_RESOLUTION)
        assert result.task_result is not None
        self.assertEqual(result.task_result.status, TaskResultStatus.SUCCESS)

    def test_capability_failure_surfaces_as_failed_with_task_result(self) -> None:
        placeholder_task_id = TaskId.new()
        executor = _SpyCapabilityExecutor(result=_failed_result(placeholder_task_id))
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content("company_resolution", {"raw_query": "Apple"})
        )

        self.assertEqual(result.status, ToolCallResultStatus.FAILED)
        self.assertEqual(len(executor.calls), 1)
        assert result.task_result is not None
        self.assertEqual(result.task_result.status, TaskResultStatus.FAILED)
        self.assertEqual(result.error_code, "capability_execution_failed")

    def test_executor_exception_does_not_leak_and_is_reported_as_failed(self) -> None:
        secret_marker = "AUDIT_MARKER_internal_db_host_10.0.0.5"
        executor = _SpyCapabilityExecutor(raises=RuntimeError(secret_marker))
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content("company_resolution", {"raw_query": "Apple"})
        )

        self.assertEqual(result.status, ToolCallResultStatus.FAILED)
        self.assertNotIn(secret_marker, result.message)
        self.assertNotIn(secret_marker, json.dumps(result.to_dict()))

    def test_unresolvable_company_query_fails_without_fabricating_success(self) -> None:
        executor = _SpyCapabilityExecutor(result=_success_result(TaskId.new()))
        service = _make_service(executor)

        result = service.handle_model_output(
            _tool_call_content("company_resolution", {"raw_query": "Totally Unknown Company Ltd"})
        )

        self.assertEqual(result.status, ToolCallResultStatus.FAILED)
        self.assertEqual(result.error_code, "company_resolution_failed")
        self.assertEqual(executor.calls, [], "unresolved company must never reach the executor")


class ToolCallResultTests(TestCase):
    def test_succeeded_requires_successful_task_result(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallResult(
                tool_call_id=ToolCallId.new(),
                status=ToolCallResultStatus.SUCCEEDED,
                message="ok",
                task_result=_failed_result(TaskId.new()),
            )

    def test_rejected_requires_error_code(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallResult(
                tool_call_id=ToolCallId.new(),
                status=ToolCallResultStatus.REJECTED,
                message="rejected",
            )

    def test_failed_requires_task_result_or_error_code(self) -> None:
        with self.assertRaises(ValueError):
            ToolCallResult(
                tool_call_id=ToolCallId.new(),
                status=ToolCallResultStatus.FAILED,
                message="failed",
            )

    def test_to_dict_round_trips_status_value(self) -> None:
        result = ToolCallResult(
            tool_call_id=ToolCallId.new(),
            status=ToolCallResultStatus.SUCCEEDED,
            message="ok",
            task_result=_success_result(TaskId.new()),
        )
        as_dict = result.to_dict()
        self.assertEqual(as_dict["status"], "succeeded")
        self.assertEqual(as_dict["kind"], "tool_call_result")


class DefaultRegistryCoverageTests(TestCase):
    def test_default_registry_has_no_hidden_extra_capabilities(self) -> None:
        """Sanity check: the closed registry lookup only ever matches these ids."""

        ids = {c.capability_id for c in default_capability_registry()}
        self.assertEqual(
            ids,
            {
                "company_resolution",
                "market_intelligence",
                "financial_intelligence",
                "news_event_intelligence",
                "industry_intelligence",
                "regulatory_intelligence",
            },
        )

    def test_every_registered_capability_is_satisfiable_by_build_company_query(self) -> None:
        """Architectural contract: Phase 4 has exactly one argument-building
        path (``build_company_query``), and it only ever produces a
        ``CompanyQuery``. That is only a safe, complete argument source for a
        capability whose ``required_inputs`` are themselves derivable from a
        resolved ``CompanyQuery``/``CompanyIdentity`` -- i.e. a company-centric
        capability.

        This test encodes that assumption explicitly rather than leaving it
        implicit. If a future capability is registered whose
        ``required_inputs`` fall outside this set, this test fails -- loudly,
        and before any tool call involving it is silently mis-validated --
        signaling that ``ToolCallExecutionService``'s single hardcoded
        ``build_company_query`` path must be generalized (e.g. into a
        per-capability argument-builder keyed off the resolved
        ``CapabilityDescriptor``) before that capability can be exposed as a
        tool call.
        """

        # Inputs a resolved CompanyQuery/CompanyIdentity can satisfy without
        # any additional tool-call argument: "company_query" is the argument
        # build_company_query itself produces; "company_id" and "listing" are
        # derived downstream from the resolved company by
        # Phase6CapabilityExecutor (listing defaults to None when absent --
        # see MarketSnapshotQuery.listing_id), not supplied separately by the
        # model.
        company_derivable_inputs = {"company_query", "company_id", "listing"}

        for capability in default_capability_registry():
            unsatisfiable = set(capability.required_inputs) - company_derivable_inputs
            self.assertFalse(
                unsatisfiable,
                msg=(
                    f"capability '{capability.capability_id}' requires inputs "
                    f"{sorted(unsatisfiable)} that a CompanyQuery built by "
                    "build_company_query cannot supply -- ToolCallExecutionService's "
                    "argument-building path must be generalized beyond "
                    "build_company_query before this capability can be safely "
                    "exposed as a tool call."
                ),
            )
