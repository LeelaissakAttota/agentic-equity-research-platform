"""Deterministic approval policy — no LLM."""

from __future__ import annotations

from financial_intelligence.domain.orchestration import ResearchObjective
from financial_intelligence.domain.workflow import ApprovalRequirement


class DeterministicApprovalPolicy:
    """Conservative approval policy based on explicit flags and objective.

    Comprehensive equity research requires human approval before first execution
    unless the caller did not request approval AND objective is not comprehensive.
    Explicit ``require_approval=True`` always requires approval.
    """

    def evaluate(
        self,
        *,
        objective: ResearchObjective,
        require_approval: bool,
    ) -> ApprovalRequirement:
        if require_approval:
            return ApprovalRequirement(
                required=True,
                reason="caller requested human approval before workflow execution",
            )
        if objective is ResearchObjective.COMPREHENSIVE_EQUITY_RESEARCH:
            return ApprovalRequirement(
                required=True,
                reason="comprehensive equity research requires human approval before execution",
            )
        return ApprovalRequirement(
            required=False,
            reason="approval not required for this objective",
        )
