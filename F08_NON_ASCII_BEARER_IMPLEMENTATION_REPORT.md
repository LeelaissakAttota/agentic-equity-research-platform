# F08 — Non-ASCII Bearer Token Causing HTTP 500: Implementation Report

**Scope: F08 only. F01–F07 untouched. No commit or push performed.**

## 1. Finding Summary

A Bearer credential containing any non-ASCII byte (e.g. `café`, `token-测试`, `token-€`) caused the API to return **HTTP 500 Internal Server Error** instead of **HTTP 401 Unauthorized**, on every protected endpoint, in both `production` and `staging` (wherever authentication is enforced with at least one API key configured). The F08 audit reproduced this against both `TestClient` (with byte-level header control) and a real `uvicorn` server over a raw TCP socket.

## 2. Root Cause

`InMemoryApiKeyStore.is_valid()` passed the raw, unvalidated Bearer credential directly into `secrets.compare_digest()`. CPython's `secrets.compare_digest` (an alias for `hmac.compare_digest`) raises `TypeError: comparing strings with non-ASCII characters is not supported` whenever either `str` operand contains a non-ASCII character. This `TypeError` is not an `AuthenticationError`, so it bypassed the dedicated 401 handler and was caught only by the generic `@app.exception_handler(Exception)` in `api/errors.py`, which correctly-but-unhelpfully treated it as a genuinely unanticipated error and returned 500.

## 3. Exact Fix

**File changed:** [src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py](src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py) — one guard clause added to `is_valid()`:

```python
def is_valid(self, presented_key: str) -> bool:
    ...
    if not presented_key or not self._keys or not presented_key.isascii():
        return False
    return any(secrets.compare_digest(presented_key, stored) for stored in self._keys)
```

Only `or not presented_key.isascii()` was added to the existing guard condition (previously `if not presented_key or not self._keys:`). A docstring note explaining the F08 rationale was added alongside it. No other line in the method, class, or file changed.

This satisfies every constraint from the approved remediation exactly:
- Empty credential → unchanged (`not presented_key` still short-circuits first).
- ASCII credential → unchanged (falls through to the existing `compare_digest` comparison, byte-for-byte identical behavior to before).
- Non-ASCII credential → returns `False` immediately, never reaching `compare_digest`.
- `secrets.compare_digest()` can now never receive a non-ASCII `str` from this method.
- The `False` return flows back through `require_api_key()`'s existing `if not container.api_key_store.is_valid(credential): _reject_401(request)` check exactly as any other invalid key does — through the existing `AuthenticationError` → registered handler → HTTP 401 path, unmodified.

No change was made to `security/auth.py`, `api/errors.py`, the generic exception handler, `ApiKeyStorePort`, health/readiness/version routing, or any other file.

## 4. Files Changed

- [src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py](src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py) — the fix (§3).
- [tests/unit/test_auth.py](tests/unit/test_auth.py) — 15 new regression tests appended (two new test classes: `TestNonAsciiBearerToken`, `TestNonAsciiBearerAtStoreLevel`); no existing test in this file was modified.
- `F08_NON_ASCII_BEARER_IMPLEMENTATION_REPORT.md` — this report.

No other file was modified. `Dockerfile`, `docker-compose.yml`, `requirements-lock.txt`, `.github/workflows/ci.yml`, `pyproject.toml`, and every other `src/`/`tests/` file are unchanged by this implementation (their working-tree diffs, where present, are the pre-existing, already-approved F01–F07 state — see §13).

## 5. Regression Tests

Added to [tests/unit/test_auth.py](tests/unit/test_auth.py):

**`TestNonAsciiBearerToken`** (end-to-end, via the real `require_api_key` dependency and a production `TestClient`, using raw `(bytes, bytes)` header tuples — the only way to actually deliver non-ASCII header content, since `httpx`'s convenience `dict[str, str]` API ASCII-encodes client-side and would raise `UnicodeEncodeError` before the request is ever sent):
- `test_ascii_invalid_bearer_returns_401` — existing behavior unchanged.
- `test_ascii_valid_bearer_succeeds` — existing behavior unchanged.
- `test_non_ascii_accented_bearer_returns_401_not_500` (`café`)
- `test_non_ascii_cjk_bearer_returns_401_not_500` (`token-测试`)
- `test_non_ascii_currency_symbol_bearer_returns_401_not_500` (`token-€`)
- `test_non_ascii_bearer_response_matches_generic_auth_failure_shape` — asserts the exact same `authentication_required` body used for every other rejection reason.
- `test_non_ascii_bearer_does_not_expose_internal_exception_details` — asserts the response text contains none of `"TypeError"`, `"compare_digest"`, `"Traceback"`, `"non-ASCII characters"`, `"internal_error"`, or the submitted credential itself.
- `test_malformed_empty_bearer_returns_existing_401`
- `test_missing_header_returns_existing_401`
- `test_health_remains_accessible`, `test_ready_remains_accessible`, `test_version_remains_accessible`

**`TestNonAsciiBearerAtStoreLevel`** (direct unit coverage of the exact call site that used to raise, without any HTTP machinery):
- `test_non_ascii_presented_key_returns_false_without_raising` — `café`, `token-测试`, `token-€` all return `False`.
- `test_non_ascii_presented_key_against_empty_store_returns_false`
- `test_ascii_behavior_unchanged_by_the_guard`

Only synthetic, non-secret credentials (`"prod-test-key-f08"`, `"configured-ascii-key"`) were used; no real API key was printed, logged, or referenced.

## 6. Non-Vacuous Proof

Performed exactly as the approved remediation required, against the real repository file (not a hardcoded snippet):

**Step 1 — tests pass against the fix** (already in place before this experiment):
```
$ python -m pytest tests/unit/test_auth.py -v
... 62 passed in 2.27s
```

**Step 2 — temporarily reproduce the vulnerable implementation, safely, via `git stash`:**
```
$ git stash push -- src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py
Saved working directory and index state WIP on main: d983bce ...
```
This restored the file to its exact pre-fix HEAD content (`if not presented_key or not self._keys: return False`, no `.isascii()` guard).

**Step 3/4 — run the same regression tests against the vulnerable implementation and confirm the non-ASCII tests fail:**
```
$ python -m pytest tests/unit/test_auth.py::TestNonAsciiBearerToken tests/unit/test_auth.py::TestNonAsciiBearerAtStoreLevel -v
...
FAILED ...::test_non_ascii_accented_bearer_returns_401_not_500          (500 != 401)
FAILED ...::test_non_ascii_bearer_does_not_expose_internal_exception_details
FAILED ...::test_non_ascii_bearer_response_matches_generic_auth_failure_shape
FAILED ...::test_non_ascii_cjk_bearer_returns_401_not_500
FAILED ...::test_non_ascii_currency_symbol_bearer_returns_401_not_500
FAILED ...::test_non_ascii_presented_key_returns_false_without_raising   (TypeError raised)
6 failed, 9 passed in 1.56s
```
Exactly and only the six non-ASCII-specific assertions failed — every ASCII, malformed-syntax, missing-header, and health/ready/version test in the same run still passed, proving the tests are precisely targeted at the defect and not incidentally broken by an unrelated change. The captured failure output shows the real `TypeError`/500 behavior described in the F08 audit, reproduced live.

**Step 5 — restore the fix:**
```
$ git stash pop
... Dropped refs/stash@{0} ...
```

**Step 6 — re-run and confirm all tests pass again:**
```
$ python -m pytest tests/unit/test_auth.py -v
... 62 passed in 1.89s
```

`git status` after `stash pop` showed the working tree in the same fixed state as before the experiment (the `.isascii()` guard present), confirming no permanent alteration occurred during the exercise.

## 7. Original Reproduction: Before/After

Re-ran the audit's exact real-server/raw-socket reproduction, this time against the fixed code, on a fresh `uvicorn` instance (`APP_ENV=production`, `AUTH_ENABLED=true`, `API_KEYS=prod-test-key-abc`, port 18082):

| Case | Before (audit, vulnerable) | After (this implementation, fixed) |
|---|---|---|
| ASCII invalid bearer | `HTTP/1.1 401 Unauthorized` | `HTTP/1.1 401 Unauthorized` (unchanged) |
| `Bearer café` (UTF-8 bytes) | `HTTP/1.1 500 Internal Server Error` | **`HTTP/1.1 401 Unauthorized`** |
| `Bearer token-测试` (UTF-8 bytes) | `HTTP/1.1 500 Internal Server Error` | **`HTTP/1.1 401 Unauthorized`** |
| `Bearer token-€` (UTF-8 bytes) | *(not run in original audit; added here)* | **`HTTP/1.1 401 Unauthorized`** |
| Valid configured key | `HTTP/1.1 200 OK` | `HTTP/1.1 200 OK` (unchanged) |

Raw command/output (post-fix):
```
$ python -c "<raw socket script, see F08 audit §4b>"
ascii_invalid                              -> HTTP/1.1 401 Unauthorized
non_ascii_cafe_utf8_raw_socket (POST-FIX)  -> HTTP/1.1 401 Unauthorized
non_ascii_chinese_utf8_raw_socket (POST-FIX) -> HTTP/1.1 401 Unauthorized
non_ascii_euro_utf8_raw_socket (POST-FIX)  -> HTTP/1.1 401 Unauthorized
valid_key                                  -> HTTP/1.1 200 OK
```
The temporary server script and log were created under the system temp directory only, never inside the repository, and were removed (along with the server process) after this verification.

## 8. Authentication Behavior Matrix (Post-Fix)

| Input | Status | Notes |
|---|---|---|
| Missing Authorization header | 401 | Unchanged |
| `Authorization: Bearer <ascii-invalid>` | 401 | Unchanged |
| `Authorization: Bearer <ascii-valid-configured-key>` | 200 (or business-logic code) | Unchanged |
| `Authorization: Bearer café` | **401** (was 500) | Fixed |
| `Authorization: Bearer token-测试` | **401** (was 500) | Fixed |
| `Authorization: Bearer token-€` | **401** (was 500) | Fixed |
| `Authorization: Basic invalid` | 401 | Unchanged (rejected before reaching `is_valid`) |
| `Authorization: Bearer` (no token) | 401 | Unchanged |
| `Authorization: Bearer ` (trailing space, empty credential) | 401 | Unchanged |
| `development`/`test` environment, any credential | Auth bypassed (business-logic status) | Unchanged — `require_api_key` never reads the header in these environments |

## 9. Health/Readiness/Version Verification

`TestNonAsciiBearerToken.test_health_remains_accessible`, `test_ready_remains_accessible`, and `test_version_remains_accessible` (production settings, no credential) all assert `status_code == 200` and pass. These endpoints are registered without `dependencies=_auth` (per `api/app.py`, unchanged), so they never call `require_api_key`/`is_valid` and were structurally unreachable by this defect both before and after the fix; the tests confirm this remains true post-fix.

## 10. Full Test Result

```
$ python -m pytest -q
811 passed, 130 subtests passed in ~27-31s (3 consecutive clean runs)
```
Baseline before F08 was 796 passed / 130 subtests; the 15 new F08 tests (`TestNonAsciiBearerToken`: 12, `TestNonAsciiBearerAtStoreLevel`: 3) bring the total to 811 passed, with no failures or regressions elsewhere.

**Note on a one-off warning:** a single run during validation printed a `PytestUnhandledThreadExceptionWarning` wrapping a `UnicodeDecodeError` from an unrelated background-thread teardown (`codecs.charmap_decode`), with 811 tests still passing in that same run. Three immediate, consecutive re-runs of the full suite (`811 passed, 130 subtests passed`, no warnings, each time) did not reproduce it. This is consistent with a flaky, timing-dependent resource-teardown warning in the test-runner environment, not a deterministic regression introduced by this change; no F08 test or fix code touches threading, and the warning did not recur under repeated runs.

## 11. Ruff Result

```
$ python -m ruff check src tests
All checks passed!

$ python -m ruff format --check src tests
258 files already formatted
```
(An initial `ruff check` pass flagged 5 `UP012` findings — unnecessary explicit `"utf-8"` argument to `.encode()` — in the newly added test code; these were fixed via `ruff check --fix tests/unit/test_auth.py`, which only removed the redundant encoding argument from 5 `.encode()` calls. Re-verified clean afterward, and the full test suite and F08 tests were re-run and confirmed passing after this fix.)

## 12. Mypy Result

```
$ PYTHONPATH=src python -m mypy
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check ... [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check ... [comparison-overlap]
Found 2 errors in 1 file (checked 190 source files)
```
Identical to the documented pre-existing baseline (same file, same lines, same message). This implementation did not touch `graph.py` or any orchestration code. (As previously documented for F07: `mypy` must be invoked with `PYTHONPATH=src` in this shell to resolve the `financial_intelligence` package at all — a pre-existing environment detail, unrelated to F08.)

## 13. F01–F07 Regression Verification

- `git diff -- src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py` shows exactly the one-line guard + docstring addition described in §3 — nothing else in the file changed.
- `git diff --stat -- Dockerfile requirements-lock.txt .github/workflows/ci.yml docker-compose.yml` shows only the pre-existing, already-approved F06 (`docker-compose.yml`) and F07 (`Dockerfile`) diffs — identical to their state before this F08 session began. Neither file was touched during F08 implementation.
- F06's loopback-only Docker binding is unchanged: `docker-compose.yml`'s `ports:` section (with its `# Bound to loopback only (F06)` comment and `host_ip: 127.0.0.1` binding) is untouched — confirmed by inspection, not re-derived.
- F07's Docker dependency locking is unchanged: `Dockerfile`'s `pip install -c requirements-lock.txt .` and digest-pinned `FROM` lines are untouched; `requirements-lock.txt` has zero diff.
- No dependency file (`pyproject.toml`, `requirements-lock.txt`) was modified; no package version changed.
- `git status --short` before and after this implementation shows the same set of pre-existing F01–F07 modified/untracked files, unchanged by this session, plus exactly three new/changed items: the modified `in_memory_api_key_store.py`, the modified `tests/unit/test_auth.py`, and this report.
- No secret, real API key, or credential value was printed, logged, or committed at any point in this implementation — only synthetic test values (`"prod-test-key-f08"`, `"prod-test-key-abc"`, `"configured-ascii-key"`) were used throughout, consistent with the audit's own constraint.
- No commit or push was performed.

## 14. Git Diff/Status

```
$ git status --short
 M Dockerfile                          <- pre-existing, approved F07 change, untouched this session
 M docker-compose.yml                  <- pre-existing, approved F06 change, untouched this session
 M docs/development/README.md          <- pre-existing, untouched this session
 M src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py   <- NEW (F08 fix)
 M src/... (10 other files)            <- pre-existing F01-F06-scope changes, untouched this session
 M tests/unit/test_auth.py             <- NEW (F08 regression tests)
 M tests/... (5 other files)           <- pre-existing F01-F06-scope changes, untouched this session
?? F08_NON_ASCII_BEARER_IMPLEMENTATION_REPORT.md   <- new (this report)
?? (other pre-existing untracked F0*/audit .md files, unchanged)
```
`git diff -- src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py` shown in full in §3. No other tracked file's diff changed as a result of this implementation. Nothing was staged, committed, or pushed.

## 15. Remaining Limitations

- **Scope is intentionally narrow.** The fix closes exactly the confirmed defect (non-ASCII credential reaching `compare_digest`); it does not add broader input sanitization, length limits, or a new validation layer for the Authorization header, per the approved remediation's explicit "do not redesign authentication" constraint.
- **`get_authorization_scheme_param` and the scheme/credential presence checks in `require_api_key` are unchanged and untested for non-ASCII *scheme* values** (e.g. a non-ASCII string before the space) — this was out of scope because the audit's reproduction and this fix are specifically about the *credential* reaching `compare_digest`; a non-ASCII scheme name fails the existing `scheme.lower() != "bearer"` check before ever reaching `is_valid`, so it was already correctly rejected with 401 pre-fix (not part of the confirmed defect).
- **The one-off flaky test-runner warning noted in §10** was not deterministically reproducible and is not believed to be related to this change, but is disclosed here for transparency rather than silently omitted.

## 16. Final Conclusion

**F08 FIXED.**

`InMemoryApiKeyStore.is_valid()` now rejects any non-ASCII presented credential before it can reach `secrets.compare_digest()`, returning `False` (routed through the existing `AuthenticationError` → HTTP 401 path) instead of raising `TypeError` (routed through the generic exception handler → HTTP 500). The fix was verified non-vacuously against the real repository file via `git stash`/`git stash pop` (6 targeted tests failed against the genuine pre-fix code, then passed after restoring the fix), and the original audit's real-server/raw-socket reproduction was re-run and now shows `401 Unauthorized` for `café`, `token-测试`, and `token-€` where it previously showed `500`. ASCII-valid and ASCII-invalid behavior, malformed-Bearer handling, and health/readiness/version accessibility are all unchanged (811 passed total, up from 796, with zero regressions). Ruff and Mypy show no new issues (Mypy: the same 2 pre-existing, unrelated `graph.py` errors only). F01–F07 files, Docker configuration, and dependency locking are all confirmed unchanged. No commit or push was performed.
