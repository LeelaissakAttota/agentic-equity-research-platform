"""Lightweight research execution budget (safety, not billing)."""

from __future__ import annotations

from dataclasses import dataclass

from financial_intelligence.domain.orchestration.tasks import ResearchTask


class BudgetExceededError(ValueError):
    """Raised when a plan would violate execution budget bounds."""


@dataclass(frozen=True, slots=True)
class ResearchExecutionBudget:
    """Bounded execution limits for orchestration safety.

    ``max_external_calls`` counts **capability executor invocations** (each
    ``execute_task`` call), not verified network I/O. Fixture/in-memory adapters
    and optional live HTTP adapters share the same invocation counter. The
    orchestration layer cannot currently distinguish whether a downstream
    adapter performed network I/O; do not treat this counter as packet-accurate
    network accounting.
    """

    max_tasks: int = 20
    max_attempts_per_task: int = 3
    max_total_attempts: int = 40
    max_plan_depth: int = 10
    max_external_calls: int = 40

    def __post_init__(self) -> None:
        for name, value, lo, hi in (
            ("max_tasks", self.max_tasks, 1, 100),
            ("max_attempts_per_task", self.max_attempts_per_task, 1, 10),
            ("max_total_attempts", self.max_total_attempts, 1, 500),
            ("max_plan_depth", self.max_plan_depth, 1, 50),
            ("max_external_calls", self.max_external_calls, 1, 500),
        ):
            if value < lo or value > hi:
                msg = f"{name} must be between {lo} and {hi}"
                raise ValueError(msg)

    def validate_tasks(self, tasks: tuple[ResearchTask, ...]) -> None:
        """Fail closed when a candidate task set exceeds the budget."""

        if len(tasks) > self.max_tasks:
            msg = f"plan exceeds max_tasks={self.max_tasks}"
            raise BudgetExceededError(msg)
        total_attempts = 0
        depths: dict[str, int] = {}
        by_id = {t.task_id.as_text(): t for t in tasks}
        for task in tasks:
            if task.max_attempts > self.max_attempts_per_task:
                msg = (
                    f"task {task.task_id.as_text()} max_attempts exceeds "
                    f"budget max_attempts_per_task={self.max_attempts_per_task}"
                )
                raise BudgetExceededError(msg)
            total_attempts += task.max_attempts
            depth = 1
            seen: set[str] = set()
            stack = list(task.dependencies)
            while stack:
                dep = stack.pop().as_text()
                if dep in seen:
                    continue
                seen.add(dep)
                depth += 1
                parent = by_id.get(dep)
                if parent is not None:
                    stack.extend(parent.dependencies)
            depths[task.task_id.as_text()] = depth
            if depth > self.max_plan_depth:
                msg = f"plan depth exceeds max_plan_depth={self.max_plan_depth}"
                raise BudgetExceededError(msg)
        if total_attempts > self.max_total_attempts:
            msg = f"plan exceeds max_total_attempts={self.max_total_attempts}"
            raise BudgetExceededError(msg)
        if len(tasks) > self.max_external_calls:
            msg = f"plan exceeds max_external_calls={self.max_external_calls}"
            raise BudgetExceededError(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "max_tasks": self.max_tasks,
            "max_attempts_per_task": self.max_attempts_per_task,
            "max_total_attempts": self.max_total_attempts,
            "max_plan_depth": self.max_plan_depth,
            "max_external_calls": self.max_external_calls,
            "kind": "research_execution_budget",
        }
