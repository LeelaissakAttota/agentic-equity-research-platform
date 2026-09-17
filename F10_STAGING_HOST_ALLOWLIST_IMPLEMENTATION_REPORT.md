# F10 — Staging Host Allowlist Not Enforced: Implementation Report

**Scope: F10 only. F01–F09 untouched. No commit or push performed.**

## Executive Summary

`RequestSafetyMiddleware`'s host-allowlist enforcement was gated on `app_env == "production"` (exact string match), so `staging` — an environment `Settings` already requires to declare a real, non-wildcard `ALLOWED_HOSTS` at startup, identical to `production` — silently accepted every `Host` header. The fix changes the gate to a membership check against `{"production", "staging"}`, so enforcement now matches exactly the same pair of environments `Settings`'s own validator already treats as requiring a hardened host allowlist. `development`/`test` are unaffected — they were never subject to the strict-allowlist requirement and remain fully permissive.

## Root Cause

Three related pieces of code, two of which agreed and one of which didn't:

- `config/settings.py:213`: `if self.app_env in ("production", "staging"): ... if not allowed_hosts or "*" in allowed_hosts: raise ValueError(...)` — **requires** a real allowlist for both environments.
- `security/auth.py`'s `_ENFORCED_ENVIRONMENTS = frozenset({"production", "staging"})` — **enforces** API-key authentication for both environments (from F08's session).
- `api/app.py:72` (before this fix): `enforce_allowed_hosts=resolved_container.settings.app_env == "production"` — **enforced the host allowlist for `production` only**, disagreeing with the other two.

The middleware's `allowed_hosts` frozenset was always correctly populated from the validated configuration regardless of environment; only the boolean gate deciding whether to actually consult it was wrong for `staging`.

## Implementation

**File changed:** [src/financial_intelligence/api/app.py](src/financial_intelligence/api/app.py) only.

```python
# F10: environments in which Settings requires (and validates at startup) an
# explicit, non-wildcard ALLOWED_HOSTS (config/settings.py's model_validator
# uses this identical pair). Host-allowlist enforcement must match that same
# set, or a hardened-looking staging configuration silently goes unenforced.
_HOST_ENFORCEMENT_ENVIRONMENTS = frozenset({"production", "staging"})
```
and
```python
enforce_allowed_hosts=resolved_container.settings.app_env in _HOST_ENFORCEMENT_ENVIRONMENTS,
```
(previously `resolved_container.settings.app_env == "production"`).

**Design notes:**
- The host-validation algorithm itself (`RequestSafetyMiddleware.__call__`, `middleware.py`) was **not touched** — it remains the single, unmodified enforcement implementation, exactly as required. Only the boolean input to its existing `enforce_allowed_hosts` constructor parameter changed.
- `Settings` was **not touched** — its validator already correctly required `staging` to have a real allowlist; the fix only makes the middleware actually use that guarantee.
- A local module-level constant (`_HOST_ENFORCEMENT_ENVIRONMENTS`) was used rather than importing `security.auth`'s `_ENFORCED_ENVIRONMENTS`, consistent with the same constraint F09 encountered: `security/auth.py` imports `AppContainer`/composition-adjacent types and a cross-import back into `api/app.py` risks the same category of circularity F09's implementation report documented for `composition/__init__.py`. The literal pair is duplicated (a pattern already present at least twice in this codebase per F09's own implementation report), not invented.

## Tests

Added to [tests/unit/test_phase10_prompt1_production.py](tests/unit/test_phase10_prompt1_production.py) — the file that already contained the production host-allowlist tests this finding is the counterpart of:

- **New helper** `_staging_settings(**overrides)` — mirrors `_production_settings()`, with `APP_ENV="staging"`, a real `ALLOWED_HOSTS`, and a synthetic `API_KEYS` value (so `/ready`'s F09 authentication check doesn't interfere with a test that is about host enforcement, not readiness).
- `test_staging_host_allowlist_rejects_untrusted_host_with_safe_error` — **the critical F10 regression**: a spoofed `Host` header against a `staging` app must return `400 invalid_host` with the identical safe error contract (`X-Correlation-ID` echoed, `X-Content-Type-Options: nosniff`, no internal detail) that `production` already uses.
- `test_staging_allowed_host_is_accepted` — a `Host` header matching the configured allowlist is accepted (`200`) in `staging` — proves the fix doesn't over-reject legitimate staging traffic.
- `test_production_allowed_host_is_still_accepted` — non-regression: production's existing accept path for a matching `Host` is unchanged.
- `test_development_spoofed_host_remains_accepted` — non-regression: `development` (wildcard `ALLOWED_HOSTS`) remains fully permissive.
- `test_test_env_spoofed_host_remains_accepted` — non-regression: the `test` environment remains fully permissive.

Only synthetic values were used (`"trusted.example.com"`, `"staging.example.com"`, `"phase10-prompt1-staging-key"`); no real credential or host was referenced.

## Non-Vacuous Proof

Performed against the real repository file via `git stash`, exactly as required:

**Before this experiment:** all 22 tests in `test_phase10_prompt1_production.py` passed against the fix already in place.

**Step 1 — temporarily reproduce the vulnerable implementation:**
```
$ git stash push -- src/financial_intelligence/api/app.py
Saved working directory and index state WIP on main: d983bce ...
```
This restored `app.py` to its exact pre-fix HEAD content (`enforce_allowed_hosts=resolved_container.settings.app_env == "production"`, no `_HOST_ENFORCEMENT_ENVIRONMENTS`).

**Step 2 — run the F10-related tests against the vulnerable implementation:**
```
$ python -m pytest tests/unit/test_phase10_prompt1_production.py -v
...
FAILED tests/unit/test_phase10_prompt1_production.py::test_staging_host_allowlist_rejects_untrusted_host_with_safe_error
    AssertionError: assert 200 == 400
     +  where 200 = <Response [200 OK]>.status_code
1 failed, 21 passed in 2.34s
```
**Exactly 1 test failed against the genuine pre-fix code** — `test_staging_host_allowlist_rejects_untrusted_host_with_safe_error`, with the spoofed `Host` header incorrectly accepted (`200`) instead of rejected (`400`). All 21 other tests, including `test_staging_allowed_host_is_accepted` (which cannot distinguish enforced-vs-unenforced since the host already matches the allowlist either way) and every production/development/test-environment test, still passed — confirming the new critical regression test is precisely targeted at the defect and the rest of the suite is unaffected by the pre-fix state.

**Step 3 — restore the fix:**
```
$ git stash pop
... Dropped refs/stash@{0} ...
```

**Step 4 — re-run and confirm all tests pass again:**
```
$ python -m pytest tests/unit/test_phase10_prompt1_production.py -v
... 22 passed in 3.35s
```
`git status` after `stash pop` showed the working tree in the same fixed state as before the experiment, confirming no permanent alteration occurred.

## Original Reproduction: Before/After

Re-ran the audit's exact reproduction scenario against the fixed code (`ALLOWED_HOSTS="trusted.example.com"`, in-process `TestClient`, real `create_app`/`Settings` factories):

```
staging     (spoofed Host: evil.attacker.example) -> 400   (was 200 before the fix)
staging     (trusted Host: trusted.example.com)   -> 200   (unchanged)
production  (spoofed Host: evil.attacker.example) -> 400   (unchanged)
production  (trusted Host: trusted.example.com)   -> 200   (unchanged)
development (wildcard ALLOWED_HOSTS, spoofed Host)-> 200   (unchanged, intentional)
test        (default ALLOWED_HOSTS, spoofed Host) -> 200   (unchanged, intentional)
```
Every required post-fix outcome is confirmed: `staging` now rejects a spoofed host exactly like `production`; a configured allowed host continues to work in both `staging` and `production`; `development`/`test` behavior is unchanged.

## Security / Regression Checks

- **No authentication behavior changed.** `security/auth.py` (`require_api_key`, `_ENFORCED_ENVIRONMENTS`) was not touched. `tests/unit/test_auth.py` (81 combined with readiness tests) re-run: all pass unchanged.
- **No API-key behavior changed.** `infrastructure/auth/in_memory_api_key_store.py` (F08's fix) shows zero diff beyond its already-approved state.
- **`/health` unchanged.** Confirmed via the pre-existing `test_production_allowed_host_preserves_health_ready_version_distinction` and the new staging/development/test tests, all of which hit `/health` and observe unaffected behavior (only the host-enforcement gate around it changed, not the endpoint itself).
- **`/ready` unchanged.** `tests/unit/test_readiness_registry.py` (F09's authentication-readiness suite, 19 tests) re-run: all pass unchanged. `test_production_allowed_host_preserves_health_ready_version_distinction` also directly asserts `/ready`'s check contents are unaffected.
- **F09 authentication readiness behavior unchanged.** `composition/__init__.py` (F09's fix location) shows zero diff beyond its already-approved state.
- **F06 Docker loopback binding unchanged.** `docker-compose.yml` shows zero diff beyond its already-approved F06 state.
- **F07 dependency/lock behavior unchanged.** `Dockerfile` and `requirements-lock.txt` show zero diff beyond `Dockerfile`'s already-approved F07 state; `requirements-lock.txt` and `.github/workflows/ci.yml` show **zero diff at all**.
- **F08 non-ASCII Bearer behavior unchanged.** Covered by the `test_auth.py` re-run above; `in_memory_api_key_store.py` diff unchanged from its approved state.
- **No F01–F05 behavior changed.** None of those fixes' files (`domain/verification/*`, `application/manage_research_workflow.py`, `infrastructure/financial/*`, `infrastructure/orchestration/capability_executor.py`, `infrastructure/workflow/in_memory_store.py`) were touched by this implementation; their diffs are identical to their pre-existing, already-approved state.

No unrelated issue was discovered during this implementation that required documentation-and-stop; the change was fully contained to the single confirmed F10 defect.

## Validation

**Focused F10 tests:**
```
$ python -m pytest tests/unit/test_phase10_prompt1_production.py -v
22 passed in 1.68s
```

**Full test suite:**
```
$ python -m pytest -q
830 passed, 130 subtests passed (3 consecutive runs, ~23-71s each)
```
Baseline before F10 was 825 passed / 130 subtests; the 5 genuinely new F10 tests (`test_staging_host_allowlist_rejects_untrusted_host_with_safe_error`, `test_staging_allowed_host_is_accepted`, `test_production_allowed_host_is_still_accepted`, `test_development_spoofed_host_remains_accepted`, `test_test_env_spoofed_host_remains_accepted`) bring the total to 830 passed — **no existing test was replaced or had its assertion changed**; this is a pure, additive count increase. (One run showed a single flaky, non-reproducible `PytestUnhandledThreadExceptionWarning`, the same class of environment-level flakiness already documented in the F08/F09 implementation reports, with all 830 tests still passing in that run; two immediate re-runs showed zero warnings.)

**Ruff:**
```
$ python -m ruff check src tests
All checks passed!

$ python -m ruff format --check src tests
258 files already formatted
```

**Mypy:**
```
$ PYTHONPATH=src python -m mypy
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check ... [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check ... [comparison-overlap]
Found 2 errors in 1 file (checked 190 source files)
```
Identical to the documented pre-existing baseline (same file, same lines, same message). Not touched, not "fixed," as instructed.

## F01–F09 Safety

Confirmed via `git diff --stat` against every prior fix's file (§ Security/Regression Checks above): `Dockerfile` (F07), `docker-compose.yml` (F06), `requirements-lock.txt`/`.github/workflows/ci.yml` (F07), `infrastructure/auth/in_memory_api_key_store.py` (F08), `composition/__init__.py` (F09) all show either zero diff or exactly their already-approved diff from before this F10 session began. No F01–F09 source, test, or configuration file was modified by this implementation.

## Diff Scope

```
$ git status --short   (F10-attributable changes only, filtered from the full pre-existing F01-F09 baseline)
 M src/financial_intelligence/api/app.py                    <- NEW (F10 fix)
 M tests/unit/test_phase10_prompt1_production.py            <- NEW (F10 regression tests + staging helper)
?? F10_STAGING_HOST_ALLOWLIST_IMPLEMENTATION_REPORT.md      <- new (this report)
```
`git diff -- src/financial_intelligence/api/app.py` shown in full above (Implementation section). No other file's diff changed as a result of this implementation — every other entry in `git status --short` is the pre-existing, already-approved F01–F09 state (including `F10_STAGING_HOST_ALLOWLIST_NOT_ENFORCED_AUDIT_REPORT.md`, created during the prior, separate audit step). Nothing was staged, committed, or pushed.

## Final Verdict

**F10 IMPLEMENTATION COMPLETE**
