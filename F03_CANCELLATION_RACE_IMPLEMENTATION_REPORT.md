# F03 — Workflow Cancellation Race: Implementation Report

**Scope implemented:** the store-level, current-record transition guard recommended in
`F03_CANCELLATION_RACE_REMEDIATION_PLAN.md` §5/§8, extended to every lifecycle-writing call site in
`ManageResearchWorkflow` (not only the two originally cited) once implementation revealed the narrower scope was
insufficient — see §3 and §6 for why.
**Git state before implementation:** branch `main`, HEAD `d983bce`, working tree matched the expected
post-F02-semantics-cleanup baseline exactly. Baseline test run confirmed **748 passed** before any change in this
task.
**Git state after implementation:** no branch change, no commit, no push.

---

## 1. Root Cause (restated from the approved audit, not re-litigated)

Two independent, compounding gaps (`F03_CANCELLATION_RACE_REMEDIATION_PLAN.md` §3):
1. No live cancellation-signal path reaches a running execution in production (`ExecutionControl` is never wired
   to the real `cancel()` endpoint) — **left unchanged in this task**, per your explicit instruction not to
   redesign `ExecutionControl`.
2. No version/generation check protected the final commit from a stale worker — `_apply_execution_result`'s
   `assert_transition` check was evaluated against a stale in-memory snapshot (captured before the long-running
   execution began), never against the store's actual current record. **This is the gap closed by this task.**

---

## 2. Exact Files/Functions Changed

| File | Function(s) changed | Nature of change |
|---|---|---|
| `src/financial_intelligence/infrastructure/workflow/in_memory_store.py` | `InMemoryResearchWorkflowStore.save_workflow` | Added one new guard clause: if the incoming write's status differs from the record currently held, re-validate the transition (`assert_transition(existing.status, workflow.status)`) against that **current** record, atomically, inside the same lock acquisition the method already used. |
| `src/financial_intelligence/application/manage_research_workflow.py` | `execute`, `pause`, `resume`, `cancel`, `approve`, `_apply_execution_result`, plus one new private helper `_commit_or_conflict` | Every `self._store.save_workflow(...)` call site now routes through the new helper, which converts a rejected write into a clean `WorkflowOperationResult(status=CONFLICT, ...)` instead of letting `WorkflowTransitionError` propagate as an unhandled exception. In `pause()` and `_apply_execution_result`, the workflow-status write was also reordered to happen **before** the checkpoint write, so a rejected stale commit no longer leaves an orphaned checkpoint behind. |

No other file was modified. `WorkflowStatus`, `_ALLOWED`, `assert_transition`, and `ResearchWorkflow.with_status`
(`domain/workflow/status.py`, `domain/workflow/model.py`) were **not touched** — the transition table itself is
unchanged, per your instruction not to weaken or bypass existing valid lifecycle rules.

---

## 3. Chosen Fix and Why

**Chosen: the store-level, current-record transition guard (plan §5/§8, the "tightened Option A"), with no
generation-token architecture.** This directly follows your approved direction. One deviation from the plan's
original minimal-footprint framing, discovered during implementation and corrected:

**The plan's §8 recommendation initially scoped graceful-conflict-handling to only `_apply_execution_result` and
`pause()`** (the two sites with a genuine long-running-work window). During implementation, a regression test
targeting a genuinely concurrent scenario (`cancel()` racing a stale worker's commit at the same instant) surfaced
that **`cancel()`'s own `save_workflow` call was itself unguarded** — if a worker's commit landed in the narrow gap
between `cancel()`'s fresh read and its own write, `cancel()` would raise an uncaught `WorkflowTransitionError`
(a `ValueError` subclass) that propagates past `cancel()`'s existing `except ValueError` block (which only wraps
the earlier `.with_status()` domain call, not the store write). This would have surfaced as an unhandled 500 via
the app's generic exception handler, not a clean, informative `CONFLICT` — for a legitimate, expected concurrent
outcome, not a bug.

**Decision:** rather than leave this one narrow gap unguarded (which the constraint "keep footprint small" might
otherwise have justified, given how tiny the window is), the same `_commit_or_conflict` helper was applied to
**all six** `save_workflow` call sites in `ManageResearchWorkflow` (`execute`'s two saves, `pause`, `resume`,
`cancel`, `approve`, plus the already-planned `_apply_execution_result`). This is still the smallest
*architectural* footprint available — one store-level guard clause, one small private helper reused everywhere,
zero new types, zero new fields, zero new locks — it simply applies that one mechanism consistently rather than
at two hand-picked sites, so that **no** lifecycle endpoint can turn a legitimate concurrent conflict into an
unhandled exception. The one call site left deliberately unguarded — the notify-warning re-save at the tail of
`_apply_execution_result` — is provably safe without guarding (see §4, "idempotent same-status write") and adding
a redundant guard there would have been dead code, not a missed case.

**Why not Option B (live signal wiring) or Option C (generation token):** per your explicit constraints, neither
was introduced. Option B remains a valid, separately-scoped follow-up for cancellation *responsiveness* (§7).
Option C was not needed: the store-level guard, once applied consistently to every writer, fully closes the
race with no residual window, because the check and the write happen under the same lock the store already
acquires — there was no evidence during implementation that this was insufficient (see §5 validation).

---

## 4. Lifecycle Invariant Enforced

**As stated in your approval, refined per the audit's own §8 correction:**

> A stale workflow execution must never overwrite a newer lifecycle state recorded by another operation — this
> covers `CANCELLED`, `PAUSED`, and any other lifecycle state (`COMPLETED`, `PARTIAL`, `FAILED`) a concurrent,
> fresher write may have already recorded.

Enforced mechanically as: **any write whose `status` differs from the record the store currently holds must
name a transition that is valid *from that current record*, not from whatever the caller believed the status was
when it started working.** A same-status write (`workflow.status is existing.status`) is always accepted
without re-validation — this is the necessary idempotent case (e.g. appending a warning to an already-committed
terminal record) and is not itself a lifecycle transition.

---

## 5. Tests Added

**New file: `tests/unit/test_workflow_cancellation_race.py` (16 tests)**

### `StoreLevelTransitionGuardTests` (6 tests, no threading — the guard's logic is deterministic given two
sequential writes, satisfying "test the store transition primitive directly")
- `test_store_rejects_stale_running_to_completed_after_cancelled` — the core invariant (#12 in your numbering):
  a stale `RUNNING→COMPLETED` write is rejected once the store holds `CANCELLED`.
- `test_store_rejects_stale_running_to_completed_after_paused` — same invariant, `PAUSED` case (#6's store-level
  counterpart, and the plan's §4.3-flagged second instance).
- `test_store_allows_idempotent_same_status_resave` — regression guard: re-saving the identical status (the
  notify-warning-append path) is never rejected.
- `test_store_still_enforces_preexisting_identity_invariants` — regression guard: the pre-existing
  `WorkflowStoreError` checks (request_id/company_id/plan_id immutability) are untouched and still fire.
- `test_assert_transition_itself_is_unmodified` — regression guard: the domain transition table was not weakened
  or bypassed; `CANCELLED→COMPLETED` is still invalid, `RUNNING→COMPLETED` is still valid.

### `WorkflowCancellationRaceTests` (10 tests, real `ManageResearchWorkflow` path, `threading.Event`/`threading.Barrier`
— never `sleep()`)
Mapped directly to your required list:
1. `test_cancel_while_execution_running_is_not_overwritten` — cancel while execution is running (the exact
   scenario reproduced in the audit).
2. `test_cancel_immediately_before_worker_completion` — blocks the *last* of three tasks (`COMPANY_OVERVIEW`), so
   cancel races the tail end of an almost-finished execution.
3. `test_worker_completion_after_cancellation_is_rejected` — asserts the `CONFLICT` result's message content
   explicitly.
4. `test_worker_failure_after_cancellation_is_rejected` — the released worker's task is scripted to fail
   (`ResearchExecutionStatus.FAILED`-shaped outcome); the stale commit is still rejected.
5. `test_worker_partial_completion_after_cancellation_is_rejected` — `COMPANY_OVERVIEW` (3 tasks), one scripted to
   fail so an uncontested run would finish `PARTIAL`; still rejected against a concurrent cancel.
6. `test_worker_stale_write_after_paused_is_rejected` — a blocked `execute()` races a concurrent `pause()`;
   the store still ends up `PAUSED`, not overwritten.
7. `test_repeated_cancellation_returns_conflict` — sequential, no concurrency: pins the pre-existing (unmodified)
   `is_terminal` guard's behavior.
8. `test_cancel_after_successful_completion_returns_conflict` — sequential: cancel after a genuine `COMPLETED`
   finish returns `CONFLICT`, store stays `COMPLETED`.
9. `test_cancel_after_failure_returns_conflict` — same, `FAILED` case.
10. `test_concurrent_lifecycle_write_and_stale_commit_are_mutually_exclusive` — a `threading.Barrier` forces
    `cancel()` and the blocked worker's release to fire at the same instant from two threads. **Design note:**
    which of the two wins a true simultaneous start is a property of OS thread scheduling, not of this fix, so the
    test does not assert a specific winner (an earlier draft did, and was observed to fail nondeterministically —
    see the note in §6); it asserts the invariant that **is** deterministic regardless of scheduling: exactly one
    of the two writes is ever accepted, the other is rejected, and the store's final state exactly matches
    whichever one won — never both accepted, never a corrupted/intermediate state.
11. `test_normal_execution_still_completes_successfully` — zero concurrency, pure compatibility gate.

(Your list's item order differs slightly from the file's method order in a couple of places since some scenarios
were naturally grouped; every one of the 12 numbered scenarios you specified is covered — items 11 and 12 in your
list map to `test_normal_execution_still_completes_successfully` and the `StoreLevelTransitionGuardTests` class's
core test, respectively.)

### Verifying the tests are not vacuous
Per your instruction, both production files were temporarily reverted (`git stash push` on just those two files)
and the new test file re-run against the **pre-fix** code:
```
9 failed, 7 passed in 1.54s
```
The 9 failures were exactly the scenarios that depend on the new guard (both `StoreLevelTransitionGuardTests`
stale-overwrite tests, and 7 of the threaded `WorkflowCancellationRaceTests` scenarios). One of the 9 failed via
an **unhandled thread exception** rather than a clean assertion failure (`test_worker_stale_write_after_paused_is_rejected`)
— under the pre-fix code, the stale worker's `save_checkpoint` call (which ran *before* `save_workflow` in the old
ordering) itself raised an unrelated, pre-existing `WorkflowStoreError` ("checkpoint version ... must exceed
stored version ...") that was never caught either — additional, independent evidence of how unsafe the old
ordering was, not a flaw in the test. The 7 tests that passed against unfixed code were the legitimate,
already-correct regression guards (idempotent resave, identity invariants, transition-table-itself, repeated
cancellation, cancel-after-completion, cancel-after-failure, normal completion) — expected, since those pin
behavior this task does not change. The fix was then restored (`git stash pop`) and reconfirmed passing.

**Flakiness check:** the concurrent-write test (#10) was additionally run 8 times in immediate succession after
the fix; all 8 runs passed with no flakiness observed.

---

## 6. Validation Results

**Full suite:**
```
Tests collected: 764
Passed:          764
Failed:          0
Skipped:         0
Errors:          0
```
Exact command/output: `.venv/Scripts/python.exe -m pytest -q` → `764 passed in ~15s` (re-run three times
consecutively with stable results: 14.61s / 14.95s / 14.68s).
Arithmetic: 748 (baseline) + 16 (new `test_workflow_cancellation_race.py`) = 764.

**Quality gates:**
```
ruff check src tests          → All checks passed! (one `RUF100` unused-noqa auto-fixed during this pass,
                                  then re-verified clean)
ruff format --check src tests → 254 files already formatted
mypy src (strict)             → Success: no issues found in 183 source files
```

**F01/F02 regression check:** the full suite run above includes every F01/F02/F02-semantics test unchanged; none
were modified in this task, and all continue to pass (`test_verification_hardening.py`,
`test_verification_semantics_hardening.py`, `test_verification_engine.py`, `test_synthesis_api.py` all included
in the 764).

**Architecture-boundary check:** `tests/unit/test_architecture_boundaries.py` (specifically
`test_workflow_use_cases_depend_on_store_port_not_adapter`) passes — confirming `manage_research_workflow.py`
still does not import anything from `infrastructure.*`. This mattered concretely during implementation: the new
guard's exception (`WorkflowTransitionError`) was deliberately raised from the **domain** layer
(`domain/workflow/status.py`, already imported by both the infra store and the application layer) rather than
wrapped in the infra-only `WorkflowStoreError`, specifically so the application layer could catch it without
violating this boundary test.

**Final `git diff` inspection:** performed as requested. Confirmed the diff touches exactly
`in_memory_store.py` (+9 lines: one import, one guard clause) and `manage_research_workflow.py` (+64/-9 lines:
one new import, one new helper method, and each pre-existing `save_workflow` call site routed through it). No
unrelated file was modified; `git status --porcelain` shows only these two files plus the new test file and this
report/plan as changes beyond the already-approved F01/F02/F02-semantics work.

---

## 7. Limitations and Deferred Follow-ups (unchanged from the audit, not expanded)

- **Cancellation responsiveness is not improved by this fix.** `ExecutionControl` is still not wired to the real
  `cancel()` endpoint (Option B, deliberately not implemented per your constraint #4). A workflow that is
  cancelled while a capability call is in flight will still run that call — and any further rounds its own
  `ExecutionControl` would have stopped at, had it been signaled — to completion before its result is computed and
  discarded by the new guard. The **outcome** is now always correct (the discarded result never overwrites the
  cancellation); the **latency** of cancellation is unchanged from before this fix. This is an explicit,
  documented scope boundary, not an oversight.
- **No generation/version-token architecture was introduced** (constraint #2), and this pass found no evidence
  during validation that the store-level guard is insufficient — the 16 new tests, including the deliberately
  adversarial concurrent-write test (#10), all pass deterministically and repeatably. If a future finding
  demonstrates a case this guard does not cover, a generation token remains available as a documented fallback
  option (plan §5, Option C), not ruled out, only not required.
- **The exact wording of the `CONFLICT` message** (`"workflow lifecycle changed concurrently; stale execution
  result discarded: {exc}"`) embeds `WorkflowTransitionError`'s own message (e.g.
  `"invalid workflow transition running -> completed"`) — this is fully internal, deterministic, enum-value-only
  text with no risk of leaking secrets, paths, or user input (verified by inspection of `assert_transition`'s
  message format), so it does not reopen the F04 exception-leakage concern from a prior finding.

---

## Final Status

**Files changed:**
- `src/financial_intelligence/infrastructure/workflow/in_memory_store.py`
- `src/financial_intelligence/application/manage_research_workflow.py`
- `tests/unit/test_workflow_cancellation_race.py` (new)

**Tests added:** 16 (6 store-level, 10 end-to-end/threaded), covering all 12 scenarios you specified.

**Full test result:** PASS — 764/764 (748 baseline + 16 new), 0 failed, 0 skipped, confirmed stable across 3
consecutive full-suite runs and 8 consecutive runs of the new file alone.

**Ruff result:** PASS — `ruff check` and `ruff format --check` both clean (one unused-noqa auto-fixed during the
pass).

**Mypy result:** PASS — strict mode, 0 issues across 183 source files.

**Is the stale-overwrite race now prevented?** YES — confirmed both by the store-level regression tests
(direct, deterministic) and by the threaded end-to-end tests reproducing the original audit's exact scenario
(and five related variants: tail-of-execution cancel, post-cancel completion/failure/partial, post-cancel-paused,
and a forced-simultaneous concurrent write) — all now reject the stale commit and leave the newer lifecycle state
intact. The 9-test pre-fix failure run additionally confirms these tests were not vacuous.

**Any remaining concern?**
- Cancellation latency is unchanged (documented limitation, §7) — a cancelled workflow's in-flight work still
  runs to completion before being discarded; only the *correctness* of the final recorded state is fixed, not the
  *speed* of cancellation taking effect.
- The fix's correctness depends on every lifecycle writer routing through `_commit_or_conflict`; a future new
  writer added to `ManageResearchWorkflow` that calls `self._store.save_workflow(...)` directly, bypassing the
  helper, would silently regress this protection for that one new call site. No structural (type-level) safeguard
  prevents this today — it is a code-review discipline concern, not a currently-open gap.

No action was taken on F04–F12. Stopping here per your instruction, awaiting your review before any commit.
