"""Strict parser/validator for the structured JSON a future LLM planner returns.

This module is the first, provider-independent step of LLM planning::

    untrusted LLM text -> strict JSON parse -> strict validation -> PlannerOutput

It knows nothing about OpenRouter, HTTP, prompts, or any provider, and it
deliberately does **not** build ``ResearchTask`` / ``ResearchPlan`` /
``TaskId`` / ``TaskType``. Turning a validated :class:`PlannerOutput` into a
domain ``ResearchPlan`` (server-generated ids, ``TaskType`` resolution against
the capability registry, company/run binding, dependency-cycle detection and
``ResearchExecutionBudget`` checks) belongs to a later adapter.

The planner is prompted to emit exactly one closed JSON object::

    {
      "type": "research_plan",
      "tasks": [
        {
          "capability_id": "market_intelligence",
          "description": "Fetch current market snapshot and valuation context",
          "depends_on": [],
          "priority": 10
        }
      ]
    }

Nothing else is accepted: unknown fields at either level are rejected, values
are never coerced (``"10"`` is not ``10``; ``{}`` is not ``[]``), and every
string/collection is bounded. ``depends_on`` holds zero-based indexes into the
same ``tasks`` array, because the model must never supply ``TaskId`` UUIDs.
Everything server-controlled (ids, status, attempts, timestamps, company,
research run, planner version, evidence, URLs) has no field here at all.

Failures raise :class:`PlannerOutputError`, a ``ValueError`` subclass (this
codebase's domain convention) that carries a closed
:class:`PlannerOutputErrorKind`. Messages are fixed, safe strings: they never
echo model output or attacker-controlled text.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NoReturn

from financial_intelligence.domain.orchestration.budget import ResearchExecutionBudget

PLANNER_OUTPUT_TYPE = "research_plan"

# Raw-content bound, checked before any parsing work. Kept equal to
# ``structured_output._MAX_STRUCTURED_CONTENT_LENGTH`` (asserted in tests) so
# planner output and general structured output share one conceptual limit.
MAX_PLANNER_OUTPUT_LENGTH = 32_768

# Never above what a plan may hold: the default ``ResearchExecutionBudget``
# cap (whose validated ceiling is 100). A runtime budget may be stricter; the
# later adapter still enforces it via ``ResearchExecutionBudget.validate_tasks``.
MAX_PLANNER_TASKS = ResearchExecutionBudget().max_tasks

# Mirror the bounds ``ResearchTask.__post_init__`` enforces, so anything this
# parser accepts is constructible later (compatibility is asserted in tests).
MAX_DESCRIPTION_LENGTH = 512
MIN_PRIORITY = 1
MAX_PRIORITY = 1000

MAX_CAPABILITY_ID_LENGTH = 64
_CAPABILITY_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*")

_TOP_LEVEL_FIELDS = frozenset({"type", "tasks"})
_TASK_FIELDS = frozenset({"capability_id", "description", "depends_on", "priority"})


class PlannerOutputErrorKind(StrEnum):
    """Closed classification a caller can branch on without inspecting text."""

    MALFORMED_JSON = "malformed_json"
    INVALID_STRUCTURE = "invalid_structure"
    OVERSIZED = "oversized"


class PlannerOutputError(ValueError):
    """Planner output was rejected. The message is fixed and safe to surface."""

    def __init__(self, kind: PlannerOutputErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class _AmbiguousJsonError(ValueError):
    """Internal: syntactically JSON, but ambiguous (duplicate object keys)."""


def _invalid(message: str) -> NoReturn:
    raise PlannerOutputError(PlannerOutputErrorKind.INVALID_STRUCTURE, message)


def _is_strict_int(value: object) -> bool:
    # ``bool`` is an ``int`` subclass; ``True`` must never pass as 1.
    return type(value) is int


def _has_control_characters(text: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in text)


@dataclass(frozen=True, slots=True)
class PlannerTaskSpec:
    """One validated planner-proposed task. Carries no domain identity.

    ``depends_on`` holds zero-based indexes into the owning
    :class:`PlannerOutput` ``tasks`` tuple. Index range and self-reference are
    checked by ``PlannerOutput`` (which knows the task count); cycles are left
    to the domain graph validation performed when a ``ResearchPlan`` is built.
    """

    capability_id: str
    description: str
    depends_on: tuple[int, ...]
    priority: int

    def __post_init__(self) -> None:
        capability_id = self.capability_id
        if not isinstance(capability_id, str):
            _invalid("capability_id must be a string")
        if (
            len(capability_id) > MAX_CAPABILITY_ID_LENGTH
            or _CAPABILITY_ID_PATTERN.fullmatch(capability_id) is None
        ):
            _invalid("capability_id is empty, oversized, or malformed")

        description = self.description
        if not isinstance(description, str):
            _invalid("description must be a string")
        if _has_control_characters(description):
            _invalid("description must not contain control characters")
        # Same normalization as ResearchTask so accepted text round-trips.
        description = " ".join(description.split())
        if not description or len(description) > MAX_DESCRIPTION_LENGTH:
            _invalid("description is empty or exceeds bounds")
        object.__setattr__(self, "description", description)

        depends_on = self.depends_on
        if not isinstance(depends_on, tuple):
            _invalid("depends_on must be a list")
        if len(depends_on) >= MAX_PLANNER_TASKS:
            _invalid("depends_on exceeds bounds")
        for ref in depends_on:
            if not _is_strict_int(ref):
                _invalid("depends_on entries must be integers")
            if ref < 0:
                _invalid("depends_on entries must be non-negative")
        if len(set(depends_on)) != len(depends_on):
            _invalid("depends_on must not contain duplicates")

        priority = self.priority
        if not _is_strict_int(priority):
            _invalid("priority must be an integer")
        if priority < MIN_PRIORITY or priority > MAX_PRIORITY:
            _invalid(f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}")


@dataclass(frozen=True, slots=True)
class PlannerOutput:
    """Validated planner output: a bounded, non-empty tuple of task specs."""

    tasks: tuple[PlannerTaskSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tasks, tuple):
            _invalid("tasks must be a list")
        if not self.tasks:
            _invalid("tasks must not be empty")
        if len(self.tasks) > MAX_PLANNER_TASKS:
            _invalid("tasks exceeds maximum count")
        count = len(self.tasks)
        for index, task in enumerate(self.tasks):
            if not isinstance(task, PlannerTaskSpec):
                _invalid(f"tasks[{index}] is not a planner task")
            for ref in task.depends_on:
                if ref == index:
                    _invalid(f"tasks[{index}] must not depend on itself")
                if ref >= count:
                    _invalid(f"tasks[{index}] depends_on references a missing task")

    @classmethod
    def parse(cls, content: str) -> PlannerOutput:
        """Parse untrusted planner text into a validated :class:`PlannerOutput`.

        Only ``json.loads`` is used; nothing in ``content`` is executed,
        imported, or evaluated. Raises :class:`PlannerOutputError` otherwise.
        """

        if not isinstance(content, str):
            raise PlannerOutputError(
                PlannerOutputErrorKind.MALFORMED_JSON, "planner output must be text"
            )
        if len(content) > MAX_PLANNER_OUTPUT_LENGTH:
            raise PlannerOutputError(
                PlannerOutputErrorKind.OVERSIZED, "planner output exceeds size bounds"
            )
        if not content.strip():
            raise PlannerOutputError(PlannerOutputErrorKind.MALFORMED_JSON, "planner output empty")

        payload = _load_json(content)
        if not isinstance(payload, dict):
            _invalid("planner output must be a JSON object")
        if not _TOP_LEVEL_FIELDS.issuperset(payload):
            _invalid("planner output contains unknown fields")
        if not _TOP_LEVEL_FIELDS.issubset(payload):
            _invalid("planner output is missing required fields")
        if payload["type"] != PLANNER_OUTPUT_TYPE or not isinstance(payload["type"], str):
            _invalid(f"planner output type must be '{PLANNER_OUTPUT_TYPE}'")

        raw_tasks = payload["tasks"]
        if not isinstance(raw_tasks, list):
            _invalid("tasks must be a list")
        if len(raw_tasks) > MAX_PLANNER_TASKS:
            _invalid("tasks exceeds maximum count")

        return cls(tasks=tuple(_build_task(i, raw) for i, raw in enumerate(raw_tasks)))


def _load_json(content: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise _AmbiguousJsonError
            obj[key] = value
        return obj

    def reject_constant(_name: str) -> NoReturn:
        # NaN / Infinity / -Infinity are not JSON.
        raise ValueError

    try:
        return json.loads(
            content, object_pairs_hook=reject_duplicates, parse_constant=reject_constant
        )
    except _AmbiguousJsonError:
        _invalid("planner output contains duplicate keys")
    except (ValueError, RecursionError) as exc:
        # JSONDecodeError, int-digit-limit ValueError, and pathological nesting.
        raise PlannerOutputError(
            PlannerOutputErrorKind.MALFORMED_JSON, "planner output is not valid JSON"
        ) from exc


def _build_task(index: int, raw: object) -> PlannerTaskSpec:
    try:
        if not isinstance(raw, dict):
            _invalid("task must be an object")
        if not _TASK_FIELDS.issuperset(raw):
            _invalid("task contains unknown fields")
        if not _TASK_FIELDS.issubset(raw):
            _invalid("task is missing required fields")
        depends_on = raw["depends_on"]
        if not isinstance(depends_on, list):
            _invalid("depends_on must be a list")
        return PlannerTaskSpec(
            capability_id=raw["capability_id"],
            description=raw["description"],
            depends_on=tuple(depends_on),
            priority=raw["priority"],
        )
    except PlannerOutputError as exc:
        raise PlannerOutputError(exc.kind, f"tasks[{index}]: {exc}") from None
