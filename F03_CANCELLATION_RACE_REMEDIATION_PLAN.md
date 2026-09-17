# F03 — Workflow Cancellation Race: Concurrency/Root-Cause Audit and Remediation Plan

**Status:** AUDIT/DESIGN ONLY — no source code modified, no dependency added, no commit, no push, no branch
change.
**Verified against:** HEAD `d983bce`, branch `main`, working tree in the expected post-F02-semantics-cleanup
state (748/748 passing, confirmed before this audit began).
**Method:** every claim below is backed by a direct file/line read performed in this pass, and the race itself was
**empirically reproduced** with a throwaway, non-destructive harness run against the actual, unmodified
application/domain code (script kept outside the repository, under this session's scratchpad directory — no
repository file was created, edited, or deleted to produce this evidence).

---

## 1. Complete Workflow Lifecycle Trace

### 1.1 Files and classes involved

| Concern | File | Class/Function |
|---|---|---|
| Lifecycle enum + transition table | `src/financial_intelligence/domain/workflow/status.py` | `WorkflowStatus`, `_ALLOWED`, `assert_transition`, `is_terminal` |
| Workflow aggregate (immutable, `frozen=True`) | `src/financial_intelligence/domain/workflow/model.py` | `ResearchWorkflow.with_status`, `.with_checkpoint`, `.with_approval` |
| Checkpoint (execution progress snapshot) | `src/financial_intelligence/domain/workflow/checkpoint.py` | `WorkflowCheckpoint` (own `version` field, unrelated to workflow `status`) |
| Application orchestration of lifecycle ops | `src/financial_intelligence/application/manage_research_workflow.py` | `ManageResearchWorkflow.execute`, `.pause`, `.resume`, `.cancel`, `.approve`, `._apply_execution_result` |
| Cooperative cancellation token | `src/financial_intelligence/domain/orchestration/execution_control.py` | `ExecutionControl` (`is_cancelled`, `is_pause`, `.cancel()`, `.request_pause()`) |
| Bounded execution loop (checks the token) | `src/financial_intelligence/application/execute_research_plan.py` | `ExecuteResearchPlan.execute_prepared` (the `while rounds < max_rounds:` loop) |
| Persistent store (process-local, in-memory) | `src/financial_intelligence/infrastructure/workflow/in_memory_store.py` | `InMemoryResearchWorkflowStore` (`_lock: RLock`, `save_workflow`, `get_workflow`, `save_checkpoint`) |
| HTTP surface | `src/financial_intelligence/api/routes/workflows.py` | `execute_research_workflow` (line 232), `cancel_research_workflow` (line 313) — both plain `def` (sync) route handlers |
| DI wiring | `src/financial_intelligence/composition/__init__.py` | `build_container` — constructs one shared `InMemoryResearchWorkflowStore` instance per process, injected into every use case |

### 1.2 Concurrency model (confirmed, not assumed)

- Every `workflows.py` route handler is a plain `def` (synchronous) function, not `async def` (confirmed by
  `grep -n "async def\|^def "` — every handler in that file is `def`). Starlette/FastAPI dispatch synchronous
  route handlers to a **thread-pool executor**, so two simultaneous HTTP requests to
  `POST /research/workflows/{id}/execute` and `POST /research/workflows/{id}/cancel` genuinely run on **two
  different OS threads concurrently**, both holding a reference to the same process-wide `AppContainer` and its
  single `InMemoryResearchWorkflowStore` instance.
- `InMemoryResearchWorkflowStore` uses one `threading.RLock` (`in_memory_store.py:26`), but the lock is acquired
  and released **per individual method call** (`get_workflow`, `save_workflow`, `save_checkpoint`,
  `list_workflows` each take and release it independently). It does **not** span the multi-step sequence
  `get → (long-running work) → save` that `ManageResearchWorkflow.execute` performs. This is confirmed by reading
  the full method bodies — there is no lock acquisition anywhere in `manage_research_workflow.py` itself (grep
  for `Lock`/`lock` in that file returns zero hits outside of the unrelated `clock` callable name).
- `ExecutionControl` (`execution_control.py`) is a plain, unsynchronized mutable object (`__slots__`, three plain
  attributes, no lock). Its own docstring states cancellation is "cooperative" and "does not interrupt an
  in-flight capability call" — this is a correctly-documented *design limitation* of the token itself, but (see
  §1.3) the token is never even wired to the real cancel endpoint, so this limitation is moot in production.

### 1.3 The full CREATE → EXECUTE → RUNNING → CANCEL → CANCELLED → completion/failure trace

```
POST /research/workflows                (create_research_workflow route)
    -> CreateResearchWorkflow.execute -> ResearchWorkflow(status=CREATED) -> .with_status(READY|AWAITING_APPROVAL)
    -> store.save_workflow(...)

POST /research/workflows/{id}/execute   (execute_research_workflow route, workflows.py:232)
    -> container.manage_research_workflow.execute(wid)      <-- NO `control=` argument is ever passed here
       [manage_research_workflow.py:104]
       1. workflow = store.get_workflow(wid)                          (snapshot #1, e.g. status=READY)
       2. running  = workflow.with_status(RUNNING, at=now)            (assert_transition(READY, RUNNING) -- OK)
       3. store.save_workflow(running)                                 <-- store now shows RUNNING
       4. control = control or ExecutionControl()                     <-- a BRAND NEW, throwaway token;
                                                                            nothing outside this call frame
                                                                            ever holds a reference to it
       5. exec_result = self._execute.execute_prepared(running.plan, ..., control=control, ...)
          [execute_research_plan.py:143 execute_prepared]
              while rounds < max_rounds:
                  if control.is_cancelled:  <-- only ever True if THIS SAME control object's .cancel()/
                                                 .request_pause() was called; nothing external can reach it
                      ...
                  <select next ready task, call capability_executor.execute_task(...)>  <-- can block for an
                                                                                             arbitrary amount of
                                                                                             real time (a slow
                                                                                             adapter, network
                                                                                             call, etc.)
       6. return self._apply_execution_result(running, exec_result, ...)  <-- `running` is snapshot #1,
                                                                               taken BEFORE step 5's
                                                                               long-running work, and is
                                                                               NEVER refreshed from the store

POST /research/workflows/{id}/cancel    (cancel_research_workflow route, workflows.py:313)
    -- runs concurrently, on a different thread, while the above is blocked inside step 5 --
    -> container.manage_research_workflow.cancel(wid)   [manage_research_workflow.py:269]
       1. workflow = store.get_workflow(wid)             (snapshot #2, e.g. status=RUNNING, fetched fresh)
       2. cancelled = workflow.with_status(CANCELLED, at=now)   (assert_transition(RUNNING, CANCELLED) -- OK)
       3. store.save_workflow(cancelled)                         <-- store NOW correctly shows CANCELLED
       4. returns 200 OK, "workflow cancelled"                   <-- caller is truthfully told it is cancelled

-- back in the execute() thread, the blocked capability call finally returns --
       7. _apply_execution_result(workflow=<snapshot #1, status still RUNNING>, exec_result=<COMPLETED/PARTIAL/
          FAILED, computed with NO knowledge that a cancel happened>)
          [manage_research_workflow.py:349]
              updated = workflow.with_checkpoint(checkpoint, at=now)   <-- workflow is snapshot #1; status
                                                                            field is still RUNNING here
              updated = updated.with_status(terminal, at=now)          <-- assert_transition(RUNNING, terminal)
                                                                            -- ALWAYS OK, because it is checked
                                                                            against snapshot #1's stale RUNNING
                                                                            status, NEVER against the store's
                                                                            actual current (CANCELLED) status
              store.save_checkpoint(checkpoint)
              store.save_workflow(updated)                             <-- silently OVERWRITES the CANCELLED
                                                                            record with COMPLETED/PARTIAL/FAILED
```

**This is the complete mechanism.** The state-transition guard (`assert_transition`) is real, correctly
implemented, and does correctly reject truly invalid transitions such as `CANCELLED → COMPLETED` **when checked
against the right object** — but step 7 never checks it against the *store's current record*; it checks it
against a private, stale, in-memory copy that was captured before the cancel happened. The guard is not missing;
it is **evaluated against the wrong (stale) data**.

---

## 2. Reproducing the Race (empirical, not merely inferred)

A read-only, non-destructive harness was written and executed **outside the repository** (kept in this session's
scratchpad directory, not committed, not added to the repo's `tests/` tree) that:
1. Builds a real `AppContainer` via `build_container(...)` — the same composition path production uses.
2. Creates a real `ResearchWorkflow` (Apple/NASDAQ, `MARKET_ANALYSIS` objective) through the real
   `CreateResearchWorkflow` use case.
3. Wraps the container's real capability executor in a thin pass-through that blocks the **first** task's
   execution on a `threading.Event`, simulating a slow external adapter call — this is the same technique the
   existing `PRODUCT_AUDIT_2026-09-15.md` used, re-implemented and re-run independently in this pass rather than
   taken on faith.
4. Starts `manage_research_workflow.execute(workflow_id)` on a background thread — **calling it exactly the way
   the real HTTP route calls it: with no `control=` argument**, to prove the production code path, not a
   best-case test-only path.
5. On the main thread, once the capability call is confirmed blocked, calls
   `manage_research_workflow.cancel(workflow_id)` — exactly what `POST /cancel` does.
6. Releases the blocked capability call, joins the background thread, and reads the final stored workflow status.

**Actual output from running this harness against the current, unmodified code:**
```
[setup] created workflow c563394b-0292-4b10-855e-dd9cd233b31b status=ready
[t=0] execute() is now blocked mid-capability-call (simulating a slow adapter)
[t=1] cancel() returned status=ok workflow.status=cancelled
[t=1] store now reports status=cancelled
[t=2] execute() finished with WorkflowOperationResult.status=ok, workflow.status=partial
[t=2] FINAL store status = partial

RESULT: RACE REPRODUCED -- workflow was CANCELLED at t=1 but the store now shows 'partial' at t=2. The completed
execute() silently overwrote the cancellation.
```

**This confirms, by direct execution against the real code (not a mock, not a simulation of the logic, an actual
run of `ManageResearchWorkflow`/`InMemoryResearchWorkflowStore`/`ExecuteResearchPlan`):**
1. Execution starts (`execute()` called, workflow moves `READY → RUNNING`, real store write).
2. Execution becomes long-running (blocked inside the first capability call).
3. Cancellation occurs concurrently (`cancel()` called from a second thread while step 2 is still blocked).
4. Cancellation state is correctly recorded (`store.get_workflow` immediately after step 3 shows `CANCELLED`; the
   HTTP-equivalent caller of `cancel()` receives a truthful `200 OK "workflow cancelled"`).
5. The original execution resumes (the blocking event is released) and completes on its own terms, entirely
   unaware that a cancellation happened.
6. **It can, and in this run did, overwrite the cancellation state** — the final persisted status is `partial`
   (a legitimate execution outcome, computed with zero knowledge of the intervening cancel), not `cancelled`. A
   client that called `GET /research/workflows/{id}` any time after step 6 would see `partial`, contradicting the
   `200 OK "workflow cancelled"` response it (or another caller) received at step 4.

No production code was altered to obtain this result; the harness only wraps the capability executor
(dependency-injected, not source-modified) and calls existing, unmodified public methods.

---

## 3. Exact Root Cause

**Not a single mechanism — two independent, compounding gaps, both confirmed by direct code reading and by the
reproduction above:**

### 3.1 Missing task cancellation (the live-signal path does not exist in production)
`ExecutionControl` is the domain's only cancellation-signaling primitive, and `execute_prepared`'s loop does
correctly check it. But:
- `ManageResearchWorkflow.cancel()` (the method the real `/cancel` HTTP route calls) **never references
  `ExecutionControl` at all** — confirmed by reading the entire method body (`manage_research_workflow.py:269-308`):
  it only touches `ResearchWorkflow.with_status` and the store. There is no registry mapping `workflow_id ->
  ExecutionControl` anywhere in the composition container, the store, or the application layer.
- `ManageResearchWorkflow.execute()` creates a **fresh, private** `ExecutionControl()` per call
  (`manage_research_workflow.py:186`) when the caller doesn't supply one — and `workflows.py`'s
  `execute_research_workflow` route (the only real caller in production) never supplies one (confirmed: `grep -n
  "ExecutionControl\|control=" src/financial_intelligence/api/routes/workflows.py` returns zero matches).
- **Consequence:** in the real, running system, there is no code path by which a `cancel()` HTTP call can ever
  set `is_cancelled = True` on the `ExecutionControl` instance a concurrently-running `execute()` is checking.
  The cooperative-cancellation mechanism inside `execute_prepared` is fully functional in isolation (and is
  exercised by `_CancelAfterN` in existing tests — see §6) but is **architecturally unreachable from the
  production cancel endpoint**.

### 3.2 Missing generation/version token at commit time (the stale-snapshot overwrite)
Independent of §3.1 — even if a live signal path existed and the running execution noticed the cancellation
*eventually*, the final commit in `_apply_execution_result` (`manage_research_workflow.py:349-434`) still has no
way to detect that the workflow it is about to write has been mutated since it was read:
- `_apply_execution_result` receives `workflow` as a plain function parameter — the exact `ResearchWorkflow`
  object captured at the *start* of `execute()`, before the long-running work. It is never re-fetched.
- `assert_transition` (called inside `.with_status(terminal, at=now)`, line 427) validates against
  `workflow.status`, i.e., the **parameter's** field, not the store's current record. Since the parameter's
  status is always `RUNNING` at this point (that's what it was set to at the top of `execute()`), and `RUNNING →
  {COMPLETED, PARTIAL, FAILED, CANCELLED}` are all valid transitions in the table, `assert_transition` **always
  passes**, regardless of what actually happened to the record in the store in the meantime.
- `InMemoryResearchWorkflowStore.save_workflow` (`in_memory_store.py:30-53`) is the one place that *could* have
  caught this — it does do optimistic-concurrency-style checks (identity fields must match; `checkpoint_version`
  must not regress) — but it has **no check comparing the incoming write's status/legality against the
  currently-stored status**. And critically, `cancel()` never advances `checkpoint_version` (it calls
  `.with_status()` directly, not `.with_checkpoint()`), so the later stale write's `checkpoint_version` (computed
  as `stale_snapshot.checkpoint_version + 1`) is **not** a regression relative to what `cancel()` left behind —
  the one existing version guard in the store is blind to this specific race because the two operations
  (`cancel`, and the stale execution's final commit) don't share a version counter that both of them advance.

### 3.3 Which named candidate mechanisms actually apply (answering the audit brief directly, not assuming the prior audit was right)
- **Missing state-transition guard** — **NO.** The guard (`assert_transition`) exists and is logically correct
  for the table it enforces (confirmed in §4). It is not missing; it is fed stale input.
- **Missing task cancellation** — **YES**, confirmed in §3.1: there is no live signal path from the real
  `cancel()` to any running `execute()`'s `ExecutionControl` in production.
- **Missing generation/version token** — **YES**, confirmed in §3.2: nothing ties the final commit to "is the
  record I'm about to overwrite still the one I originally read," and the one version counter that exists
  (`checkpoint_version`) is not advanced by `cancel()`, so it cannot detect this specific interleaving.
- **Missing lock** — **PARTIALLY / MISCHARACTERIZED.** A lock exists (`RLock` in the store) but at the wrong
  granularity — it protects each individual store method call, not the full `read → long-running-work → write`
  sequence that constitutes the actual critical section. Calling this "missing" would be imprecise; it is more
  accurate to say **the existing lock's scope does not cover the actual race window**, which no single additional
  lock acquisition inside `execute()` could fix on its own without also addressing §3.1/§3.2 (a lock alone would
  make the *store* internally consistent but would not stop a stale execution from *legitimately* overwriting a
  cancellation once it acquires the lock, since the stale execution still believes its own transition is valid).
- **Stale worker** — **YES**, this is an accurate description of the execution thread itself: once it has been
  dispatched, it is a "stale worker" with respect to any cancellation that happens after it started, and nothing
  currently prevents a stale worker from committing.
- **Race between async tasks** — **NO**, not literally; this is a **thread-based** race (synchronous route
  handlers dispatched to FastAPI's thread pool), not an `asyncio.Task` race. The underlying hazard (check-then-act
  across a suspend point) is the same class of bug, but the concrete mechanism is OS threads plus a shared
  in-process store, not asyncio concurrency.
- **Incorrect lifecycle ordering** — **NO**, the *ordering* of calls (`execute` then `cancel` then completion) is
  a legitimate, expected interleaving the system must handle correctly, not a bug in the sequence itself; the bug
  is in how the *later* commit fails to account for what happened in between.

**Conclusion: the root cause is the combination of §3.1 (no live cancellation signal reaches a running
execution in production) and §3.2 (no version/generation check protects the final commit from a stale
worker).** Fixing either one alone is insufficient: fixing only §3.1 would make cancellation *usually* faster to
take effect (the loop would notice sooner, at the next round boundary) but would not eliminate the race window
for whatever capability call is already in flight at the moment of cancellation (the docstring's own
"does not interrupt an in-flight capability call" caveat) — the stale worker could still finish and commit
without ever having rechecked after the in-flight call returned. Fixing only §3.2 (a version check at commit
time) would stop the incorrect overwrite but would leave cancellation just as ineffective at actually shortening
a running execution's real-world duration as it is today.

---

## 4. State-Machine Analysis

### 4.1 Currently allowed transitions (from `status.py:_ALLOWED`, read directly, not inferred)

```
CREATED           -> READY, AWAITING_APPROVAL, CANCELLED
READY             -> RUNNING, AWAITING_APPROVAL, CANCELLED
RUNNING           -> PAUSED, AWAITING_APPROVAL, COMPLETED, PARTIAL, FAILED, CANCELLED
PAUSED            -> READY, RUNNING, CANCELLED
AWAITING_APPROVAL -> READY, CANCELLED, FAILED
COMPLETED         -> (none -- terminal)
PARTIAL           -> (none -- terminal)
FAILED            -> (none -- terminal)
CANCELLED         -> (none -- terminal)
```

### 4.2 Does the implementation permit invalid transitions such as `CANCELLED → COMPLETED`?

**Not through `assert_transition` itself — that function correctly rejects it, always, when given the true
current status.** `_ALLOWED[WorkflowStatus.CANCELLED]` is `frozenset()` — empty — so
`assert_transition(WorkflowStatus.CANCELLED, anything)` unconditionally raises `WorkflowTransitionError`. This
was confirmed directly in this pass and is not in dispute.

**The invalid outcome is reached anyway, via a different mechanism**: the write that lands in the store never
actually asks `assert_transition(CANCELLED, COMPLETED)` — it asks `assert_transition(RUNNING, COMPLETED)` (which
is valid) because the object performing the check is a stale copy whose `.status` field was never updated to
`CANCELLED` in the first place. The **store ends up holding a `COMPLETED`/`PARTIAL`/`FAILED` record for a
workflow that a client was already truthfully told is `CANCELLED`** — the practical, observable effect is
equivalent to an illegal `CANCELLED → COMPLETED` transition having occurred, even though no single line of code
ever literally attempted that specific transition check. This distinction matters for the fix (§5): a fix that
only hardens `assert_transition` itself would do nothing, since it is never called with `CANCELLED` as the
"current" argument in this scenario.

### 4.3 Every invalid outcome possible via this mechanism, enumerated

Given the transition table, any status that is **terminal** and reachable from `RUNNING`/`PAUSED` can be
silently overwritten by a stale worker that started before the terminal status was set:

| Recorded (truthful) status at cancel-time | Can be overwritten by a stale worker's commit to | Confirmed how |
|---|---|---|
| `CANCELLED` (via `cancel()` while `execute()` is in flight) | `COMPLETED`, `PARTIAL`, `FAILED` | Empirically reproduced (§2); statically traced (§1.3, §3.2) |
| `CANCELLED` (via `cancel()` while a `pause()` is concurrently in flight) | `PAUSED` | Same mechanism: `pause()` (`manage_research_workflow.py:206-240`) also reads a workflow snapshot, builds a checkpoint, and calls `with_status(PAUSED)` — it has the identical stale-snapshot shape as `execute()`'s commit path, just a shorter code path. **Not empirically reproduced in this pass** (only the `execute()`-vs-`cancel()` interleaving was run); flagged as a **statically-derived, not yet executed**, second instance of the same bug class. |
| `PAUSED` (via `pause()` while `execute()` is concurrently in flight, e.g. a second `execute()`/`resume()` call racing a `pause()`) | `COMPLETED`, `PARTIAL`, `FAILED`, or a duplicate `PAUSED` checkpoint | Same mechanism, not empirically reproduced this pass; flagged as a plausible third instance sharing the identical root cause, since `pause()` and `execute()`'s commit paths share the same stale-parameter pattern. |

**No terminal→terminal transition was found to be directly reachable** (once `save_workflow` actually persists a
terminal status, a *second* stale worker attempting to commit afterward would still be operating on its own,
separately-stale snapshot from before either terminal write — the race is always "stale-RUNNING-snapshot commits
over a newer terminal write," not "terminal-A gets relabeled terminal-B after the fact by a third party reading
the already-terminal record," since nothing re-derives a terminal-to-terminal transition from an already-updated
terminal record). The risk is specifically: **a terminal write from a stale in-flight operation can silently
replace a different, already-correctly-recorded terminal (or `PAUSED`) write**, not that a settled terminal record
can later be re-opened by unrelated code.

---

## 5. Fix Strategy Evaluation (comparison only, nothing implemented)

### Option A — State-transition guard (reject completion/failure if already cancelled)
Re-fetch the current workflow from the store immediately before the final `with_status`/`save_workflow` in
`_apply_execution_result` (and the equivalent spot in `pause()`), and call `assert_transition` against **that**
fresh read instead of the stale parameter.

- **Correctness:** closes the specific race demonstrated in §2 for the "final commit" moment, provided the
  re-fetch-then-check-then-write itself is atomic (see Option D) — without atomicity, this narrows the race
  window (from "the entire execution duration" to "the gap between the re-fetch and the write") but does not
  eliminate it; a second cancel could still land in that narrower gap.
- **Concurrency behavior:** does not stop the stale worker from *running* — it still does all the wasted work — it
  only stops it from *committing* a wrong result. Correctly turns the eventual outcome into "execution ran to
  completion but its result was discarded because the workflow was cancelled in the meantime," which is an honest
  and reasonable outcome for a cancelled workflow.
- **Complexity:** SMALL — one additional store read plus a status check, in the one function
  (`_apply_execution_result`) and its `pause()` sibling.
- **Effect on existing architecture:** minimal; `ResearchWorkflow`/`WorkflowStatus`/`assert_transition` are reused
  as-is. Does not require adding a lock, token, or new field.
- **Testability:** straightforward — the exact harness in §2 can be adapted to assert the final store status
  stays `CANCELLED` instead of being overwritten.
- **Compatibility:** no wire-format or API change; purely an internal correctness fix.
- **Failure modes:** without additional synchronization (Option D), there is a **residual, narrower race**:
  between "re-fetch current status" and "write the terminal result," another `cancel()` could still interleave.
  In the current single-`RLock`-per-call store, this residual window is small (milliseconds) but not zero, and a
  determined enough test (or an unlucky production timing) could still hit it. **Option A alone is an
  improvement, not a complete fix.**

### Option B — Actual task cancellation (cancel the underlying execution)
Wire a real workflow_id → `ExecutionControl` registry (e.g., held by `ManageResearchWorkflow` or the store) so
`cancel()` can call `.cancel()` on the `ExecutionControl` a concurrently-running `execute()` is actually checking,
closing the §3.1 gap.

- **Correctness:** improves *responsiveness* of cancellation (the loop notices sooner, at the next round
  boundary) but, per `ExecutionControl`'s own documented limitation, **does not interrupt an in-flight capability
  call** — so it cannot, by itself, prevent the exact race reproduced in §2 (which blocks *inside* a capability
  call, the one place this mechanism explicitly cannot reach). It reduces how often the race window is entered,
  but does not close it.
- **Concurrency behavior:** requires the registry itself to be thread-safe (a dict keyed by workflow_id, mutated
  from both `execute()` — to register/unregister — and `cancel()` — to look up and signal — needs its own lock or
  a concurrent-safe structure); introduces a new shared-mutable-state surface that does not exist today.
- **Complexity:** MEDIUM — new registry, lifecycle management (register on execute start, unregister on
  execute end/exception, handle the case where `cancel()` runs before `execute()` ever registers, handle
  process-restart semantics matching the store's own "in-memory, not durable" caveat).
- **Effect on existing architecture:** touches `ManageResearchWorkflow.execute`/`.cancel`, and likely
  `AppContainer`'s composition (a new shared component). `ExecutionControl` itself needs no change.
- **Testability:** the existing `_CancelAfterN`-style pattern can be adapted, but proving the *fast* case
  (cancel lands between rounds) requires new coordination primitives distinct from what tests already do (see
  §7).
- **Compatibility:** no wire-format change; internal only.
- **Failure modes:** **does not, by itself, fix the exact bug reproduced in §2** (which is specifically an
  in-flight-capability-call scenario) — it is a genuine improvement to cancellation latency, not a substitute for
  Option A/C's commit-time safety.

### Option C — Generation/version token (worker only commits if its execution generation is still current)
Give each `execute()` invocation a generation/epoch number (e.g., increment a counter on the workflow — distinct
from `checkpoint_version`, which today is not advanced by `cancel()` and is therefore not usable as-is for this
purpose without also changing `cancel()` to advance it) at the moment it transitions to `RUNNING`. At commit time,
`_apply_execution_result` writes only if the workflow's generation in the store still matches the generation this
particular execution started with; `cancel()` (and any other terminal-status writer) also advances the
generation, so a stale worker's write is rejected by the store itself (not merely by an application-level status
check as in Option A) even in a full-concurrency scenario.

- **Correctness:** the strongest option considered — it does not depend on re-deriving "is this still the same
  logical execution attempt" from status alone (which can be ambiguous — e.g., `RUNNING → PAUSED → RUNNING` via
  resume is a legitimate same-workflow-different-attempt sequence); a monotonically-increasing generation counter
  unambiguously distinguishes "this specific execute() attempt" from any later one, including from a `resume()`
  that itself starts a fresh `RUNNING` generation.
  - **Assessment (not full analysis — flagged for the actual design task):** this looks correct against every case
    traced in this audit and against the reproduction scenario, but this pass did not attempt to construct an
    adversarial case that defeats a generation token specifically (e.g., an interleaving where two executions
    started under the very same generation, which should not be possible if `execute()` bumps the generation
    itself before releasing, but this exact ordering was not exhaustively re-verified against every call site
    such as `resume()`'s own call into `execute()`). This should be re-checked during actual design, not assumed
    complete because it "looks strongest" here.
- **Concurrency behavior:** if enforced **inside the store's existing lock** (i.e., the store itself checks and
  rejects a stale-generation write atomically with the read-modify-write it already does under its `RLock`), this
  closes the race completely, with no residual window — unlike Option A alone.
- **Complexity:** MEDIUM — requires a new field on `ResearchWorkflow` (or reuse/repurpose of
  `checkpoint_version`, which would need `cancel()`/`pause()` to also advance it, a behavior change to a field
  currently scoped to checkpoint/resume semantics, not lifecycle-race protection — conflating the two concerns
  should be considered carefully, not assumed free), plus updating every writer (`execute`, `cancel`, `pause`,
  `resume`, `approve`) to participate in the same generation discipline, plus the store's `save_workflow` guard
  logic.
- **Effect on existing architecture:** the most structurally invasive of the single-mechanism options — touches
  the aggregate's field set (or repurposes an existing field with a semantic change) and every writer.
- **Testability:** very testable — a stale-generation write is a simple, deterministic assertion (attempt to save
  a workflow object built from an old generation; expect rejection), no timing/threading needed for that part of
  the test (though the end-to-end race reproduction still benefits from a threaded test, see §7).
- **Compatibility:** internal only; if a new field is added to `ResearchWorkflow.to_dict()`'s output it would be
  a wire-format-adjacent addition (the workflow JSON response) — additive, not breaking, but worth flagging
  explicitly rather than assuming zero API surface impact.
- **Failure modes:** if generation is not bumped at every relevant transition (easy to miss one call site), the
  protection silently degrades back to today's behavior for whichever site was missed — this option's safety is
  only as strong as its discipline across all five lifecycle methods, which raises its practical risk of
  incomplete implementation despite being conceptually the strongest guarantee.

### Option D — Lock-based synchronization (protect the lifecycle transition and result commit)
Introduce a per-workflow (or, more coarsely, a single global) lock at the **application layer**
(`ManageResearchWorkflow`) that is held across the read-check-write sequence for whichever operation is mutating
lifecycle status, so `cancel()` cannot interleave with `execute()`'s final commit at all.

- **Correctness:** correct **only if the lock scope actually covers the entire race window**, which for
  `execute()` includes the *entire capability-call duration* — meaning a coarse "hold the lock for the whole
  `execute()` call" approach would serialize `cancel()` behind the full running execution, **defeating the
  purpose of cancellation** (a caller could never cancel a workflow until it finished on its own, which is exactly
  the failure mode cancellation exists to prevent). A *fine-grained* lock (held only around the final
  check-then-write, not the whole execution) is really Option A's fix made atomic, not a distinct approach.
- **Concurrency behavior:** a coarse lock would serialize all lifecycle operations per workflow, which is simple
  but removes the ability to cancel a genuinely long-running execution promptly — directly undermining this
  task's goal. A per-workflow lock scoped only to the commit step (not the execution) avoids this but is then
  materially the same shape as "Option A, made atomic" rather than a fully independent option.
- **Complexity:** SMALL (coarse, wrong-scope version) to MEDIUM (correctly-scoped version, which starts to
  resemble A+D combined).
- **Effect on existing architecture:** adds a new lock at the application layer, which does not exist today
  (only the store has one, and at the wrong granularity per §3.2) — a genuinely new primitive for this layer.
- **Testability:** a coarse lock is trivially testable (and trivially seen to break cancellation responsiveness —
  a test could show `cancel()` blocking for the full execution duration, which is itself a regression worth
  catching). A correctly-scoped lock's tests look like Option A's.
- **Compatibility:** internal only.
- **Failure modes:** the main risk with this option is choosing the wrong scope (too coarse defeats
  cancellation's purpose; too fine and it degenerates into Option A). Locking alone, at any scope, does **not**
  address §3.1 (a stale worker inside a capability call still doesn't know it should stop) — it only prevents an
  *incorrect commit*, same ceiling as Option A.

### Option E — Combination
Given the two independent root causes identified in §3, **no single option above fully closes both**:
- Option A (or D, correctly scoped) closes §3.2 (stale commit) but not §3.1 (cancellation still can't interrupt
  an in-flight capability call, so a cancelled workflow still runs to completion before its result is discarded —
  wasteful, though no longer *incorrect*).
- Option B closes part of §3.1 (faster notice between rounds) but not the in-flight-call gap, and not §3.2 at all
  on its own.
- Option C, correctly and completely implemented across every writer, is the only single option that could close
  §3.2 with no residual window, but does nothing for §3.1's responsiveness problem (a stale worker would still run
  to completion before being told, via the generation check, that its result must be discarded — same "wasteful
  but no longer incorrect" outcome as A/D).

**A combination is therefore required to satisfy both "the recorded outcome is never wrong" and "cancellation is
reasonably prompt":** at minimum, a commit-time safety net (A and/or C) is **mandatory** to eliminate the
incorrect-overwrite defect this task exists to fix; a live-signal improvement (B) is a **valuable but separable**
responsiveness improvement that does not, by itself, satisfy the core invariant and should not be substituted for
A/C. This is elaborated as a concrete recommendation in §8.

---

## 6. Existing Tests — What They Actually Prove, and What They Don't

| Test | File | What it actually proves | What race scenario it does NOT cover |
|---|---|---|---|
| `test_pause_resume_preserves_identity_evidence_attempts` | `tests/unit/test_research_workflows.py:306` | Using `_CancelAfterN` (which calls `control.request_pause()`, **not** `.cancel()`), a single-threaded, fully deterministic sequence: execute one task, pause, resume, complete. Proves checkpoint/resume plumbing preserves identity, evidence counts, and attempt counts correctly across a pause/resume cycle. | No concurrency at all — everything happens sequentially on one thread, driven by the *same* `ExecutionControl` the execution itself is checking (passed in directly by the test, which is not how the real HTTP layer calls `execute()`). Does not touch `cancel()`, does not touch two independent store reads racing each other, does not touch the stale-snapshot commit path at all. |
| `test_wrong_exchange_resolution_blocked`, `test_approval_gate_approve_and_reject`, `test_apple_nasdaq_market_workflow_golden`, etc. (same file) | `tests/unit/test_research_workflows.py` | Various single-threaded lifecycle correctness properties (approval gating, resolution blocking, golden-path completion, re-execution of a terminal workflow is rejected). | None involve two concurrent callers; none involve `cancel()` racing anything. |
| Any test asserting `assert_transition` rejects `CANCELLED → X` directly (if one exists — not found by name in this pass; `test_allowed_and_forbidden_transitions` in `test_research_workflows.py:85` was found by name but its exact assertions were not re-read line-by-line in this pass) | `tests/unit/test_research_workflows.py:85` (`WorkflowLifecycleTests`) | Presumably proves the **transition table itself** is correct in isolation (i.e., calling `assert_transition(CANCELLED, COMPLETED)` directly raises). **Flagged UNVERIFIED — full test body not re-read this pass**, but even if it asserts exactly this, per §4.2 it would still **not** prove race safety, since the actual bug never calls `assert_transition` with `CANCELLED` as the current argument — it calls it with a stale `RUNNING`. | Cannot cover the race by construction, regardless of what it asserts, because the vulnerable code path never exercises `assert_transition(CANCELLED, ...)` at all. |
| **No test anywhere uses `threading.Thread`/`threading.Event` in `test_research_workflows.py`** (confirmed by grep across the whole `tests/unit/` directory — only two unrelated files, for market/financial infra, use threading primitives at all) | — | **Nothing.** | The entire race class (§1–§3) is completely unexercised by the existing suite. A fully green `test_research_workflows.py` (and it is fully green — reconfirmed as part of today's 748-passing baseline) provides **zero evidence** of race safety, only of correct single-threaded, sequential lifecycle behavior. |

**Direct answer to "do not assume a passing cancellation test proves race safety": confirmed, it does not.**
Every existing lifecycle/cancellation-adjacent test in this codebase is single-threaded and deterministic by
construction (using `_CancelAfterN` or direct method calls in sequence); none of them can, even in principle,
observe the interleaving this audit reproduced in §2, because none of them run two operations concurrently
against the same workflow.

---

## 7. Regression-Test Design (specification only, not implemented)

All ten scenarios below are designed to avoid timing-based `sleep()` calls, using the same
event/barrier-based determinism technique validated in §2's reproduction. General pattern: wrap the injected
capability executor so it blocks on a `threading.Event` inside `execute_task`, and signals a second
`threading.Event` the instant it starts — the test thread waits on the *start* event (not a fixed sleep) before
acting, and controls exactly when the blocked call is allowed to proceed via the *release* event. This makes every
scenario deterministic regardless of machine speed.

1. **Cancel while execution is running** (the exact scenario reproduced in §2): background thread calls
   `execute()`; main thread waits for the start-event, calls `cancel()`, asserts `cancel()` reports success and
   the store immediately shows `CANCELLED`; then releases the block and asserts the **final** stored status
   remains `CANCELLED` (post-fix — today it does not, per §2).
2. **Cancel immediately before completion**: use a capability executor stub with **N** tasks where the block is
   placed on the *last* task rather than the first, so cancellation races the tail end of a nearly-finished
   execution rather than the beginning — proves the fix isn't accidentally relying on "cancel always happens
   early."
3. **Cancellation followed by worker completion**: identical to #1 but the released execution's remaining tasks
   all succeed (`COMPLETED` outcome, not `PARTIAL`) — proves the fix applies to the `COMPLETED` overwrite case,
   not just `PARTIAL` (the one this pass's reproduction happened to produce).
4. **Cancellation followed by worker failure**: the released execution's remaining task(s) fail
   (`ResearchExecutionStatus.FAILED`/`BUDGET_EXCEEDED`) — proves a stale *failure* commit is blocked exactly like
   a stale *success* commit; failure and success paths share the same `_apply_execution_result` code, but should
   both be asserted explicitly, not assumed symmetric.
5. **Repeated cancellation**: call `cancel()` twice in immediate succession (no concurrency needed) — assert the
   second call returns `CONFLICT` (`is_terminal` already true) and does not raise or corrupt state; a pure
   regression guard for existing, already-correct behavior (`is_terminal` check at the top of `cancel()`), to be
   preserved by whatever fix is chosen.
6. **Cancel after completion**: let `execute()` run to a genuine, uncontested `COMPLETED` finish; then call
   `cancel()`; assert `CONFLICT` (existing, already-correct `is_terminal` guard) and that the stored status
   remains `COMPLETED`, unchanged.
7. **Cancel after failure**: same as #6 with a `FAILED` terminal outcome instead of `COMPLETED`.
8. **Concurrent cancel requests**: two threads both call `cancel()` on the same `RUNNING` workflow at
   (deterministically-forced) the same moment, using a barrier so both requests reach the store read at the same
   instant; assert exactly one succeeds with `OK`/`CANCELLED` and the other observes either `CONFLICT` (if it
   loses the race after the first one's write lands) — the store's existing identity/version checks in
   `save_workflow` should already make this safe today (this is a **regression guard for existing correct
   behavior**, not a new gap — worth confirming explicitly rather than assumed).
9. **Stale worker/result attempting to commit** (the core invariant test, generalized beyond #1): construct a
   scenario with **two full `execute()` invocations** against the same workflow — e.g., a first `execute()` call
   that gets blocked, a `pause()` that "wins" and completes first establishing a new baseline, and then the first,
   stale `execute()`'s block is released — assert the stale execution's attempted commit is rejected/discarded,
   not just for the `cancel()` case but for any terminal-or-non-terminal status change that happened while it was
   stuck. This is the most general form of the invariant and should be the primary acceptance test for whichever
   fix is chosen (Option A/C/E).
10. **Normal completion remains unaffected**: no concurrency at all — a plain, uncontested `execute()` call runs
    to `COMPLETED`/`PARTIAL`/`FAILED` exactly as today; this is the existing golden-path test suite
    (`test_apple_nasdaq_market_workflow_golden` et al.) re-run unchanged as the compatibility gate — the fix must
    not alter any of these tests' outcomes, since they represent zero concurrent contention and should be
    completely untouched by whichever option is chosen.

All ten should be added as new tests (not retrofits of existing ones), living alongside
`tests/unit/test_research_workflows.py` in a new, clearly-named file (e.g.
`test_workflow_cancellation_race.py`, matching this repo's convention of dedicated hardening files per concern),
so the existing, still-valid single-threaded lifecycle tests are not disturbed.

---

## 8. Recommended Remediation

**Required invariant, restated precisely (the task's proposed wording is checked against the trace above and
found to need one clarification):**

> Once a workflow has been recorded as `CANCELLED` (or, by the same mechanism, `PAUSED`, `COMPLETED`, `PARTIAL`,
> or `FAILED` — i.e., **any** status transition that actually lands in the store, not only `CANCELLED`), no
> execution attempt that began before that transition was recorded may subsequently overwrite the store with a
> result computed without knowledge of it.

The task's proposed invariant ("Once cancelled, no stale execution may transition it to a terminal
success/failure state or commit stale execution results") is **correct as far as it goes, and is the primary case
this task exists to fix**, but per §4.3, the identical mechanism also threatens the `PAUSED` case (a stale
execution overwriting a concurrently-recorded pause) — the precise, general invariant should cover **any**
lifecycle writer racing **any** other, not `CANCELLED` alone, since the underlying defect (stale-snapshot commit,
§3.2) is not specific to cancellation; cancellation is simply the case this audit was tasked with and the one
empirically reproduced.

**Recommended smallest architecture-consistent fix: Option A (re-fetch-and-check immediately before commit),
made atomic by extending the existing store-level lock's effective scope to cover the check — i.e., a combination
closest to "A tightened by D applied narrowly," not full Option C.**

Reasoning:
- Option C (generation token) is the most theoretically complete single mechanism, but per its own complexity
  note, correctly threading a new generation concept through all five lifecycle-writing methods
  (`execute`/`pause`/`resume`/`cancel`/`approve`) is the largest, most architecture-touching change of the
  options considered, and carries the highest risk of an incomplete rollout silently leaving one writer
  unprotected (§5, Option C, Failure modes). It should remain on the table as a **future hardening step**, not the
  first fix.
- Option A, made atomic by having the **store itself** (not the application layer) perform the "is my
  status-transition still valid against what you currently hold" check inside the same lock acquisition it
  already uses for `save_workflow`'s existing identity/version checks, closes the exact defect reproduced in §2
  with the smallest possible change: it teaches `InMemoryResearchWorkflowStore.save_workflow` to also validate
  `assert_transition(existing.status, incoming.status)` — using the **store's own currently-held record** as the
  "current" argument, not the caller's stale parameter — before accepting a write. This requires no new field, no
  new registry, and no change to `ResearchWorkflow`'s shape or `WorkflowStatus`'s transition table; it only moves
  the *point at which* the already-correct `assert_transition` logic is evaluated, from "inside the caller's stale
  object, before the long-running work" to "inside the store, atomically with the write, using the record the
  store actually holds right now."
- This directly and completely closes §3.2 (the store will now itself reject a `RUNNING → COMPLETED` write if it
  currently holds `CANCELLED`, because it will correctly evaluate the transition as `CANCELLED → COMPLETED`,
  which `_ALLOWED` already says is invalid) with no residual window, because the check and the write happen under
  the same lock acquisition the store already takes.
- It does **not** close §3.1 (cancellation still cannot interrupt an in-flight capability call, so a cancelled
  workflow's stale execution still runs to completion before its result is discarded) — this is an accepted,
  explicitly-flagged limitation of the recommended minimal fix, not an oversight: **Option B (live signal
  wiring) is recommended as a valuable, separately-scoped follow-up** to reduce wasted work and improve perceived
  responsiveness, but is not required to satisfy the core correctness invariant, which the store-level guard
  alone fully satisfies.
- `ManageResearchWorkflow._apply_execution_result` and `.pause()` would need a small change to **handle the new
  rejection gracefully** (catch the store's new rejection and return a `CONFLICT`-shaped `WorkflowOperationResult`
  instead of letting an exception escape to the API layer as an unhandled 500) — this is the one required
  application-layer change alongside the store-level fix, and is itself small.

---

## 9. Definition of Done (F03, acceptance criteria — not implemented yet)

- **Lifecycle correctness:** `InMemoryResearchWorkflowStore.save_workflow` rejects any incoming write whose
  status-transition, evaluated against the record the store **currently holds** (not the caller's parameter),
  would be invalid per `_ALLOWED` — verified by a store-level unit test that attempts exactly this
  (construct a stored `CANCELLED` record, then attempt to save an incoming `COMPLETED` record built from a stale
  pre-cancel snapshot; expect rejection, not silent acceptance).
- **Concurrency correctness:** the §2 reproduction harness (adapted into a permanent, deterministic,
  event/barrier-based regression test per §7 item 1 and item 9), re-run against the fixed code, must show the
  **final** stored status as `CANCELLED`, not `PARTIAL`/`COMPLETED`/`FAILED` — the exact scenario this audit
  demonstrated must be closed, not merely narrowed.
- **Regression tests:** all ten scenarios in §7 implemented and passing, including the "normal completion remains
  unaffected" compatibility gate (§7 item 10) and the "repeated/after-terminal cancel" guards (§7 items 5–7,
  6) which pin down already-correct behavior that must not regress.
- **API behavior:** `POST /research/workflows/{id}/execute` must not return an unhandled 500 when its underlying
  commit is rejected by the new store-level guard; it must return a `WorkflowOperationResult`
  (`WorkflowOperationStatus.CONFLICT` or equivalent) whose message clearly states the workflow was cancelled (or
  otherwise transitioned) concurrently and the execution's result was discarded — this is a new, explicit
  behavior that must be tested at the API layer (`TestClient`-based test), not only at the application layer.
- **Full-suite compatibility:** the entire existing 748-test suite must continue to pass unchanged, plus `ruff
  check`, `ruff format --check`, and `mypy --strict` must remain clean, matching the standard already established
  in the F01/F02 work — no existing test's expected outcome may be weakened or deleted to accommodate this fix.
- **Explicitly out of scope for "done" on this specific finding** (tracked as a recommended, separately-approved
  follow-up per §8): wiring a live `ExecutionControl` signal path from `cancel()` to a running `execute()`
  (Option B); a full generation/version-token redesign across all five lifecycle writers (Option C). Neither is
  required to satisfy the invariant in §8, and bundling either into this fix would exceed "the smallest
  architecture-consistent fix."

---

## Summary Answers

- **§1:** full lifecycle traced across `status.py`, `model.py`, `manage_research_workflow.py`,
  `execution_control.py`, `execute_research_plan.py`, `in_memory_store.py`, and `api/routes/workflows.py`; the
  concurrency model is real OS threads (FastAPI's thread pool for sync `def` routes), not asyncio.
- **§2:** the race was **empirically reproduced** by running a non-destructive harness against the actual,
  unmodified code — final stored status was `partial` after a workflow had been truthfully reported as
  `cancelled` moments earlier.
- **§3:** root cause is **two independent, compounding gaps** — no live cancellation-signal path reaches a
  running execution in production (missing task cancellation), and no version/generation check protects the
  final commit from a stale worker (missing generation/version token). A pre-existing lock exists but at the
  wrong granularity to help. The state-transition guard itself is correct but is evaluated against stale data.
- **§4:** the transition table itself has no invalid entries; `CANCELLED → COMPLETED` is correctly rejected
  whenever actually checked — the bug produces the equivalent outcome by never performing that specific check
  against real data. The same mechanism can also let a stale execution overwrite a concurrently-recorded
  `PAUSED` state (not empirically reproduced this pass, statically derived).
- **§5:** four options plus a required combination compared without scoring; no single option (A, B, C, or D
  alone) fully satisfies both correctness and responsiveness.
- **§6:** every existing cancellation/lifecycle test is single-threaded and deterministic by construction; none
  can observe this race, so a fully-green existing suite provides no evidence of race safety.
- **§7:** ten deterministic, event/barrier-based (no `sleep`) regression tests specified, none implemented.
- **§8:** recommended fix is a store-level, atomic re-validation of the status transition against the store's
  own currently-held record (a tightened Option A), which fully closes the reproduced defect with the smallest
  architectural footprint; live-signal wiring (Option B) and a full generation-token redesign (Option C) are
  flagged as valuable, separately-scoped follow-ups, not required for this fix. The stated invariant is corrected
  to cover any lifecycle writer, not only cancellation.
- **§9:** explicit, objective acceptance criteria defined, covering lifecycle correctness, concurrency
  correctness, all ten regression tests, new API-level conflict-handling behavior, and full-suite compatibility.

**No code was modified in the production of this plan. Awaiting approval before any implementation. Not
proceeding to F04.**
