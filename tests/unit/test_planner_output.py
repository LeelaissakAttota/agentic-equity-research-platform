"""Domain tests for the strict LLM planner-output parser/validator (Step 1)."""

from __future__ import annotations

import dataclasses
import json
from typing import Any
from unittest import TestCase
from uuid import uuid4

from financial_intelligence.domain.llm.structured_output import _MAX_STRUCTURED_CONTENT_LENGTH
from financial_intelligence.domain.orchestration.budget import ResearchExecutionBudget
from financial_intelligence.domain.orchestration.planner_output import (
    MAX_CAPABILITY_ID_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_PLANNER_OUTPUT_LENGTH,
    MAX_PLANNER_TASKS,
    MAX_PRIORITY,
    MIN_PRIORITY,
    PlannerOutput,
    PlannerOutputError,
    PlannerOutputErrorKind,
    PlannerTaskSpec,
)
from financial_intelligence.domain.orchestration.tasks import ResearchTask, TaskId, TaskType


def _task(**overrides: Any) -> dict[str, Any]:
    task: dict[str, Any] = {
        "capability_id": "market_intelligence",
        "description": "Fetch current market snapshot and valuation context",
        "depends_on": [],
        "priority": 10,
    }
    task.update(overrides)
    return task


def _plan(*tasks: dict[str, Any], **top: Any) -> str:
    payload: dict[str, Any] = {"type": "research_plan", "tasks": list(tasks) or [_task()]}
    payload.update(top)
    return json.dumps(payload)


class PlannerOutputTestCase(TestCase):
    def assertRejected(
        self,
        content: Any,
        kind: PlannerOutputErrorKind = PlannerOutputErrorKind.INVALID_STRUCTURE,
    ) -> PlannerOutputError:
        with self.assertRaises(PlannerOutputError) as ctx:
            PlannerOutput.parse(content)
        self.assertIs(ctx.exception.kind, kind)
        return ctx.exception


class ValidPlannerOutputTests(PlannerOutputTestCase):
    def test_valid_minimal_output(self) -> None:
        output = PlannerOutput.parse(_plan())
        self.assertEqual(len(output.tasks), 1)
        task = output.tasks[0]
        self.assertEqual(task.capability_id, "market_intelligence")
        self.assertEqual(task.description, "Fetch current market snapshot and valuation context")
        self.assertEqual(task.depends_on, ())
        self.assertEqual(task.priority, 10)

    def test_valid_multiple_tasks(self) -> None:
        output = PlannerOutput.parse(
            _plan(
                _task(capability_id="company_resolution", priority=1),
                _task(capability_id="financial_intelligence", priority=20),
                _task(capability_id="news_event_intelligence", priority=30),
            )
        )
        self.assertEqual(
            [t.capability_id for t in output.tasks],
            ["company_resolution", "financial_intelligence", "news_event_intelligence"],
        )

    def test_valid_dependency_references(self) -> None:
        output = PlannerOutput.parse(
            _plan(
                _task(),
                _task(depends_on=[0]),
                _task(depends_on=[0, 1]),
                _task(depends_on=[2]),
            )
        )
        self.assertEqual([t.depends_on for t in output.tasks], [(), (0,), (0, 1), (2,)])

    def test_forward_reference_is_structurally_valid(self) -> None:
        # Cycle/ordering detection is deferred to ResearchPlan construction.
        output = PlannerOutput.parse(_plan(_task(depends_on=[1]), _task()))
        self.assertEqual(output.tasks[0].depends_on, (1,))

    def test_max_task_count_accepted(self) -> None:
        output = PlannerOutput.parse(_plan(*[_task() for _ in range(MAX_PLANNER_TASKS)]))
        self.assertEqual(len(output.tasks), MAX_PLANNER_TASKS)

    def test_description_whitespace_is_normalized(self) -> None:
        output = PlannerOutput.parse(_plan(_task(description="  spaced    out   text  ")))
        self.assertEqual(output.tasks[0].description, "spaced out text")

    def test_output_is_frozen(self) -> None:
        output = PlannerOutput.parse(_plan())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            output.tasks = ()  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            output.tasks[0].priority = 5  # type: ignore[misc]

    def test_output_carries_only_validated_planner_data(self) -> None:
        output = PlannerOutput.parse(_plan(_task(), _task(depends_on=[0])))
        self.assertEqual({f.name for f in dataclasses.fields(output)}, {"tasks"})
        self.assertEqual(
            {f.name for f in dataclasses.fields(PlannerTaskSpec)},
            {"capability_id", "description", "depends_on", "priority"},
        )
        for task in output.tasks:
            self.assertIs(type(task), PlannerTaskSpec)
            self.assertIs(type(task.capability_id), str)
            self.assertIs(type(task.description), str)
            self.assertIs(type(task.depends_on), tuple)
            self.assertIs(type(task.priority), int)
            self.assertNotIsInstance(task, ResearchTask)
            self.assertNotIsInstance(task.capability_id, TaskType)

    def test_output_does_not_manufacture_server_controlled_values(self) -> None:
        output = PlannerOutput.parse(_plan(_task(), _task(depends_on=[0])))
        forbidden_names = {
            "task_id",
            "task_type",
            "company_id",
            "research_run_id",
            "evidence",
            "source_url",
            "url",
            "status",
            "attempt_count",
            "max_attempts",
            "created_at",
            "planner_version",
        }
        self.assertFalse(forbidden_names & {f.name for f in dataclasses.fields(output)})
        for task in output.tasks:
            self.assertFalse(forbidden_names & {f.name for f in dataclasses.fields(task)})
            self.assertFalse(any(isinstance(v, (TaskId, TaskType)) for v in vars_of(task)))
            self.assertTrue(all(isinstance(d, int) for d in task.depends_on))
            self.assertNotIn("http", task.description.lower())


def vars_of(task: PlannerTaskSpec) -> list[object]:
    return [getattr(task, f.name) for f in dataclasses.fields(task)]


class MalformedInputTests(PlannerOutputTestCase):
    def test_invalid_json(self) -> None:
        for content in ("{not json", '{"type": "research_plan",', "null nope", "```json\n{}\n```"):
            with self.subTest(content=content):
                self.assertRejected(content, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_empty_or_blank(self) -> None:
        for content in ("", "   \n\t "):
            with self.subTest(content=content):
                self.assertRejected(content, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_non_string_input(self) -> None:
        for content in (None, b'{"type": "research_plan"}', 123, {"type": "research_plan"}):
            with self.subTest(content=content):
                self.assertRejected(content, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_non_finite_constants_are_not_json(self) -> None:
        content = '{"type": "research_plan", "tasks": [{"priority": NaN}]}'
        self.assertRejected(content, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_pathological_nesting_is_rejected_not_crashed(self) -> None:
        content = "[" * 16_000 + "]" * 16_000
        self.assertRejected(content, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_huge_integer_literal_is_rejected_not_crashed(self) -> None:
        digits = "9" * 6_000
        content = f'{{"type": "research_plan", "tasks": [{{"priority": {digits}}}]}}'
        self.assertRejected(content, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_duplicate_keys_are_rejected(self) -> None:
        content = (
            '{"type": "research_plan", "tasks": [], "tasks": '
            '[{"capability_id": "market_intelligence", "description": "d", '
            '"depends_on": [], "priority": 1}]}'
        )
        self.assertRejected(content)
        task = (
            '{"capability_id": "a", "capability_id": "b", "description": "d", '
            '"depends_on": [], "priority": 1}'
        )
        self.assertRejected(f'{{"type": "research_plan", "tasks": [{task}]}}')

    def test_oversized_raw_content(self) -> None:
        content = _plan(_task(description="x" * MAX_PLANNER_OUTPUT_LENGTH))
        self.assertGreater(len(content), MAX_PLANNER_OUTPUT_LENGTH)
        self.assertRejected(content, PlannerOutputErrorKind.OVERSIZED)

    def test_oversized_check_precedes_parsing(self) -> None:
        # Not even valid JSON: must still be classified by size, not syntax.
        self.assertRejected("{" * (MAX_PLANNER_OUTPUT_LENGTH + 1), PlannerOutputErrorKind.OVERSIZED)

    def test_content_exactly_at_limit_is_not_oversized(self) -> None:
        padding = " " * (MAX_PLANNER_OUTPUT_LENGTH - len(_plan()))
        output = PlannerOutput.parse(_plan() + padding)
        self.assertEqual(len(output.tasks), 1)


class TopLevelStructureTests(PlannerOutputTestCase):
    def test_top_level_not_an_object(self) -> None:
        for content in ("[]", '"research_plan"', "42", "true", "null", "[{}]"):
            with self.subTest(content=content):
                self.assertRejected(content)

    def test_wrong_type_discriminator(self) -> None:
        for value in ("final_answer", "tool_call", "", "Research_Plan", None, 1, ["research_plan"]):
            with self.subTest(value=value):
                self.assertRejected(json.dumps({"type": value, "tasks": [_task()]}))

    def test_missing_top_level_fields(self) -> None:
        self.assertRejected(json.dumps({"tasks": [_task()]}))
        self.assertRejected(json.dumps({"type": "research_plan"}))
        self.assertRejected("{}")

    def test_unknown_top_level_fields(self) -> None:
        for extra in ("company_id", "research_run_id", "planner_version", "metadata", "evidence"):
            with self.subTest(extra=extra):
                self.assertRejected(_plan(**{extra: "x"}))

    def test_tasks_not_a_list(self) -> None:
        for value in ({}, {"0": _task()}, "tasks", 3, None, True):
            with self.subTest(value=value):
                self.assertRejected(json.dumps({"type": "research_plan", "tasks": value}))

    def test_empty_tasks(self) -> None:
        self.assertRejected(json.dumps({"type": "research_plan", "tasks": []}))

    def test_excessive_task_count(self) -> None:
        self.assertRejected(_plan(*[_task() for _ in range(MAX_PLANNER_TASKS + 1)]))

    def test_task_not_an_object(self) -> None:
        for value in ("market_intelligence", 1, None, [], [_task()]):
            with self.subTest(value=value):
                self.assertRejected(json.dumps({"type": "research_plan", "tasks": [value]}))


class TaskFieldTests(PlannerOutputTestCase):
    def test_missing_task_fields(self) -> None:
        for name in ("capability_id", "description", "depends_on", "priority"):
            with self.subTest(missing=name):
                task = _task()
                del task[name]
                self.assertRejected(_plan(task))

    def test_unknown_task_fields(self) -> None:
        for extra in (
            "task_id",
            "task_type",
            "company_id",
            "research_run_id",
            "evidence",
            "source_url",
            "status",
            "attempt_count",
            "max_attempts",
            "created_at",
            "planner_version",
            "metadata",
        ):
            with self.subTest(extra=extra):
                self.assertRejected(_plan(_task(**{extra: "x"})))

    def test_invalid_capability_id_type(self) -> None:
        for value in (None, 1, True, [], {}, ["market_intelligence"]):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(capability_id=value)))

    def test_invalid_capability_id_value(self) -> None:
        for value in (
            "",
            " ",
            " market_intelligence",
            "market_intelligence\n",
            "Market_Intelligence",
            "market-intelligence",
            "market intelligence",
            "1market",
            "../etc/passwd",
            "x" * (MAX_CAPABILITY_ID_LENGTH + 1),
        ):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(capability_id=value)))

    def test_capability_id_at_max_length(self) -> None:
        value = "a" * MAX_CAPABILITY_ID_LENGTH
        output = PlannerOutput.parse(_plan(_task(capability_id=value)))
        self.assertEqual(output.tasks[0].capability_id, value)

    def test_invalid_description_type(self) -> None:
        for value in (None, 1, True, [], {}, ["text"]):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(description=value)))

    def test_empty_description(self) -> None:
        for value in ("", "   ", chr(0x2003)):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(description=value)))

    def test_oversized_description(self) -> None:
        self.assertRejected(_plan(_task(description="x" * (MAX_DESCRIPTION_LENGTH + 1))))

    def test_description_at_max_length(self) -> None:
        value = "x" * MAX_DESCRIPTION_LENGTH
        output = PlannerOutput.parse(_plan(_task(description=value)))
        self.assertEqual(output.tasks[0].description, value)

    def test_description_with_control_characters(self) -> None:
        for value in (
            "line1\nline2",
            "tab\there",
            "nul\x00byte",
            "esc\x1b[31m",
            "del\x7f",
            "c1\x85",
        ):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(description=value)))

    def test_invalid_depends_on_type(self) -> None:
        for value in (None, 0, "0", {}, {"0": 0}, True, "[]"):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(), _task(depends_on=value)))

    def test_invalid_dependency_reference_type(self) -> None:
        for value in ("0", 0.0, 1.5, True, False, None, [0], {"index": 0}, "task-1"):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(), _task(depends_on=[value])))

    def test_negative_dependency_reference(self) -> None:
        self.assertRejected(_plan(_task(), _task(depends_on=[-1])))

    def test_out_of_range_dependency_reference(self) -> None:
        self.assertRejected(_plan(_task(), _task(depends_on=[2])))
        self.assertRejected(_plan(_task(), _task(depends_on=[10**9])))
        self.assertRejected(_plan(_task(depends_on=[1])))

    def test_self_dependency(self) -> None:
        self.assertRejected(_plan(_task(depends_on=[0])))
        self.assertRejected(_plan(_task(), _task(depends_on=[0, 1])))

    def test_duplicate_dependency_reference(self) -> None:
        self.assertRejected(_plan(_task(), _task(depends_on=[0, 0])))

    def test_excessive_dependency_list(self) -> None:
        refs = [0] * MAX_PLANNER_TASKS
        self.assertRejected(_plan(_task(), _task(depends_on=refs)))

    def test_invalid_priority_type(self) -> None:
        for value in ("10", 10.0, 10.5, True, False, None, [10], {"v": 10}):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(priority=value)))

    def test_invalid_priority_range(self) -> None:
        for value in (0, -1, MIN_PRIORITY - 1, MAX_PRIORITY + 1, 10**12):
            with self.subTest(value=value):
                self.assertRejected(_plan(_task(priority=value)))

    def test_priority_bounds_accepted(self) -> None:
        for value in (MIN_PRIORITY, MAX_PRIORITY):
            with self.subTest(value=value):
                self.assertEqual(
                    PlannerOutput.parse(_plan(_task(priority=value))).tasks[0].priority, value
                )


class NoCoercionTests(PlannerOutputTestCase):
    def test_string_priority_is_rejected_not_coerced(self) -> None:
        self.assertRejected(_plan(_task(priority="10")))

    def test_float_priority_is_rejected_not_coerced(self) -> None:
        self.assertRejected(_plan(_task(priority=10.0)))

    def test_bool_priority_is_rejected_not_coerced(self) -> None:
        self.assertRejected(_plan(_task(priority=True)))

    def test_string_dependency_index_is_rejected_not_coerced(self) -> None:
        self.assertRejected(_plan(_task(), _task(depends_on=["0"])))

    def test_object_tasks_is_rejected_not_coerced(self) -> None:
        self.assertRejected('{"type": "research_plan", "tasks": {}}')

    def test_scalar_depends_on_is_rejected_not_wrapped(self) -> None:
        self.assertRejected(_plan(_task(), _task(depends_on=0)))

    def test_nested_object_values_are_rejected(self) -> None:
        self.assertRejected(_plan(_task(description={"text": "nested"})))
        self.assertRejected(_plan(_task(capability_id={"id": "market_intelligence"})))
        self.assertRejected(_plan(_task(priority={"value": 10})))
        self.assertRejected(_plan(_task(), _task(depends_on=[[0]])))
        self.assertRejected(_plan(_task(), _task(depends_on=[{"task": 0}])))


class ErrorModelTests(PlannerOutputTestCase):
    def test_error_is_value_error_with_kind(self) -> None:
        error = self.assertRejected("{nope", PlannerOutputErrorKind.MALFORMED_JSON)
        self.assertIsInstance(error, ValueError)
        self.assertIs(error.kind, PlannerOutputErrorKind.MALFORMED_JSON)

    def test_kinds_are_distinguishable(self) -> None:
        malformed = self.assertRejected("{nope", PlannerOutputErrorKind.MALFORMED_JSON)
        structural = self.assertRejected("[]", PlannerOutputErrorKind.INVALID_STRUCTURE)
        oversized = self.assertRejected(
            "x" * (MAX_PLANNER_OUTPUT_LENGTH + 1), PlannerOutputErrorKind.OVERSIZED
        )
        self.assertEqual(len({malformed.kind, structural.kind, oversized.kind}), 3)

    def test_messages_never_echo_untrusted_content(self) -> None:
        secret = f"SECRET-{uuid4().hex}"
        attacks = [
            secret,
            "{" + secret,
            json.dumps([secret]),
            json.dumps({"type": secret, "tasks": [_task()]}),
            json.dumps({secret: 1, "type": "research_plan", "tasks": [_task()]}),
            _plan(_task(capability_id=secret)),
            _plan(_task(description=secret + "\n")),
            _plan(_task(priority=secret)),
            _plan(_task(depends_on=[secret])),
            _plan(_task(**{secret: 1})),
            _plan(_task(description=secret * MAX_DESCRIPTION_LENGTH)),
            secret * MAX_PLANNER_OUTPUT_LENGTH,
        ]
        for content in attacks:
            with self.subTest(content=content[:40]):
                with self.assertRaises(PlannerOutputError) as ctx:
                    PlannerOutput.parse(content)
                text = str(ctx.exception)
                self.assertNotIn(secret, text)
                self.assertNotIn("SECRET", text)
                self.assertLess(len(text), 160)

    def test_task_errors_identify_position_only(self) -> None:
        error = self.assertRejected(_plan(_task(), _task(priority="high")))
        self.assertIn("tasks[1]", str(error))


class ConstantsAndCompatibilityTests(TestCase):
    def test_raw_bound_matches_structured_output_bound(self) -> None:
        self.assertEqual(MAX_PLANNER_OUTPUT_LENGTH, _MAX_STRUCTURED_CONTENT_LENGTH)

    def test_task_bound_is_compatible_with_execution_budget(self) -> None:
        self.assertEqual(MAX_PLANNER_TASKS, ResearchExecutionBudget().max_tasks)
        self.assertLessEqual(MAX_PLANNER_TASKS, 100)  # ResearchExecutionBudget.max_tasks ceiling
        ResearchExecutionBudget(max_tasks=MAX_PLANNER_TASKS)

    def test_worst_case_valid_plan_fits_raw_bound(self) -> None:
        worst = _plan(
            *[
                _task(
                    capability_id="a" * MAX_CAPABILITY_ID_LENGTH,
                    description="x" * MAX_DESCRIPTION_LENGTH,
                    depends_on=list(range(1, MAX_PLANNER_TASKS)) if i == 0 else [],
                    priority=MAX_PRIORITY,
                )
                for i in range(MAX_PLANNER_TASKS)
            ]
        )
        self.assertLessEqual(len(worst), MAX_PLANNER_OUTPUT_LENGTH)
        self.assertEqual(len(PlannerOutput.parse(worst).tasks), MAX_PLANNER_TASKS)

    def test_field_bounds_are_accepted_by_research_task(self) -> None:
        for description, priority in (
            ("x" * MAX_DESCRIPTION_LENGTH, MAX_PRIORITY),
            ("x", MIN_PRIORITY),
        ):
            spec = PlannerOutput.parse(
                _plan(_task(description=description, priority=priority))
            ).tasks[0]
            ResearchTask(
                task_id=TaskId.new(),
                task_type=TaskType.MARKET_INTELLIGENCE,
                capability_id=spec.capability_id,
                description=spec.description,
                priority=spec.priority,
            )

    def test_field_bounds_match_research_task_rejections(self) -> None:
        def build(description: str, priority: int) -> ResearchTask:
            return ResearchTask(
                task_id=TaskId.new(),
                task_type=TaskType.MARKET_INTELLIGENCE,
                capability_id="market_intelligence",
                description=description,
                priority=priority,
            )

        with self.assertRaises(ValueError):
            build("x" * (MAX_DESCRIPTION_LENGTH + 1), 10)
        with self.assertRaises(ValueError):
            build("ok", MAX_PRIORITY + 1)
        with self.assertRaises(ValueError):
            build("ok", MIN_PRIORITY - 1)
