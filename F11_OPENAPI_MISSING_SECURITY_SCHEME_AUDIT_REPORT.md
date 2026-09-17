# F11 — OpenAPI Schema Omits the Required Authentication Contract: Audit Report

**Status: AUDIT ONLY. No source, test, Docker, dependency, or configuration file was modified during this audit.**

## 1. Executive Summary

**Finding:** The application's generated OpenAPI schema (served publicly, unauthenticated, at `/openapi.json`) contains **no `components.securitySchemes` entry at all**, and **no protected route carries a `security` requirement** in its operation object — even though `require_api_key` genuinely and correctly enforces Bearer-token authentication at runtime for every one of those routes in `production`/`staging` (verified extensively across F08, F09, and F10's audits this session). The schema is architecturally incapable of describing this requirement because `require_api_key` (`security/auth.py:66`) is a plain `async def` dependency that reads `request.headers.get("Authorization", "")` directly (`security/auth.py:91`) rather than declaring one of FastAPI's `fastapi.security.*` scheme classes (e.g. `HTTPBearer`) as a parameter — and FastAPI's OpenAPI generator derives `securitySchemes`/`security` entries specifically by recognizing those parameter types, not by inspecting a dependency's runtime behavior.

**Severity:** Medium. This is **not** a runtime access-control gap — authentication enforcement itself is correct and unaffected (confirmed by direct execution below) — it is a self-description/API-contract accuracy defect: any OpenAPI-driven tooling (client/SDK generators, API gateways, automated security scanners, contract-testing tools) consuming `/openapi.json` would conclude, incorrectly, that every endpoint in this API — including the protected business endpoints — requires no credentials at all.

**Affected component:** `src/financial_intelligence/security/auth.py` (`require_api_key`'s dependency signature) and, by consequence, the OpenAPI schema FastAPI generates in `src/financial_intelligence/api/app.py`.

## 2. Baseline

- **Branch:** `main`
- **HEAD:** `d983bcea152488c1005168c22f2766fc9dd24056`
- **Working tree:** unchanged throughout this audit; `git status --short` reports the same 58 pre-existing lines (the already-approved F01–F10 modified/untracked files) before and after this audit — confirmed via a diff-count check at both the start and end of this session.
- **Tests:** `830 passed, 130 subtests passed` — matches the stated baseline, re-confirmed at the start of this audit with zero repository changes.
- **Ruff:** `All checks passed!` (re-confirmed).
- **Mypy:** same 2 pre-existing, unrelated errors in `domain/orchestration/graph.py:149,152` (re-confirmed).

## 3. Prior-Audit Cross-Check

`DEFECT_REMEDIATION_PLAN.md` (an existing planning document already present in the repository, not authored by this audit) independently labels this exact defect "F11 — OpenAPI omits the required authentication contract," citing the same two files and the same root-cause mechanism (a header-reading dependency invisible to FastAPI's OpenAPI generator).

This audit did **not** accept that prior citation at face value — it was independently re-verified against the current, live repository state in this session:
- Fetched the actual generated OpenAPI schema from a `production`-configured `create_app()` instance (not read from any cached/prior document) and confirmed `components.securitySchemes` is `None` and both a protected route (`/companies/resolve`) and the public `/health` route show `security: None` (§6).
- Re-read `require_api_key`'s current source directly (`security/auth.py:66-99`) and confirmed it is still a manual-header-reading `Request`-typed dependency, not a `fastapi.security` scheme object.
- Confirmed via `grep` across the entire `src/financial_intelligence` tree that no `openapi_extra`, `securitySchemes`, `OAuth2`, `HTTPBearer`, or `APIKeyHeader` reference exists anywhere — ruling out a manual schema patch elsewhere that might compensate for the generator gap.
- Confirmed this was **not fixed as a side effect of F08, F09, or F10** — none of those fixes touched `security/auth.py`'s dependency signature, `app.py`'s OpenAPI configuration, or added any schema patching; F08 modified only `infrastructure/auth/in_memory_api_key_store.py`, F09 modified only `composition/__init__.py`, and F10 modified only the host-allowlist condition in `app.py` (a different line, unrelated to OpenAPI).
- Confirmed the one previously-flagged "unverified" item from the prior document — whether an existing test (`test_openapi_includes_workflow_paths`) already asserts (incorrectly) that no security scheme is expected — is **not the case**: that test only asserts path-string presence (§7), so no existing test needs to be reconciled or contradicted by a future fix.

**Conclusion: independently confirmed, newly substantiated with fresh evidence this session (not merely re-cited), and not already fixed by F01–F10.**

## 4. Root Cause

**File:** `src/financial_intelligence/security/auth.py`, `require_api_key` (lines 66-99):
```python
async def require_api_key(request: Request) -> None:
    ...
    authorization: str = request.headers.get("Authorization", "")
    scheme, credential = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer" or not credential:
        _reject_401(request)
        return
    if not container.api_key_store.is_valid(credential):
        _reject_401(request)
```
This dependency takes a plain `fastapi.Request` parameter and manually parses the `Authorization` header itself. FastAPI's OpenAPI generator builds `components.securitySchemes` and each operation's `security` list by statically inspecting a route's dependency graph for parameters whose **type** is one of `fastapi.security`'s recognized scheme classes (e.g. `HTTPBearer`, `HTTPBasic`, `APIKeyHeader`, `OAuth2PasswordBearer`) — it has no mechanism to infer a security requirement from a dependency's *runtime behavior*, however correct that behavior is. Because `require_api_key` never declares such a parameter, it is structurally invisible to that generator, regardless of the fact that it is wired via `dependencies=_auth` (`api/app.py:84-98`) onto every protected router.

No compensating mechanism exists: `create_app` (`api/app.py`) sets `openapi_url="/openapi.json"` with no `openapi_extra` on the `FastAPI(...)` constructor, and no route or router in `src/financial_intelligence/api/routes/` was found to declare `openapi_extra={"security": [...]}` individually.

## 5. Expected vs. Actual Behavior

| | Expected (an API that correctly documents its own enforced contract) | Actual |
|---|---|---|
| `/openapi.json`, `components.securitySchemes` | A bearer/API-key scheme definition | `None` — key absent entirely |
| `/companies/resolve` (protected), `security` | `[{"<scheme-name>": []}]` | `None` |
| `/health` (public), `security` | `None` or `[]` (no requirement) | `None` (same as the protected route — no distinction) |
| Runtime behavior for a request without a valid key | `401 Unauthorized` | `401 Unauthorized` — **unchanged, correct** |

The gap is entirely in the schema's *description* of the contract, not in the contract's *enforcement*.

## 6. Reproduction

**Method:** direct, in-process execution against the real `create_app()`/`Settings` factories and FastAPI's own `app.openapi()` schema generator (no mocking).

```python
from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings

s = Settings(_env_file=None, APP_ENV="production", LOG_LEVEL="INFO",
             ALLOWED_HOSTS="api.example.com", AUTH_ENABLED="true", API_KEYS="k1")
app = create_app(settings=s)
schema = app.openapi()
print("securitySchemes:", schema.get("components", {}).get("securitySchemes"))
for p in ["/companies/resolve", "/health"]:
    for method, op in schema["paths"][p].items():
        print(p, method, "security=", op.get("security"))
```

**Observed output (this audit, this session):**
```
securitySchemes: None
/companies/resolve get security= None
/health get security= None
```

**Reachability confirmed:** the schema is served without authentication, even in `production`, via a plain `TestClient` request:
```python
from fastapi.testclient import TestClient
with TestClient(app) as c:
    r = c.get("/openapi.json", headers={"HOST": "api.example.com"})
    print(r.status_code, list(r.json().get("components", {}).keys()))
```
```
200 ['schemas']
```
`/openapi.json` returns `200` with no `Authorization` header supplied, and its `components` dict contains only `schemas` — no `securitySchemes` key at all. Any consumer fetching this schema (unauthenticated, by design — the schema itself is meant to be public) receives a document that describes `/companies/resolve` and `/health` identically with respect to authentication, despite one requiring a valid Bearer key in `production`/`staging` and the other never requiring one.

## 7. Existing Test Coverage

- `tests/unit/test_research_workflows.py::WorkflowApiTests::test_openapi_includes_workflow_paths` (line 444-454) is the only test in the suite matching a broad grep for `openapi()`/`securitySchemes`/`HTTPBearer` across all test files that actually calls `self.client.app.openapi()`. Reading it in full: it asserts only that a fixed list of workflow path strings appears in `schema["paths"]` — it makes **no assertion whatsoever about `security` or `securitySchemes`**, so it neither catches this defect nor would it need to be changed by a fix (confirmed directly, resolving the prior document's own "unverified" flag on this exact question).
- A broader grep for `securitySchemes|security_scheme|HTTPBearer|APIKeyHeader` across the entire `tests/` directory returned matches only in files that happen to also call `.openapi()` for unrelated reasons (contract-freeze tests checking path/schema presence for specific phases) — none of them assert anything about the security scheme.
- **Conclusion: zero existing test coverage for OpenAPI security-scheme accuracy anywhere in the suite.** The missing regression boundary is precisely: no test asserts that `components.securitySchemes` exists, that a representative protected path's operation carries a `security` requirement, or that a public path's operation does not.

## 8. Impact Analysis

**Confirmed behavior (this session's direct execution):**
- `/openapi.json` is served publicly (unauthenticated, `200`) in every environment, including `production`.
- It contains zero authentication metadata for any route.
- Runtime enforcement (`require_api_key` → 401 for missing/invalid keys) is completely unaffected and correct — this was independently re-verified across F08/F09/F10's audits this session and is not disturbed by this finding.

**Potential downstream impact (distinguished from confirmed behavior, per the audit's own instruction not to exaggerate):**
- Automated client/SDK generation tooling (e.g. `openapi-generator`, `swagger-codegen`) driven by this schema would generate a client that never attaches an `Authorization` header anywhere, because the schema gives it no basis to do so — such a generated client would fail every protected call in `production`/`staging` with 401s that its author would have no schema-level clue to expect.
- Automated API security/contract-testing tools that specifically check "does every non-public endpoint declare a security requirement" (a common API-governance control) would either report a false negative (concluding the API has no auth) or flag every endpoint as a policy violation, depending on the tool's default assumption for an absent `security` field.
- This does **not** itself expose data, weaken enforcement, or create a bypass — the actual HTTP boundary (`require_api_key`) is untouched by this defect and continues to reject unauthenticated/invalid requests exactly as before.

**Affected environments:** all (`development`, `test`, `staging`, `production`) — the schema-generation gap is environment-independent, since it stems from `require_api_key`'s Python-level signature, not from any environment-conditional wiring. The *practical* consequence (a generated client silently missing credentials) is naturally most relevant to `production`/`staging`, where authentication is actually enforced.

**Affected endpoints/components:** every protected router (`companies`, `market`, `financials`, `news`, `industry`, `regulatory`, `research`, `synthesis`, `workflows`, `watchlists`, and their `/v1/` aliases where present) — none of their operations carry a `security` requirement in the schema, identically to the public `health`/`version` routes.

**Exploitability/reachability:** this is not an exploitable vulnerability in the traditional sense (no authentication bypass, no data leakage beyond the schema's own intentionally-public path/parameter/response-shape metadata, which was already fully public before this finding). It is reachable by definition — the schema is served to anyone who requests it, in every environment, right now.

**Production relevance:** as with F09/F10, no live `production`/`staging` deployment currently exists per the project's own release-status documentation, so no external tooling is currently being misled by this in a live deployment today — but the defect is present in the schema any such deployment would serve starting from day one.

## 9. Severity

**Severity: Medium.**

Justification:
- Not a security-boundary failure (category 1 in the audit's priority list) in the traditional sense — no bypass, no leakage, no weakened enforcement. Ranked below F06/F08/F09/F10, which were genuine boundary/signal defects with a demonstrated wrong outcome at the HTTP layer.
- It is a genuine, independently-confirmed **architectural/self-description defect** (closer to category 10, "significant architectural defects that affect current behavior") with a concrete, demonstrated downstream consequence: any schema-driven tooling is actively misled about which endpoints require credentials, and the project's own test suite already treats OpenAPI path/schema accuracy as a thing worth asserting (`test_openapi_includes_workflow_paths` and multiple `test_phase*_contract_freeze.py` files), so this is not a cosmetic gap relative to the project's own stated quality bar.
- Not rated higher because runtime security is completely unaffected — this was proven, not assumed, in §6 and cross-checked against F08/F09/F10's independent runtime-enforcement verification this session.
- Not rated lower (e.g., Informational) because it has a concrete, demonstrable failure mode for real tooling (a generated client would systematically omit required credentials), not merely an aesthetic or documentation-nitpick concern.

## 10. Recommended Remediation (plan only — not implemented)

**Design approach:** wrap `require_api_key`'s existing header-extraction and validation logic behind a proper `fastapi.security.HTTPBearer` dependency, so FastAPI's OpenAPI generator recognizes it and emits the correct `securitySchemes`/`security` entries — without changing any observable runtime behavior (still 401 for missing/invalid/malformed/non-ASCII credentials, still bypassed in `development`/`test`, still the same generic error body).

Two implementation options, consistent with the prior document's own framing:

- **Option A (more idiomatic, more invasive):** declare an `HTTPBearer(auto_error=False)` instance as a dependency parameter inside `require_api_key` (or a thin wrapper around it), and use its returned `HTTPAuthorizationCredentials` in place of manually reading `request.headers.get("Authorization", "")`. `auto_error=False` preserves the existing behavior of routing every rejection reason (missing header, wrong scheme, empty credential, invalid key) through the same generic `AuthenticationError` → 401 path, rather than letting `HTTPBearer`'s own default error handling short-circuit that.
- **Option B (more contained, more fragile to FastAPI upgrades):** leave `require_api_key` entirely as-is, and instead patch the generated schema post-hoc — e.g. inside `install_openapi_version_policy` (`api/versioning.py`) or a new small hook called from `create_app` — by manually injecting a `securitySchemes` entry and adding a `security` requirement to each protected route's operation object, keyed off the same `_auth` dependency list already used for route wiring in `app.py`.

This audit does not select between them (that is an implementation-phase decision, as the prior document also noted), but recommends Option A as more maintainable long-term, since it keeps the security metadata and the enforcement logic co-located and self-consistent by construction, rather than requiring the schema patch to be kept in sync by hand every time a route's auth wiring changes.

**Files likely to change:**
- `src/financial_intelligence/security/auth.py` — `require_api_key`'s signature/implementation (Option A), or unchanged (Option B).
- `src/financial_intelligence/api/app.py` and/or `src/financial_intelligence/api/versioning.py` — wherever the schema-emitting change is anchored (Option B), or no change beyond what Option A's dependency swap already requires.
- A new or extended test file (e.g. `tests/unit/test_openapi_security_contract.py`, or an addition to `test_phase10_prompt3a_interfaces.py`/`test_research_workflows.py`).

**Expected behavior after remediation:**
- `/openapi.json`'s `components.securitySchemes` contains a bearer-scheme definition.
- Every protected route's operation object carries a `security` requirement referencing that scheme.
- `/health`, `/ready`, `/version` (and `/v1/` equivalents) carry **no** `security` requirement, matching their actual public status.
- All existing runtime authentication behavior (F08's non-ASCII handling, F09's readiness semantics, the generic-401 contract, development/test bypass) is unchanged — this is a schema-description fix, not a behavior fix.

**Regression tests to add (at minimum):**
1. `components.securitySchemes` exists and describes a bearer scheme.
2. A representative protected path (e.g. `/companies/resolve`) has a non-empty `security` requirement referencing that scheme.
3. The public paths (`/health`, `/ready`, `/version`) have no `security` requirement.
4. Runtime behavior is unchanged: re-run the existing `tests/unit/test_auth.py` suite (all environments, all rejection reasons, F08's non-ASCII cases) unmodified and confirm it still passes without alteration.
5. `test_openapi_includes_workflow_paths` still passes unmodified (proving the fix is additive to the schema, not disruptive to existing path-presence assertions).

**Non-vacuous validation strategy:** the same pattern already established across F07–F10 in this session — write the new schema-assertion tests, confirm they fail against the current (unmodified) `require_api_key`/schema-generation code (trivially true today, demonstrated in §6), apply the fix, confirm they pass, then run the full suite to confirm zero regressions elsewhere (particularly `test_auth.py`, since Option A touches the authentication dependency's signature even though not its behavior).

**Compatibility/regression risks:**
- Option A changes `require_api_key`'s parameter list, which — if not done carefully — could interact with how FastAPI resolves the dependency for routes that also declare other dependencies; this should be verified against every protected router, not just one, before considering the fix complete.
- If any external tooling or test already asserts the *absence* of a security scheme (this audit found none, §7), that would need to be reconciled, not silently overridden.
- Changing `require_api_key`'s exception-raising surface (e.g. if `HTTPBearer(auto_error=False)` is used incorrectly and `auto_error` is left `True` by mistake) could alter the response shape for malformed-scheme requests — the F08 non-ASCII regression suite and the broader `test_auth.py` suite would catch this if the implementation phase runs them, which the plan above already specifies.

## 11. Non-Vacuous Evidence

This audit independently demonstrated the finding is real by direct execution against the current, unmodified repository (§6), not by trusting the prior planning document's citation:
- Fetched the live-generated OpenAPI schema from a `production`-configured app and observed `securitySchemes: None` directly.
- Compared a protected route's `security` field against a public route's `security` field and found them identical (`None`/`None`) — the schema draws no distinction, which is the crux of the defect.
- Confirmed `/openapi.json` is served with `200` and no authentication required, establishing reachability.
- Re-read `require_api_key`'s current source directly and confirmed the manual-header-parsing mechanism that causes the generator gap is still present, unmodified, at HEAD `d983bce`.
- Confirmed via full-repository `grep` that no compensating schema patch exists anywhere.
- Read the one existing OpenAPI-related test in full and confirmed it does not cover (and would not need to be altered by a fix to) this specific gap.

No pre-fix/post-fix `git stash` experiment was applicable or necessary here, because no fix has been implemented in this repository to compare against — the defect is directly observable in the current, single state of the code (unlike F07–F10, where a "before" and "after" comparison required either a real prior build or a stash of an already-applied fix). This audit's evidence is the direct demonstration that the current, unmodified code lacks the schema metadata a correct implementation would have.

## 12. Regression Safety

- `git status --short` before and after this audit reports the identical 58 lines (the already-approved F01–F10 modified/untracked files) — confirmed via count comparison; the only addition is this new report file.
- `git diff --stat` against every prior fix's file was re-confirmed unchanged from its already-approved state: `Dockerfile` (F07), `docker-compose.yml` (F06), `requirements-lock.txt`/`.github/workflows/ci.yml` (F07, zero diff), `src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py` (F08), `src/financial_intelligence/composition/__init__.py` (F09), `src/financial_intelligence/api/app.py` (F10).
- **F06 Docker loopback binding:** unchanged (no `docker-compose.yml` inspection beyond the diff-count check was needed this audit, since no reproduction touched Docker at all).
- **F07 dependency/lock behavior:** unchanged (`requirements-lock.txt` and CI show zero diff; `Dockerfile`'s diff is exactly its already-approved F07 state).
- **F08 non-ASCII Bearer handling:** unchanged — `in_memory_api_key_store.py`'s diff is exactly its already-approved F08 state; this audit's reproduction never called `is_valid` with non-ASCII input.
- **F09 readiness/authentication behavior:** unchanged — `composition/__init__.py`'s diff is exactly its already-approved F09 state; this audit's reproduction did not call `/ready`.
- **F10 staging host allowlist enforcement:** unchanged — `api/app.py`'s diff is exactly its already-approved F10 state (the `_HOST_ENFORCEMENT_ENVIRONMENTS` constant and its usage); this audit's reproduction used `production` settings with a valid `Host` header throughout, never exercising the host-rejection path, and did not modify `app.py`.
- No unrelated issue requiring separate documentation was discovered during this audit; the investigation converged cleanly on the single finding above.
- All reproduction in this audit used in-process Python execution against the real application factories; no server process, container, or temporary file was created outside ordinary Python process memory.

## 13. Final Audit Verdict

**F11 FINDING CONFIRMED**
