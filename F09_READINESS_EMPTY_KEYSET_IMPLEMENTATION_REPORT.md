# F09 — Readiness Ignores Empty API-Key Set: Implementation Report

**Scope: F09 only. F01–F08 untouched. No commit or push performed.**

## 1. Finding Summary

In `production`/`staging`, `/ready` reported `status: "ready"` (HTTP 200) even when the API-key store contained zero usable keys — a state in which `require_api_key` unconditionally rejects every caller with 401. The two registered readiness probes (`"application"`, `"configuration"`) were hardcoded `ready=True` constants that never inspected the API-key configuration. `development`/`test` were unaffected in practice (auth is bypassed there, so the signal wasn't actually misleading), but nothing in the code distinguished that case from the broken one.

## 2. Root Cause

`build_container()` (`composition/__init__.py`) registered its two readiness probes without ever consulting `resolved.auth_enabled`, `resolved.app_env`, or the later-constructed `api_key_store.has_keys`. `Settings`'s production/staging validator enforces `auth_enabled=True` but never enforces `api_keys` non-empty, so a syntactically valid configuration (`AUTH_ENABLED=true`, `API_KEYS=""`) could start successfully and run indefinitely while being completely unusable — with no readiness signal reflecting that.

## 3. Exact Implementation

**File changed:** [src/financial_intelligence/composition/__init__.py](src/financial_intelligence/composition/__init__.py) only.

**a) New readiness probe**, registered in `build_container()` immediately after `api_key_store` is constructed:

```python
readiness.register(
    "authentication",
    lambda: ReadinessCheckResult(
        name="authentication",
        ready=(resolved.app_env not in _AUTH_ENFORCED_ENVIRONMENTS) or api_key_store.has_keys,
        detail=(
            "authentication_not_enforced_in_this_environment"
            if resolved.app_env not in _AUTH_ENFORCED_ENVIRONMENTS
            else "usable_api_keys_configured"
            if api_key_store.has_keys
            else "auth_enabled_but_no_usable_api_keys_configured"
        ),
    ),
)
```

**b) A module-level constant** mirroring the exact set of environments that enforce authentication:

```python
_AUTH_ENFORCED_ENVIRONMENTS = frozenset({"production", "staging"})
```

**Design decisions, explained:**

- **The probe uses `api_key_store.has_keys`, not a re-parse of `API_KEYS`.** This is the same authoritative property `require_api_key`/`InMemoryApiKeyStore.is_valid()` ultimately relies on for the same question ("is there at least one usable key?"), so there is exactly one place in the codebase that decides that fact — no duplicated CSV-parsing logic.
- **The probe checks `resolved.app_env in _AUTH_ENFORCED_ENVIRONMENTS`, not `resolved.auth_enabled` directly.** This was a deliberate correction made *during* implementation after manual verification exposed a bug in a first draft: `require_api_key` (`security/auth.py`) bypasses authentication by **environment** (`if settings.app_env not in _ENFORCED_ENVIRONMENTS: return`), independently of the `auth_enabled` field's value — so a `development`/`test` deployment with `AUTH_ENABLED=true` explicitly set is *still* bypassed in practice. An initial implementation that checked `not resolved.auth_enabled` incorrectly reported "not ready" for that case (verified directly: `APP_ENV=development, AUTH_ENABLED=true, API_KEYS=""` → incorrectly `503` before the correction, `200` after). The final implementation mirrors `require_api_key`'s actual bypass predicate, not the config flag alone, so readiness can never contradict actual endpoint usability.
- **The environment set is duplicated as a local constant, not imported from `security/auth.py`.** `security/auth.py` imports `AppContainer` from `composition/__init__.py`; importing `security.auth`'s `_ENFORCED_ENVIRONMENTS` back into `composition/__init__.py` would create a circular import. The duplicated `frozenset({"production", "staging"})` mirrors both `security/auth.py`'s `_ENFORCED_ENVIRONMENTS` and `Settings`'s own model-validator condition (`config/settings.py:213`, which already uses the identical tuple) — it is not a new, independently-invented rule, and a comment on the constant flags all three call sites to keep in sync if this ever changes.

## 4. Readiness Semantics Before/After

| State | Before | After |
|---|---|---|
| `production`/`staging`, ≥1 usable key | `ready=true` (only by coincidence — the check never looked) | `ready=true`, `authentication` check `ready=true`, detail `usable_api_keys_configured` |
| `production`/`staging`, 0 usable keys | `ready=true` (defect) | **`ready=false`, HTTP 503**, `authentication` check `ready=false`, detail `auth_enabled_but_no_usable_api_keys_configured` |
| `development`/`test`, any key count | `ready=true` | `ready=true`, `authentication` check `ready=true`, detail `authentication_not_enforced_in_this_environment` (unchanged outcome, now explicitly documented rather than accidental) |

**Startup-validator alternative was evaluated and deliberately not implemented**, per the task's explicit instruction to choose one mechanism and document the decision:

- Extending `Settings`'s model-validator to reject `auth_enabled=True and not api_keys` in production/staging would require **re-implementing** `InMemoryApiKeyStore.from_csv`'s parsing semantics (comma-split, strip, discard-blank-tokens) inside `Settings`, since `Settings` validates before any `ApiKeyStorePort` exists and has no access to it. That would create exactly the "duplicate source of truth" the task asked to avoid — two independent places deciding what counts as a "usable key," which could silently drift (e.g., if `from_csv`'s parsing rules are ever refined, `Settings`'s copy would need a matching, easy-to-forget update).
- The chosen readiness-probe approach uses the single existing authoritative source (`api_key_store.has_keys`) and requires zero duplicated parsing logic — it was preferred for that reason, not because startup validation is a worse idea in general.
- **Is a readiness probe alone sufficient for the documented `/ready` contract?** Yes: `docs/operations/SLO.md`'s stated contract — "`/ready` returns ready only when registered required checks pass... deployment dependencies must be registered when introduced" — describes exactly a registered-probe model, not a startup-rejection model. The fix satisfies that documented contract directly.
- A startup-validator hardening remains a reasonable **complementary, separate** future enhancement (fail-closed at process start rather than discoverable only via `/ready`), but implementing it now would exceed F09's approved scope ("do not redesign the configuration system") and was correctly identified by the audit as optional, not required.

## 5. Files Changed

- [src/financial_intelligence/composition/__init__.py](src/financial_intelligence/composition/__init__.py) — the fix (§3).
- [tests/unit/test_readiness_registry.py](tests/unit/test_readiness_registry.py) — 14 new regression tests (new `AuthenticationReadinessTests` class); no existing test in this file was modified.
- [tests/unit/test_phase10_prompt1_production.py](tests/unit/test_phase10_prompt1_production.py) — added a default `API_KEYS` value to the file's local `_production_settings()` helper (see §16 — necessary collateral fix, not scope creep).
- [tests/unit/test_phase10_prompt2_hardening.py](tests/unit/test_phase10_prompt2_hardening.py) — same helper fix, plus updated one assertion's expected readiness-check-name set to include `"authentication"`.
- [tests/unit/test_phase10_prompt3_acceptance.py](tests/unit/test_phase10_prompt3_acceptance.py) — updated one assertion's expected readiness-check-name set to include `"authentication"` (this file imports its `_production_settings` helper from `test_phase10_prompt2_hardening.py`, so no separate helper edit was needed here).
- `F09_READINESS_EMPTY_KEYSET_IMPLEMENTATION_REPORT.md` — this report.

No other file was modified. `Dockerfile`, `docker-compose.yml`, `requirements-lock.txt`, `.github/workflows/ci.yml`, `security/auth.py`, `infrastructure/auth/in_memory_api_key_store.py` (beyond its pre-existing, already-approved F08 diff), and every other `src/`/`tests/` file are unchanged by this implementation.

## 6. Regression Tests

Added to [tests/unit/test_readiness_registry.py](tests/unit/test_readiness_registry.py), class `AuthenticationReadinessTests` (14 tests):

1. `test_production_configured_key_is_ready`
2. `test_production_zero_keys_is_not_ready`
3. `test_production_whitespace_only_keys_is_not_ready`
4. `test_production_comma_only_empty_entries_is_not_ready`
5. `test_staging_zero_keys_is_not_ready`
6. `test_staging_configured_key_is_ready`
7. `test_development_zero_keys_remains_ready`
8. `test_development_zero_keys_with_auth_enabled_true_remains_ready` — the specific case that caught the bypass-predicate bug during implementation (§3)
9. `test_test_env_zero_keys_remains_ready`
10. `test_health_unaffected_by_zero_keys_in_production`
11. `test_protected_endpoint_still_401_with_zero_keys`
12. `test_protected_endpoint_succeeds_with_configured_key`
13. `test_not_ready_response_identifies_failed_check_without_leaking_keys`
14. `test_existing_application_and_configuration_checks_still_pass`

Only synthetic, non-secret credentials (`"prod-key-f09"`, `"staging-key-f09"`) were used throughout; no real API key was printed, logged, or referenced.

## 7. Non-Vacuous Proof

Performed against the real repository file via `git stash`, exactly as required:

**Before this experiment:** all 19 tests in `test_readiness_registry.py` passed against the fix already in place.

**Step 1 — temporarily reproduce the vulnerable implementation:**
```
$ git stash push -- src/financial_intelligence/composition/__init__.py
Saved working directory and index state WIP on main: d983bce ...
```
This restored `build_container()` to its exact pre-fix HEAD content (no `"authentication"` probe, no `_AUTH_ENFORCED_ENVIRONMENTS`).

**Step 2 — run the F09 regression tests against the vulnerable implementation:**
```
$ python -m pytest tests/unit/test_readiness_registry.py -v
...
FAILED ...::test_development_zero_keys_remains_ready
FAILED ...::test_development_zero_keys_with_auth_enabled_true_remains_ready
FAILED ...::test_not_ready_response_identifies_failed_check_without_leaking_keys
FAILED ...::test_production_comma_only_empty_entries_is_not_ready
FAILED ...::test_production_configured_key_is_ready
FAILED ...::test_production_whitespace_only_keys_is_not_ready
FAILED ...::test_production_zero_keys_is_not_ready
FAILED ...::test_staging_configured_key_is_ready
FAILED ...::test_staging_zero_keys_is_not_ready
FAILED ...::test_test_env_zero_keys_remains_ready
10 failed, 9 passed in 1.57s
```
Exactly 10 of the 14 new tests failed — every test that asserts the presence, absence, or `ready` value of an `"authentication"` check — with `AssertionError: no readiness check named 'authentication' in [...]` (that check did not exist at all in the pre-fix code) or a wrong overall `status`/HTTP-status-code value. The remaining 4 new tests (`test_health_unaffected_by_zero_keys_in_production`, `test_protected_endpoint_still_401_with_zero_keys`, `test_protected_endpoint_succeeds_with_configured_key`, `test_existing_application_and_configuration_checks_still_pass`) still passed against the vulnerable code, because their assertions don't reference the `"authentication"` check at all (`/health` behavior, the 401/200 authentication decision, and the pre-existing `application`/`configuration` checks were never broken by F09 in the first place) — this is expected and correctly demonstrates the new tests are precisely targeted at the defect rather than incidentally coupled to unrelated behavior. All 9 pre-existing `ReadinessRegistryTests` mechanics tests also still passed.

**Step 3 — restore the fix:**
```
$ git stash pop
... Dropped refs/stash@{...} ...
```

**Step 4 — re-run and confirm all tests pass again:**
```
$ python -m pytest tests/unit/test_readiness_registry.py -v
... 19 passed in 1.28s
```

`git status` after `stash pop` showed the working tree in the same fixed state as before the experiment, confirming no permanent alteration occurred.

## 8. Original Reproduction: Before/After

Re-ran the audit's exact reproduction against the fixed code (in-process `TestClient`, real `create_app`/`Settings` factories):

```
BEFORE (documented in the F09 audit):
  production, AUTH_ENABLED=true, API_KEYS=""
    /ready      -> 200, {"status": "ready", ...}
    protected   -> 401 (any credential or none)

AFTER (this implementation):
  production, AUTH_ENABLED=true, API_KEYS=""
    /ready      -> 503, {"status": "not_ready", ...,
                    "checks": [..., {"name": "authentication", "ready": false,
                                      "detail": "auth_enabled_but_no_usable_api_keys_configured"}]}
    protected   -> 401 (unchanged — no authentication bypass introduced)

  production, AUTH_ENABLED=true, API_KEYS="real-key-1" (configured-key control case)
    /ready      -> 200, {"status": "ready", ...}
    protected (Authorization: Bearer real-key-1) -> 200 (unchanged)
```
Confirmed via direct execution in this session (§3/§8 evidence above): `/ready` correctly flips from `200`/`ready` to `503`/`not_ready` for the zero-key case, the protected endpoint remains `401` in that same state (proving no bypass), and the configured-key control case is completely unaffected (`/ready` → `200`, protected endpoint → `200`).

## 9. Environment Behavior Matrix (Post-Fix)

| Environment | `AUTH_ENABLED` | Usable keys | `/ready` | Protected endpoint |
|---|---|---|---|---|
| `production` | `true` | ≥1 | 200, ready | Normal (200/404/422 depending on business logic with a valid key) |
| `production` | `true` | 0 | **503, not_ready** | 401 (unchanged) |
| `staging` | `true` | ≥1 | 200, ready | Normal |
| `staging` | `true` | 0 | **503, not_ready** | 401 (unchanged) |
| `development` | `false` (default) | 0 | 200, ready | Bypassed (200/business logic, unchanged) |
| `development` | `true` (explicit) | 0 | 200, ready (bypass predicate is environment, not the flag) | Bypassed (unchanged) |
| `test` | (any) | 0 | 200, ready | Bypassed (unchanged) |

## 10. `/health` Regression Verification

`health.py`'s `get_health()` never calls `container.readiness` at all — it is structurally unreachable by this change. Confirmed directly: `test_health_unaffected_by_zero_keys_in_production` asserts `GET /health` under a zero-key `production` container still returns `200`, `{"status": "ok", ...}`. Also re-confirmed via the pre-existing (now-passing) `test_phase10_prompt1_production.py`/`test_phase10_prompt3_acceptance.py` suites, which assert `/health` is unaffected by host/readiness state changes generally.

## 11. Protected-Endpoint Correlation

Directly verified (§8): under the identical zero-key `production` container, `/ready` now correctly reports `not_ready` while the protected endpoint continues to return `401` — the authentication *decision* is completely unchanged by this fix; only the readiness *signal* now accurately reflects it. `test_protected_endpoint_still_401_with_zero_keys` and `test_protected_endpoint_succeeds_with_configured_key` codify both halves of this correlation as permanent regression tests.

## 12. Docker/Deployment Impact

Per the approved scope, **no Docker or deployment file was touched**:
- `Dockerfile`'s `HEALTHCHECK` still targets `/health` (unchanged, confirmed via `git diff` showing zero change to `Dockerfile` beyond its pre-existing, already-approved F07 diff).
- `docker-compose.yml` is unchanged beyond its pre-existing, already-approved F06 diff (loopback-only binding, confirmed intact — see §16).
- No new deployment infrastructure (Kubernetes manifests, readiness-probe configuration, etc.) was added.
- `/ready`'s HTTP contract shape (`status`, `service`, `version`, `checks[]`, 200/503 status code semantics) is unchanged — only the *contents* of `checks[]` gained one new, additive entry.

## 13. Full Test Result

```
$ python -m pytest -q
825 passed, 130 subtests passed (3 consecutive clean runs; ~18-33s each)
```
Baseline before F09 was 811 passed / 130 subtests; the 14 new F09 tests bring the total to 825 passed, with no failures or regressions elsewhere. (One run in this session's history showed a single flaky, non-reproducible `PytestUnhandledThreadExceptionWarning` — the same class of environment-level flakiness already documented in the F08 implementation report — with all 825 tests still passing in that run; two immediate re-runs showed zero warnings.)

## 14. Ruff Result

```
$ python -m ruff check src tests
All checks passed!

$ python -m ruff format --check src tests
258 files already formatted
```
(An initial `ruff check` pass flagged one `I001` import-block-spacing finding — a blank-line-count issue introduced by inserting the new module-level constant directly after the import block in `composition/__init__.py` — fixed via `ruff check --fix` restricted to that one file, which only adjusted blank-line spacing around the import block; the fix's logic was unaffected, confirmed by re-reading the file and re-running the full test suite afterward.)

## 15. Mypy Result

```
$ PYTHONPATH=src python -m mypy
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check ... [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check ... [comparison-overlap]
Found 2 errors in 1 file (checked 190 source files)
```
Identical to the documented pre-existing baseline (same file, same lines, same message). This implementation did not touch `graph.py` or any orchestration code.

## 16. F01–F08 Regression Verification

- `git diff -- src/financial_intelligence/composition/__init__.py` shows exactly the new constant and the new probe registration described in §3 — nothing else in the file changed.
- `git diff --stat -- Dockerfile requirements-lock.txt .github/workflows/ci.yml docker-compose.yml` shows only the pre-existing, already-approved F06 (`docker-compose.yml`) and F07 (`Dockerfile`) diffs — identical to their state before this F09 session began.
- `git diff --stat -- src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py` shows only the pre-existing, already-approved F08 diff — untouched this session.
- **F06's loopback-only Docker binding is unchanged**: `docker-compose.yml`'s `ports:` section (with its `# Bound to loopback only (F06)` comment and `host_ip: 127.0.0.1` binding) is untouched.
- **F07's Docker dependency locking is unchanged**: `Dockerfile`'s `pip install -c requirements-lock.txt .` and digest-pinned `FROM` lines are untouched; `requirements-lock.txt` has zero diff.
- No dependency file was modified; no package version changed.
- `security/auth.py` (F08's fix location) and `tests/unit/test_auth.py`'s F08 test additions are untouched — confirmed via `git diff` showing no new changes beyond their already-approved state.
- No secret, real API key, or credential value was printed, logged, or committed — only synthetic test values (`"prod-key-f09"`, `"staging-key-f09"`, `"phase10-prompt1-test-key"`, `"phase10-prompt2-test-key"`, `"real-key-1"`) were used throughout.
- No commit or push was performed.

## 17. Git Diff/Status

```
$ git status --short
 M Dockerfile                                    <- pre-existing, approved F07 change, untouched this session
 M docker-compose.yml                            <- pre-existing, approved F06 change, untouched this session
 M docs/development/README.md                    <- pre-existing, untouched this session
 M src/financial_intelligence/composition/__init__.py                       <- NEW (F09 fix)
 M src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py <- pre-existing, approved F08 change, untouched this session
 M src/... (9 other files)                       <- pre-existing F01-F06-scope changes, untouched this session
 M tests/unit/test_readiness_registry.py         <- NEW (F09 regression tests)
 M tests/unit/test_phase10_prompt1_production.py <- NEW (collateral fix: default API_KEYS in test helper, see §18)
 M tests/unit/test_phase10_prompt2_hardening.py  <- NEW (same collateral fix + one assertion update)
 M tests/unit/test_phase10_prompt3_acceptance.py <- NEW (one assertion update)
 M tests/unit/test_auth.py                       <- pre-existing, approved F08 change, untouched this session
 M tests/... (4 other files)                     <- pre-existing F01-F06-scope changes, untouched this session
?? F09_READINESS_EMPTY_KEYSET_IMPLEMENTATION_REPORT.md   <- new (this report)
?? (other pre-existing untracked F0*/audit .md files, unchanged)
```
Full diff of the actual fix shown in §3. Nothing was staged, committed, or pushed.

## 18. Remaining Limitations

- **Three pre-existing tests required updates as a direct, necessary consequence of the approved fix** (`test_phase10_prompt1_production.py`, `test_phase10_prompt2_hardening.py`, `test_phase10_prompt3_acceptance.py`). These tests encoded the *old, defective* readiness behavior as their expected value: two asserted `{check["name"] for check in ready["checks"]} == {"application", "configuration"}` (an exhaustive-set assertion that would fail for any additive check, including a legitimate one), and two others used a `_production_settings()` test helper with no configured `API_KEYS`, which — after the fix — now correctly makes `/ready` report `not_ready` for reasons unrelated to what those tests were actually verifying (host-header allowlist enforcement). Fixing these was treated as in-scope because it is a direct, mechanical consequence of the approved readiness-contract change, not an unrelated refactor — no test's *intent* was altered, only the readiness-check-name set and the default fixture's key configuration were updated to match the new, intentional contract.
- **The startup-validator enhancement discussed in §4 was deliberately not implemented**, per the task's instruction to choose one mechanism. If a future finding wants defense-in-depth (rejecting the misconfiguration at process start, not just reporting it via `/ready`), it should be scoped as its own follow-up rather than bundled here, to avoid the duplicate-parsing-logic risk identified in §4.
- **The duplicated `_AUTH_ENFORCED_ENVIRONMENTS` constant** (also present independently in `security/auth.py` and `config/settings.py`) is a pre-existing pattern in this codebase (both of those already existed before this fix), not a new duplication category introduced by F09 — but it is now present in three places instead of two. A future refactor could centralize this in a location importable by all three modules without circularity (e.g. a small shared constants module), but that is a structural change beyond F09's minimal-fix scope.

## 19. Final Conclusion

**F09 FIXED.**

`/ready` now includes an `"authentication"` readiness check that reports `ready=false` (HTTP 503 overall) whenever authentication is enforced (`production`/`staging`, mirroring `require_api_key`'s own environment-based enforcement predicate) and zero usable API keys are configured — verified for an explicitly empty key set, a whitespace-only key set, and a comma-only/empty-entries key set, all three correctly triggering `not_ready`. `development`/`test` environments remain unaffected, including the specific case of `AUTH_ENABLED=true` explicitly set in a bypassed environment, which was caught and corrected during implementation before finalizing. The fix was verified non-vacuously against the real repository file via `git stash`/`git stash pop` (10 of 14 new tests failed against the genuine pre-fix code with `AssertionError: no readiness check named 'authentication'`, then all 19 tests passed after restoring the fix), and the original audit's reproduction was re-run and now shows the required `200→503` transition with the protected endpoint remaining `401` throughout (no authentication bypass). `/health` is confirmed unaffected, and the configured-key control case is fully unchanged (825 passed total, up from 811, with zero unaddressed regressions — three pre-existing tests were updated as a necessary, in-scope consequence of the approved readiness-contract change). Ruff and Mypy show no new issues. F01–F08 files, Docker configuration, and dependency locking are all confirmed unchanged. No commit or push was performed.
