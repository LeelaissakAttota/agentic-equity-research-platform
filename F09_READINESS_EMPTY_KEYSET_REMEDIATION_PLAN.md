# F09 — Readiness Ignores Empty API-Key Set: Audit Report

**Status: AUDIT ONLY. No source, test, Docker, dependency, or configuration file was modified during this audit.**

## 1. Executive Summary

In `production` and `staging` — the only environments where API-key authentication is enforced — the `/ready` endpoint reports `status: "ready"` (HTTP 200) even when **zero usable API keys are configured**. In this state, `require_api_key` will reject every single request to every protected endpoint with 401, because `InMemoryApiKeyStore.is_valid()` returns `False` unconditionally whenever its key set is empty. Readiness gives no signal of this: its only two registered checks (`"application"` and `"configuration"`) are hardcoded `ready=True` constants that never inspect `container.api_key_store` at all.

This was independently reproduced in this audit: a `production`-configured app with `AUTH_ENABLED=true` and `API_KEYS=""` (also tested: unset, and whitespace/comma-only) returns `/ready` → `200 {"status": "ready", ...}`, while every request to a protected endpoint — including one presenting a Bearer token — returns `401 {"error": {"code": "authentication_required", ...}}`. `staging` behaves identically. `development`/`test` also report `ready=true` with zero keys, but this is **not** misleading there, because authentication is intentionally bypassed in those environments and protected endpoints genuinely are usable without any key.

`/ready` is not currently wired to any deployment gate in this repository: the Dockerfile's `HEALTHCHECK` and `docker-compose.yml` both target `/health` (not `/ready`), and no Kubernetes/orchestrator manifest exists in the repository. So today, in the current deployment model, nothing automated is misled by this signal — the risk is realized only if/when an external readiness-gated deployment (a load balancer, Kubernetes `readinessProbe`, etc.) is introduced and configured to consume `/ready`, per the project's own stated intent (`docs/development/README.md`: "`/ready` — foundation readiness"; `docs/operations/SLO.md`: "Readiness correctness | `/ready` returns ready only when registered required checks pass").

This is a genuine gap between the readiness endpoint's documented intent and its actual coverage — not a security vulnerability (no authentication bypass, no credential exposure), but an operational/observability defect that could mask a broken production deployment behind an all-green readiness signal.

**Verdict: F09 CONFIRMED.**

## 2. Baseline and Repository State

- Branch: `main`
- HEAD commit: `d983bcea152488c1005168c22f2766fc9dd24056`
- F01–F08 approved and untouched; `git status --short` before and after this audit is identical apart from this new report file.
- Full test suite re-run at the start of this audit (no files changed): **811 passed, 130 subtests passed** — matches the stated baseline.
- Ruff/Mypy were not re-run as part of this audit's core investigation (no code was touched); the stated baseline (Ruff clean; Mypy 2 pre-existing unrelated errors in `graph.py`) is taken as given and reconfirmed in Final Verification below.
- All reproduction used `TestClient` against in-process apps built via the real `create_app`/`Settings` factories — no mocking of the authentication or readiness subsystems. No files were created or modified in the repository during reproduction.
- **Prior documentation already anticipated this exact finding.** `DEFECT_REMEDIATION_PLAN.md` (an existing, untracked planning document already present at the start of this session, not authored by this audit) contains a detailed prior write-up of what it also labels "F09" with the same root cause and the same affected files. This audit treated that document as a lead to independently verify, not as a substitute for verification — every claim below was re-derived from the current repository state and re-reproduced live in this session (§5–§10), and the conclusions in this report stand on that independent evidence.

## 3. Readiness Call Chain

```
HTTP GET /ready  (and /v1/ready)
        ↓
src/financial_intelligence/api/routes/health.py:64  get_ready(request, response)
        - container = _container(request)
        - readiness = container.readiness.evaluate(container.metadata)
        - if not readiness.ready: response.status_code = 503  (else default 200)
        ↓
src/financial_intelligence/application/readiness.py:32  ReadinessRegistry.evaluate()
        - iterates registered probes in sorted name order
        - each probe is called; exceptions become a failed check
          (probe_error:<ExceptionType>); a name mismatch also fails
        - overall `ready = all(check.ready for check in checks)`
        ↓
Registered probes — src/financial_intelligence/composition/__init__.py:165-181
        (inside `build_container`, executed once at container construction,
        BEFORE `api_key_store` is even constructed at line 361):

        readiness.register("application", lambda: ReadinessCheckResult(
            name="application", ready=True,
            detail="application foundation loaded"))

        readiness.register("configuration", lambda: ReadinessCheckResult(
            name="configuration", ready=True,
            detail=f"{resolved.app_env}_configuration_validated"))

        Neither closure reads `resolved.auth_enabled`, `resolved.api_keys`,
        or `container.api_key_store.has_keys` (a property that already
        exists, in_memory_api_key_store.py:61-64, and is already unit-tested
        in isolation — just never connected to readiness).
        ↓
Both checks are unconditional `ready=True` constants → `all([True, True])`
        is always `True`, regardless of API-key configuration → /ready
        always reports "ready", 200, for every environment and every
        API-key configuration this audit tested.
```

Separately, and entirely independently: `require_api_key` (`security/auth.py`) → `InMemoryApiKeyStore.is_valid()` (`infrastructure/auth/in_memory_api_key_store.py:57`, `if not presented_key or not self._keys: return False`) — this is the code path that actually determines whether a request can authenticate, and it is never consulted by the readiness path above.

## 4. Readiness Contract/Semantics

Established from code, tests, and documentation (not assumed):

- **What `ready=true` officially means:** per `docs/development/README.md:43`, "`/ready` reports a non-secret `configuration` check. It does not claim PostgreSQL, Redis, providers, auth, rate limiting, or other deferred dependencies are ready." This is an important, explicit scoping statement — the project has already documented that `/ready` does **not** currently claim to cover authentication.
- **Which checks contribute:** exactly the two registered in `build_container` today — `"application"` and `"configuration"` — plus whatever any caller registers afterward (e.g. `test_readiness_registry.py`'s `test_http_ready_returns_503_when_probe_fails` dynamically registers a third probe to prove the mechanism works generically).
- **Is API-key configuration currently one of those checks?** No — confirmed by direct reading of `composition/__init__.py` and by reproduction (§5–§7): no probe reads `api_keys`/`api_key_store` state.
- **If not, should it logically be?** The project's own `docs/operations/SLO.md:11` states the intended contract: *"Readiness correctness | `/ready` returns ready only when registered required checks pass | Current application/configuration checks are tested. **Deployment dependencies must be registered when introduced.**"* Phase 11.2 introduced API-key authentication as a hard, fail-closed requirement for production/staging (`settings.py:220-225`, `AUTH_ENABLED=false` rejected at startup) without registering a corresponding readiness probe — this reads as an oversight relative to the project's own stated pattern, not a documented, deliberate exclusion. (The `docs/development/README.md:43` line above documents the *current* scope honestly, but does not assert this scope is *intended to stay that way* — it reads as an accurate-as-of-today disclaimer, not a design decision to permanently exclude auth from readiness.)
- **Does another startup/configuration validation already catch empty keys?** No. `Settings`'s `model_validator` (`settings.py:212-231`) validates `LOG_LEVEL != DEBUG`, a non-wildcard `ALLOWED_HOSTS`, and `auth_enabled` truthiness in production/staging — it does **not** validate that `api_keys` is non-empty when `auth_enabled=True`. This was independently confirmed: constructing `Settings(APP_ENV="production", AUTH_ENABLED="true", API_KEYS="")` raises no exception (§5, Scenario 2).
- **Is an empty key set considered valid configuration elsewhere?** Yes, by construction: `InMemoryApiKeyStore.from_csv("")` is explicitly documented to produce a valid, zero-key store (`in_memory_api_key_store.py:44-48`: *"The resulting store may contain zero keys if the input is blank... in that state `is_valid` always returns `False`"*) — the store's own design treats "configured with zero keys" as a legitimate, non-error state (correctly, for the store's own narrow contract), it is simply never cross-checked against `auth_enabled` anywhere in the readiness path.
- **Does `/ready` return HTTP 200 even when the app cannot authenticate protected requests?** Yes — confirmed directly (§5–§7).
- **Does anything in this deployment consume `/ready` as a gate?** No — see §11.

## 5. Exact Reproduction Steps

All scenarios built the real application via `create_app(settings=...)` and called it through `TestClient`, using only synthetic, non-secret key values.

```python
from fastapi.testclient import TestClient
from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings

# Scenario 1 — normal configured key
s1 = Settings(_env_file=None, APP_ENV="production", ALLOWED_HOSTS="example.com",
              AUTH_ENABLED="true", API_KEYS="real-key-1")

# Scenario 2 — explicit empty key set
s2 = Settings(_env_file=None, APP_ENV="production", ALLOWED_HOSTS="example.com",
              AUTH_ENABLED="true", API_KEYS="")

# Scenario 3 — whitespace/comma-only (functionally empty, syntactically present)
s3 = Settings(_env_file=None, APP_ENV="production", ALLOWED_HOSTS="example.com",
              AUTH_ENABLED="true", API_KEYS=" , , ")

# Scenario 4 — API_KEYS entirely unset (field default)
s4 = Settings(_env_file=None, APP_ENV="production", ALLOWED_HOSTS="example.com",
              AUTH_ENABLED="true")
```
For each, `create_app(settings=...)` then `client.get("/ready", headers={"HOST": "example.com"})`, and for Scenario 2, also a protected-endpoint call with and without a Bearer token.

## 6. Results for Configured Keys

**Scenario 1** (`API_KEYS="real-key-1"`):
```
GET /ready -> 200
{"status": "ready", "service": "agentic-financial-intelligence", "version": "1.0.0",
 "checks": [{"name": "application", "ready": true, "detail": "application foundation loaded"},
            {"name": "configuration", "ready": true, "detail": "production_configuration_validated"}]}
```
Correct and expected: one usable key is configured, protected endpoints authenticate successfully with it (already covered by `tests/unit/test_auth.py::TestProtectedEndpointsProduction::test_companies_resolve_valid_key_returns_2xx`), and readiness reporting "ready" matches actual usability.

## 7. Results for Empty Key Set

**Scenario 2** (`API_KEYS=""`) — the primary F09 reproduction:
```
GET /ready -> 200
{"status": "ready", "service": "agentic-financial-intelligence", "version": "1.0.0",
 "checks": [{"name": "application", "ready": true, "detail": "application foundation loaded"},
            {"name": "configuration", "ready": true, "detail": "production_configuration_validated"}]}
```
**Individual check result:** both `"application"` and `"configuration"` report `ready: true` — neither reflects the zero-key state. **Overall: `ready=true`, HTTP 200.**

Correlated protected-endpoint calls under the identical container:
```
GET /companies/resolve?q=Apple  (Authorization: Bearer anything-at-all) -> 401
  {"error": {"code": "authentication_required", "message": "Authentication required", ...}}
GET /companies/resolve?q=Apple  (no Authorization header)               -> 401
  {"error": {"code": "authentication_required", "message": "Authentication required", ...}}
```
**Every protected endpoint is completely unusable by any caller in this state — including one presenting a well-formed Bearer token — yet `/ready` reports `ready=true`.**

**Scenario 3** (`API_KEYS=" , , "`, whitespace/comma-only): identical result — `GET /ready -> 200, status: "ready"`. `from_csv` strips and discards all-blank tokens, producing the same zero-key store as Scenario 2; readiness cannot distinguish "empty string" from "string that reduces to nothing after parsing," which is correct given neither is checked at all.

## 8. Results for Missing Configuration

**Scenario 4** (`API_KEYS` field omitted entirely, using its declared default): `GET /ready -> 200, status: "ready"` — **byte-for-byte identical to Scenario 2.**

This is because `Settings.api_keys` has an explicit default of `Field(default=SecretStr(""), alias="API_KEYS")` (`settings.py:74`) — an unset `API_KEYS` environment variable and an explicitly empty `API_KEYS=""` produce the exact same `SecretStr("")` value at the `Settings` layer. **Missing configuration is not distinguishable from explicitly empty configuration anywhere in this codebase** — there is no tri-state (unset / empty / populated) representation to distinguish them. Both collapse to the same zero-key `InMemoryApiKeyStore` and the same misleading `ready=true` readiness result.

## 9. Environment-Specific Behavior

| Environment | `AUTH_ENABLED` enforcement | `/ready` with 0 keys | Protected endpoint with 0 keys | Misleading? |
|---|---|---|---|---|
| `development` | Bypassed (`require_api_key` returns immediately regardless of header/keys) | `ready=true` | **200** (business logic, auth bypassed) | **No** — readiness and actual usability agree |
| `test` | Bypassed (same as development) | `ready=true` | **200** (business logic, auth bypassed) | **No** — same reasoning |
| `staging` | Enforced (fail-closed; `AUTH_ENABLED=false` rejected at startup) | `ready=true` (confirmed by direct reproduction) | **401** for every caller | **Yes** |
| `production` | Enforced (identical to staging) | `ready=true` (confirmed by direct reproduction) | **401** for every caller | **Yes** |

This directly answers the audit's key distinction: the application does *not* intentionally allow "0 configured keys" as an acceptable production-ready state — it simply never checks for it. In `development`/`test`, `ready=true` with zero keys is correct and non-misleading, because authentication is bypassed there and the service genuinely is usable without any key — this is the intentional design already covered by `tests/unit/test_auth.py::TestAuthBypassInTestEnv`. The defect is confined to `production`/`staging`, where authentication is enforced but its prerequisite (at least one usable key) is never verified before declaring readiness.

## 10. Protected-Endpoint Correlation

Directly demonstrated in §7: under the identical `production` container with `API_KEYS=""`,
- `/ready` → `200`, `status: "ready"`
- `/companies/resolve` (any credential, or none) → `401`, `authentication_required`

This is the core operational concern: a readiness probe or load balancer checking only `/ready` would conclude the instance is healthy and route traffic to it, while every protected business endpoint — the actual product surface — is unconditionally unusable. `/health` and `/version` remain unaffected by this (they carry no readiness semantics and were not expected to reflect auth state).

## 11. Docker/Deployment Impact

- **`Dockerfile`'s `HEALTHCHECK`** (line 49-50) targets **`/health`**, not `/ready`:
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
  ```
  `/health` is documented as pure liveness ("Return process liveness without probing external systems," `health.py:54`) and correctly does not, and should not, reflect readiness/auth state. **Docker's own healthcheck is entirely unaffected by F09.**
- **`docker-compose.yml`** defines no separate healthcheck of its own and does not reference `/ready` anywhere.
- **No Kubernetes or other orchestrator manifest exists in this repository** (`grep -rl "readinessProbe|livenessProbe"` over the entire repo returned zero matches) — there is currently no `readinessProbe`-style consumer of `/ready` in this codebase at all.
- **CI** (`.github/workflows/ci.yml`) does not call `/ready` as a gate; it runs the test suite, which includes `/ready`'s own unit/integration tests, but does not use the live endpoint operationally.
- **Deployment documentation** (`docs/operations/RUNBOOK.md`, `docs/operations/DEPLOYMENT_EVIDENCE.md`, `docs/operations/SLO.md`) references `/ready` as part of a manual smoke-check sequence ("Check `/health`... `/ready`... `/version`...") and as a documented SLO target, but not as an automated deployment gate today. No production deployment currently exists (consistent with prior audits already on record in this repository, e.g. `docs/development/README.md:36`: "no Git tag or GitHub Release exists yet").

**Conclusion for this section:** `/ready` is not currently wired to any deployment gate in this repository. The defect is real and the signal is genuinely wrong, but its *current* blast radius is limited to whatever a human or external system chooses to do with that signal — nothing in-repo acts on it automatically today.

## 12. Existing Test Coverage

- `tests/unit/test_readiness_registry.py` (71 lines): thoroughly tests the `ReadinessRegistry` mechanism in isolation (sorted evaluation order, probe-exception handling, name-mismatch handling, and one live `TestClient` case proving a registered probe failure produces HTTP 503). **It never registers or tests an API-key-aware probe, and never constructs a container with an empty key set.**
- `tests/unit/test_auth.py`: tests `InMemoryApiKeyStore.has_keys` in isolation (`test_has_keys_false_when_empty`) and extensively tests authentication behavior, but **never calls `/ready`** and never correlates key configuration with readiness.
- No test anywhere in the suite builds a `production`/`staging` container with an empty or missing `API_KEYS` and asserts anything about `/ready`'s response.

**Why the gap exists:** the two test files each correctly and thoroughly cover their own subsystem (readiness-mechanism correctness; authentication-decision correctness) but there is no test that exercises the *seam* between them — i.e., no test treats "is the configured authentication state itself operable" as a readiness concern. This is a coverage gap at the integration boundary between two well-tested but siloed subsystems, not a case of a specific test being wrong.

## 13. Root Cause

`build_container()` (`composition/__init__.py`) registers exactly two readiness probes, both authored as unconditional `ready=True` constants, at the time API-key authentication (Phase 11.2) had presumably not yet been retrofitted into the readiness contract. Neither probe closes over `resolved.auth_enabled`, `resolved.api_keys`, or the later-constructed `api_key_store.has_keys`. Compounding this, `Settings`'s production/staging validator enforces `auth_enabled=True` but never enforces that `api_keys` is non-empty, so a syntactically valid, non-startup-rejecting configuration (`AUTH_ENABLED=true`, `API_KEYS=""`) can produce a running instance where authentication is enforced but structurally unsatisfiable by any caller — and nothing in the readiness path was ever built to notice.

## 14. Security/Operational Impact

- **Authentication bypass: None.** Every request without a valid key still correctly returns 401 (confirmed in §7) — the defect is a false-positive readiness *signal*, not a hole in the authentication *decision* itself. No credential or internal detail is exposed by this defect.
- **Can a production instance start with zero usable keys?** Yes, confirmed directly — `Settings` construction succeeds with no exception, and the resulting app starts and serves `/health`/`/ready`/`/version` normally.
- **Would load balancers/orchestrators consider it ready?** Only if one is configured to consume `/ready` — none currently exists in this repository (§11). If one were added in the future using the documented `/ready` contract, yes, it would be misled.
- **Would protected endpoints be unusable?** Yes, unconditionally, for every caller — confirmed in §7.
- **Does it cause traffic to be routed to an unusable instance?** Not today (no consumer exists), but it would under the deployment model the project's own documentation (`SLO.md`, `RUNBOOK.md`) describes as the intended use of `/ready`.
- **Is the problem limited to operational correctness?** Yes — this is an observability/operational defect (a broken deployment can appear healthy), not a confidentiality/integrity/availability compromise of data or credentials.
- **Is there a safer existing configuration validation path?** Yes — the `Settings.model_validator` (`settings.py:212-231`) is the existing, already-proven mechanism for fail-closed startup validation (it already rejects `AUTH_ENABLED=false` in production/staging); it does not currently extend that same fail-closed posture to "`AUTH_ENABLED=true` but zero usable keys," which is an equally broken configuration state, arguably more insidious because it doesn't fail loudly at startup at all.

## 15. Severity Assessment

**Severity: Medium** (operational/observability defect; no demonstrated security compromise; currently unreachable by any in-repo deployment gate).

Justification:
- **Affected environments:** `production` and `staging` only (confirmed identical behavior in both); `development`/`test` are unaffected because the same signal is not misleading there (auth is bypassed, so the service genuinely is usable — §9).
- **Affected deployment scenarios:** any future deployment that gates traffic on `/ready` (Kubernetes `readinessProbe`, a load balancer health check, an external monitoring rule) combined with a misconfiguration that leaves `API_KEYS` empty in production/staging. This is a plausible, realistic misconfiguration — omitting or blanking a secret-provisioning step is a common deployment mistake, and this project's own design makes that specific mistake silent at every layer (Settings doesn't reject it, readiness doesn't detect it).
- **Actual operational/security consequence, as demonstrated:** an all-green readiness signal on an instance where 100% of protected endpoints are unusable — a "looks up, is actually completely broken for its real purpose" state, which is exactly the kind of failure a readiness check exists to prevent.
- **Reachability in the current deployment model:** bounded. No Kubernetes manifest, no external load balancer config, and no CI/CD gate in this repository currently consumes `/ready` (§11); Docker's own `HEALTHCHECK` targets `/health`, which is unaffected. **No production deployment currently exists** (per the project's own release-status documentation). So today, this is a latent defect relative to the project's *documented intent* for `/ready`, not an active incident.
- Not rated higher because there is no authentication bypass, no data exposure, and no currently-active consumer that this defect actively misleads.
- Not rated lower because it directly contradicts the project's own stated readiness contract (`docs/operations/SLO.md`) and would be a genuine, hard-to-detect production incident risk the moment a readiness-gated deployment is introduced — which the project's roadmap (Phase 11+ auth work, per commit history) suggests is an active direction, not a hypothetical one.

## 16. Minimal Remediation Options (not implemented)

1. **Register an `"authentication"` (or similarly named) readiness probe** in `build_container()`, closing over `resolved.auth_enabled` and the constructed `api_key_store`: `ready=True` when `not resolved.auth_enabled` (development/test bypass — always trivially satisfied) or when `resolved.auth_enabled and api_key_store.has_keys`; `ready=False` when `resolved.auth_enabled and not api_key_store.has_keys`. This is the option the readiness registry was explicitly designed for (per its own docstring: "Collect named readiness probes without inventing future dependencies" and `SLO.md`'s "deployment dependencies must be registered when introduced") and requires no change to `Settings`, `require_api_key`, or the authentication decision path at all.
2. **Extend the existing `Settings.model_validator`** to reject `auth_enabled=True and not api_keys` in `production`/`staging` at startup (fail-closed, consistent with the existing `AUTH_ENABLED=false` rejection pattern at `settings.py:220-225`). This prevents the broken state from ever starting at all, rather than merely reporting it via `/ready`.
3. **Both together** (register the probe *and* harden settings validation): the settings-level check prevents the misconfiguration from ever running; the readiness probe provides defense-in-depth for any future path that could construct a container with a stale/mutated key store after startup (e.g., a hypothetical future key-rotation feature), and keeps the readiness contract honestly self-describing per `SLO.md`.

## 17. Recommended Remediation

Base decision on the evidence gathered: **both options are complementary, not competing** — but if only one must be chosen for a minimal fix, **option 1 (register a readiness probe) is the more directly responsive fix to F09 specifically**, because F09's finding is about `/ready`'s signal being wrong, not about whether the configuration should be rejected outright at a different layer. Recommend implementing option 1 as the primary fix (smallest, most targeted, and matches the existing registry's designed extension point), and flag option 2 as a strong complementary hardening measure worth doing at the same time or as an immediate follow-up, since it closes the same root cause one layer earlier and more assertively (fail-closed at startup rather than a runtime-queryable signal).

Either way, the fix must:
- Preserve `development`/`test` bypass behavior exactly (the new probe/check must be a no-op — trivially `ready=True` — whenever `auth_enabled` is `False`).
- Preserve the existing `"application"` and `"configuration"` checks unchanged.
- Preserve `/health` and `/version` behavior unchanged (they carry no readiness semantics and are out of scope).
- Preserve all existing authentication behavior (`require_api_key`, `is_valid`) unchanged — F09's fix is about the readiness *signal*, not the authentication *decision*.
- Not redesign `ReadinessRegistry`, `ApiKeyStorePort`, or the configuration system.

## 18. Exact Regression-Test Strategy

To be added during the implementation phase (not created now):

1. **Configured API keys → ready.** Build a `production` container with a non-empty `API_KEYS`; assert `/ready` returns `200`, `status: "ready"`, and (once added) the new check reports `ready: true`.
2. **Zero API keys, auth enabled → not ready.** Build a `production` (and separately `staging`) container with `API_KEYS=""`; assert `/ready` returns `503`, `status: "not_ready"`, and the new check specifically reports `ready: false` with a non-leaking detail string (no key values, no internal exception text).
3. **Missing key configuration.** Since §8 established this is indistinguishable from Scenario 2 at the `Settings` layer, this test is the same as #2 using an omitted `API_KEYS` field rather than an explicit empty string — asserting identical `503`/`not_ready` behavior, proving the fix closes both forms of the gap uniformly.
4. **Development/test bypass unchanged.** Build `development` and `test` containers with `API_KEYS=""`; assert `/ready` still returns `200`, `status: "ready"` (auth bypass must remain a genuine no-op for readiness, matching actual endpoint usability in those environments per §9).
5. **Readiness HTTP status/body.** Assert the exact status code (200 vs 503) and that the response JSON shape (`status`, `service`, `version`, `checks[]`) is unchanged in structure — only the new check's presence/value and the aggregate `status` differ.
6. **Individual readiness check result.** Assert the new check's `name` and `ready` fields directly (not just the aggregate `status`), so a future regression in just that one check is caught even if other checks compensate.
7. **Protected-endpoint correlation.** Under the same zero-key `production` container, assert a protected endpoint still returns `401` (unchanged) — proving the fix only changes the *signal*, not the *authentication decision* — and, ideally, assert this alongside the `/ready` call in the same test to keep the correlation explicit and regression-proof.
8. **Existing `/health` unchanged.** Re-run the existing `TestPublicEndpoints::test_health_no_key_production`-style assertions to confirm `/health` remains `200` and untouched by this fix (it never consults `readiness` at all, per `health.py:52-61`).

## 19. Non-Vacuous Validation Strategy

For the implementation phase (not performed now):

1. **Before the fix:** run the new "zero keys → not ready" test (#2 above) against the current, unmodified `build_container()` and confirm it **fails** — the current code returns `200`/`"ready"` where the test expects `503`/`"not_ready"`. This is a direct re-run of the exact reproduction already performed and documented in §7 of this report, now expressed as an automated assertion.
2. **Apply the fix** (the new readiness probe from §16/§17, and optionally the settings-validator hardening).
3. **After the fix:** re-run the same test and confirm it now **passes**.
4. **Run the complete test suite** (`python -m pytest`) and confirm the full 811+N passed / 130 subtests baseline holds with zero regressions, plus Ruff (`ruff check`, `ruff format --check`) and Mypy (expect the same 2 pre-existing, unrelated `graph.py` errors only).
5. This mirrors the same non-vacuousness pattern already used for F07 (`git stash`/`pop` a real file) and F08 (same technique, applied to `in_memory_api_key_store.py`) in this project — for F09, the "vulnerable state" to reproduce is simply the current, unmodified `build_container()` readiness registration, which already exists at HEAD and requires no reconstruction from a hardcoded snippet.

## 20. Explicit Conclusion

**F09 CONFIRMED.**

`/ready` reports `ready=true` in `production` and `staging` (the only environments that enforce authentication) even when zero usable API keys are configured — reproduced directly for an explicitly empty key set, a whitespace/comma-only key set, and an entirely unset key configuration (all three collapse to the same, indistinguishable, misleading result). Under the identical container, every protected endpoint correctly and consistently returns 401 for every caller, confirming there is no authentication bypass — only a false-positive readiness signal. `development`/`test` are correctly unaffected because authentication is intentionally bypassed there and the signal is not misleading. `/ready` is not currently consumed by any deployment gate in this repository (Docker's `HEALTHCHECK` uses `/health`; no Kubernetes manifest exists), which bounds today's real-world impact but does not change that the endpoint's behavior contradicts its own documented contract (`docs/operations/SLO.md`). Recommended fix: register a readiness probe that reflects `auth_enabled` + `api_key_store.has_keys`, optionally paired with hardening `Settings`'s existing production/staging validator to reject the same misconfiguration at startup.

## 21. Git Status/Diff Summary

`git status --short` before and after this audit is identical apart from this new report file. No file under `src/`, `tests/`, `.github/`, or any configuration/Docker/dependency file was modified. All reproduction was performed via in-process `TestClient` calls against the real application factories; no server process, container, or temporary file was created outside of ordinary Python process memory. Nothing was staged, committed, or pushed.
