"""Phase 4 — controlled LLM tool-call execution.

Orchestrates the explicit, closed path required between "the model asked
for tool X with arguments Y" and "tool X actually runs":

    parsed StructuredModelOutput
        -> resolve tool name via CapabilityRegistry (closed lookup; unknown
           names are rejected with zero execution)
        -> validate arguments into a CompanyQuery (typed value objects;
           malformed/unsupported arguments are rejected with zero execution)
        -> resolve company identity via ResolveCompany
        -> execute exactly one deterministic capability via the injected
           ResearchCapabilityExecutorPort (Phase6CapabilityExecutor in
           production) — the same dispatch bridge Phase 6 orchestration
           already uses, never duplicated here
        -> typed ToolCallResult carrying the same TaskExecutionResult shape
           that already flows through the rest of the system (verification,
           evidence aggregation, etc.), so a tool-call result is not a new,
           parallel, unverified kind of output

No dynamic name resolution (``eval``, ``exec``, ``importlib``, string-based
``getattr``) is used anywhere in this module. Tool dispatch is a plain dict
lookup (``CapabilityRegistry.get``) followed by one fixed method call
(``ResearchCapabilityExecutorPort.execute_task``); nothing derived from
model output ever selects a Python callable dynamically.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.application.capability_registry import (
    CapabilityAvailability,
    CapabilityRegistry,
)
from financial_intelligence.application.company_resolution import (
    QUERY_MAX_LENGTH,
    CompanyQuery,
    ResolutionStatus,
)
from financial_intelligence.application.ports import ResearchCapabilityExecutorPort
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.domain.llm.ids import ToolCallId
from financial_intelligence.domain.llm.structured_output import (
    StructuredModelOutput,
    StructuredOutputKind,
    ToolCallPayload,
)
from financial_intelligence.domain.orchestration import (
    ResearchTask,
    TaskExecutionResult,
    TaskId,
    TaskResultStatus,
)

# Fixed, safe, bounded client-facing messages. Real exception details (if
# any) must never be interpolated into these — matches the
# ``_SAFE_CAPABILITY_FAILURE_MESSAGE`` convention in
# ``infrastructure/orchestration/capability_executor.py``.
_SAFE_MALFORMED_OUTPUT_MESSAGE = "model output was malformed or did not match a recognized shape"
_SAFE_UNEXPECTED_FAILURE_MESSAGE = "tool call execution failed unexpectedly"

_ALLOWED_TOOL_CALL_ARGUMENT_KEYS = frozenset({"raw_query", "country", "exchange", "ticker"})


class ToolCallResultStatus(StrEnum):
    """Outcome of handling one piece of parsed LLM output."""

    FINAL_ANSWER = "final_answer"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Typed, bounded outcome of ``ToolCallExecutionService.handle_model_output``.

    ``REJECTED`` means the requested tool call never reached execution
    (unknown tool, malformed structured output, or invalid arguments).
    ``FAILED`` means execution was attempted through the capability
    executor (or company resolution) and did not succeed. ``SUCCEEDED``
    carries the underlying ``TaskExecutionResult`` unchanged so downstream
    consumers (evidence aggregation, verification) see the exact same
    result shape as any other Phase 6 capability execution.
    """

    tool_call_id: ToolCallId
    status: ToolCallResultStatus
    message: str
    final_text: str | None = None
    task_result: TaskExecutionResult | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        message = self.message.strip()
        if not message or len(message) > 500:
            msg = "result message empty or exceeds bounds"
            raise ValueError(msg)
        object.__setattr__(self, "message", message)

        if self.error_code is not None:
            code = self.error_code.strip().lower().replace(" ", "_")
            if not code or len(code) > 64:
                msg = "error_code empty or exceeds bounds"
                raise ValueError(msg)
            object.__setattr__(self, "error_code", code)

        if self.status is ToolCallResultStatus.FINAL_ANSWER:
            if self.final_text is None or not self.final_text.strip():
                msg = "final_answer result requires non-empty final_text"
                raise ValueError(msg)
            if self.task_result is not None or self.error_code is not None:
                msg = "final_answer result must not carry task_result/error_code"
                raise ValueError(msg)
        elif self.status is ToolCallResultStatus.SUCCEEDED:
            if self.final_text is not None:
                msg = "succeeded result must not carry final_text"
                raise ValueError(msg)
            if self.task_result is None:
                msg = "succeeded result requires a task_result"
                raise ValueError(msg)
            if self.task_result.status not in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL}:
                msg = "succeeded result requires a successful/partial task_result"
                raise ValueError(msg)
        elif self.status is ToolCallResultStatus.REJECTED:
            if self.final_text is not None or self.task_result is not None:
                msg = "rejected result must not carry final_text/task_result"
                raise ValueError(msg)
            if self.error_code is None:
                msg = "rejected result requires an error_code"
                raise ValueError(msg)
        elif self.status is ToolCallResultStatus.FAILED:
            if self.final_text is not None:
                msg = "failed result must not carry final_text"
                raise ValueError(msg)
            if self.task_result is None and self.error_code is None:
                msg = "failed result requires a task_result or an error_code"
                raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "tool_call_id": self.tool_call_id.as_text(),
            "status": self.status.value,
            "message": self.message,
            "final_text": self.final_text,
            "task_result": self.task_result.to_dict() if self.task_result is not None else None,
            "error_code": self.error_code,
            "kind": "tool_call_result",
        }


def _optional_argument_text(arguments: Mapping[str, object], key: str) -> str | None:
    """Return a bounded string argument, or None; raises on an ambiguous type.

    Fail-closed: a present-but-non-string, non-null value is rejected rather
    than silently ignored (Phase 4 rule: reject rather than proceed when
    ambiguous).
    """

    if key not in arguments:
        return None
    value = arguments[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        msg = f"tool_call argument '{key}' must be a non-empty string when provided"
        raise ValueError(msg)
    return value


def build_company_query(arguments: Mapping[str, object]) -> CompanyQuery:
    """Validate-and-construct a ``CompanyQuery`` from tool-call arguments.

    Every current capability's ``Phase6CapabilityExecutor`` dispatch branch
    consumes a ``CompanyQuery`` (see ``infrastructure/orchestration/
    capability_executor.py``), so this is the one argument shape every
    registered capability needs from a tool call. Unknown argument keys are
    rejected rather than silently ignored.
    """

    unknown_keys = set(arguments) - _ALLOWED_TOOL_CALL_ARGUMENT_KEYS
    if unknown_keys:
        msg = "tool_call arguments include unsupported fields"
        raise ValueError(msg)

    raw_query = arguments.get("raw_query")
    if not isinstance(raw_query, str) or not raw_query.strip():
        msg = "tool_call arguments require a non-empty 'raw_query'"
        raise ValueError(msg)
    if len(raw_query) > QUERY_MAX_LENGTH:
        msg = "tool_call 'raw_query' exceeds bounds"
        raise ValueError(msg)

    country_text = _optional_argument_text(arguments, "country")
    exchange_text = _optional_argument_text(arguments, "exchange")
    ticker_text = _optional_argument_text(arguments, "ticker")

    return CompanyQuery(
        raw_query=raw_query,
        country=CountryCode(country_text) if country_text is not None else None,
        exchange=ExchangeCode(exchange_text) if exchange_text is not None else None,
        ticker=TickerSymbol(ticker_text) if ticker_text is not None else None,
    )


class ToolCallExecutionService:
    """Application-layer bridge from parsed LLM output to a deterministic result.

    Depends only on ports/application types already used elsewhere
    (``CapabilityRegistry``, ``ResolveCompany``,
    ``ResearchCapabilityExecutorPort``) — no new execution path, no
    duplicated dispatch logic, no infrastructure imports.
    """

    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        resolve_company: ResolveCompany,
        capability_executor: ResearchCapabilityExecutorPort,
    ) -> None:
        self._registry = registry
        self._resolve_company = resolve_company
        self._executor = capability_executor

    def handle_model_output(self, content: str) -> ToolCallResult:
        """Parse raw model text and route it to a typed, safe result.

        Never raises: malformed input, unknown tools, invalid arguments,
        and unexpected exceptions all become a typed ``ToolCallResult``.
        """

        tool_call_id = ToolCallId.new()
        try:
            structured = StructuredModelOutput.parse(content)
        except ValueError:
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.REJECTED,
                message=_SAFE_MALFORMED_OUTPUT_MESSAGE,
                error_code="malformed_structured_output",
            )

        if structured.kind is StructuredOutputKind.FINAL_ANSWER:
            assert structured.final_text is not None
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.FINAL_ANSWER,
                message="model returned a final answer (no tool call)",
                final_text=structured.final_text,
            )

        assert structured.tool_call is not None
        return self._execute_tool_call(tool_call_id, structured.tool_call)

    def _execute_tool_call(
        self, tool_call_id: ToolCallId, payload: ToolCallPayload
    ) -> ToolCallResult:
        # Step 1: tool names resolve only through CapabilityRegistry. Unknown
        # or arbitrary names (e.g. "os.system", "eval") are rejected here,
        # before anything resembling execution happens.
        capability = self._registry.get(payload.tool_name)
        if capability is None:
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.REJECTED,
                message="requested tool is not a registered capability",
                error_code="unknown_tool",
            )
        if capability.availability is CapabilityAvailability.UNAVAILABLE:
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.REJECTED,
                message="requested capability is currently unavailable",
                error_code="capability_unavailable",
            )

        # Step 2: schema-validate arguments before anything is executed.
        try:
            company_query = build_company_query(payload.arguments)
        except ValueError:
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.REJECTED,
                message="tool_call arguments failed validation",
                error_code="invalid_arguments",
            )

        try:
            resolution = self._resolve_company.execute(company_query)
        except Exception:
            # Fail closed: never leak an unexpected internal exception.
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.FAILED,
                message=_SAFE_UNEXPECTED_FAILURE_MESSAGE,
                error_code="tool_execution_failed",
            )

        if resolution.status is not ResolutionStatus.RESOLVED or resolution.company is None:
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.FAILED,
                message="company could not be resolved for this tool call",
                error_code="company_resolution_failed",
            )

        # Step 3: execute exactly one deterministic capability through the
        # existing Phase 6 dispatch bridge — never duplicated here, and
        # never a dynamically-resolved callable.
        task = ResearchTask(
            task_id=TaskId.new(),
            task_type=capability.task_type,
            capability_id=capability.capability_id,
            description=f"tool_call:{capability.capability_id}",
        )
        try:
            task_result = self._executor.execute_task(
                task,
                company=resolution.company,
                company_query=company_query,
            )
        except Exception:
            # Phase6CapabilityExecutor already catches its own exceptions;
            # this is a last-resort guard for any other executor port
            # implementation (e.g. a test double) that does not.
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.FAILED,
                message=_SAFE_UNEXPECTED_FAILURE_MESSAGE,
                error_code="tool_execution_failed",
            )

        if task_result.status in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL}:
            return ToolCallResult(
                tool_call_id=tool_call_id,
                status=ToolCallResultStatus.SUCCEEDED,
                message=task_result.message,
                task_result=task_result,
            )
        return ToolCallResult(
            tool_call_id=tool_call_id,
            status=ToolCallResultStatus.FAILED,
            message=task_result.message,
            task_result=task_result,
            error_code=task_result.error_code or "capability_execution_failed",
        )
