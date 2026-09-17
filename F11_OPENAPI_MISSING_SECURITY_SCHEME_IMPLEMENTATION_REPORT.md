# F11 — OpenAPI Missing Security Scheme: Implementation Report

**Scope: F11 only. F01–F10 untouched. No commit or push performed.**

## Executive Summary

The generated OpenAPI schema had no `components.securitySchemes` entry and no protected route carried a `security` requirement, even though `require_api_key` correctly enforces Bearer-token authentication at runtime. The fix declares a native `fastapi.security.HTTPBearer(auto_error=False)` dependency parameter inside `require_api_key`, which FastAPI's OpenAPI generator can discover — without changing any runtime authentication behavior. The schema now accurately describes the existing contract; the enforcement logic that decides pass/fail is byte-for-byte the same as before.

## Root Cause

FastAPI's OpenAPI generator derives `components.securitySchemes` and each operation's `security` list by statically inspecting a route's dependency graph for parameters whose **type** is one of `fastapi.security`'s recognized scheme classes (`HTTPBearer`, `HTTPBasic`, `APIKeyHeader`, `OAuth2PasswordBearer`, etc.). It has no mechanism to infer a security requirement from a dependency's *runtime behavior*. `require_api_key` (`security/auth.py`) took only a plain `Request` parameter and read `request.headers.get("Authorization", "")` manually — architecturally invisible to that generator, regardless of what it actually enforced.

## Implementation

**File changed:** [src/financial_intelligence/security/auth.py](src/financial_intelligence/security/auth.py) only.

**a) A module-level `HTTPBearer` instance**, declared once:
```python
_bearer_scheme = HTTPBearer(
    scheme_name="ApiKeyBearer",
    description="Opaque API key issued to the caller, presented as a Bearer token.",
    auto_error=False,
)
```

**b) `require_api_key` now takes the parsed credentials as a typed parameter:**
```python
async def require_api_key(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> None:
    ...
    if credentials is None or not credentials.credentials:
        _reject_401(request)
        return
    if not container.api_key_store.is_valid(credentials.credentials):
        _reject_401(request)
```

The manual `get_authorization_scheme_param(authorization)` call and its `if not authorization or scheme.lower() != "bearer" or not credential` guard were removed — that exact logic now lives inside `HTTPBearer.__call__` itself (FastAPI's own implementation uses the identical `get_authorization_scheme_param` utility internally), which returns `None` for precisely the same set of inputs the old manual check rejected.

## Runtime Compatibility

`auto_error=False` was the deliberate, non-negotiable choice specified in the task: it makes `HTTPBearer` parse the header and return `None` on any absence/malformed/wrong-scheme header instead of raising its own `HTTPException` — so `require_api_key`'s own logic remains the single authority that decides the final outcome and produces the existing generic `AuthenticationError` → 401 response. Concretely, `HTTPBearer(auto_error=False).__call__` returns `None` when:
- the header is absent,
- there is no space-separated scheme/credential pair,
- the credential part is empty, or
- the scheme is not (case-insensitively) `"bearer"`,

and otherwise returns `HTTPAuthorizationCredentials(scheme=..., credentials=<token>)` — the exact same partition this dependency used to perform by hand. Every prior rejection reason therefore still funnels through `credentials is None or not credentials.credentials` → `_reject_401(request)` → the unchanged `AuthenticationError` handler, and every prior success path still funnels through `container.api_key_store.is_valid(credentials.credentials)` — F08's `.isascii()` guard inside `is_valid` was not touched and still applies identically to `credentials.credentials` as it did to the old `credential` variable.

## OpenAPI Before/After

Fetched from the real `create_app()` factory (`production` settings, in-process, not a hand-built fixture):

| | Before | After |
|---|---|---|
| `components.securitySchemes` | *(absent)* | `{"ApiKeyBearer": {"type": "http", "description": "...", "scheme": "bearer"}}` |
| `/companies/resolve` `security` | `None` | `[{"ApiKeyBearer": []}]` |
| `/market/snapshot` `security` | `None` | `[{"ApiKeyBearer": []}]` |
| `/research/plans` (POST) `security` | `None` | `[{"ApiKeyBearer": []}]` |
| `/health` `security` | `None` | `None` (unchanged — correctly still public) |
| `/ready`, `/version` `security` | `None` | `None` (unchanged) |
| `GET /openapi.json` (unauthenticated) | `200`, no `securitySchemes` | `200`, `securitySchemes` present |

## Regression Tests

New file: [tests/unit/test_openapi_security_contract.py](tests/unit/test_openapi_security_contract.py) (12 tests):

**`OpenApiSecuritySchemeTests`** (schema-shape assertions against the real generated schema):
1. `test_security_schemes_are_present`
2. `test_bearer_http_scheme_is_declared`
3. `test_companies_resolve_requires_the_bearer_scheme`
4. `test_market_snapshot_also_requires_the_bearer_scheme` (a second protected route)
5. `test_research_plans_post_also_requires_the_bearer_scheme` (a third protected route, POST method)
6. `test_health_remains_public_with_no_security_requirement`
7. `test_ready_and_version_remain_public_with_no_security_requirement`
8. `test_openapi_json_is_served_and_matches_the_in_process_schema` (confirms the fix is visible through the real HTTP boundary, not just `app.openapi()`)

**`OpenApiFixDoesNotAlterRuntimeAuthenticationTests`** (co-located runtime proof that the schema fix didn't change enforcement):
9. `test_missing_credentials_still_returns_401`
10. `test_invalid_credentials_still_return_401`
11. `test_valid_credentials_still_succeed`
12. `test_health_remains_publicly_accessible`

**No existing test was deleted or weakened.** `tests/unit/test_auth.py` (62 tests, including all F08 non-ASCII cases and `test_research_workflows.py`'s pre-existing `test_openapi_includes_workflow_paths`) is unmodified and re-confirmed passing.

## Non-Vacuous Proof

Performed against the real repository file via `git stash`, exactly as required — and re-verified against the final, ruff-clean version of the fix (the parameter style was adjusted once during implementation to satisfy Ruff's `B008`, §Full Validation; the proof below is the final, accurate result):

**Step 1 — the fix already in place, tests pass:**
```
$ python -m pytest tests/unit/test_openapi_security_contract.py -v
12 passed
```

**Step 2 — temporarily reproduce the vulnerable implementation:**
```
$ git stash push -- src/financial_intelligence/security/auth.py
Saved working directory and index state WIP on main: d983bce ...
```
Confirmed via `grep` that this restored the exact pre-fix content (`get_authorization_scheme_param` import and manual header-parsing logic back in place).

**Step 3 — run the F11 tests against the vulnerable implementation:**
```
$ python -m pytest tests/unit/test_openapi_security_contract.py -v
...
FAILED tests/unit/test_openapi_security_contract.py::OpenApiSecuritySchemeTests::test_bearer_http_scheme_is_declared
FAILED tests/unit/test_openapi_security_contract.py::OpenApiSecuritySchemeTests::test_companies_resolve_requires_the_bearer_scheme
FAILED tests/unit/test_openapi_security_contract.py::OpenApiSecuritySchemeTests::test_market_snapshot_also_requires_the_bearer_scheme
FAILED tests/unit/test_openapi_security_contract.py::OpenApiSecuritySchemeTests::test_openapi_json_is_served_and_matches_the_in_process_schema
FAILED tests/unit/test_openapi_security_contract.py::OpenApiSecuritySchemeTests::test_research_plans_post_also_requires_the_bearer_scheme
FAILED tests/unit/test_openapi_security_contract.py::OpenApiSecuritySchemeTests::test_security_schemes_are_present
6 failed, 6 passed in 4.23s
```
**Exactly 6 of the 12 tests failed** against the genuine pre-fix code — every test asserting `securitySchemes` presence or a protected route's `security` requirement. The remaining 6 tests (`test_health_remains_public_with_no_security_requirement`, `test_ready_and_version_remain_public_with_no_security_requirement`, and all 4 of `OpenApiFixDoesNotAlterRuntimeAuthenticationTests`) correctly still passed against the pre-fix code, because the runtime authentication decision and the public-route behavior were never broken by F11 — this confirms the new tests are precisely targeted at the schema defect, not incidentally coupled to unrelated behavior.

**Step 4 — restore the fix:**
```
$ git stash pop
... Dropped refs/stash@{0} ...
```

**Step 5 — re-run and confirm all pass again:**
```
$ python -m pytest tests/unit/test_openapi_security_contract.py -q
12 passed
```
`git status` after `stash pop` showed the working tree in the same fixed state as before the experiment.

## F08 Compatibility

Ran the full `tests/unit/test_auth.py` suite (62 tests) unmodified alongside the new F11 tests — **74 passed, 0 failed**. Specifically confirmed for F08's own scenarios:
- `TestNonAsciiBearerToken::test_ascii_invalid_bearer_returns_401` — passes (401, unchanged).
- `TestNonAsciiBearerToken::test_non_ascii_accented_bearer_returns_401_not_500` (`café`) — passes (401, not 500).
- `TestNonAsciiBearerToken::test_non_ascii_cjk_bearer_returns_401_not_500` (`token-测试`) — passes.
- `TestNonAsciiBearerToken::test_non_ascii_currency_symbol_bearer_returns_401_not_500` (`token-€`) — passes.
- `TestNonAsciiBearerToken::test_ascii_valid_bearer_succeeds` — passes (existing success behavior, unchanged).
- All `TestNonAsciiBearerAtStoreLevel` unit-level tests (directly against `InMemoryApiKeyStore.is_valid`, unaffected by this change since `is_valid` itself was not touched) — pass.

F08's fix (`infrastructure/auth/in_memory_api_key_store.py`'s `.isascii()` guard) was not modified and continues to receive the exact same `credentials.credentials` string F11's new `HTTPBearer`-based parsing produces, which is identical in content to the old manually-parsed `credential` variable for every input tested.

## Full Validation

**Focused F11 tests:**
```
$ python -m pytest tests/unit/test_openapi_security_contract.py -v
12 passed in 2.63s
```

**F11 + F08 authentication tests together:**
```
$ python -m pytest tests/unit/test_openapi_security_contract.py tests/unit/test_auth.py -q
74 passed in 3.33s
```

**Full test suite:**
```
$ python -m pytest -q
842 passed, 130 subtests passed (3 consecutive runs, ~19-62s each)
```
Baseline before F11 was 830 passed / 130 subtests; the 12 genuinely new F11 tests bring the total to 842 — a pure additive count increase, no existing test was replaced or altered. (One run showed the same class of flaky, non-reproducible `PytestUnhandledThreadExceptionWarning` already documented in the F08/F09/F10 implementation reports — environment-level thread-teardown flakiness, unrelated to this change; all 842 tests still passed in that run, and two immediate re-runs showed zero warnings.)

**Ruff:**
```
$ python -m ruff check src tests
All checks passed!

$ python -m ruff format --check src tests
259 files already formatted
```
(An initial pass flagged two issues, both fixed without changing behavior: `B008` on the first-draft `= Depends(_bearer_scheme)` default-argument form in `security/auth.py` — resolved by switching to the `Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]` style, which is Ruff/bugbear's accepted modern-FastAPI idiom and produces identical runtime and OpenAPI behavior, re-verified after the change; and one `E501` line-length finding in the new test file, fixed by shortening an assertion message.)

**Mypy:**
```
$ PYTHONPATH=src python -m mypy
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check ... [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check ... [comparison-overlap]
Found 2 errors in 1 file (checked 190 source files)
```
Identical to the documented pre-existing baseline. Not touched, not "fixed."

## F01–F10 Regression Safety

- **F01** (numeric evidence verification): `src/financial_intelligence/domain/verification/*` files untouched by this implementation; their diffs are identical to their pre-existing, already-approved state.
- **F02** (verification semantics): same files, same confirmation.
- **F03** (workflow cancellation race): `application/manage_research_workflow.py`, `infrastructure/workflow/in_memory_store.py` untouched by this implementation; diffs unchanged from pre-existing approved state.
- **F04** (exception leakage): `infrastructure/orchestration/capability_executor.py` untouched; diff unchanged.
- **F05** (SEC filing-date provenance): `infrastructure/financial/*` untouched; diffs unchanged.
- **F06** (Docker loopback binding): `docker-compose.yml` shows zero diff beyond its already-approved F06 state.
- **F07** (dependency/lock behavior): `Dockerfile` shows zero diff beyond its already-approved F07 state; `requirements-lock.txt` and `.github/workflows/ci.yml` show zero diff at all.
- **F08** (non-ASCII Bearer handling): `infrastructure/auth/in_memory_api_key_store.py` shows zero diff beyond its already-approved F08 state; confirmed behaviorally unchanged above.
- **F09** (authentication readiness): `composition/__init__.py` shows zero diff beyond its already-approved F09 state; `tests/unit/test_readiness_registry.py` was not re-run in this session's validation pass but is included in the full-suite run (842 passed) with no failures.
- **F10** (staging host allowlist enforcement): `api/app.py` shows zero diff beyond its already-approved F10 state (the `_HOST_ENFORCEMENT_ENVIRONMENTS` constant and its usage are untouched); this implementation's runtime checks used `production`/`staging` settings with a matching `Host` header throughout, never exercising the host-rejection path, and did not modify `app.py`.

`git diff -- src/financial_intelligence/security/auth.py` (shown in full in the Implementation section) is the only source change; `tests/unit/test_openapi_security_contract.py` is the only new test file. No unrelated file was modified.

## Diff Scope

```
$ git status --short   (F11-attributable changes only, filtered from the full pre-existing F01-F10 baseline)
 M src/financial_intelligence/security/auth.py            <- NEW (F11 fix)
?? tests/unit/test_openapi_security_contract.py           <- NEW (F11 regression tests)
?? F11_OPENAPI_MISSING_SECURITY_SCHEME_IMPLEMENTATION_REPORT.md   <- new (this report)
```
Every other entry in `git status --short` is the pre-existing, already-approved F01–F10 state (including `F11_OPENAPI_MISSING_SECURITY_SCHEME_AUDIT_REPORT.md`, created during the prior, separate audit step). Nothing was staged, committed, or pushed.

## Final Verdict

**F11 IMPLEMENTATION COMPLETE**
