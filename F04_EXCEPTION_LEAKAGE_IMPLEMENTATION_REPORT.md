# F04 — Exception Message Leakage: Implementation Report

**Scope implemented:** the approved F04 remediation from `F04_EXCEPTION_LEAKAGE_REMEDIATION_PLAN.md` §9 (Option
A + E) — sanitize the client-facing message at its exact source, paired with server-side logging so diagnostic
detail is not lost.
**Git state before implementation:** branch `main`, HEAD `d983bce`, working tree matched the expected post-F03
baseline exactly. Baseline test run confirmed **764 passed** before any change in this task.
**Git state after implementation:** no branch change, no commit, no push.

---

## 1. Root Cause (confirmed in the audit, re-verified unchanged before fixing)

`Phase6CapabilityExecutor.execute_task` (`src/financial_intelligence/infrastructure/orchestration/capability_executor.py`)
caught any exception raised by a capability adapter with a broad `except Exception as exc:` and interpolated
`str(exc)` directly into `TaskExecutionResult.message`, with no sanitization and no server-side logging. That
message reaches the client verbatim through `POST /research/execute`'s `200 OK` response body, in two locations
(`task_results` and the nested `orchestration.results`).

---

## 2. Exact Files/Functions Changed

| File | Function(s) changed | Nature of change |
|---|---|---|
| `src/financial_intelligence/infrastructure/orchestration/capability_executor.py` | `Phase6CapabilityExecutor.execute_task` (module-level additions: a logger and one constant) | Added a `logger.error(...)` call inside the existing except block, logging the exception's type, message, and task/capability context server-side. Replaced the client-facing `message=f"capability executor exception: {exc.__class__.__name__}: {exc}"` with a fixed constant, `_SAFE_CAPABILITY_FAILURE_MESSAGE = "capability execution failed unexpectedly"`. |

No other file was modified. `_dispatch`, `TaskExecutionResult`, `ResearchExecutionResult`, the API route
(`api/routes/research.py`), and every other file in the F01/F02/F03 diffs are untouched.

---

## 3. Remediation Implemented

Exactly the approved Option A + E, nothing broader:
```python
except Exception as exc:
    logger.error(
        "capability_execution_failed",
        extra={
            "task_id": task.task_id.as_text(),
            "capability_id": task.capability_id,
            "error_type": exc.__class__.__name__,
            "error_detail": str(exc),
        },
    )
    return TaskExecutionResult(
        task_id=task.task_id,
        status=TaskResultStatus.FAILED,
        message=_SAFE_CAPABILITY_FAILURE_MESSAGE,
        retryable=True,
        error_code="executor_exception",
    )
```
- **No new exception hierarchy was introduced** — the constraint's condition ("unless implementation proves it
  strictly necessary") was not met; a single fixed string was sufficient because `error_code="executor_exception"`
  (already present, already a stable, finite-vocabulary field) already gives a client a machine-readable signal
  distinct from the human-readable message, so no per-exception-type message differentiation was needed to
  preserve useful client-facing signal.
- **No dependency was added.** Logging uses this repo's existing `observability.logging.get_logger`, the same
  convention used throughout `api/errors.py`, `manage_research_workflow.py`, and elsewhere.
- **The `create_research_plan.py` `KeyError` observation was deliberately NOT touched**, per your scope
  instruction — it is a different code path (plan creation, not task execution), catches a narrower, lower-risk
  `KeyError` (an internal capability-identifier string, not arbitrary exception content), and changing it was not
  required to close the confirmed F04 contract. It remains documented as a deferred, separate, lower-severity
  observation (see §11).

---

## 4. Logging Behavior

The `logger.error(...)` call captures, server-side only:
- `task_id` — the specific task that failed (already a public identifier, appears in successful responses too)
- `capability_id` — which capability adapter failed (e.g. `"market_intelligence"`) — already public information,
  visible in the plan/task structure of every response, successful or not
- `error_type` — the exception's class name (e.g. `"RuntimeError"`) — matches the existing precedent already set
  by `api/errors.py`'s `unhandled_exception_handler`, which treats the exception type as safe telemetry
- `error_detail` — the exception's full message (`str(exc)`) — the one piece of information that must never reach
  the client, now captured server-side instead of being discarded or leaked

**No secrets, credentials, API keys, or authorization headers are logged** — this log statement has no access to
any of those (it operates purely on the caught `Exception` object and the `ResearchTask`, neither of which carries
request-level auth material) and does not need to redact anything beyond what `StructuredFormatter` already
redacts automatically for any accidentally-sensitive-looking key name (confirmed: none of the four keys used here
match any fragment in the existing `_SECRET_KEY_FRAGMENTS` redaction list, so no field is accidentally masked
either — the diagnostic content survives fully, exactly as intended).

**Correlation ID:** confirmed via the live re-reproduction (§7) that the emitted log line also includes
`correlation_id` — this is added automatically by this repo's existing correlation-binding logging filter/adapter
(not something this fix added explicitly), giving operators a way to tie a specific failed capability execution
back to the exact request that triggered it.

---

## 5. API Contract Preservation

- **Status code unchanged.** `POST /research/execute` still returns `200 OK` for a single capability's unexpected
  failure — confirmed by both the new regression tests and the live re-reproduction. Option C (escalating to a
  5xx) was explicitly rejected in the approved plan and was not revisited.
- **Response shape unchanged.** `TaskExecutionResult`'s fields (`task_id`, `status`, `message`, `evidence_refs`,
  `output_summary`, `retryable`, `error_code`) are exactly as before; only the *content* of `message` changed for
  this one failure case.
- **`error_code="executor_exception"` and `retryable=True` are unchanged**, preserving whatever a well-behaved
  client already does with those fields.
- **Safe, intentional domain/application error messages are unaffected** — confirmed directly: a request with an
  invalid `objective` value still returns its own deliberately-authored `400` message
  (`invalid_research_execution_query`) unchanged, via a dedicated regression test (§6).

---

## 6. Regression Tests Added

**New file: `tests/unit/test_capability_executor_hardening.py` (9 tests)**

### `ExceptionLeakageHardeningTests` (6 tests — items 1-6 of your list)
- `test_unexpected_exception_returns_safe_client_facing_message` — asserts on structured fields
  (`message == _SAFE_CAPABILITY_FAILURE_MESSAGE`, `status == "failed"`, `error_code == "executor_exception"`,
  `retryable is True`), not brittle full-response string matching, per your instruction.
- `test_synthetic_hostname_does_not_appear_in_response` — item 2.
- `test_synthetic_filesystem_path_does_not_appear_in_response` — item 3.
- `test_raw_exception_text_does_not_appear_anywhere_in_response` — item 4; also asserts the exception class name
  and the old message's literal prefix (`"capability executor exception"`) are both absent.
- `test_traceback_and_implementation_details_do_not_appear_in_response` — item 5; **parametrized** (via
  `subTest`) across `ValueError`, `KeyError`, and a generic `Exception` subclass, each carrying the synthetic
  host/path, plus a check that no `.py`/`"Traceback"` substring appears — proving the fix sanitizes by mechanism
  (unconditional replacement), not by pattern-matching one exception type, per the plan's own design intent.
- `test_failure_remains_inside_existing_200_partial_failure_contract` — item 6; pins `status_code == 200`, plus
  `failed_count`/`completed_count`, confirming the endpoint's existing partial-failure contract is untouched.
- `test_duplicated_orchestration_results_location_is_also_safe` — explicitly checks the second, nested
  `orchestration.results` location the audit found the content duplicated into, not just `task_results`, per your
  instruction to verify both locations.

### `SafeDomainErrorRegressionTests` (1 test — item 7)
- `test_invalid_objective_still_returns_its_own_safe_message` — an invalid `objective` value still produces its
  own deliberately-authored `400 invalid_research_execution_query` message, unchanged by this fix.

### `ServerSideDiagnosticsTests` (1 test — item 8)
- `test_capability_execution_failure_is_logged_with_full_detail` — using the same log-capture technique already
  established in this repo's `test_logging_safety.py` (a `StringIO` + `StructuredFormatter` handler attached
  directly to the target logger), asserts the captured, parsed JSON log record contains `error_type`,
  `error_detail` (the full synthetic marker), `capability_id`, and `task_id` — **and, in the same test, on the
  same request/response pair**, asserts the HTTP response text does not contain the marker — directly proving the
  "available server-side, absent client-side" split in one assertion, not two disconnected tests that could
  drift apart.

### Non-vacuousness check
Per your validation instructions, the production fix was temporarily reverted (`git stash push` on just
`capability_executor.py`) and the new test file re-run:
```
ImportError: cannot import name '_SAFE_CAPABILITY_FAILURE_MESSAGE' from
'financial_intelligence.infrastructure.orchestration.capability_executor'
```
All 9 tests failed to even collect, because the old code does not define the safe-message constant the tests
import and assert against — direct proof the tests are coupled to the fix, not vacuous. (Beyond the import
coupling: by inspection, the old message format
`f"capability executor exception: {exc.__class__.__name__}: {exc}"` trivially contains `"RuntimeError"` and the
synthetic marker, so `test_raw_exception_text_does_not_appear_anywhere_in_response` and the hostname/path tests
would also have failed on their own assertions had the import succeeded.) The fix was then restored
(`git stash pop`) and reconfirmed passing (9/9).

---

## 7. Evidence the Original Reproduction Is Now Blocked

The exact reproduction harness from the audit (kept outside the repository, unchanged) was re-run against the
fixed code:

**Server-side log line actually emitted** (captured via the harness's own logging output):
```json
{"timestamp": "...", "level": "ERROR", "logger": "financial_intelligence.infrastructure.orchestration.capability_executor",
 "message": "capability_execution_failed", "correlation_id": "5877eeba-...",
 "task_id": "1afec6d8-...", "capability_id": "market_intelligence",
 "error_type": "RuntimeError",
 "error_detail": "AUDIT_MARKER: connection failed to internal-db-host.corp.local:5432 at /var/app/secrets/db.conf"}
```
**Client-facing result:**
```
STATUS: 200
BODY CONTAINS MARKER: False
BODY CONTAINS PATH: False
BODY CONTAINS HOST: False
```
Relevant excerpt of the actual (fixed) response body:
```json
"task_results":[{"task_id":"1afec6d8-...","status":"failed",
  "message":"capability execution failed unexpectedly",
  "evidence_refs":[],"output_summary":null,"retryable":true,
  "error_code":"executor_exception","kind":"task_execution_result"}]
```
The identical safe message also appears in the second, nested `orchestration.results` location. Response headers
were re-checked and remain clean (unchanged from the audit — no fix was needed there).

**This directly confirms:** the exact synthetic hostname and filesystem path that reached the client before this
fix (per the F04 audit) no longer do, while the full diagnostic detail needed to debug the real failure is now
captured server-side, where it was previously not captured at all.

---

## 8. Full Test Result

**Full suite after this fix:**
```
Tests collected: 773
Passed:          773
Failed:          0
Skipped:         0
Errors:          0
```
Exact command/output: `.venv/Scripts/python.exe -m pytest -q` → `773 passed` (re-run 3 times consecutively:
11.33s / 11.50s / 19.09s, stable).
Arithmetic: 764 (baseline) + 9 (new `test_capability_executor_hardening.py`) = 773.

**Targeted pre-full-suite run** (the files most likely to interact with this change):
`test_research_execution.py`, `test_phase6_contract_freeze.py`, `test_architecture_boundaries.py`,
`test_research_workflows.py` → 58 passed, 0 failed — confirming no regression in retry/budget logic, the
architecture-boundary tests, or the workflow lifecycle tests (which also invoke `Phase6CapabilityExecutor`
indirectly).

**F01/F02/F03 regression check:** included in the full-suite run above; all of `test_verification_hardening.py`,
`test_verification_semantics_hardening.py`, `test_verification_engine.py`, `test_synthesis_api.py`, and
`test_workflow_cancellation_race.py` continue to pass unchanged — none were modified in this task.

---

## 9. Ruff Result

```
ruff check src tests          → All checks passed!
ruff format --check src tests → 255 files already formatted
```

---

## 10. Mypy Result

```
mypy src (strict, project config) → Success: no issues found in 183 source files
```

---

## 11. Deferred Observations / Limitations

- **The `create_research_plan.py:110-118` `KeyError`-derived message** (`f"required capability unavailable:
  {exc}"`) was reviewed again in this pass and confirmed to be a **different, lower-severity** finding: it echoes
  only an internal capability-identifier string from a `KeyError`, not arbitrary exception content, and belongs to
  plan *creation*, not task *execution* — a different code path from the confirmed F04 vulnerability. Per your
  explicit scope instruction, it was **not** bundled into this fix and remains a documented, deferred, separate
  observation for future consideration, not part of F04's closure.
- **The secondary observability gap noted in the audit** (the global `unhandled_exception_handler` in
  `api/errors.py` logs only `error_type`, never the message, for genuinely unhandled exceptions) was left
  unchanged, as planned — it is a safe-but-less-debuggable behavior, not a leakage risk, and was explicitly out of
  this task's scope.
- **This fix does not enumerate every exception a live capability adapter (the optional SEC EDGAR or Yahoo chart
  clients) could realistically raise** — it does not need to, since the sanitization is unconditional
  (`except Exception`, not a pattern-matched allowlist), so no future new exception type from any adapter can
  reopen this specific leak path without a further code change to reintroduce raw interpolation.
- **No implementation was performed beyond the approved scope.** F05–F12 were not investigated or touched.

---

## Final Status

**Files changed:**
- `src/financial_intelligence/infrastructure/orchestration/capability_executor.py`
- `tests/unit/test_capability_executor_hardening.py` (new)

**Tests added:** 9, covering all 8 scenarios you specified (item 6 mapped to
`test_duplicated_orchestration_results_location_is_also_safe` plus the contract-preservation test, and item 5 was
parametrized across three exception types rather than split into three separate test methods).

**Full test result:** PASS — 773/773 (764 baseline + 9 new), 0 failed, 0 skipped, stable across 3 consecutive
full-suite runs.

**Ruff result:** PASS — `ruff check` and `ruff format --check` both clean.

**Mypy result:** PASS — strict mode, 0 issues across 183 source files.

**Confirmation no F01/F02/F03 regressed:** confirmed — all of that work's tests re-ran unchanged and passing as
part of the 773; none of those files were touched in this task.

**Original reproduction re-run against the fix:** the synthetic hostname and filesystem path no longer appear
anywhere in the response body (both serialized locations checked); the full exception detail is now captured in a
structured server-side log line instead.

No action was taken on F05–F12. Stopping here per your instruction, awaiting your review before any commit.
