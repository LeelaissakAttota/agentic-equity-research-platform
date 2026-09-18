"""Tests for the orchestration-level meta-step model (distinct from TaskType)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase
from uuid import UUID

from financial_intelligence.application.capability_registry import CapabilityRegistry
from financial_intelligence.domain.orchestration import (
    MetaStep,
    MetaStepId,
    MetaStepStatus,
    MetaStepType,
    TaskType,
)


def _clock() -> datetime:
    return datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _step(
    *,
    step_type: MetaStepType = MetaStepType.PLAN,
    status: MetaStepStatus = MetaStepStatus.PENDING,
    sequence: int = 0,
) -> MetaStep:
    return MetaStep(
        step_id=MetaStepId.new(),
        step_type=step_type,
        sequence=sequence,
        description=f"meta step for {step_type.value}",
        status=status,
        created_at=_clock(),
    )


class MetaStepIdentityTests(TestCase):
    def test_uuidv4_roundtrip(self) -> None:
        step_id = MetaStepId.new()
        self.assertEqual(step_id.value.version, 4)
        self.assertEqual(MetaStepId.from_string(step_id.as_text()).as_text(), step_id.as_text())

    def test_rejects_non_v4_uuid(self) -> None:
        with self.assertRaises(ValueError):
            MetaStepId(value=UUID("11111111-1111-1111-8111-111111111111"))


class MetaStepTypeValueTests(TestCase):
    def test_valid_meta_step_values(self) -> None:
        self.assertEqual(
            {t.value for t in MetaStepType},
            {"plan", "evidence_collection", "critique", "synthesis"},
        )

    def test_invalid_meta_step_value_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MetaStepType("not_a_real_step")

    def test_meta_step_types_are_disjoint_from_task_type(self) -> None:
        task_type_values = {t.value for t in TaskType}
        meta_step_values = {t.value for t in MetaStepType}
        self.assertEqual(task_type_values & meta_step_values, set())


class MetaStepRegistryIsolationTests(TestCase):
    def test_meta_steps_are_not_registered_as_capabilities(self) -> None:
        registry = CapabilityRegistry()
        registered_ids = {cap.capability_id for cap in registry.all()}
        for meta_type in MetaStepType:
            self.assertNotIn(meta_type.value, registered_ids)

    def test_every_task_type_capability_has_no_meta_step_counterpart(self) -> None:
        registry = CapabilityRegistry()
        for cap in registry.all():
            self.assertNotIn(cap.task_type.value, {m.value for m in MetaStepType})


class MetaStepValidationTests(TestCase):
    def test_construct_valid_step(self) -> None:
        step = _step()
        self.assertEqual(step.status, MetaStepStatus.PENDING)
        self.assertEqual(step.step_type, MetaStepType.PLAN)

    def test_rejects_negative_sequence(self) -> None:
        with self.assertRaises(ValueError):
            MetaStep(
                step_id=MetaStepId.new(),
                step_type=MetaStepType.CRITIQUE,
                sequence=-1,
                description="bad",
            )

    def test_rejects_empty_description(self) -> None:
        with self.assertRaises(ValueError):
            MetaStep(
                step_id=MetaStepId.new(),
                step_type=MetaStepType.SYNTHESIS,
                sequence=0,
                description="   ",
            )

    def test_rejects_naive_timestamps(self) -> None:
        with self.assertRaises(ValueError):
            MetaStep(
                step_id=MetaStepId.new(),
                step_type=MetaStepType.EVIDENCE_COLLECTION,
                sequence=0,
                description="collect evidence",
                created_at=datetime(2026, 1, 1),  # intentional naive input
            )

    def test_to_dict_roundtrip_shape(self) -> None:
        step = _step()
        payload = step.to_dict()
        self.assertEqual(payload["kind"], "meta_step")
        self.assertEqual(payload["step_type"], "plan")
        self.assertEqual(payload["status"], "pending")


class MetaStepTransitionTests(TestCase):
    def test_pending_to_running_to_completed(self) -> None:
        step = _step()
        running = step.with_status(MetaStepStatus.RUNNING, at=_clock())
        self.assertEqual(running.status, MetaStepStatus.RUNNING)
        self.assertEqual(running.started_at, _clock())
        completed = running.with_status(MetaStepStatus.COMPLETED, at=_clock())
        self.assertEqual(completed.status, MetaStepStatus.COMPLETED)
        self.assertEqual(completed.completed_at, _clock())

    def test_pending_to_unsupported_is_the_no_implementation_path(self) -> None:
        step = _step()
        unsupported = step.with_status(
            MetaStepStatus.UNSUPPORTED, at=_clock(), message="no agent implemented yet"
        )
        self.assertEqual(unsupported.status, MetaStepStatus.UNSUPPORTED)
        self.assertEqual(unsupported.message, "no agent implemented yet")
        # UNSUPPORTED is terminal and distinct from COMPLETED.
        self.assertNotEqual(unsupported.status, MetaStepStatus.COMPLETED)

    def test_terminal_states_reject_further_transitions(self) -> None:
        step = _step(status=MetaStepStatus.COMPLETED)
        with self.assertRaises(ValueError):
            step.with_status(MetaStepStatus.RUNNING)

    def test_running_cannot_skip_back_to_pending(self) -> None:
        step = _step().with_status(MetaStepStatus.RUNNING, at=_clock())
        with self.assertRaises(ValueError):
            step.with_status(MetaStepStatus.PENDING)

    def test_invalid_transition_raises(self) -> None:
        step = _step()
        with self.assertRaises(ValueError):
            step.with_status(MetaStepStatus.COMPLETED)
