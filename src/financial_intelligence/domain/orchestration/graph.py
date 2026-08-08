"""Deterministic task DAG semantics (no orchestration framework)."""

from __future__ import annotations

from collections.abc import Sequence

from financial_intelligence.domain.orchestration.tasks import (
    ResearchTask,
    TaskStatus,
)


class TaskGraphError(ValueError):
    """Invalid task graph structure."""


def validate_task_graph(tasks: Sequence[ResearchTask]) -> None:
    """Reject duplicate IDs, missing deps, self-deps, and cycles."""

    by_id: dict[str, ResearchTask] = {}
    for task in tasks:
        key = task.task_id.as_text()
        if key in by_id:
            msg = f"duplicate task_id: {key}"
            raise TaskGraphError(msg)
        by_id[key] = task

    for task in tasks:
        for dep in task.dependencies:
            if dep.as_text() not in by_id:
                msg = f"missing dependency {dep.as_text()} for task {task.task_id.as_text()}"
                raise TaskGraphError(msg)
            if dep == task.task_id:
                msg = f"self dependency on {task.task_id.as_text()}"
                raise TaskGraphError(msg)

    # Kahn cycle detection
    indegree = {t.task_id.as_text(): 0 for t in tasks}
    for task in tasks:
        for _dep in task.dependencies:
            indegree[task.task_id.as_text()] += 1
    queue = sorted(k for k, v in indegree.items() if v == 0)
    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for task in tasks:
            if any(d.as_text() == node for d in task.dependencies):
                child = task.task_id.as_text()
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
                    queue.sort()
    if visited != len(tasks):
        msg = "task graph contains a cycle"
        raise TaskGraphError(msg)


def topological_order(tasks: Sequence[ResearchTask]) -> tuple[ResearchTask, ...]:
    """Return deterministic topological order (priority asc, then task_id)."""

    validate_task_graph(tasks)
    by_id = {t.task_id.as_text(): t for t in tasks}
    indegree = {t.task_id.as_text(): 0 for t in tasks}
    children: dict[str, list[str]] = {t.task_id.as_text(): [] for t in tasks}
    for task in tasks:
        for dep in task.dependencies:
            indegree[task.task_id.as_text()] += 1
            children[dep.as_text()].append(task.task_id.as_text())

    def sort_key(task_id: str) -> tuple[int, str]:
        task = by_id[task_id]
        return (task.priority, task_id)

    ready = sorted((k for k, v in indegree.items() if v == 0), key=sort_key)
    ordered: list[ResearchTask] = []
    while ready:
        node = ready.pop(0)
        ordered.append(by_id[node])
        for child in sorted(children[node], key=sort_key):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=sort_key)
    return tuple(ordered)


def ready_tasks(tasks: Sequence[ResearchTask]) -> tuple[ResearchTask, ...]:
    """Tasks whose required dependencies have SUCCEEDED (or no deps)."""

    by_id = {t.task_id.as_text(): t for t in tasks}
    ready: list[ResearchTask] = []
    for task in tasks:
        if task.status not in {TaskStatus.PENDING, TaskStatus.READY}:
            continue
        ok = True
        for dep in task.dependencies:
            parent = by_id[dep.as_text()]
            if parent.status is not TaskStatus.SUCCEEDED:
                ok = False
                break
        if ok:
            ready.append(task)
    return tuple(sorted(ready, key=lambda t: (t.priority, t.task_id.as_text())))


def blocked_tasks(tasks: Sequence[ResearchTask]) -> tuple[ResearchTask, ...]:
    """Tasks blocked because a required dependency FAILED/BLOCKED/SKIPPED."""

    by_id = {t.task_id.as_text(): t for t in tasks}
    blocked: list[ResearchTask] = []
    terminal_fail = {TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.SKIPPED}
    for task in tasks:
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.SKIPPED}:
            continue
        for dep in task.dependencies:
            parent = by_id[dep.as_text()]
            if parent.status in terminal_fail and task.required:
                blocked.append(task)
                break
    return tuple(sorted(blocked, key=lambda t: (t.priority, t.task_id.as_text())))


def apply_failure_propagation(tasks: Sequence[ResearchTask]) -> tuple[ResearchTask, ...]:
    """Propagate dependency failures without destroying unrelated branches.

    Required dependents of FAILED/BLOCKED/SKIPPED parents become BLOCKED.
    Optional dependents of those parents become SKIPPED (not left hanging
    PENDING, which would create a no-progress loop).
    Independent optional tasks without a failed dependency remain schedulable.
    """

    by_id = {t.task_id.as_text(): t for t in tasks}
    changed = True
    while changed:
        changed = False
        for task in list(by_id.values()):
            if task.status in {
                TaskStatus.SUCCEEDED,
                TaskStatus.FAILED,
                TaskStatus.SKIPPED,
                TaskStatus.BLOCKED,
                TaskStatus.RUNNING,
            }:
                continue
            for dep in task.dependencies:
                parent = by_id[dep.as_text()]
                if parent.status in {TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.SKIPPED}:
                    if task.required and task.status is not TaskStatus.BLOCKED:
                        by_id[task.task_id.as_text()] = task.with_status(TaskStatus.BLOCKED)
                        changed = True
                    elif not task.required and task.status is not TaskStatus.SKIPPED:
                        by_id[task.task_id.as_text()] = task.with_status(TaskStatus.SKIPPED)
                        changed = True
                    break
    return tuple(sorted(by_id.values(), key=lambda t: (t.priority, t.task_id.as_text())))


def select_next_ready_task(tasks: Sequence[ResearchTask]) -> ResearchTask | None:
    """Pick the next ready task with stable priority then task_id ordering."""

    ready = ready_tasks(tasks)
    return ready[0] if ready else None


def dependency_edges(tasks: Sequence[ResearchTask]) -> tuple[tuple[str, str], ...]:
    """Return (dependency_id, task_id) edges in deterministic order."""

    edges: list[tuple[str, str]] = []
    for task in tasks:
        for dep in task.dependencies:
            edges.append((dep.as_text(), task.task_id.as_text()))
    return tuple(sorted(edges))
