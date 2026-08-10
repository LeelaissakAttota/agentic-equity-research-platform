"""Static MCP facade over a minimal allowlist of approved application capabilities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.contracts import ApplicationMetadata
from financial_intelligence.application.readiness import ReadinessRegistry
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol


class McpCapability(StrEnum):
    """The complete selected MCP allowlist for Phase 10."""

    SERVICE_STATUS = "service_status"
    RESOLVE_COMPANY = "resolve_company"


class McpResultStatus(StrEnum):
    """Bounded facade outcomes."""

    OK = "ok"
    INVALID = "invalid"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class McpToolDescriptor:
    """Read-only MCP capability metadata; never executable discovery data."""

    name: McpCapability
    description: str
    allowed_arguments: tuple[str, ...]
    read_only: bool = True
    external_calls: bool = False
    financial_advice: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "description": self.description,
            "allowed_arguments": list(self.allowed_arguments),
            "read_only": self.read_only,
            "external_calls": self.external_calls,
            "financial_advice": self.financial_advice,
        }


@dataclass(frozen=True, slots=True)
class McpInvocationResult:
    """Safe structured result without exception or secret detail."""

    status: McpResultStatus
    capability: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "capability": self.capability,
            "payload": dict(self.payload),
            "error_code": self.error_code,
            "message": self.message,
        }


_TOOLS = (
    McpToolDescriptor(
        name=McpCapability.SERVICE_STATUS,
        description="Return safe service version and readiness metadata.",
        allowed_arguments=(),
    ),
    McpToolDescriptor(
        name=McpCapability.RESOLVE_COMPANY,
        description="Resolve a bounded company query using canonical identity contracts.",
        allowed_arguments=("q", "country", "exchange", "ticker"),
    ),
)
_ALLOWED_ARGUMENTS = {
    descriptor.name: frozenset(descriptor.allowed_arguments) for descriptor in _TOOLS
}
_SAFE_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class SelectedMcpFacade:
    """Invoke only the frozen read-only MCP allowlist through explicit dispatch."""

    def __init__(
        self,
        *,
        metadata: ApplicationMetadata,
        readiness: ReadinessRegistry,
        resolve_company: ResolveCompany,
    ) -> None:
        self._metadata = metadata
        self._readiness = readiness
        self._resolve_company = resolve_company

    def list_tools(self) -> tuple[McpToolDescriptor, ...]:
        """Return the immutable, statically defined allowlist."""

        return _TOOLS

    def invoke(self, capability: str, arguments: Mapping[str, object]) -> McpInvocationResult:
        """Validate bounded arguments and dispatch without dynamic execution."""

        try:
            selected = McpCapability(capability)
        except ValueError:
            return self._rejected(capability, "tool_not_allowed", "Capability is not allowed")
        if len(arguments) > 4:
            return self._invalid(selected, "invalid_arguments", "Arguments are invalid")
        allowed = _ALLOWED_ARGUMENTS[selected]
        if set(arguments) - allowed:
            return self._invalid(selected, "invalid_arguments", "Arguments are invalid")
        if selected is McpCapability.SERVICE_STATUS:
            if arguments:
                return self._invalid(selected, "invalid_arguments", "Arguments are invalid")
            return self._service_status()
        if selected is McpCapability.RESOLVE_COMPANY:
            return self._resolve(arguments)
        return self._rejected(capability, "tool_not_allowed", "Capability is not allowed")

    def _service_status(self) -> McpInvocationResult:
        readiness = self._readiness.evaluate(self._metadata)
        return McpInvocationResult(
            status=McpResultStatus.OK,
            capability=McpCapability.SERVICE_STATUS.value,
            payload={
                "service": self._metadata.service,
                "version": self._metadata.version,
                "environment": self._metadata.environment,
                "readiness": readiness.status,
                "checks": [
                    {"name": item.name, "ready": item.ready, "detail": item.detail}
                    for item in readiness.checks
                ],
            },
        )

    def _resolve(self, arguments: Mapping[str, object]) -> McpInvocationResult:
        for value in arguments.values():
            if value is not None and not isinstance(value, str):
                return self._invalid(
                    McpCapability.RESOLVE_COMPANY,
                    "invalid_arguments",
                    "Arguments are invalid",
                )
            if isinstance(value, str) and len(value) > 200:
                return self._invalid(
                    McpCapability.RESOLVE_COMPANY,
                    "invalid_arguments",
                    "Arguments are invalid",
                )
        q = arguments.get("q", "")
        country = arguments.get("country")
        exchange = arguments.get("exchange")
        ticker = arguments.get("ticker")
        try:
            query = CompanyQuery(
                raw_query=q if isinstance(q, str) else "",
                country=CountryCode(country) if isinstance(country, str) and country else None,
                exchange=ExchangeCode(exchange) if isinstance(exchange, str) and exchange else None,
                ticker=TickerSymbol(ticker) if isinstance(ticker, str) and ticker else None,
            )
        except ValueError:
            return self._invalid(
                McpCapability.RESOLVE_COMPANY,
                "invalid_company_query",
                "Company query is invalid",
            )
        result = self._resolve_company.execute(query)
        return McpInvocationResult(
            status=McpResultStatus.OK,
            capability=McpCapability.RESOLVE_COMPANY.value,
            payload=result.to_dict(),
        )

    @staticmethod
    def _invalid(
        capability: McpCapability,
        error_code: str,
        message: str,
    ) -> McpInvocationResult:
        return McpInvocationResult(
            status=McpResultStatus.INVALID,
            capability=capability.value,
            error_code=error_code,
            message=message,
        )

    @staticmethod
    def _rejected(capability: str, error_code: str, message: str) -> McpInvocationResult:
        safe_capability = (
            capability if _SAFE_CAPABILITY_PATTERN.fullmatch(capability) else "invalid"
        )
        return McpInvocationResult(
            status=McpResultStatus.REJECTED,
            capability=safe_capability,
            error_code=error_code,
            message=message,
        )
