# Pre-existing Mypy Errors Fix Report

**Scope:** Type-safety cleanup only. No F01–F12 behavior was reopened, redesigned, or touched.
**Files changed:** `src/financial_intelligence/domain/orchestration/graph.py`,
`tests/unit/test_orchestration_domain.py` — nothing else.

---

## 1. Original Errors

Captured via the project's exact CI invocation (`python -m mypy`, using `[tool.mypy]`'s
`packages = ["financial_intelligence"]` with `strict = true`):

```
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check
    (left operand type: "Literal[TaskStatus.PENDING, TaskStatus.READY]",
     right operand type: "Literal[TaskStatus.BLOCKED]")  [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check
    (left operand type: "Literal[TaskStatus.PENDING, TaskStatus.READY]",
     right operand type: "Literal[TaskStatus.SKIPPED]")  [comparison-overlap]
Found 2 errors in 1 file (checked 190 source files)
```

Both errors are `comparison-overlap` — mypy's diagnostic for an `is`/`is not`/`==`/`!=` comparison where the
statically-inferred type of one operand can never equal the other operand's literal value, making the comparison's
result provably constant.

---

## 2. Root Cause

**Function:** `apply_failure_propagation` (`graph.py:124-156`)

```python
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
            if task.required and task.status is not TaskStatus.BLOCKED:      # line 149
                by_id[task.task_id.as_text()] = task.with_status(TaskStatus.BLOCKED)
                changed = True
            elif not task.required and task.status is not TaskStatus.SKIPPED:  # line 152
                by_id[task.task_id.as_text()] = task.with_status(TaskStatus.SKIPPED)
                changed = True
            break
```

`TaskStatus` (`domain/orchestration/tasks.py:22-31`) is a closed `StrEnum` with exactly seven members: `PENDING`,
`READY`, `RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`, `BLOCKED`. The outer `if ... continue` guard excludes five of
them (`SUCCEEDED`, `FAILED`, `SKIPPED`, `BLOCKED`, `RUNNING`) before the inner block is ever reached. Mypy performs
exhaustive literal narrowing over the enum: having ruled out five of the seven members via the `continue`, it
correctly infers that within the inner block, `task.status` can only be `Literal[TaskStatus.PENDING,
TaskStatus.READY]` — exactly the type mypy reports as the left operand at both flagged lines.

Given that narrowed type, `task.status is not TaskStatus.BLOCKED` (line 149) and `task.status is not
TaskStatus.SKIPPED` (line 152) compare a value that is statically known to be `PENDING` or `READY` against a
literal (`BLOCKED`, `SKIPPED`) that has already been excluded from the possible value set. The comparison can
never be `False` — mypy is not reporting a *bug* in the classic sense, but a **redundant/dead runtime check**: a
comparison whose outcome is fully determined by control flow that occurs earlier in the same function, which
strict mode surfaces because it can prove the check adds no information.

**Classification (per the Phase 1 checklist):** this is a **type-narrowing issue** — specifically, a
comparison against a value already excluded by prior control-flow narrowing over a closed enum — not a missing/
incorrect annotation, generic, Optional-handling gap, or callable/protocol mismatch. `task.status`'s type
(`TaskStatus`) was always correctly annotated; the issue is purely that the *value* is statically over-determined
at the point of comparison.

**Was runtime behavior already correct?** Yes. Because the comparisons are provably always `True` given the
current `TaskStatus` enum and the current control flow, they never influenced which branch executed or whether
`changed` was set — removing them changes nothing observable at runtime. This was confirmed empirically (§5),
not just argued from the type derivation.

---

## 3. Fix

The two now-redundant guards were removed, and the `if/elif` was collapsed into `if task.required: ... else: ...`
(exhaustive over `required: bool`, so `else` is exactly equivalent to `not task.required`). `changed = True` was
hoisted once, since it was set unconditionally in both original branches.

```python
if parent.status in {TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.SKIPPED}:
    # `task` reaches this point only via the loop's own continue-guard
    # above, which already excludes BLOCKED/SKIPPED (and every other
    # terminal status) — so task.status here is always PENDING or
    # READY, never BLOCKED or SKIPPED already. The prior explicit
    # `task.status is not ...` guards were therefore always true;
    # removed as dead comparisons (mypy: comparison-overlap).
    if task.required:
        by_id[task.task_id.as_text()] = task.with_status(TaskStatus.BLOCKED)
    else:
        by_id[task.task_id.as_text()] = task.with_status(TaskStatus.SKIPPED)
    changed = True
    break
```

**Why this is type-correct, and not a workaround:** the fix does not add an annotation, cast, `Any`, or
`# type: ignore` anywhere — it removes exactly the two comparisons mypy proved to be dead, which is the
canonical resolution for `comparison-overlap`: either the comparison is a genuine bug (it isn't, per §2/§4) or it
is truly redundant and should be deleted. No third-party typing defect is involved (`TaskStatus` is this
project's own enum), so a documented `# type: ignore[comparison-overlap]` would have been an unjustified
workaround under the task's own constraints — deletion is the precise fix, not a suppression.

---

## 4. Runtime Impact

None. The removed comparisons were provably always `True` (§2), so:
- The `if task.required: ... else: ...` split selects exactly the same branch, for exactly the same tasks, as
  the original `if ... and ... / elif ... and ...` did.
- `changed = True` is set in exactly the same cases as before (both original branches set it unconditionally
  whenever they executed; hoisting it above the `if/else` does not change when it fires, since the surrounding
  `if parent.status in {...}` still gates the whole block).
- No public API, function signature, return type, or domain semantic changed. `apply_failure_propagation`'s
  signature, docstring, and sort/ordering behavior (`return tuple(sorted(...))`) are untouched.
- This function is not part of the F01–F12 remediation diff — it was not modified by any of F01–F12 and shares
  no code path with any of those findings' fixes.

---

## 5. Validation

**Targeted mypy** (full strict run, project's exact CI invocation):
```
Success: no issues found in 190 source files
```
Both original errors are gone; zero new errors anywhere in the codebase.

**Targeted tests** — `tests/unit/test_orchestration_domain.py`, `test_phase6_contract_freeze.py`,
`test_research_execution.py` (all files exercising `graph.py`/`apply_failure_propagation`):
```
48 passed in 2.15s
```
including the new `test_failure_propagation_skips_optional_dependents` (previously-uncovered case: an optional/
`not required` dependent of a failed parent must become `SKIPPED`, not `BLOCKED` — mirrors the existing
`test_transitions_and_failure_propagation`, which only covered the `required` → `BLOCKED` path).

**Non-vacuous confirmation:** `git stash` isolated only `graph.py` back to its pre-fix state, and:
1. Mypy reproduced the identical 2 errors (`Found 2 errors in 1 file`) — confirming the fix, not an unrelated
   environment change, is what resolves them.
2. The new regression test was re-run against the *pre-fix* code and **passed** — confirming the fix is a pure
   type-level dead-code removal with no runtime effect (the test was not "written to the fix"; it validates a
   behavior that was already correct and remains correct after the cleanup).

`git stash pop` restored the fix; mypy was re-confirmed clean immediately after.

**Full test suite:**
```
848 passed, 1 warning, 130 subtests passed
```
(baseline before this cleanup: 847 passed / 130 subtests; +1 is the legitimate new regression test named above,
per the task's own allowance for a test-count increase when a genuine new regression test is added.)

The single warning is the same pre-existing, environment-level `PytestUnhandledThreadExceptionWarning` /
`UnicodeDecodeError` (Windows `cp1252` subprocess-output decoding in the untracked Docker sanity tests) already
documented in `FINAL_F01_F12_VALIDATION_REPORT.md` §9 — unrelated to this change, not newly introduced, does not
fail any test.

**Ruff (lint):**
```
All checks passed!
```
(`python -m ruff check src tests`, the project's CI-scoped invocation.)

**Ruff (format check):**
```
1 file would be reformatted, 258 files already formatted
```
(`python -m ruff format --check src tests`, the project's CI-scoped invocation.) The one flagged file is
`src/financial_intelligence/infrastructure/financial/sec_company_facts.py` — a pre-existing formatting drift
from the prior F12 implementation session, **not** touched by this mypy cleanup task. Neither `graph.py` nor
`test_orchestration_domain.py` (the two files this task changed) appear in the flagged output — this task's own
change is format-clean. Flagged here as an out-of-scope observation only, per the task's own instruction not to
fix unrelated files; not remediated in this pass.

**Mypy (full strict, final):**
```
Success: no issues found in 190 source files
```
**Target result achieved: Mypy CLEAN — 0 errors.**

---

## 6. F01–F12 Regression

The complete test suite remains green: **848 passed / 130 subtests**, with the only delta from the F01–F12
final-validation baseline (847/130) being the one new, intentional orchestration regression test added by this
task. No F01–F12 source file was touched — `git diff --stat` (§7) shows the same 26 F01–F12 files plus exactly
two new files (`graph.py`, `test_orchestration_domain.py`) from this task, and none of the 26 F01–F12 files'
line-change counts differ from the F01–F12 final-validation report. F01–F12 was not reopened, redesigned, or
re-implemented in any way.

---

## 7. Git Diff

Files changed by **this** mypy cleanup task only (relative to the state at the end of F01–F12 final validation):

- `src/financial_intelligence/domain/orchestration/graph.py` — the fix (13 lines changed: removed two dead
  `is not` comparisons, collapsed `if/elif` to `if/else`, hoisted one `changed = True`).
- `tests/unit/test_orchestration_domain.py` — one new regression test (22 lines added) covering the
  previously-untested "optional dependent → `SKIPPED`" propagation path.

No other file was modified by this task. `git status --short --branch` confirms `## main...origin/main` with the
same working-tree modification/untracked-file set as before, plus these two files and this report.

---

## 8. Verdict

**MYPY CLEANUP PASSED**
