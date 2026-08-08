"""Capability registry describing Phase 2-5 research capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from financial_intelligence.domain.orchestration.tasks import TaskType


class CapabilityAvailability(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Metadata for an orchestratable research capability (not the implementation)."""

    capability_id: str
    description: str
    availability: CapabilityAvailability
    required_inputs: tuple[str, ...]
    produced_output_type: str
    task_type: TaskType

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "description": self.description,
            "availability": self.availability.value,
            "required_inputs": list(self.required_inputs),
            "produced_output_type": self.produced_output_type,
            "task_type": self.task_type.value,
            "kind": "capability_descriptor",
        }


class CapabilityRegistry:
    """Read-only registry of Phase 2-5 capabilities for orchestration."""

    def __init__(self, capabilities: tuple[CapabilityDescriptor, ...] | None = None) -> None:
        data = capabilities if capabilities is not None else default_capability_registry()
        by_id: dict[str, CapabilityDescriptor] = {}
        for cap in data:
            if cap.capability_id in by_id:
                msg = f"duplicate capability_id: {cap.capability_id}"
                raise ValueError(msg)
            by_id[cap.capability_id] = cap
        self._by_id = by_id

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        return self._by_id.get(capability_id)

    def require(self, capability_id: str) -> CapabilityDescriptor:
        cap = self.get(capability_id)
        if cap is None:
            msg = f"unknown capability_id: {capability_id}"
            raise KeyError(msg)
        return cap

    def all(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(sorted(self._by_id.values(), key=lambda c: c.capability_id))

    def available(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(
            c for c in self.all() if c.availability is not CapabilityAvailability.UNAVAILABLE
        )


def default_capability_registry() -> tuple[CapabilityDescriptor, ...]:
    """Phase 2-5 capability descriptors (orchestration metadata only)."""

    return (
        CapabilityDescriptor(
            capability_id="company_resolution",
            description="Resolve company identity to canonical CompanyIdentity",
            availability=CapabilityAvailability.AVAILABLE,
            required_inputs=("company_query",),
            produced_output_type="company_resolution_result",
            task_type=TaskType.COMPANY_RESOLUTION,
        ),
        CapabilityDescriptor(
            capability_id="market_intelligence",
            description="Market OHLCV snapshot and deterministic market metrics",
            availability=CapabilityAvailability.AVAILABLE,
            required_inputs=("company_id", "listing"),
            produced_output_type="market_snapshot",
            task_type=TaskType.MARKET_INTELLIGENCE,
        ),
        CapabilityDescriptor(
            capability_id="financial_intelligence",
            description="Financial fundamentals snapshot and deterministic ratios",
            availability=CapabilityAvailability.AVAILABLE,
            required_inputs=("company_id",),
            produced_output_type="financial_snapshot",
            task_type=TaskType.FINANCIAL_INTELLIGENCE,
        ),
        CapabilityDescriptor(
            capability_id="news_event_intelligence",
            description="News and qualitative event snapshot with evidence refs",
            availability=CapabilityAvailability.AVAILABLE,
            required_inputs=("company_id",),
            produced_output_type="news_event_snapshot",
            task_type=TaskType.NEWS_EVENT_INTELLIGENCE,
        ),
        CapabilityDescriptor(
            capability_id="industry_intelligence",
            description="Industry classification and competitor relationships",
            availability=CapabilityAvailability.AVAILABLE,
            required_inputs=("company_id",),
            produced_output_type="industry_context_snapshot",
            task_type=TaskType.INDUSTRY_INTELLIGENCE,
        ),
        CapabilityDescriptor(
            capability_id="regulatory_intelligence",
            description="Regulatory events with authority and allegation labels",
            availability=CapabilityAvailability.AVAILABLE,
            required_inputs=("company_id",),
            produced_output_type="regulatory_snapshot",
            task_type=TaskType.REGULATORY_INTELLIGENCE,
        ),
    )
