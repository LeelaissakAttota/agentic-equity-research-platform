# F04 — Exception Message Leakage: Audit and Remediation Plan

**Status:** AUDIT ONLY — no source code modified, no dependency added, no commit, no push, no branch change.
**Verified against:** HEAD `d983bce`, branch `main`, working tree in the expected post-F03 state (764/764 passing,
confirmed before this audit began). `capability_executor.py` (the file this finding centers on) is confirmed
**unmodified** by F01/F02/F03 — it does not appear in any of those tasks' `git diff` output.
**Method:** every claim below is backed by a direct file/line read performed in this pass (not carried unread from
the original `PRODUCT_AUDIT_2026-09-15.md`), plus a **live, empirical reproduction** against the current,
unmodified code using a non-destructive `TestClient`-based harness kept outside the repository (this session's
scratchpad directory — never committed, never added to `tests/`).

---

## 1. Finding Status

**CONFIRMED.**

A deliberately-injected internal exception, raised inside a capability adapter, reaches the client verbatim —
including a synthetic internal hostname and filesystem path used as stand-ins for real sensitive values — in the
JSON body of a normal `HTTP 200 OK` response from `POST /research/execute`. This was reproduced by direct
execution against the current code, not inferred.

---

## 2. Severity Assessment

**HIGH — confirmed, not downgraded from the original audit.** Reasoning:
- The leak is **deterministic**, not merely possible-under-unusual-conditions: any exception raised inside a
  capability adapter's `.execute(...)` call (market, financial, news, industry, regulatory, or company
  resolution) is guaranteed to have its `str(exc)` embedded in the response, every time, by construction of the
  `except Exception as exc:` block — there is no code path in which this particular exception type is instead
  suppressed, generalized, or logged-only.
- The response is `HTTP 200 OK`, not a 4xx/5xx — a client, monitoring system, or log aggregator that only inspects
  status codes for anomalies would not flag this as an error response at all, making the leak easy to miss in
  normal operation.
- The content is unbounded in *kind* (bounded only in *length*, to 1000 characters, by
  `TaskExecutionResult.__post_init__`) — whatever an underlying adapter's exception message happens to contain
  (a connection string, a file path, a provider's internal hostname, a stack-adjacent repr) passes through
  untouched.
- Severity is **not** escalated to CRITICAL because: (a) this pass found no live adapter today whose exceptions
  are known to carry actual credentials or secrets (the fixture/reference-dataset-backed adapters raise only
  domain-level, already-safe `ValueError`s in normal operation — see §5); (b) the two adapters with genuine
  external I/O (`sec_company_facts.py`'s SEC EDGAR client, the Yahoo chart adapter) are both off by default in
  this deployment and use a bounded HTTP client (per prior audit passes); realistic exception content from them
  would more likely be network/timeout text than credentials. The severity is HIGH because the *mechanism* is a
  real, deterministic, unbounded-content disclosure path with no current guardrail — not because a specific
  secret has been proven reachable through it today.

---

## 3. Exact Root Cause

**File:** `src/financial_intelligence/infrastructure/orchestration/capability_executor.py`
**Function:** `Phase6CapabilityExecutor.execute_task` (the outer try/except; `_dispatch` is the inner method it
wraps)
**Exact code (confirmed present, unchanged, in the current working tree):**
```python
def execute_task(
    self,
    task: ResearchTask,
    *,
    company: CompanyIdentity,
    company_query: CompanyQuery,
) -> TaskExecutionResult:
    try:
        return self._dispatch(task, company=company, company_query=company_query)
    except Exception as exc:
        return TaskExecutionResult(
            task_id=task.task_id,
            status=TaskResultStatus.FAILED,
            message=f"capability executor exception: {exc.__class__.__name__}: {exc}",
            retryable=True,
            error_code="executor_exception",
        )
```
`{exc}` interpolates `str(exc)` — the full exception message, with no allowlist, redaction, or content
inspection of any kind. The only bound applied anywhere downstream is a **length** cap (1000 characters,
`TaskExecutionResult.__post_init__`, `domain/orchestration/results.py:75-78`) — this truncates long content, it
does not sanitize sensitive content.

**Exact propagation path (confirmed by reading, then by execution):**
```
Phase6CapabilityExecutor.execute_task          (message constructed here)
  -> TaskExecutionResult.message                 (domain/orchestration/results.py)
  -> ExecuteResearchPlan.execute_prepared        (application/execute_research_plan.py -- appends to state.results)
  -> ResearchExecutionResult.task_results        (application/research_execution_contracts.py)
  -> ResearchExecutionResult.to_dict()           ("task_results": [r.to_dict() for r in self.task_results])
       -- this ALSO appears a second time, nested inside "orchestration": {"results": [...]}, since the
          orchestration state's own results list is separately serialized in the same to_dict() call
  -> api/routes/research.py: execute_research_plan()
       result = container.execute_research_plan.execute(exec_query)
       return ResearchExecutionResponse.model_validate(result.to_dict())
  -> HTTP 200 OK response body
```

---

## 4. Reproduction Evidence

**Harness:** a `TestClient`-driven script, built the same way this repo's own tests inject fakes (matching the
pattern in `tests/unit/test_research_workflows.py`'s `container.execute_research_plan._executor` substitution),
kept outside the repository. It replaces the **inner** `GetMarketSnapshot` dependency the real
`Phase6CapabilityExecutor` delegates to (not the executor itself, which would bypass the very code path under
test) with a stub that raises:
```python
raise RuntimeError(
    "AUDIT_MARKER: connection failed to internal-db-host.corp.local:5432 "
    "at /var/app/secrets/db.conf"
)
```
No real secret, credential, or production hostname was used — this is a synthetic stand-in chosen to be
unambiguously identifiable in the response if the leak occurs, per the task's "do not use real secrets"
instruction.

**Result of `POST /research/execute` with `{"q": "Apple", "exchange": "NASDAQ", "objective": "market_analysis"}`:**
```
STATUS: 200
BODY CONTAINS MARKER: True
BODY CONTAINS PATH: True   (/var/app/secrets/db.conf)
BODY CONTAINS HOST: True   (internal-db-host.corp.local)
```
Relevant excerpt of the actual response body (verbatim, from the real run):
```json
"task_results":[{
  "task_id":"3acb9291-60a2-4ffd-ae81-7fcdb8b7dbcd",
  "status":"failed",
  "message":"capability executor exception: RuntimeError: AUDIT_MARKER: connection failed to internal-db-host.corp.local:5432 at /var/app/secrets/db.conf",
  "evidence_refs":[],
  "output_summary":null,
  "retryable":true,
  "error_code":"executor_exception",
  "kind":"task_execution_result"
}]
```
The identical string also appears a second time, nested under `"orchestration":{"results":[...]}`, in the same
response body — the leak is duplicated within a single response, not merely present once.

**Response headers** (checked per the task's instruction): clean.
```
{'content-length': '4749', 'content-type': 'application/json', 'x-content-type-options': 'nosniff',
 'x-frame-options': 'DENY', 'referrer-policy': 'no-referrer', 'cache-control': 'no-store',
 'x-correlation-id': '...'}
```
No exception content, path, or hostname appears in any header — **the leak is confined to the response body.**

**Control case — the workflow-managed path is NOT affected by this specific leak.** The identical fault was
injected and exercised through `POST /research/workflows/{id}/execute` instead:
```
EXECUTE STATUS: 200
BODY CONTAINS MARKER: False
```
Confirmed by reading `ResearchWorkflow.to_dict()` (`domain/workflow/model.py:153-191`): it hand-constructs its
`latest_checkpoint` summary from a fixed, explicit field list (`completed_task_ids`, `pending_task_ids`,
`failed_task_ids`, `blocked_task_ids`, `total_attempts`, `external_calls`, and the **checkpoint's own** `message`
field — which is a separately-authored, safe string like `"one or more required tasks failed"`, not any
individual task's `message`). `WorkflowCheckpoint.task_results` (which does carry the unsafe per-task messages,
`checkpoint.py:91`) is **never included** in `ResearchWorkflow.to_dict()`'s output. This is not a deliberate fix
for F04 — it is incidental to how the workflow summary was designed — but it means **the workflow-managed
endpoints are not currently exploitable through this exact path**, confirmed by execution, not assumed.

---

## 5. Affected Endpoints / Code Paths

| Endpoint | Affected? | Evidence |
|---|---|---|
| `POST /research/execute` | **YES — confirmed by reproduction** | `ResearchExecutionResponse.model_validate(result.to_dict())` includes `task_results` and nested `orchestration.results` verbatim (`api/routes/research.py:251`) |
| `POST /research/workflows/{id}/execute` | **NO — confirmed by reproduction** | `ResearchWorkflow.to_dict()` never serializes `task_results` (see §4) |
| `GET /research/workflows/{id}` | **NO** | Same `ResearchWorkflow.to_dict()` path, same reasoning |
| `POST /research/plans` (create-only, no execution) | **Not applicable** | No task execution occurs; plan creation does not invoke `Phase6CapabilityExecutor` |
| `POST /research/synthesis` | **Not applicable** | Synthesis takes caller-supplied claims/evidence directly (already covered by F01/F02); does not invoke `Phase6CapabilityExecutor` |
| Any other route in `api/routes/*.py` | **Reviewed, not affected by this mechanism** | See §9 — every other `str(exc)`/`f"...{exc}"` occurrence in the codebase was individually inspected (11 sites outside `capability_executor.py`) and found to catch narrow, deliberately-raised domain `ValueError`s with bounded, safe, already-part-of-the-contract messages, not broad `Exception` from external/unexpected sources |

---

## 6. Current vs. Expected Behavior

| | Current | Expected |
|---|---|---|
| Client-facing `task_results[].message` on an unexpected capability failure | Raw `f"capability executor exception: {type}: {exc}"` — unbounded content, bounded only in length | A stable, generic, safe message (e.g. `"capability execution failed"`) plus the already-present `error_code="executor_exception"` and `retryable` flag, which are sufficient for a client to act on (retry, surface a generic error) without needing the raw exception text |
| Server-side log of the same failure | **Nothing.** `capability_executor.py` contains zero logging calls — confirmed by direct grep; the exception's content exists *only* inside the value that gets returned to the caller | The exception's full detail (type, message, and ideally a correlation ID) should be logged server-side at `ERROR` level so operators retain diagnostic visibility that is currently available *only* by way of the leak this finding flags for removal |
| Response headers | Clean, no leakage found | Unchanged — no fix needed here |

**Important secondary observation, directly relevant to the audit's explicit instruction to check that diagnostic
information remains available server-side:** it currently does **not**. Removing the leaked detail from the
client response without also adding a log statement would not just close the leak — it would **delete the only
place this diagnostic information exists today**, since nothing logs it currently. Any remediation must add
logging, not merely redact the response (see §8/§9).

A related, narrower observation on the **global** unhandled-exception handler (`api/errors.py`,
`unhandled_exception_handler`) — this handler is already safe (logs only `error_type`, never `str(exc)` or a
traceback) but shares the same "no message/traceback captured server-side" characteristic. This is **not** a
leakage risk (the client never sees it either) — it is a separate, smaller observability gap, noted here for
completeness per the audit's logging-inspection instruction, but it is **not part of the F04 finding** (F04 is
about client-facing leakage) and is flagged only as an optional, out-of-scope-for-this-fix improvement.

---

## 7. Existing Test Coverage and Gaps

**Coverage found:** `tests/unit/test_research_execution.py` contains multiple tests exercising `FAILED`
`TaskExecutionResult`s with `error_code="executor_exception"` (e.g. around lines 423-440, 480-497, 536-553) —
confirmed by direct read. **Every one of these constructs the `TaskExecutionResult` by hand**, with a
pre-authored, already-safe `message` (`"transient"`, `"still broken"`, etc.), via a test-only `_ScriptedExecutor`
stand-in. **None of them exercises the real `Phase6CapabilityExecutor.execute_task`'s except-block** — they test
retry/budget/exhaustion behavior around already-FAILED results, not how a FAILED result's message is
*constructed* from a real exception.

**Gap, confirmed by search:** no test anywhere in `tests/unit/` constructs a real exception and asserts on what
ends up in `TaskExecutionResult.message` or in an HTTP response body. `grep` for
`Phase6CapabilityExecutor`/`executor_exception` across all test files returns only the three files already
reviewed in this pass, none of which cover this. **This finding has zero existing regression coverage** — a
fully-green test suite (764/764, confirmed at the top of this audit) provides no evidence against this
vulnerability, for the same reason a green suite provided no evidence against F03's race before that fix.

---

## 8. Remediation Options (comparison only, nothing implemented)

### A. Centralized exception sanitization (a shared "safe-message" helper)
Introduce one small function (e.g. `_safe_capability_failure_message(exc: Exception) -> str`) that
`capability_executor.py` calls instead of interpolating `{exc}` directly, returning a fixed, generic string
(optionally varying by `exc.__class__.__name__` if that alone is judged safe — see §9 for why the class name
itself is safe, unlike the message).
- **Correctness:** directly closes the confirmed leak at its exact source.
- **Complexity:** SMALL — one function, one call-site change.
- **Effect on architecture:** none; purely local to the one file already responsible for this boundary.
- **Testability:** straightforward — inject a real exception, assert the message is the fixed safe string, assert
  the original exception text does not appear anywhere in the result.
- **Compatibility:** the `message` field's *content* changes for the failure case; its *presence*, type, and the
  `error_code`/`retryable` fields do not. No schema change.

### B. Typed/public application errors (a dedicated exception taxonomy for capability failures)
Define a small set of typed exceptions (e.g. `CapabilityUnavailableError`, `CapabilityTimeoutError`) that
adapters are expected to raise instead of letting arbitrary exceptions propagate, and have
`Phase6CapabilityExecutor` map each known type to its own safe, specific message, falling back to a generic
message for anything unrecognized.
- **Correctness:** closes the leak and additionally gives clients more specific, still-safe signal (e.g.
  distinguishing "timeout" from "unavailable").
- **Complexity:** MEDIUM–LARGE — requires every adapter (`GetMarketSnapshot`, `GetFinancialSnapshot`, etc.,
  and any live provider adapters like the SEC/Yahoo clients) to be audited and updated to raise the new typed
  errors instead of letting arbitrary library exceptions escape, which is a much larger surface than this one
  file.
- **Effect on architecture:** the most invasive option — introduces a new error taxonomy that every current and
  future capability adapter must adopt to get its full benefit; adapters that don't adopt it fall back to the
  same generic path as Option A anyway.
- **Testability:** more test surface (one taxonomy of typed errors to test), but each individual test is simple.
- **Compatibility:** same as A for the fallback case; additive for adapters that opt in.

### C. Generic 500 response with correlation/request ID (change the HTTP-level contract)
Instead of encoding a capability failure as a `200 OK` with a `FAILED` task result, escalate it to a genuine
`HTTP 5xx` at the route level, relying on the existing global `unhandled_exception_handler` (already safe) to
produce the response, with the correlation ID as the only client-visible identifier.
- **Correctness:** would close the leak, but **changes the existing, intentional API contract** — this endpoint
  is designed to return `200 OK` with a structured per-task result set even when some tasks fail (that is the
  entire point of `TaskResultStatus.FAILED`/`PARTIAL`/`BLOCKED` existing as first-class, expected outcomes,
  confirmed throughout `execute_research_plan.py`'s design and its own tests). Converting a single capability's
  unexpected failure into a full-request 500 would be a regression in API design, not a fix — it would make a
  partial, still-useful result (other tasks may have succeeded) look like a total request failure.
- **Assessment: rejected.** This conflates "one capability adapter had an unexpected internal error" with "the
  whole request is invalid/failed," which is not true today and should not become true as a side effect of a
  leak fix. Noted here because the task asked for a comparison, but not seriously pursued further.

### D. Exception-to-HTTP mapping (route-level translation table)
Similar in spirit to C but scoped only to genuinely-unexpected exception types, mapping them to specific HTTP
status codes at the route boundary rather than inside the capability executor.
- **Correctness:** does not fit this specific defect well — the exception is already caught and converted
  *inside* the capability executor, several layers below the route handler; by the time execution reaches
  `api/routes/research.py`, there is no exception left to map — only a `ResearchExecutionResult` with a `FAILED`
  task result already embedded in it. Implementing this option would require *removing* the existing
  try/except in `capability_executor.py` so the exception propagates further, which would itself be a larger,
  riskier change (affecting retry/budget logic that currently depends on receiving a `TaskExecutionResult` back,
  not an exception) than fixing the message at its current, correct catch point.
- **Assessment: not a good fit for this defect's actual location.**

### E. Logging internal exception details while returning safe public messages (paired with A)
Not a standalone alternative — this is the necessary complement to Option A (or B), per §6's finding that nothing
currently logs this information server-side at all. Add a single `logger.error(...)` call (or equivalent) inside
`capability_executor.py`'s except block, logging `exc.__class__.__name__` and the full `str(exc)` (server-side
only, using this repo's existing structured-logging convention, e.g. `get_logger(...)` + `extra={...}`, matching
the pattern already used in `api/errors.py`), immediately before constructing the now-sanitized
`TaskExecutionResult`.
- **Correctness:** restores the diagnostic visibility that closing the leak would otherwise remove entirely.
- **Complexity:** SMALL — one logger call.
- **Effect on architecture:** none; this repo's logging pattern (`observability.logging.get_logger`) is already
  used pervasively and is the established convention (confirmed in `api/errors.py`, `manage_research_workflow.py`,
  and others read across this and prior audits).
- **Testability:** can assert (via a caplog-style test, matching this repo's existing logging tests such as
  `test_logging_safety.py`) that the log record contains the exception detail while the returned
  `TaskExecutionResult.message` does not.

### F. Endpoint-specific handling
Considered and rejected as a *primary* fix: the defect is not endpoint-specific (it is in the shared
`Phase6CapabilityExecutor`, used by every task-executing path, including the currently-unaffected workflow path
— see §5's "not affected... incidentally" caveat: a future change to `ResearchWorkflow.to_dict()` that started
including `task_results` would silently reopen this exact leak on the workflow path too, since the underlying
`TaskExecutionResult.message` would still be unsafe). Fixing at the shared source (Option A) protects both the
currently-affected and the currently-incidentally-safe path at once; an endpoint-specific fix would not.

---

## 9. Recommended Remediation

**Option A (centralized sanitization at the exact source, inside `capability_executor.py`) combined with Option E
(add server-side logging in the same location), and explicitly not Option B, C, D, or F as the primary
mechanism.**

Reasoning:
- This is the smallest change that closes the confirmed leak at its one confirmed source, consistent with this
  task's implicit expectation (matching the scale of the F01/F02/F03 fixes already made) of a narrow, targeted
  correction rather than a taxonomy-wide redesign.
- It protects **both** the currently-affected (`/research/execute`) and currently-incidentally-safe
  (`/research/workflows/.../execute`) paths at once, since both ultimately construct `TaskExecutionResult` through
  this one function.
- It does not change the endpoint's HTTP-level contract (still `200 OK` with structured, per-task results) —
  preserving the existing, intentional "partial failure is a normal, expected outcome" design that Option C would
  have broken.
- `error_code="executor_exception"` and `retryable=True` (both already present, both safe — they are fixed,
  finite-vocabulary fields, not free-text) are sufficient for a client to distinguish and react to this failure
  mode without needing the raw exception text; nothing about the existing *contract* requires the message to
  contain exception internals — confirmed by reading `TaskExecutionResult`'s full field set (§3) and observing
  that `error_code` already exists specifically to serve this purpose.
- Keeping `exc.__class__.__name__` in the (now server-side-only) log line, but **not** in the client-facing
  message, matches the existing precedent already set by `api/errors.py`'s `unhandled_exception_handler`, which
  already logs `error_type` (the class name) without the message — this repo's own established convention treats
  the exception *type* as safe telemetry and the exception *message* as the part requiring protection, which this
  recommendation is consistent with rather than inventing a new policy.

**What the recommended fix does NOT do (explicitly, to keep scope narrow):** it does not introduce a new
exception taxonomy (Option B), does not change any HTTP status code or the endpoint's success/failure contract
(Option C/D), and does not touch any other file's `str(exc)` usage — every other occurrence found in §9's own
census (the eleven sites listed in §5's table footnote) was individually confirmed safe and is explicitly out of
scope for this fix.

---

## 10. Deterministic Regression-Test Plan (specification only, not implemented)

Following this repo's existing conventions (`unittest.TestCase`, the `TestClient` + container-substitution pattern
already used throughout `tests/unit/test_research_workflows.py` and this audit's own reproduction harness, and the
existing `test_logging_safety.py` style for log-content assertions):

1. **Unexpected internal exception → safe response, not an error status:** inject a real exception (e.g.
   `RuntimeError` with a synthetic marker, matching this audit's reproduction) into a capability dependency;
   `POST /research/execute`; assert `response.status_code == 200` (the endpoint's existing, correct contract for
   a single-capability failure is preserved) and `task_results[0]["status"] == "failed"`.
2. **Internal exception details are absent from the response body:** same setup; assert the synthetic marker
   string does **not** appear anywhere in `response.text` (not just in the obvious `message` field — the same
   check the original reproduction used, since the content is currently duplicated into a second, nested location
   in the payload).
3. **Internal exception details are absent from relevant response headers:** assert the marker does not appear in
   any `response.headers` value (pinning down today's already-clean behavior so it cannot regress silently).
4. **Safe structured application/domain errors remain unchanged:** re-run (unchanged) a representative existing
   test that exercises a genuine, safe domain `ValueError` reaching a client (e.g. an existing test in
   `test_company_api.py`/`test_financial_api.py` asserting a validation message reaches the response) and confirm
   it still passes exactly as before — proving this fix does not over-sanitize legitimate, intentional
   validation messages.
5. **Authentication errors preserve their intended contract:** re-run (unchanged) the existing `test_auth.py`
   suite; no code touched by this fix is shared with the authentication path, so this is a pure regression check,
   not a new test.
6. **Validation errors preserve their intended contract:** same rationale — re-run existing
   `RequestValidationError`-handling tests unchanged (e.g. any existing test asserting `422` with `loc`/`msg`
   detail) as a regression check, not a new test targeting this fix.
7. **Internal details remain available in server-side logging:** using a log-capture technique consistent with
   `test_logging_safety.py`'s existing approach, assert that after the same injected exception, a log record
   exists containing the exception's class name and original message (server-side only) — proving Option E's
   complement was actually implemented, not merely that the client-side leak was closed by accident (e.g. by
   swallowing the exception silently, which would close the leak but destroy diagnostics, and which this test is
   specifically designed to catch as a wrong-shaped fix).
8. **No sensitive traceback/path/provider details reach the client, generalized beyond one exception type:**
   parametrize test #2 (or add siblings) across at least: a `ValueError` with an embedded fake path, a
   `KeyError`, and a generic `Exception` subclass with a fake internal hostname in its message — proving the fix
   sanitizes by mechanism (catching broadly and replacing unconditionally), not by pattern-matching specific
   known-bad strings, which would be fragile and incomplete.

**New test file recommendation, matching this repo's naming convention for dedicated hardening suites** (as used
for F01/F02/F03): `tests/unit/test_capability_executor_hardening.py`, kept separate from the existing
`test_research_execution.py` so the pre-existing retry/budget-focused tests in that file are not disturbed.

---

## 11. Compatibility / API-Contract Considerations

- **No wire-format/schema change.** `TaskExecutionResult`'s field set (`task_id`, `status`, `message`,
  `evidence_refs`, `output_summary`, `retryable`, `error_code`) is unchanged; only the *content* of `message` for
  the one specific failure case (an uncaught exception inside `_dispatch`) changes from unbounded exception text
  to a fixed, safe string.
- **A client that currently parses the `message` field for specific exception-derived substrings** (e.g.
  screen-scraping a provider name or error detail out of the raw text) would see different content after this
  fix. This is presumed acceptable and is the entire point of the fix — no legitimate integration should depend on
  parsing leaked internal exception text — but it is named explicitly here as a discoverable, if unlikely,
  breaking change in *behavior* (not in the *type/shape* of the response).
- **`error_code="executor_exception"` and `retryable=True` are unchanged**, preserving whatever a well-behaved
  client already does with those fields today.
- No change to any endpoint's URL, method, status code, or top-level response shape.

---

## 12. Limitations and Deferred Follow-ups

- **This audit did not exhaustively fuzz every capability adapter** (market, financial, news, industry,
  regulatory, company resolution) to find every real exception each could realistically raise in production; it
  confirmed the *mechanism* (any exception, of any content, passes through unmodified) via one representative
  injected exception. The recommended fix (sanitize unconditionally at the catch site) does not depend on
  enumerating every possible real exception, so this is not a blocking gap for the recommended remediation, but a
  future defense-in-depth review of what the two optional live adapters (SEC EDGAR, Yahoo chart) can actually
  raise in practice would still be a reasonable, separate follow-up.
- **The secondary observation in §6** (the global `unhandled_exception_handler` does not log `str(exc)` or a
  traceback either, which is safe for clients but reduces server-side debuggability for genuinely unhandled
  exceptions) is **not** part of this fix's scope and is flagged only as an optional future observability
  improvement, not a leakage risk.
- **The `KeyError`-derived message in `create_research_plan.py:110-118`** (`f"required capability unavailable:
  {exc}"`) was reviewed in this pass and found to echo only an internal capability-identifier string (e.g. a
  dict-lookup key), not a path, host, or credential — assessed as a much lower-severity, narrower information
  disclosure than the primary finding, and explicitly **not** included in this task's recommended fix scope. It
  is named here for visibility, not bundled into this remediation, per the instruction not to redesign unrelated
  error handling — a separate, smaller finding if you choose to pursue it later.
- **No implementation was performed.** Per your explicit instruction, this document is audit-and-plan only.

---

## Summary Answers

- **Verdict:** CONFIRMED.
- **Severity:** HIGH — deterministic, unbounded-content, client-visible-on-200-OK disclosure mechanism with zero
  existing regression coverage; not CRITICAL because no live-today path was shown to carry actual secrets through
  it.
- **Root cause:** `Phase6CapabilityExecutor.execute_task`'s broad `except Exception as exc:` interpolates
  `str(exc)` directly into a client-facing field, with no sanitization; the store/route layers between it and the
  HTTP response perform no filtering either.
- **Affected:** `POST /research/execute` only, confirmed by execution; the workflow-managed execute/get endpoints
  are incidentally, not deliberately, unaffected through this exact path.
- **Reproduction:** performed live; synthetic internal hostname and path both appeared verbatim, twice, in a
  `200 OK` response body; headers were clean.
- **Recommended fix:** sanitize the message at its one source (`capability_executor.py`), paired with adding
  server-side logging there (currently absent entirely) so diagnostic visibility is not lost, without changing
  the endpoint's HTTP contract or introducing a new exception taxonomy.
- **Regression tests:** 8 deterministic tests specified (new file recommended), none implemented.
- **Current test count:** 764 (unchanged by this audit-only task).
- **No source code was modified in the production of this document.**

**Awaiting your review before any implementation. Not proceeding to F05.**
