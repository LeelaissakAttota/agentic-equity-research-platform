# F10 — Staging Validates a Host Allowlist But Never Enforces It: Audit Report

**Status: AUDIT ONLY. No source, test, Docker, dependency, or configuration file was modified during this audit.**

## 1. Executive Summary

**Finding:** `Settings`'s startup validator (`config/settings.py:212-219`) requires `staging` to declare an explicit, non-wildcard `ALLOWED_HOSTS` value — identical to the requirement it imposes on `production` — but the ASGI middleware that actually rejects requests with an untrusted `Host` header is wired up only for `production` (`api/app.py:72`: `enforce_allowed_hosts=resolved_container.settings.app_env == "production"`, a literal string-equality check that evaluates `False` for `"staging"`). The result: a `staging` deployment computes and stores a real host allowlist at startup, but `RequestSafetyMiddleware` never consults it, so **every** `Host` header is accepted in `staging`, exactly as if no allowlist existed at all.

**Severity:** Medium (a real, reproducible security-boundary defect — the deployed enforcement contradicts the validated configuration's own stated intent — currently latent because no `staging` deployment exists yet; a single-line root cause with clean regression-test coverage possible).

**Affected component:** `src/financial_intelligence/api/app.py` (`create_app`'s `RequestSafetyMiddleware` wiring), in the `staging` environment only.

This was reproduced directly: an identically-configured app (`ALLOWED_HOSTS="trusted.example.com"`) rejects a spoofed `Host: evil.attacker.example` header with `400 invalid_host` in `production`, but accepts the same spoofed request with `200 OK` in `staging`. `development`/`test` are unaffected by this finding — their permissive host handling is a separate, intentional, and already-documented design choice (`Settings` does not require a strict allowlist in those environments at all), not part of this defect.

## 2. Baseline

- **Branch:** `main`
- **HEAD:** `d983bcea152488c1005168c22f2766fc9dd24056`
- **Working tree:** unchanged throughout this audit; `git status --short` reports the same 55 pre-existing lines (the already-approved F01–F09 modified/untracked files) before and after.
- **Tests:** `825 passed, 130 subtests passed` — matches the stated baseline, re-confirmed at the start and end of this audit with zero repository changes in between.
- **Ruff:** `All checks passed!` (re-confirmed).
- **Mypy:** same 2 pre-existing, unrelated errors in `domain/orchestration/graph.py:149,152` (re-confirmed; this audit did not touch that file or anything near it).
- `git diff --stat -- src/financial_intelligence/api/app.py src/financial_intelligence/api/middleware.py` returns **empty** — both files are byte-identical to HEAD; neither has been touched by any F01–F09 fix. This finding is independent of all prior work in this session.

## 3. Root Cause

**File:** `src/financial_intelligence/api/app.py`, inside `create_app` (line 69-72):
```python
application.add_middleware(
    RequestSafetyMiddleware,
    max_body_bytes=resolved_container.settings.api_max_request_body_bytes,
    allowed_hosts=resolved_container.settings.allowed_host_values(),
    enforce_allowed_hosts=resolved_container.settings.app_env == "production",
)
```
`enforce_allowed_hosts` is computed via `app_env == "production"` — a single string-equality comparison against exactly one literal. It evaluates to `False` for every other value of `app_env`, including `"staging"`.

**Contrast with `Settings`'s own validator**, `src/financial_intelligence/config/settings.py:212-219`:
```python
allowed_hosts = self.allowed_host_values()
if self.app_env in ("production", "staging"):
    ...
    if not allowed_hosts or "*" in allowed_hosts:
        msg = "production ALLOWED_HOSTS must be an explicit non-wildcard allowlist"
        raise ValueError(msg)
```
This validator treats `production` and `staging` identically — both are forced to declare a real, non-wildcard `ALLOWED_HOSTS` at startup, or the process refuses to start (`ValidationError`). The two code paths disagree about which environments the allowlist requirement actually applies to: the validator says "production and staging," the middleware wiring says "production only."

**Where enforcement actually happens:** `src/financial_intelligence/api/middleware.py:88-105`, `RequestSafetyMiddleware.__call__`:
```python
if self.enforce_allowed_hosts:
    host_values = _header_values(scope, b"host")
    host = _host_without_port(host_values[0]) if len(host_values) == 1 else None
    if not host or host not in self.allowed_hosts:
        await self._reject(..., status_code=400, code="invalid_host", ...)
        return
```
The `allowed_hosts` frozenset is always correctly populated (from the validated `ALLOWED_HOSTS` value) regardless of environment — it is `self.enforce_allowed_hosts` (the boolean gate) that silently disables the entire check outside `production`.

## 4. Expected vs. Actual Behavior

| | Expected (per `Settings`'s own validation intent) | Actual (per `app.py:72`) |
|---|---|---|
| `production`, spoofed `Host` header | Rejected, `400 invalid_host` | Rejected, `400 invalid_host` ✅ |
| `staging`, spoofed `Host` header | Rejected, `400 invalid_host` (staging is validated identically to production) | **Accepted, `200 OK`** ❌ |
| `development`/`test`, spoofed `Host` header | No enforcement (intentional — `Settings` does not require a strict allowlist here at all) | Accepted, `200 OK` ✅ (correct, by design) |

The defect is specifically the `staging` row: `Settings` treats `staging` as a hardened, production-equivalent environment for this one control, but `app.py` treats it as an unhardened one — the two layers of the same feature disagree.

## 5. Reproduction

**Method:** direct, in-process `TestClient` calls against the real `create_app`/`Settings` factories (no mocking of the middleware or settings layer).

```python
from fastapi.testclient import TestClient
from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings

def probe(label, app_env):
    s = Settings(_env_file=None, LOG_LEVEL="INFO", APP_ENV=app_env,
                 ALLOWED_HOSTS="trusted.example.com", AUTH_ENABLED="true", API_KEYS="k1")
    app = create_app(settings=s)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/health", headers={"HOST": "evil.attacker.example"})
        print(label, "->", r.status_code, r.json() if r.status_code != 200 else "ACCEPTED")

probe("staging + spoofed Host", "staging")
probe("production + spoofed Host", "production")
```

**Observed output (this audit, this session):**
```
staging + spoofed Host    -> 200 ACCEPTED
production + spoofed Host -> 400 {'error': {'code': 'invalid_host', 'message': 'Request host is not allowed', ...}}
```

**Expected output** (per `Settings`'s own stated policy, which requires `staging` to have the identical non-wildcard allowlist requirement as `production`): both should return `400 invalid_host`.

**Control checks** (development/test, confirming their permissiveness is unrelated to this defect and by design):
```
development (ALLOWED_HOSTS="*", the documented default) + spoofed Host -> 200
test (ALLOWED_HOSTS="localhost,127.0.0.1", the documented default) + spoofed Host -> 200
```
Both are expected to be `200` — `Settings`'s validator only imposes the strict-allowlist *requirement* on `production`/`staging` in the first place, so there is no contradiction for `development`/`test`.

This directly and unambiguously demonstrates the defect: identical configuration, identical `ALLOWED_HOSTS` value, identical spoofed request — `production` correctly rejects it, `staging` does not.

## 6. Impact Analysis

- **Affected environments:** `staging` only. `production` is correctly enforced (unaffected). `development`/`test` are unaffected because they were never subject to this requirement to begin with.
- **Affected endpoints/components:** every route in the application — `RequestSafetyMiddleware` runs before route dispatch for all HTTP requests (`scope["type"] == "http"`), so this is a blanket, application-wide gap in `staging`, not limited to a subset of endpoints.
- **Security impact:** this is a **host-header validation control being silently inert** in an environment that is explicitly configured (and validated at startup) to have one. Host-header trust issues are a well-known class of vulnerability (e.g., cache poisoning, virtual-host confusion on shared infrastructure, bypassing host-based routing/segmentation assumptions) — while this codebase does not currently use the `Host` header for anything beyond this one check (confirmed: no route or business logic reads `request.headers["host"]` or builds URLs from it; the check exists purely as a defense-in-depth boundary), the control itself existing-but-disabled means `staging` provides **no actual verification that the production host-enforcement behavior works**, defeating the specific purpose staging serves for this control.
- **Correctness impact:** none beyond the security boundary itself — no business logic or data correctness is affected.
- **Reliability impact:** none.
- **Exploitability/reachability:** requires only an unauthenticated HTTP request with an arbitrary `Host` header reaching a `staging` deployment — no authentication is required to exploit this (it runs entirely in front of the authentication layer). It is reachable by any network client that can send a request to a `staging` instance.
- **Production relevance:** `production` itself is correctly protected — this finding does not affect `production` at all. Per the project's own release-status documentation (already established in prior F06/F07/F08/F09 audits during this session: "no Git tag or GitHub Release exists yet," no live production or staging deployment currently exists), **this defect is currently latent** — there is no live `staging` deployment today for an attacker to target. The risk is realized the moment a `staging` environment is stood up and exposed to any network path an attacker (or another tenant on shared infrastructure) can reach, which is a direction the project's own `docs/operations/` materials describe as an eventual goal.

## 7. Existing Test Coverage

- `tests/unit/test_phase10_prompt1_production.py`, `test_phase10_prompt2_hardening.py`, and `test_phase10_prompt3_acceptance.py` all test host-allowlist enforcement — but **exclusively against `_production_settings()`** (`APP_ENV="production"`). Grepping all three files for the literal string `"staging"` returns **zero matches**.
- The only test files in the entire suite that reference `staging` at all are `tests/unit/test_auth.py` (API-key authentication behavior, from F08's session) and `tests/unit/test_readiness_registry.py` (F09's new authentication-readiness probe) — neither constructs a request with a spoofed `Host` header; neither exercises `RequestSafetyMiddleware` at all.
- **Why the gap exists:** the host-enforcement test suite was authored and has only ever been extended against the `production` fixture; no test was ever written for `staging`'s host-enforcement behavior specifically, so the middleware's silent staging exemption has never been exercised by any assertion, positive or negative. This is consistent with the same category of gap identified in F09 (a well-tested subsystem in isolation — host enforcement, thoroughly tested for `production` — never cross-checked against a second environment that the configuration layer treats identically).

## 8. Recommended Remediation (plan only — not implemented)

**Design approach:** change the single condition at `api/app.py:72` from an exact-match string comparison against `"production"` to a membership check against the same environment set `Settings`'s own validator already uses (`{"production", "staging"}`), so the two layers of "which environments require a real host allowlist" agree by construction rather than by two independently-maintained literals.

```python
enforce_allowed_hosts=resolved_container.settings.app_env in {"production", "staging"},
```

(This exact `{"production", "staging"}` — or a set variable derived from it — already appears, independently duplicated, in at least three places in this codebase per this session's F09 implementation report: `security/auth.py`'s `_ENFORCED_ENVIRONMENTS`, `config/settings.py:213`'s validator condition, and F09's newly-added `composition/__init__.py`'s `_AUTH_ENFORCED_ENVIRONMENTS`. The F10 fix would be a fourth site reusing the same pair of literals. A future, separate refactor could consider centralizing this into one importable constant — flagged here as a related observation, not part of this audit's recommended minimal fix, and out of scope for a single-condition security fix.)

**Files likely to change:**
- `src/financial_intelligence/api/app.py` — the one-line condition change.
- A test file — either a new `tests/unit/test_request_safety_middleware.py` or an addition to one of the existing `test_phase10_prompt*` files that already tests this middleware against `production`, adding parallel `staging` coverage.

**Expected behavioral change:** `staging` deployments will begin rejecting requests with a `Host` header not present in their configured `ALLOWED_HOSTS`, with the same `400 invalid_host` response `production` already returns. `production`, `development`, and `test` behavior is unchanged.

**Regression tests to add** (at minimum):
1. `staging`, configured `ALLOWED_HOSTS`, spoofed `Host` header → `400 invalid_host` (the direct fix for this finding).
2. `staging`, configured `ALLOWED_HOSTS`, matching `Host` header → request proceeds normally (proves the fix doesn't over-reject legitimate staging traffic).
3. `production` behavior unchanged (re-run existing production host-rejection tests to confirm no regression).
4. `development`/`test` behavior unchanged (re-run existing tests confirming permissive host handling remains intact where `Settings` does not require a strict allowlist).
5. Response shape/safety: the `staging` rejection body matches the same safe, non-leaking `invalid_host` envelope already used in `production` (no internal detail exposure) — mirroring the existing `test_rejection_telemetry_contains_only_safe_boundary_metadata`-style assertions already present for `production`.

**Non-vacuous validation strategy:** identical pattern already used for F07/F08/F09 in this session — reproduce the pre-fix condition safely (e.g. `git stash`/`git stash pop` on `api/app.py`, or a hardcoded pre-fix string comparison in a throwaway check function), demonstrate the new `staging`-specific test fails against the genuine pre-fix code (`200` where `400` is expected), restore the fix, re-run and confirm it passes, then run the full suite to confirm zero regressions.

**Possible compatibility risks:** minimal. Any `staging` deployment that currently relies on being reachable via an arbitrary/unlisted `Host` header (e.g., a load balancer or CDN that doesn't rewrite the `Host` header to match `ALLOWED_HOSTS`) would start receiving `400` responses after this fix — this is the *correct*, intended behavior (matching `production`'s existing contract), but it means any such `staging` deployment's `ALLOWED_HOSTS` value would need to actually match its real inbound `Host` header, exactly as `production` already requires. Since `Settings` already validates a real, non-wildcard `ALLOWED_HOSTS` is configured for `staging` today (and rejects startup otherwise), any live `staging` deployment already has *a* value there — the fix only closes the gap between that stored value and what's actually enforced; it does not change what value is required.

## 9. Regression Safety

- `git status --short` before and after this audit is identical apart from this new report file.
- `git diff --stat -- src/financial_intelligence/api/app.py src/financial_intelligence/api/middleware.py` is empty — neither file (nor any other file touched by F01–F09) was modified during this audit.
- F01–F09 source fixes, Docker security changes (F06/F07), dependency-lock changes (F07), CI, and existing configuration changes are all untouched — confirmed via the same `git status`/`git diff` checks used at the close of every prior F0x audit in this session.
- The full test suite was re-run at the start and end of this audit with zero repository changes in between: **825 passed, 130 subtests passed**, matching the stated baseline exactly.
- Ruff and Mypy were re-confirmed clean/unchanged (§2).
- All reproduction in this audit used in-process `TestClient` calls against real application factories; no server process, container, or temporary file was created outside ordinary Python process memory.

## 10. Final Audit Verdict

**F10 FINDING CONFIRMED**
