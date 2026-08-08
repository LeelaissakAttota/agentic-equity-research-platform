"""Deterministic bounded retry policy for orchestration."""

from __future__ import annotations

from financial_intelligence.domain.orchestration.budget import ResearchExecutionBudget
from financial_intelligence.domain.orchestration.results import (
    TaskExecutionResult,
    TaskResultStatus,
)
from financial_intelligence.domain.orchestration.tasks import ResearchTask

# Permanent / policy failures — never retry.
NON_RETRYABLE_ERROR_CODES = frozenset(
    {
        "identity_mismatch",
        "invalid_input",
        "policy_violation",
        "blocked_dependency",
        "unavailable",
        "budget_violation",
        "unknown_capability",
        "cancellation",
    }
)


class RetryPolicy:
    """Answer should_retry(task, result, budget, totals) without sleeps."""

    def should_retry(
        self,
        task: ResearchTask,
        result: TaskExecutionResult,
        *,
        budget: ResearchExecutionBudget,
        total_attempts: int,
    ) -> bool:
        if result.status is not TaskResultStatus.FAILED:
            return False
        if not result.retryable:
            return False
        if result.error_code is not None and result.error_code in NON_RETRYABLE_ERROR_CODES:
            return False
        if task.attempt_count >= task.max_attempts:
            return False
        if task.attempt_count >= budget.max_attempts_per_task:
            return False
        return total_attempts < budget.max_total_attempts
