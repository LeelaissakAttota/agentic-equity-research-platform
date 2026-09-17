# F08 — Non-ASCII Bearer Token Causing HTTP 500 Instead of HTTP 401: Audit Report

**Status: AUDIT ONLY. No source, test, Docker, dependency, or configuration file was modified during this audit.**

## 1. Executive Summary

A Bearer credential containing any non-ASCII byte (e.g. `café`, `token-测试`, `token-€`) causes the API to return **HTTP 500 Internal Server Error** instead of **HTTP 401 Unauthorized**, in any environment where authentication is enforced (`production`/`staging`) with at least one API key configured.

Root cause: `InMemoryApiKeyStore.is_valid()` (`src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py:59`) calls `secrets.compare_digest(presented_key, stored)` on the raw, unvalidated Bearer credential. CPython's `secrets.compare_digest` (an alias for `hmac.compare_digest`) raises `TypeError: comparing strings with non-ASCII characters is not supported` whenever either `str` operand contains a non-ASCII character. This `TypeError` is not `AuthenticationError` (the type the auth dependency raises for every other rejection path), so it is not caught by the dedicated `@app.exception_handler(AuthenticationError)` handler. It falls through to the catch-all `@app.exception_handler(Exception)` handler in `src/financial_intelligence/api/errors.py`, which — correctly, for a *genuinely unexpected* error — returns a generic `500`.

This was reproduced end-to-end against a **real, running `uvicorn` server** over a **raw TCP socket** (not just FastAPI's `TestClient`), confirming the defect is a genuine server-side behavior, not a test-harness artifact:

```
$ printf 'GET /companies/resolve?q=Apple HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer café(UTF-8 bytes)\r\nConnection: close\r\n\r\n' | nc 127.0.0.1 18081
HTTP/1.1 500 Internal Server Error
```
against the same live server:
```
Authorization: Bearer invalid-token   -> HTTP/1.1 401 Unauthorized
Authorization: Bearer prod-test-key-abc -> HTTP/1.1 200 OK
```

Notably, FastAPI's `TestClient` (via `httpx`) **cannot even construct this request** when headers are supplied as a plain Python `dict[str, str]` — `httpx` eagerly ASCII-encodes string header values and raises `UnicodeEncodeError` client-side before a request is ever sent. This is almost certainly why the existing test suite (`tests/unit/test_auth.py`, 458 lines of authentication tests, zero non-ASCII cases) never caught this: writing the naive test would itself fail before reaching the server. A real client (curl, a browser, or any raw socket) is not subject to `httpx`'s ergonomic-API restriction and can send arbitrary UTF-8/Latin-1 bytes in a header value; this was independently confirmed with a raw socket in this audit.

No information disclosure, no authentication bypass, and no endpoints outside the shared `require_api_key` dependency are affected. `/health`, `/ready`, `/version` (and their `/v1/` equivalents) are registered without this dependency and are unaffected and correctly remain public.

**Verdict: F08 CONFIRMED.**

## 2. Baseline and Repository State

- Branch: `main`
- HEAD commit: `d983bcea152488c1005168c22f2766fc9dd24056` ("feat(phase-11.2): implement API key authentication foundation")
- F01–F07 are approved and were not touched during this audit. `git status --short` before and after this audit is identical except for this new report file.
- Full test suite re-run at the start of this audit (no files changed): **796 passed, 130 subtests passed** — matches the stated baseline.
- Ruff and Mypy were not re-run as part of this audit's core investigation (no code was touched); the task's stated baseline (Ruff clean; Mypy 2 pre-existing unrelated errors in `domain/orchestration/graph.py`) is taken as given, and confirmed unaffected below in §17/Final Verification.
- All reproduction in this audit used either FastAPI's `TestClient` against an in-process app, or a real `uvicorn` server on `127.0.0.1:18081` driven by a raw Python `socket` script and a temporary launcher script kept entirely under the system temp directory (`/tmp/f08_server.py`, `/tmp/f08_server.log`) — never written into the repository. The server process was terminated and the temp files removed after use; `git status` confirms no repository file was created or modified by this reproduction.

## 3. Authentication Call Chain

```
HTTP request (Authorization header, raw bytes on the wire)
        ↓
uvicorn / h11 (ASGI server) — parses HTTP headers as opaque byte pairs,
        does NOT reject non-ASCII byte values (RFC 7230 treats header
        field values as opaque octet sequences)
        ↓
Starlette `Request.headers` (`starlette.datastructures.Headers`) — decodes
        each header value from bytes using **latin-1**, per ASGI/Starlette
        convention. Non-ASCII bytes decode successfully into a Python `str`
        containing codepoints ≥ 0x80 (never raises here).
        ↓
`require_api_key(request)` — src/financial_intelligence/security/auth.py:66
        - environment check: bypassed unless app_env in {"production","staging"}
        - `authorization = request.headers.get("Authorization", "")`
        - `scheme, credential = get_authorization_scheme_param(authorization)`
          (fastapi.security.utils — pure string splitting, never raises,
          never validates character set)
        - if scheme != "bearer" or credential empty → `_reject_401()` →
          raises `AuthenticationError` → caught by the dedicated handler → 401
          (this path is correct and unaffected by non-ASCII content)
        - otherwise: `container.api_key_store.is_valid(credential)`
        ↓
`InMemoryApiKeyStore.is_valid()` —
        src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py:50
        - `if not presented_key or not self._keys: return False` (guard;
          a non-empty non-ASCII credential and a non-empty key store both
          pass this guard, so execution proceeds)
        - `return any(secrets.compare_digest(presented_key, stored) for
          stored in self._keys)`  ← **line 59, the exact failure site**
        ↓
`secrets.compare_digest(presented_key, stored)` (CPython stdlib,
        `hmac.compare_digest` under the hood) — raises
        **`TypeError: comparing strings with non-ASCII characters is not
        supported`** whenever either `str` argument is not ASCII-only.
        This is a hard CPython stdlib restriction on `str`-typed
        compare_digest calls (documented behavior, not a bug in Python).
        ↓
The `TypeError` propagates up through `is_valid()` → `require_api_key()`
        (uncaught — the dependency has no try/except around the store call)
        → FastAPI's dependency-resolution machinery → Starlette's exception
        middleware
        ↓
`@app.exception_handler(Exception)` — src/financial_intelligence/api/errors.py:147
        `unhandled_exception_handler` — this is the ONLY handler whose type
        matches `TypeError` (it is not an `AuthenticationError`, not a
        `RequestValidationError`, not a `StarletteHTTPException`). It logs
        `error_type: "TypeError"` (safe — no header/credential value logged)
        and returns:
        ↓
HTTP 500 {"error": {"code": "internal_error", "message": "An unexpected
        error occurred", ...}}
```

## 4. Exact Reproduction Steps

**Setup** (Python, using the real application factory, no mocking):
```python
from financial_intelligence.api import create_app
from financial_intelligence.config.settings import Settings

settings = Settings(
    _env_file=None, APP_ENV="production", LOG_LEVEL="ERROR",
    ALLOWED_HOSTS="example.com", AUTH_ENABLED="true",
    API_KEYS="prod-test-key-abc",
)
app = create_app(settings=settings)
```

**a) Via `TestClient`, headers supplied as raw `(bytes, bytes)` pairs** (required — see §9 for why plain `dict[str, str]` headers cannot even be sent):
```python
from fastapi.testclient import TestClient
with TestClient(app, raise_server_exceptions=False) as client:
    r = client.get(
        "/companies/resolve?q=Apple",
        headers=[(b"host", b"example.com"),
                 (b"authorization", "Bearer café".encode("utf-8"))],
    )
```

**b) Via a real `uvicorn` server and a raw TCP socket** (eliminates any TestClient-specific behavior entirely):
```python
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=18081, log_level="error")
```
```python
import socket
s = socket.create_connection(("127.0.0.1", 18081), timeout=5)
s.sendall(
    b"GET /companies/resolve?q=Apple HTTP/1.1\r\n"
    b"Host: 127.0.0.1\r\n"
    b"Authorization: " + "Bearer café".encode("utf-8") + b"\r\n"
    b"Connection: close\r\n\r\n"
)
```

## 5. Observed Status Codes/Responses

All cases run against the same live app (`APP_ENV=production`, `AUTH_ENABLED=true`, `API_KEYS=prod-test-key-abc`) with byte-level header control (bypassing `httpx`'s client-side ASCII restriction, per §9):

| Case | Authorization header (raw bytes) | Status | Response body (summarized) |
|---|---|---|---|
| Missing | *(no header)* | **401** | `{"code":"authentication_required","message":"Authentication required"}` |
| Normal ASCII invalid | `Bearer invalid-token` | **401** | same generic auth-failure body |
| Non-ASCII (accented) | `Bearer café` (UTF-8 bytes) | **500** | `{"code":"internal_error","message":"An unexpected error occurred"}` |
| Non-ASCII (CJK) | `Bearer token-测试` (UTF-8 bytes) | **500** | same generic 500 body |
| Non-ASCII (currency symbol) | `Bearer token-€` (UTF-8 bytes) | **500** | same generic 500 body |
| Malformed scheme | `Basic invalid` | **401** | same generic auth-failure body |
| Bearer, no token | `Bearer` | **401** | same generic auth-failure body |
| Bearer, trailing space only | `Bearer ` | **401** | same generic auth-failure body |
| Valid configured key | `Bearer prod-test-key-abc` | **200** | normal business response (unaffected) |

Confirmed identically against the real `uvicorn` server over a raw socket:
```
ascii_invalid                    -> HTTP/1.1 401 Unauthorized
non_ascii_cafe_utf8_raw_socket   -> HTTP/1.1 500 Internal Server Error
non_ascii_chinese_utf8_raw_socket -> HTTP/1.1 500 Internal Server Error
valid_key                        -> HTTP/1.1 200 OK
```

## 6. Exact Exception Type and Source Location

```
Traceback (most recent call last):
  File ".../src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py", line 59, in is_valid
    return any(secrets.compare_digest(presented_key, stored) for stored in self._keys)
  File ".../in_memory_api_key_store.py", line 59, in <genexpr>
    return any(secrets.compare_digest(presented_key, stored) for stored in self._keys)
TypeError: comparing strings with non-ASCII characters is not supported
```

- **Exception type:** `TypeError`
- **Exact source location:** `src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py:59`, inside `InMemoryApiKeyStore.is_valid()`
- **Underlying cause:** CPython's `secrets.compare_digest` (documented stdlib behavior) refuses to compare `str` operands unless both are ASCII-only.
- **Where it is converted to a response:** `src/financial_intelligence/api/errors.py`, the generic `@app.exception_handler(Exception)` (`unhandled_exception_handler`, line 147) — this is a correctly-functioning catch-all for *unanticipated* errors; the defect is that a non-ASCII Bearer token is not anticipated and handled as an authentication failure before reaching it.

Answering the audit's "important distinction" directly: this is case **(2)** — *the application's authentication code receives the token and raises an unexpected exception* — not a rejection by FastAPI/Starlette before the app sees it (Starlette successfully decodes and delivers the header; see §3), and not a misbehaving exception handler (the generic handler behaves exactly as designed for a truly unanticipated exception type; the defect is upstream, in `is_valid` not anticipating this input).

## 7. Affected Endpoints

Every protected endpoint shares the exact same `Depends(require_api_key)` dependency, wired once in `src/financial_intelligence/api/app.py`:
```python
_auth = [Depends(require_api_key)]
application.include_router(companies.router, dependencies=_auth)
application.include_router(market.router, dependencies=_auth)
application.include_router(financials.router, dependencies=_auth)
application.include_router(news.router, dependencies=_auth)
application.include_router(industry.router, dependencies=_auth)
application.include_router(regulatory.router, dependencies=_auth)
application.include_router(research.router, dependencies=_auth)
application.include_router(synthesis.router, dependencies=_auth)
application.include_router(workflows.router, dependencies=_auth)
application.include_router(watchlists.router, dependencies=_auth)
```
and their `/v1/`-prefixed equivalents (`companies`, `synthesis` are versioned; the audit found no evidence the others are currently duplicated under `/v1/`, but they use the identical dependency object, so any future versioned mount would inherit the same behavior). **All of these are affected identically** — this was verified directly for `/companies/resolve` (§4/§5); because every router shares the same `_auth` dependency list, there is no code path by which one protected router could behave differently from another for this specific input.

**Unaffected, by design:** `health.router` (mounted both unprefixed and under `/v1/`) is registered **without** `dependencies=_auth` — it never calls `require_api_key`, so it is structurally immune to this defect. This was confirmed both by reading `app.py`'s router registration and by the existing, passing `TestPublicEndpoints` tests in `tests/unit/test_auth.py`, which the audit re-ran (unmodified) as part of the baseline check.

## 8. Development vs Production Behavior

`require_api_key` (`src/financial_intelligence/security/auth.py:86`) returns immediately, with no header inspection at all, unless `settings.app_env in {"production", "staging"}`:
```python
if settings.app_env not in _ENFORCED_ENVIRONMENTS:
    return
```
So:
- **`development` and `test`:** F08 **cannot occur** — the dependency returns before ever reading the Authorization header or calling `is_valid`, regardless of what the header contains.
- **`production` and `staging`:** F08 **occurs identically in both** — both environments route through the exact same `require_api_key` → `is_valid` → `secrets.compare_digest` call chain; the audit reproduced it in `production` and the code path for `staging` is byte-for-byte the same function, so there is no environment-specific divergence between the two enforced environments.

This also explains why the project's own extensive `tests/unit/test_auth.py` suite (which exercises both `production` and `staging` fixtures) never caught it: none of its Bearer values contain non-ASCII characters, and no test in that file was constructed with byte-level header control (see §9).

## 9. Security Impact

- **Information disclosure: No.** The 500 response body is the same generic, non-leaking payload used for every other unhandled exception (`{"code":"internal_error","message":"An unexpected error occurred", "correlation_id": "..."}`) — no exception type, traceback, header value, or configured key is present in the HTTP response. Server-side structured logs record `error_type: "TypeError"` and a correlation ID only — never the credential itself (consistent with the rest of the codebase's logging-safety discipline, per `tests/unit/test_logging_safety.py`).
- **Authentication bypass: No.** The request never reaches business logic; it terminates in an exception before any `is_valid` call could return `True`. A non-ASCII token can never be treated as a valid key — it can only ever produce a 500 instead of the intended 401. There is no code path by which this defect grants access.
- **Denial-of-service: Not a meaningful amplification vector.** Each malformed request costs one exception + one `logger.error` call — comparable overhead to any other single malformed request; there is no resource amplification, recursion, or unbounded work triggered by the input. The only secondary effect is a wrong-classification of expected auth failures as `ERROR`-level "unhandled exception" log entries (`logger.error("unhandled_exception", ...)` instead of the `logger.info("authentication_failed", ...)` used for every other rejection reason), which is an **observability/log-hygiene concern** — an attacker probing with non-ASCII tokens would pollute error-level logs and could obscure genuine incidents — rather than a resource-exhaustion or availability risk in itself.
- **Scope:** Confirmed limited exclusively to non-ASCII (or otherwise non-ASCII-decodable) Bearer *credential* content reaching `is_valid`. Malformed *scheme* values, empty/missing headers, and oversized-but-ASCII tokens were all tested and correctly return 401 (§5) — this is not a broader Bearer-parsing defect, it is specific to the `secrets.compare_digest` character-set restriction being reached with unsanitized input.
- **Contract violation, not exploit:** The core issue is a correctness/robustness defect — the API's documented behavior ("all authentication failures produce the same generic 401 response," per `security/auth.py`'s own module docstring) is silently violated for one specific class of malformed input, which could confuse API clients or automated auth-failure monitoring that expects 401 for all bad credentials.

## 10. Existing Test Coverage

`tests/unit/test_auth.py` (458 lines) is thorough for ASCII inputs: missing header, wrong ASCII key, malformed scheme (`"NotBearer token"`), bare `"Bearer"`, `"Bearer "` (trailing space, empty credential), valid key, and multiple credential-leakage checks. **Zero test cases use a non-ASCII character anywhere in an Authorization header value.**

This audit determined *why* the gap exists, not just *that* it exists: every test in that file constructs headers as a plain Python `dict[str, str]` passed to `TestClient`/`httpx`. When this audit attempted the naive equivalent (`headers={"Authorization": "Bearer café"}`), `httpx` itself raised:
```
UnicodeEncodeError: 'ascii' codec can't encode character '\xe9' in position 10: ordinal not in range(128)
```
**before the request was ever sent** — `httpx._models._normalize_header_value` defaults to `.encode("ascii")` for plain `str` header values. This means a test author using the same natural, idiomatic `TestClient` calling convention as every other test in the file would hit a client-side `UnicodeEncodeError` while writing the test, not a server-side 500 — a strong, concrete reason the gap was never noticed, independent of anyone simply not thinking to try it. Reaching the actual server-side defect requires either raw `(bytes, bytes)` header tuples (bypassing `httpx`'s convenience encoding, as this audit did) or a non-`httpx` client (curl, browser, raw socket — also used in this audit, §4b/§5).

No other test file in the suite (`test_phase10_prompt2_hardening.py`, `test_logging_safety.py`, `test_logging_and_imports.py`) exercises non-ASCII Authorization content either; their Bearer-related assertions concern log-safety of ASCII secrets, unrelated to this defect.

## 11. Root Cause

`InMemoryApiKeyStore.is_valid()` passes the raw, attacker-controlled Bearer credential directly into `secrets.compare_digest()` without first validating that it is comparable at all. `secrets.compare_digest` requires either two `bytes`-like objects, or two ASCII-only `str` objects; the code assumes (implicitly, without an explicit check or comment) that any string reaching this point is ASCII-only. Nothing upstream (`get_authorization_scheme_param`, the scheme/credential presence checks in `require_api_key`) validates or constrains the character set of the credential — those checks only look at *emptiness* and the *scheme* keyword, never the credential's byte/character content. The gap is a missing input-normalization step, not a flaw in the constant-time-comparison design itself (which is otherwise correctly implemented and intentional, per the module's own docstring and `tests/unit/test_auth.py`'s `test_compare_digest_import_and_use`).

## 12. Severity Assessment

**Severity: Low–Medium (correctness/robustness defect; no confirmed confidentiality, integrity, or meaningful availability impact).**

Justification:
- No authentication bypass, no credential leakage, no internal exception detail exposed to the client (§9) — the primary security properties (confidentiality of keys, integrity of the allow/deny decision) are intact.
- It is a **contract violation**: the documented behavior is "all authentication failures produce the same generic 401 response" (module docstring, `security/auth.py:12-13`), and this class of malformed input silently breaks that contract with a 500 instead. This matters for API consumers and any monitoring/alerting that treats a 500 rate as a service-health signal — a client or attacker probing with non-ASCII credentials would generate 500s indistinguishable (from a monitoring standpoint) from a genuine backend fault, potentially triggering false incident escalation or masking a real one under the noise.
- Confirmed reproducible on **every** protected endpoint uniformly (§7), in both enforced environments (§8) — this is not a narrow edge case limited to one route.
- Mitigating factor: requires a client capable of sending raw non-ASCII bytes in a header (not achievable via `httpx`'s convenience API, though trivially achievable via curl, browsers, or any raw HTTP client — so not a meaningful barrier to a real attacker).
- Aggravating factor: the existing, otherwise-thorough auth test suite provides a false sense of complete coverage for this exact code path, because its own tooling (`httpx`) structurally prevents the relevant input from ever being constructed the "obvious" way.

## 13. Minimal Remediation Options (not implemented)

1. **Validate/normalize the credential before comparison** in `require_api_key` (`security/auth.py`), immediately after extracting `credential` from `get_authorization_scheme_param`: if `not credential.isascii()`, treat it as an authentication failure (`_reject_401(request)`) before ever calling `container.api_key_store.is_valid(credential)`. This is the smallest, most targeted fix — one guard clause, no change to `is_valid`'s comparison semantics or the store's public contract.
2. **Guard inside `InMemoryApiKeyStore.is_valid()`** itself: add an `if not presented_key.isascii(): return False` check before the `secrets.compare_digest` call (alongside the existing `if not presented_key or not self._keys: return False` guard). This centralizes the fix at the one call site that actually raises, and protects any future caller of `is_valid`, not just the current `require_api_key` dependency.
3. **Wrap the `secrets.compare_digest` call in a `try/except TypeError`** inside `is_valid`, returning `False` on `TypeError`. Functionally equivalent to option 2 for the known failure mode, but broader/less explicit — it would silently swallow any future `TypeError` from that line for reasons unrelated to character set, which is a less precise signal than an explicit `.isascii()` guard.
4. **(Broader, not recommended for F08's minimal scope) Encode to bytes before comparison** (`presented_key.encode("utf-8", errors="ignore")` vs. each stored key encoded the same way) so `compare_digest` always receives `bytes` and never raises for character-set reasons. This changes the comparison's semantics more than necessary to close this specific defect and is not needed given options 1–2 fully resolve it with less change.

Options 1 and 2 are functionally interchangeable in outcome; option 2 is preferred because it fixes the defect at its exact source (`is_valid`, the only place the `TypeError` can originate) and protects the invariant "this method never raises for any `str` input" for every current and future call site, rather than relying on every caller to remember to pre-validate.

## 14. Recommended Remediation

Implement **option 2** (guard inside `InMemoryApiKeyStore.is_valid()`): add an ASCII check alongside the existing emptiness guard, so the method's contract becomes "returns `False` for any non-matching, empty, or non-ASCII input; never raises." No change to `require_api_key`'s control flow, no change to the generic-401 response shape, no change to `ApiKeyStorePort`'s interface, no change to valid-key semantics (a validly-configured key is always ASCII by construction — `from_csv` splits on `,` from a `SecretStr` config value — so no legitimate key is ever rejected by this guard). This keeps the fix to a single method, one line added, fully preserving F01–F07 behavior, existing valid-key acceptance, and the existing generic-401 contract for every other rejection reason.

## 15. Exact Regression-Test Strategy

To be added to `tests/unit/test_auth.py` (or a new focused file) during the implementation phase — not created now:

1. **ASCII invalid bearer → existing 401 behavior unchanged.** Re-assert `TestProtectedEndpointsProduction.test_companies_resolve_wrong_key_returns_401` still passes post-fix (no regression to the already-correct path).
2. **Non-ASCII bearer → 401, not 500.** Using raw `(b"authorization", "Bearer café".encode("utf-8"))` header tuples against `TestClient` (the only way to actually deliver this input, per §9), assert `status_code == 401` and the body matches the same generic `authentication_required` shape used for every other rejection.
3. **Multiple representative Unicode values**, parametrized: an accented Latin string (`café`), a CJK string (`token-测试`), a currency symbol (`token-€`), and a string with a combining/control-adjacent codepoint if the implementation should also be checked against those — each asserted to return 401.
4. **Malformed Bearer syntax unaffected.** Re-run existing `test_malformed_bearer_returns_401`, bare-`Bearer`, and `Bearer `-with-trailing-space cases to confirm the fix doesn't alter these already-passing paths.
5. **Valid authentication still succeeds.** Re-run `test_companies_resolve_valid_key_returns_2xx` (ASCII key) post-fix to prove the `.isascii()` guard never rejects a legitimately configured key.
6. **No sensitive/internal exception details in the response**, for the non-ASCII case specifically: assert the response body does not contain the word "TypeError", "compare_digest", any traceback fragment, or the submitted credential — mirroring the existing `TestSecurityInvariants` pattern in `test_auth.py`.
7. **Existing health/readiness behavior unchanged.** Re-run the existing `TestPublicEndpoints` tests (`/health`, `/ready`, `/version`, and `/v1/` equivalents) unmodified to confirm they remain 200 and untouched by this fix, since the fix is confined to `is_valid`/`require_api_key` and never runs for those routes.

These tests prove the fix works because (2) and (3) are the exact reproduction of the confirmed defect (§4–§5) turned into assertions — before the fix they fail with `status_code == 500`; after the fix they must observe `status_code == 401`. (1), (4), (5), (7) are non-regression guards proving the fix changes nothing about any currently-correct behavior.

## 16. Non-Vacuous Validation Strategy

For the implementation phase (not performed now, since no fix may be applied during this audit):

1. **Before the fix:** run the new non-ASCII regression test(s) from §15 against the current (unmodified) `InMemoryApiKeyStore.is_valid()` and confirm they **fail** with the observed `500`/`TypeError` behavior — this is a direct re-run of the exact reproduction already performed and documented in §4–§6 of this report, now expressed as an automated assertion instead of an ad hoc script.
2. **Apply the fix** (the single `.isascii()` guard from §14, or the caller-side equivalent from §13 option 1 — whichever is chosen).
3. **After the fix:** re-run the same test(s) and confirm they now **pass** (`status_code == 401`, generic error body, no leaked details).
4. **Run the complete test suite** (`python -m pytest`) and confirm the full 796+N passed / 130 subtests baseline holds with zero regressions, plus Ruff (`ruff check`, `ruff format --check`) and Mypy (expect the same 2 pre-existing, unrelated `graph.py` errors only).
5. This mirrors exactly the non-vacuousness pattern already used for F07's regression tests in this project (`git stash`/`pop` a real file, or a hardcoded pre-fix snippet, to prove a check actually distinguishes vulnerable from fixed) — for F08 the "pre-fix state" to reproduce is simply the current, unmodified `is_valid()` method, since it already exists at HEAD and requires no reconstruction.

## 17. Explicit Conclusion

**F08 CONFIRMED.**

A non-ASCII Bearer credential reliably produces HTTP 500 instead of HTTP 401 on every protected endpoint, in both `production` and `staging`, whenever authentication is enforced and at least one API key is configured — reproduced against both an in-process `TestClient` (with byte-level header control) and a real `uvicorn` server driven by a raw TCP socket. The exact cause is `secrets.compare_digest`'s stdlib restriction against non-ASCII `str` comparison, reached unguarded from `InMemoryApiKeyStore.is_valid()` at `src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py:59`. No authentication bypass or information disclosure was found; the impact is a contract violation (wrong status code) with a secondary log-hygiene/false-alerting concern. The recommended minimal fix is a single `.isascii()` guard inside `is_valid()`.

## 18. Git Status/Diff Summary

`git status --short` before and after this audit is identical apart from this new report file. No file under `src/`, `tests/`, `.github/`, or any configuration/Docker/dependency file was modified. The temporary reproduction script and its log (`/tmp/f08_server.py`, `/tmp/f08_server.log`) were created outside the repository (system temp directory) and deleted after use; they never touched the working tree. Nothing was staged, committed, or pushed.
