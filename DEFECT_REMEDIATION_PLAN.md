# DEFECT REMEDIATION PLAN

**Source document:** [`PRODUCT_AUDIT_2026-09-15.md`](PRODUCT_AUDIT_2026-09-15.md)
**Verification date:** 2026-09-17 (second pass, independent)
**Verified against:** HEAD `d983bce` (unchanged since the source audit — `git status` confirms no tracked-file
changes since that report was written; only untracked docs, including this plan, have been added)
**Method:** Every finding below was re-derived by reading the exact cited file/lines in the current working tree
(not by trusting the prior report's text), cross-checked against the current test suite (`705 passed, 0 failed`,
re-run live during this pass), and, where a claim depended on Python runtime behavior (F08), confirmed with a
one-line read-only interpreter check (`secrets.compare_digest` with a non-ASCII argument — no application code
was run or modified).
**No source code was modified. No branch was changed. No commit was made. No package was installed** (the one
runtime check for F08 used only the already-installed standard-library `secrets` module via the project's
existing `.venv`).

---

## F01 — Numeric verification accepts non-numeric strings as "verified"; rejects numerically-equal values

**1. Exact issue:** The API accepts `expected_value`/`extracted_value` as `str | Decimal | datetime | None`. When
a value arrives as a plain JSON string (the normal case for any HTTP client), the finiteness guard only fires for
values that are Python `Decimal` instances — a string `"NaN"` or `"Infinity"` sails through it and is then compared
by plain string equality, so `"NaN" == "NaN"` is treated as a match and returned as **supporting** evidence.
Conversely, two values that are numerically identical but textually different (`"100"` vs `"100.0"`) fail the
string-equality check and are misclassified as **contradicting**.

**2. Affected file(s):**
- `src/financial_intelligence/domain/verification/evidence.py`
- `src/financial_intelligence/api/routes/synthesis.py`

**3. Affected function/class:**
- `EvidenceBundle._values_match` (static method), `evidence.py:196-238`
- `SynthesisClaimBody.expected_value` / `SynthesisEvidenceBody.extracted_value` field declarations,
  `synthesis.py:72`, `synthesis.py:95`

**4. Actual failure mechanism (confirmed by direct read):**
`_values_match` at lines 203-209 does:
```python
if isinstance(claim.expected_value, Decimal) and not claim.expected_value.is_finite():
    return False
if isinstance(evidence_ref.extracted_value, Decimal) and not evidence_ref.extracted_value.is_finite():
    return False
```
Both guards are gated on `isinstance(..., Decimal)`. The Pydantic field type `str | Decimal | datetime | None`
(synthesis.py:72,95) means a JSON string payload value is deserialized as Python `str`, not `Decimal` — Pydantic
does not opportunistically coerce arbitrary strings into `Decimal` in this union. So for any value that arrives
over the API as a string, both `isinstance` checks are `False` and the finiteness guard never runs. Execution
falls through to lines 218-223, which does `str(x).strip().lower()` on both sides and compares with `==`. This
means:
- `"NaN" == "nan"` → `True` → treated as a value match → placed in `supporting` (if `supports_claim` keyword
  overlap also passes, which it trivially does for any claim/evidence pair sharing enough words).
- `"100"` vs `"100.0"` → string-normalize to `"100"` vs `"100.0"` → not equal → falls through to `return False` →
  classified as **contradicting**, despite being the same number.

**5. Confirmed still present in `d983bce`:** **YES.** Read directly; lines match the prior audit's citation
exactly, no changes since.

**6. Existing test coverage:** `tests/unit/test_verification_engine.py::test_numeric_claim_nan_infinity` (line
462) exists, but it constructs `Decimal("NaN")` **directly at the domain layer**, bypassing the Pydantic
API boundary entirely — so it correctly exercises the `isinstance(..., Decimal)` branch and passes. **It does not
exercise the actual bug**, which requires the value to arrive as a `str` (the real shape of an HTTP JSON payload).
No API-level (`synthesis.py`) test with a string `"NaN"`/`"Infinity"`/`"not-a-number"` payload was found in
`tests/unit/test_synthesis_api.py` or `test_synthesis_domain.py`.

**7. Regression test(s) to add:**
- API-level test posting to `/research/synthesis` (or the appropriate verification route) with
  `expected_value="NaN"` / `extracted_value="NaN"` (and `"Infinity"`, `"not-a-number"`) as **JSON strings** —
  assert the result is NOT `verified`/`supporting`.
- API-level test with `expected_value="100"`, `extracted_value="100.0"` as JSON strings — assert the result is
  `supporting`/`verified`, not `contradicted`, once numeric normalization is fixed.
- A domain-level test on `_values_match` that passes `expected_value` and `extracted_value` as `str` (not
  pre-converted `Decimal`) to close the gap between "what the domain test exercises" and "what the API boundary
  actually hands the domain layer."

**8. Severity: CRITICAL.** This is the system's central "is this claim actually true" gate; it can currently be
made to report false certainty (or false contradiction) with attacker- or error-supplied string input.

**9. Dependencies on other findings:** None upstream. F02 shares the same `_values_match`/`classify` code path and
the same fix location (`evidence.py`), so **F01 and F02 should be fixed together in one change**, not sequentially,
to avoid re-testing the same function twice.

**10. Implementation complexity: MEDIUM.** The fix itself (normalize to bounded `Decimal` at the trust boundary,
reject unparsable/non-finite numeric input, compare numerically not textually) is contained to one method and one
Pydantic validator, but doing it correctly requires: deciding how to reject malformed numeric strings (422 at the
API boundary vs. domain-level `ValueError`), preserving the existing "type/unit/currency/period must also match"
logic, and not breaking any of the 15 existing `test_numeric_claim_*` tests, which all currently pass and must
keep passing.

---

## F02 — Keyword overlap can verify a negated factual claim

**1. Exact issue:** For a factual (non-numeric) claim with no `expected_value` supplied, any evidence snippet that
shares enough keywords with the claim text is treated as **supporting** the claim — even if the snippet's actual
meaning negates the claim.

**2. Affected file(s):** `src/financial_intelligence/domain/verification/evidence.py`

**3. Affected function/class:** `EvidenceRef.supports_claim` (evidence.py:69-122) and
`EvidenceBundle._values_match` (evidence.py:196-201, specifically the early-return branch)

**4. Actual failure mechanism (confirmed by direct read):**
`_values_match` line 199-201:
```python
if claim.expected_value is None:
    return claim.claim_type != ClaimType.NUMERIC
```
For any non-numeric (factual) claim with `expected_value is None` — the normal shape for a qualitative
claim — this unconditionally returns `True`, regardless of what the evidence snippet actually says. The only
other gate is `supports_claim` (called first, in `EvidenceBundle.classify`, evidence.py:176), which does pure
bag-of-words overlap after stopword removal (lines 74-122): `overlap >= max(1, len(claim_kw) // 2)`. Negation
words ("not", "never", "no") are not in the stopword list, but they are also not treated specially — they
contribute to the overlap count like any other word, or are simply outnumbered by the shared content words. A
claim "Apple acquired ExampleCorp" vs. evidence "Apple did not acquire ExampleCorp" shares "apple" and a stem-close
"acquir-" — the exact matching depends on tokenization but the code has no mechanism to detect negation at all, so
a high-overlap negated sentence passes `supports_claim`, then `_values_match` returns `True` unconditionally (since
`expected_value is None` and claim type is not `NUMERIC`) → classified as `supporting` → `_determine_status`
(engine.py:289-300) returns `VERIFIED` if confidence clears `min_confidence_for_verified = Decimal("0.7")`
(engine.py:34), which a single Tier-1 source easily does (Tier-1 weight = `1.0`, engine.py:56).

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** No test in `test_verification_engine.py` supplies a negated evidence snippet against
a positive factual claim. `test_superficial_keyword_overlap_does_not_support_claim` exists (grep hit in the test
file) but was not read in full this pass to confirm exactly what "superficial" scenario it covers — **this should
be read before writing the new regression test**, to avoid duplicating an existing (and presumably narrower)
case. Flagged **UNVERIFIED — read `test_superficial_keyword_overlap_does_not_support_claim` before implementing.**

**7. Regression test(s) to add:**
- Domain-level test: factual claim "Apple acquired ExampleCorp" (no expected_value) vs. evidence snippet "Apple
  did not acquire ExampleCorp" from a Tier-1 source — assert the result is NOT `VERIFIED` and NOT in `supporting`.
- A second case with an even higher-overlap negation (e.g. claim and evidence identical except for one inserted
  "not") to pin the exact boundary the fix must handle.

**8. Severity: CRITICAL.** Same rationale as F01 — this is the mechanism meant to prevent unsupported/false claims
from reaching a research output, and it can currently promote the *opposite* of what a source says to "verified,
maximum confidence."

**9. Dependencies on other findings:** Shares `evidence.py`/`classify()` with F01 — **fix together** (see F01 §9).
Any fix that introduces real entailment/negation detection is a materially larger undertaking than a pure numeric
fix; the two should not be conflated into a single "small" ticket.

**10. Implementation complexity: LARGE.** F01 is a data-type/normalization bug with a bounded fix. F02 is a
**semantic** bug — the underlying technique (bag-of-words overlap) has no mechanism for entailment, negation, or
even basic subject/object correctness, and the prior audit's own correction note says as much ("Negation-only
patches would not solve broader entity, event, and meaning mismatches"). A minimal, honest fix is likely to
**narrow** what `_values_match`/`supports_claim` are allowed to certify (e.g., require an explicit `expected_value`
or a typed relation for factual claims to ever reach `VERIFIED`, and demote pure keyword overlap to at most
`UNVERIFIABLE`/a new lower-confidence status) rather than to build real NLU. Scope this explicitly before
estimating effort further — it is a policy decision as much as a code change.

---

## F03 — Acknowledged workflow cancellation can be overwritten by a still-running execution

**1. Exact issue:** After the cancel endpoint returns `200 OK` with status `cancelled`, a concurrently-running
execution of the same workflow can later persist its own terminal status (e.g. `partial`/`completed`/`failed`)
over the stored `cancelled` state, with no check that the workflow was cancelled in the meantime.

**2. Affected file(s):**
- `src/financial_intelligence/application/manage_research_workflow.py`
- `src/financial_intelligence/infrastructure/workflow/in_memory_store.py`

**3. Affected function/class:**
- `ResearchWorkflowService.execute` (captures a local `running` snapshot before execution, line ~152-204)
- `ResearchWorkflowService.cancel` (line 269-308)
- `ResearchWorkflowService._apply_execution_result` (line 349-429, especially line 427:
  `updated = updated.with_status(terminal, at=now)` and line 429: `self._store.save_workflow(updated)`)
- `InMemoryResearchWorkflowStore.save_workflow` (in_memory_store.py:30-53)

**4. Actual failure mechanism (confirmed by direct read):**
`execute()` fetches/updates the workflow to `RUNNING` and holds it in a local variable `running` (line 152-160),
then calls `self._execute.execute_prepared(...)` and eventually `self._apply_execution_result(running, exec_result,
...)` (line 204). `_apply_execution_result` builds `updated = workflow.with_checkpoint(checkpoint, at=now)` (line
380) from the **stale `running` snapshot passed in as `workflow`**, not from a fresh `self._store.get_workflow(...)`
read — so it has no idea whether `cancel()` has since written `CANCELLED` to the store. It then unconditionally
calls `updated.with_status(terminal, at=now)` (line 427) and `self._store.save_workflow(updated)` (line 429).
`InMemoryResearchWorkflowStore.save_workflow` (in_memory_store.py:30-53) only validates **identity invariants**
(`research_run_id`, `request_id`, `company_id`, `plan_id` must be unchanged) and that `checkpoint_version` does not
**regress** (line 47-52) — it never compares the *status* of the incoming write against the *currently stored*
status. Because `cancel()` (line 296) calls `workflow.with_status(WorkflowStatus.CANCELLED, at=now)` **without**
going through `with_checkpoint` first, it does not advance `checkpoint_version`; the still-running execution's
later write carries `checkpoint_version = (stale) + 1`, which is numerically greater than whatever `cancel()` left
in the store, so the store's only guard (no version regression) is satisfied and the overwrite is accepted.

**5. Confirmed still present in `d983bce`:** **YES.** Confirmed by reading both files in full; the exact
mechanism (stale-snapshot re-use plus a store that only checks version-non-regression, not status-consistency)
is present and unchanged.

**6. Existing test coverage:** `tests/unit/test_research_workflows.py` has a `_CancelAfterN` helper (line 54) and
tests for pause/resume (`test_pause_resume_preserves_identity_evidence_attempts`), approval gating, and identity
isolation — but **no test class or test method with "cancel" in its name was found**, and no test in this file
exercises a genuinely concurrent (thread-based) cancel-during-execution race; `_CancelAfterN` appears to be a
sequential/deterministic simulation (not independently confirmed in depth this pass — **UNVERIFIED**, recommend
reading its full usage before writing the new test to avoid duplicating it).

**7. Regression test(s) to add:**
- A threaded/event-controlled test (matching the prior audit's own reproduction method): start executing a
  workflow, block one capability call on a `threading.Event`, call `cancel()` from a second "request", release the
  blocked capability, and assert the workflow's **final** stored status is `CANCELLED`, not `PARTIAL`/`COMPLETED`.
- A store-level unit test asserting `InMemoryResearchWorkflowStore.save_workflow` rejects (or the service layer
  refuses to call it with) a non-terminal-to-terminal transition that would overwrite an already-terminal
  (`CANCELLED`) status with a different terminal status.

**8. Severity: HIGH.** Not exploitable for data disclosure, but it breaks a stated lifecycle guarantee
("acknowledged terminal state") and could mislead an operator into believing a workflow stopped when it did not.

**9. Dependencies on other findings:** None required first. Fixing this will likely touch the same
`_apply_execution_result`/`save_workflow` path that F04 also flows through (capability exceptions become
`TaskExecutionResult`s that feed into the same execution-result pipeline) — **coordinate F03 and F04 fixes** since
both touch execution-result handling, but they are logically independent defects and can be fixed in either order.

**10. Implementation complexity: MEDIUM.** Requires re-fetching current stored state before applying a terminal
write (or adding an atomic compare-and-swap primitive to the store keyed on status/version), plus propagating
cancellation into the running `ExecutionControl` so the executor itself stops between tasks rather than only
being caught at write-time. The prior audit correctly notes this is two related but separable problems: (a) the
overwrite-on-write race (state-check fix, smaller) and (b) execution not actually stopping promptly on cancel
(control-signal propagation, larger). Scope and estimate these as two sub-tasks.

---

## F04 — Capability exception messages leak into research responses

**1. Exact issue:** When a capability adapter raises any exception, the full exception message text is embedded
verbatim into the `TaskExecutionResult.message` field, which is serialized into normal `200 OK` API responses.

**2. Affected file(s):** `src/financial_intelligence/infrastructure/orchestration/capability_executor.py`

**3. Affected function/class:** `Phase6CapabilityExecutor.execute_task` (lines 54-70)

**4. Actual failure mechanism (confirmed by direct read):**
```python
except Exception as exc:
    return TaskExecutionResult(
        task_id=task.task_id,
        status=TaskResultStatus.FAILED,
        message=f"capability executor exception: {exc.__class__.__name__}: {exc}",
        retryable=True,
        error_code="executor_exception",
    )
```
`{exc}` interpolates `str(exc)`, i.e., the exception's full message — which for a real adapter failure could
contain a URL, a file path, a credential fragment, or other internal detail, with **no allowlist/redaction**
applied. This `TaskExecutionResult` flows through the same `exec_result.task_results` /
`exec_result.message` path that ultimately reaches the JSON returned by `/research/execute` and similar routes
(confirmed this is a normal, non-500 code path — the `try/except` here specifically prevents the exception from
ever becoming an unhandled 500, and instead encodes it into a successful task-result payload).

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** No test in the codebase was found asserting that a capability-adapter exception's
message text does NOT appear in the serialized API response. `test_logging_safety.py` tests that secrets are not
**logged**, which is a different code path (structured logs) from the **response body** this finding is about —
so that test suite would not catch this defect even if it passed 100%.

**7. Regression test(s) to add:**
- Unit test on `Phase6CapabilityExecutor.execute_task` injecting a fake dependency (e.g. `get_market_snapshot`)
  that raises `RuntimeError("AUDIT_SYNTHETIC_SECRET_MARKER")`, asserting the returned `TaskExecutionResult.message`
  does **not** contain the marker string, only a generic message/error code.
- API-level test (`/research/execute`) with the same injected failure, asserting the marker does not appear
  anywhere in the HTTP response body.

**8. Severity: HIGH.** Real information-disclosure mechanism; severity would be CRITICAL if a concrete secret leak
via this path had been observed with production credentials, but the prior audit used only a synthetic marker —
current evidence supports HIGH, not CRITICAL.

**9. Dependencies on other findings:** None. Independent, narrowly-scoped fix.

**10. Implementation complexity: SMALL.** Replace the interpolated exception text with a stable public error code
and generic message (pattern already exists elsewhere in the codebase per the app-level "unexpected error is
normalized" test) while keeping `exc.__class__.__name__` (already safe, no argument content) for observability.
Low risk of collateral breakage since only the `message` field's content changes, not the `TaskExecutionResult`
shape.

---

## F05 — SEC ingestion fabricates filing dates and misidentifies the accession

**1. Exact issue:** The live SEC EDGAR adapter sets both `filed_at` and `published_at` on every emitted filing to
the **reporting period's end date** (not the real filing date from the source payload), and uses the company's
**CIK** (a permanent issuer identifier) as the `accession_or_reference` (which should be the filing's actual
accession number).

**2. Affected file(s):** `src/financial_intelligence/infrastructure/financial/sec_company_facts.py`

**3. Affected function/class:** the private package-assembly method that builds `FilingMetadata` (lines 263-278 in
the current file — same numbering as the prior audit's citation)

**4. Actual failure mechanism (confirmed by direct read):**
```python
accession = payload.get("cik")
accession_text = str(accession).strip() if accession is not None else None
filing = FilingMetadata(
    ...
    filed_at=reporting_period.period_end,
    published_at=reporting_period.period_end,
    ...
    accession_or_reference=accession_text or cik,
    ...
)
```
The real SEC XBRL `companyfacts` JSON payload carries **per-fact** `filed`, `accn`, and `form` fields (this is
standard SEC XBRL frame-API shape and is consistent with the file's own docstring reference to
`data.sec.gov/api/xbrl/companyfacts/`). This code discards those per-fact fields entirely and instead (a) reuses
`reporting_period.period_end` — a value derived from the fact's *fiscal period*, not its *filing date* — for both
`filed_at` and `published_at`, and (b) reads `payload.get("cik")` (the top-level company identifier) as the
"accession," which is a category error: a CIK identifies the filer across all filings; an accession number
identifies one specific filing. Both values are visibly wrong at the type level, not just imprecise.

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** `tests/unit/test_financial_live.py` (`SecCompanyFactsTests`) exercises success,
429, and unsupported-company paths against an injected fixture transport, but based on the test names found
(`test_429_returns_none_from_adapter`, `test_success_parses_live_package`, `test_unsupported_company_returns_none`)
none appear to assert anything about `filed_at`/`published_at`/`accession_or_reference` correctness specifically —
**this should be confirmed by reading the full test bodies before writing the new test**, flagged
**UNVERIFIED — read `test_success_parses_live_package` in full before implementing**, since if it already asserts
a `filed_at` value, that assertion is itself either wrong or coincidentally matching the bug and needs updating,
not just supplementing.

**7. Regression test(s) to add:**
- Extend (or add alongside) `test_success_parses_live_package` with a fixture payload where at least one fact's
  `filed` date differs from its fiscal `period_end`, and where `accn` differs from `cik`; assert the resulting
  `FilingMetadata.filed_at` matches the fact's real `filed` date (not period end) and
  `accession_or_reference` matches the real `accn` (not the CIK).

**8. Severity: HIGH.** This corrupts provenance/time-sensitivity guarantees for the *one* domain where the system
has a real live authoritative data source — directly undermines the project's central "time-aware evidence" claim
for that domain.

**9. Dependencies on other findings:** None. Independent.

**10. Implementation complexity: MEDIUM.** Requires threading the per-fact `filed`/`accn`/`form` values through
the earlier parsing steps (not shown in the excerpt read this pass — the fact-parsing loop upstream of line ~200
was not fully re-read in this pass and should be inspected before estimating further), and deciding how to handle
facts that span multiple filings with different accessions (the prior audit's correction note flags this
explicitly: "when facts span filings, retain the appropriate references instead of inventing one common filing").
That multi-filing case could push this toward LARGE if the current data model assumes one filing per package —
**flag for re-scoping once the upstream parsing loop is read.**

---

## F06 — Local Compose exposes the unauthenticated development service on all interfaces

**1. Exact issue:** `docker-compose.yml` publishes the API port without a host bind address (defaults to
`0.0.0.0`, all interfaces) while forcing `APP_ENV=development`, which bypasses authentication entirely regardless
of `AUTH_ENABLED`.

**2. Affected file(s):**
- `docker-compose.yml`
- `src/financial_intelligence/security/auth.py`

**3. Affected function/class:** `services.api.ports` (Compose config); `require_api_key`'s environment bypass
check (auth.py:86-87: `if settings.app_env not in _ENFORCED_ENVIRONMENTS: return`)

**4. Actual failure mechanism (confirmed by direct read):**
```yaml
ports:
  - "${API_HOST_PORT:-8000}:8000"
environment:
  APP_ENV: development
```
Docker's short-syntax port mapping `HOST:CONTAINER` with no explicit bind IP binds to `0.0.0.0` by default,
publishing the container port on every network interface of the host, not just loopback. Combined with
`APP_ENV: development` and `_ENFORCED_ENVIRONMENTS = frozenset({"production", "staging"})` (auth.py:32), every
protected route is reachable with **no credential** from any network interface the host exposes.

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** None expected or applicable — this is a Compose/infra configuration issue, not
something a unit test exercises. `docker compose config --quiet` (mentioned in the prior audit) validates syntax
only, not binding safety.

**7. Regression test(s) to add:** Not a unit-test candidate. Recommend either (a) a CI/lint check (e.g. a small
script asserting the compose file's port mapping includes an explicit `127.0.0.1:` bind prefix) or (b) documenting
this as a deployment-checklist item rather than a code-level regression test.

**8. Severity: MEDIUM.** Real exposure risk for anyone running the committed Compose file as-is on a host with
routable interfaces, but it is explicitly a *local/dev* configuration, not the production Dockerfile path, and
requires the host's own firewall/network policy to also permit reaching it.

**9. Dependencies on other findings:** None.

**10. Implementation complexity: SMALL.** Bind explicitly to `127.0.0.1:${API_HOST_PORT:-8000}:8000`, or provide
a separate non-development Compose profile. Minimal risk.

---

## F07 — Docker does not build the dependency baseline tested in CI

**1. Exact issue:** CI installs pinned dependencies from `requirements-lock.txt`; the Dockerfile instead runs
`pip install .` against the broad version ranges in `pyproject.toml`, so a built image's exact dependency
versions are not guaranteed to match what CI/security-scanning evidence describes.

**2. Affected file(s):**
- `Dockerfile`
- `.github/workflows/ci.yml`
- `requirements-lock.txt`
- `release_evidence/v1.0.0/MANIFEST.md`

**3. Affected function/class:** N/A (build configuration, not application code) — `Dockerfile` builder stage,
lines 12-19 (confirmed: `RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip &&
/opt/venv/bin/pip install .`)

**4. Actual failure mechanism (confirmed by direct read):** CI (`ci.yml`) runs
`python -m pip install -r requirements-lock.txt` then `pip install -e . --no-deps` — i.e., CI's tested/scanned
dependency graph is the **lock file's exact pins**. The Dockerfile never references `requirements-lock.txt` at
all; it installs `.` directly, letting `pip` resolve `fastapi>=0.115,<1`, `pydantic>=2.10,<3`, etc. against
whatever the latest compatible versions are **at image build time**. Additionally both Dockerfile stages use
`FROM python:3.12-slim-bookworm` — a mutable tag, not a pinned digest — so even the base OS/Python patch level can
drift between builds. Any SBOM/vulnerability scan performed against one build (e.g. `release_evidence/v1.0.0/`)
describes that specific build, not necessarily a later or different rebuild from the same Dockerfile.

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** None — this is a supply-chain/build-reproducibility gap, not something a pytest
test can meaningfully assert without actually building the image (which this audit's read-only mandate does not
permit).

**7. Regression test(s) to add:** Not a unit-test candidate. Recommend a CI job that builds the image and runs
`pip freeze` inside it, diffing against `requirements-lock.txt`, failing the build on drift; and pinning the base
image by digest (`FROM python@sha256:...`) rather than by mutable tag.

**8. Severity: MEDIUM.** Does not itself introduce a vulnerability, but it invalidates the ability to trust
retained scan evidence for any future rebuild, which matters given this repo places unusually heavy weight on its
`release_evidence/` artifacts as a release gate.

**9. Dependencies on other findings:** Should be fixed **before** any new release-evidence scan is generated
(see §21 roadmap) — fixing F01-F05 and then re-scanning an image built the *old* way would repeat this problem.

**10. Implementation complexity: SMALL–MEDIUM.** Changing the Dockerfile to `COPY requirements-lock.txt` and
`pip install -r requirements-lock.txt` before `pip install . --no-deps` is small; pinning the base image by digest
and re-validating the full build/test/scan cycle end-to-end is more of a MEDIUM-effort verification task even
though the diff itself is small.

---

## F08 — Non-ASCII bearer input returns 500 instead of 401

**1. Exact issue:** A malformed `Authorization: Bearer` header containing non-ASCII characters causes an
unhandled `TypeError` inside the credential-comparison call, rather than being rejected with the normal 401
response every other invalid-credential shape receives.

**2. Affected file(s):** `src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py`

**3. Affected function/class:** `InMemoryApiKeyStore.is_valid` (line 50-59, specifically line 59:
`return any(secrets.compare_digest(presented_key, stored) for stored in self._keys)`)

**4. Actual failure mechanism (confirmed by direct read AND a live interpreter check performed this pass):**
Python's `secrets.compare_digest` requires both operands to be `str` (ASCII-only) or both `bytes`/`bytearray`; a
`str` argument containing a non-ASCII code point raises `TypeError: comparing strings with non-ASCII characters
is not supported`. Confirmed directly in this session:
```
>>> secrets.compare_digest('abc', chr(255))
TypeError: comparing strings with non-ASCII characters is not supported
```
`is_valid` (line 57) only guards against falsy/empty `presented_key` or an empty store — it does not validate that
`presented_key` is ASCII-only before reaching `compare_digest` on line 59. Nothing in `require_api_key`
(security/auth.py:66-99) catches this `TypeError` either, so it propagates as an unhandled exception, which — per
the codebase's own "unexpected error is normalized" behavior described elsewhere — becomes a generic 500 rather
than the uniform 401 the module's own docstring promises ("All authentication failures produce the same generic
401 response").

**5. Confirmed still present in `d983bce`:** **YES**, confirmed both by source read and by an isolated,
read-only interpreter check of the exact stdlib call this pass (no application code executed).

**6. Existing test coverage:** `tests/unit/test_auth.py::test_malformed_bearer_returns_401` exists but only tests
a wrong authentication **scheme** (`"NotBearer token"`), not a non-ASCII **credential value** with a correct
`Bearer` scheme. This is a distinct input shape and is not covered.

**7. Regression test(s) to add:**
- `test_non_ascii_bearer_returns_401`: send `Authorization: Bearer \xff` (or a Unicode credential such as
  `"Bearer café"`) against a production/staging-configured app with a valid key configured; assert HTTP 401,
  not 500.
- A narrower unit test directly on `InMemoryApiKeyStore.is_valid` passing a non-ASCII `presented_key`; assert it
  returns `False` rather than raising.

**8. Severity: MEDIUM.** Not an authentication bypass (the prior audit is explicit about this and this pass agrees
— worst case is an availability/error-contract defect, not unauthorized access), but it does violate the module's
own documented uniform-401 guarantee and could be used to probe for the presence of this specific credential-store
implementation.

**9. Dependencies on other findings:** None. Independent, and shares no code with F09/F10/F11 despite being in the
same auth subsystem — can be fixed standalone.

**10. Implementation complexity: SMALL.** Validate/encode `presented_key` (e.g., reject or ASCII-normalize before
comparison, or compare as UTF-8 `bytes` via `compare_digest` which does support `bytes` of any content) inside
`is_valid`, returning `False` on any decoding/comparison failure rather than letting an exception escape.

---

## F09 — Readiness reports success when no production key can authenticate

**1. Exact issue:** The `/ready` endpoint's "configuration" check unconditionally reports `ready=True` in
production, even when zero usable API keys are configured — meaning every protected endpoint would return 401 for
every caller, while the readiness probe claims the service is healthy.

**2. Affected file(s):**
- `src/financial_intelligence/config/settings.py`
- `src/financial_intelligence/composition/__init__.py`

**3. Affected function/class:** the readiness-registry wiring inside `build_container` (or equivalent factory) in
`composition/__init__.py`, specifically the `"configuration"` check registration:
```python
readiness.register(
    "configuration",
    lambda: ReadinessCheckResult(
        name="configuration",
        ready=True,
        detail=f"{resolved.app_env}_configuration_validated",
    ),
)
```
(confirmed present in the current file, in the `build_container` function, near the other readiness registrations)

**4. Actual failure mechanism (confirmed by direct read):** This lambda is a constant — it always returns
`ready=True` and never inspects `container.api_key_store.has_keys` (a property that already exists and is used
elsewhere, per `in_memory_api_key_store.py:61-64`). Settings validation (`settings.py:213-225`) rejects
`AUTH_ENABLED=false` in production/staging and rejects an invalid host allowlist, but it does **not** reject an
empty `API_KEYS` value — an empty, whitespace-only, or all-commas `API_KEYS` string produces a zero-key
`InMemoryApiKeyStore` (`from_csv`, lines 39-48) that is syntactically valid configuration but functionally unusable
(`is_valid` always returns `False` per line 57's `not self._keys` short-circuit). Readiness never cross-checks
these two facts.

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** `tests/unit/test_readiness_registry.py` exists (general readiness-registry
mechanics) but was not read in full this pass to confirm it doesn't already cover this specific case —
**UNVERIFIED, read before implementing** to avoid duplicating coverage or contradicting an existing assumption
baked into that test file. `test_auth.py::test_has_keys_false_when_empty` (line 95) tests
`InMemoryApiKeyStore.has_keys` in isolation but does **not** connect it to the `/ready` endpoint's behavior.

**7. Regression test(s) to add:**
- Build a production-configured app/container with `API_KEYS=""` (or unset); call `/ready`; assert the response
  is **not** fully ready (either overall `ready=False` or the `"configuration"` check specifically reports
  `ready=False`) rather than the current unconditional `True`.

**8. Severity: MEDIUM.** Operational/observability defect (a deployment could look "up" while being completely
unusable to every legitimate caller), not a direct security vulnerability, but it can mask a serious misconfiguration
during a rollout.

**9. Dependencies on other findings:** None blocking, but conceptually related to F11 (OpenAPI not describing
auth) — both are "the system doesn't surface its own auth state clearly." Can be fixed independently.

**10. Implementation complexity: SMALL.** Change the lambda to close over `container.api_key_store` (or an
equivalent settings/container reference) and return `ready=container.api_key_store.has_keys or
settings.app_env not in {"production", "staging"}`, with an appropriate `detail` message either way.

---

## F10 — Staging validates a host allowlist but does not enforce it

**1. Exact issue:** Settings-level validation requires an explicit, non-wildcard `ALLOWED_HOSTS` for both
`production` and `staging`, but the ASGI middleware that actually enforces the host allowlist is only turned on
for `production`.

**2. Affected file(s):**
- `src/financial_intelligence/api/app.py`
- `src/financial_intelligence/config/settings.py`

**3. Affected function/class:** `create_app`'s `RequestSafetyMiddleware` wiring (app.py:68-73, specifically line
72: `enforce_allowed_hosts=resolved_container.settings.app_env == "production"`) vs. `Settings`'s validator
(settings.py:212-218, `if self.app_env in ("production", "staging"): ... if not allowed_hosts or "*" in
allowed_hosts: raise ...`)

**4. Actual failure mechanism (confirmed by direct read):** The equality check `app_env == "production"` is a
single string comparison — it evaluates to `False` for `app_env == "staging"`, so
`RequestSafetyMiddleware(enforce_allowed_hosts=False)` is installed whenever the app runs in staging, even though
`Settings` validation just forced a real, non-wildcard `ALLOWED_HOSTS` value to exist for that same environment.
The validated configuration value is computed and stored, but the piece of code that would actually reject a
request with a spoofed `Host` header never consults `enforce_allowed_hosts` differently for staging vs.
development/test.

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** Not confirmed either way this pass for a staging-specific host-spoofing test —
`test_auth.py` and other files were grepped for `allowed_hosts` matches but the middleware/host-enforcement test
file (likely under a `test_api_*` or `test_phase10_*` file) was not opened in full. **UNVERIFIED — locate and read
the `RequestSafetyMiddleware` test file before implementing**, since a staging-host test may already exist and
simply assert the (currently permissive) behavior, which would need updating rather than only supplementing.

**7. Regression test(s) to add:**
- `TestClient` configured with `app_env="staging"`, a real `ALLOWED_HOSTS` list, and a request whose `Host` header
  is **not** in that list — assert the request is rejected (matching production's behavior), not accepted.

**8. Severity: MEDIUM.** Staging is meant to be a pre-production validation environment; if it silently accepts
what production would reject, a host-policy regression could ship to production undetected by staging testing.

**9. Dependencies on other findings:** None. Independent single-line-condition fix, but requires the regression
test in (7) to actually prove the fix, since this is exactly the kind of defect a passing test suite can hide if
no test exercises the staging case specifically.

**10. Implementation complexity: SMALL.** Change the condition to
`app_env in {"production", "staging"}` (matching the settings-side check exactly). Verify no existing test
currently asserts the old (permissive) staging behavior as "correct" — if one does, it must be updated, not left
passing against the old expectation.

---

## F11 — OpenAPI omits the required authentication contract

**1. Exact issue:** The Bearer-key requirement enforced by `require_api_key` is invisible to the generated OpenAPI
schema — there is no `components.securitySchemes` entry, and protected routes carry no `security` requirement in
`/openapi.json`, so generated clients/SDKs and API-documentation tooling cannot discover that authentication is
required.

**2. Affected file(s):**
- `src/financial_intelligence/security/auth.py`
- `src/financial_intelligence/api/app.py`

**3. Affected function/class:** `require_api_key` (auth.py:66-99) as wired via
`_auth = [Depends(require_api_key)]` and `application.include_router(..., dependencies=_auth)` (app.py:78-88)

**4. Actual failure mechanism (confirmed by direct read):** `require_api_key` is declared as a plain
`async def require_api_key(request: Request) -> None`, reading the raw `Authorization` header directly off
`Request` (auth.py:91) rather than declaring a FastAPI/Starlette `fastapi.security` scheme object (e.g.
`HTTPBearer`, `APIKeyHeader`) as a parameter. FastAPI's OpenAPI generator derives `securitySchemes` and per-route
`security` entries specifically from `fastapi.security.*` dependency **parameters** it recognizes by type — a
dependency that merely inspects `Request.headers` manually is architecturally invisible to that generator,
regardless of what it actually enforces at runtime. No `openapi_extra` or manual schema patch was found in
`app.py` compensating for this.

**5. Confirmed still present in `d983bce`:** **YES.**

**6. Existing test coverage:** `tests/unit/test_research_workflows.py::WorkflowApiTests::test_openapi_includes_workflow_paths`
(line 444) exists but its name suggests it checks **path presence**, not **security-scheme presence** — likely
does not cover this finding. **UNVERIFIED — read this test in full before implementing**, to confirm it doesn't
already assert (incorrectly) that no security scheme is expected, which would need to be updated as part of the
fix rather than treated as a separate new test.

**7. Regression test(s) to add:**
- Fetch `/openapi.json` from a production-configured app; assert `components.securitySchemes` contains a bearer
  scheme, and that a representative protected path (e.g. `/companies/resolve`) has a `security` requirement while
  the public `/health` path does not.

**8. Severity: MEDIUM.** Not itself an access-control gap (enforcement already works correctly at runtime for
routes the auth dependency is attached to), but it is a real integration/documentation defect that would surprise
any client-generation tooling and undermines self-describing-API guarantees the project otherwise cares about
(per `test_openapi_includes_workflow_paths` existing at all).

**9. Dependencies on other findings:** None functionally, but naturally grouped with F09 as "the system doesn't
accurately describe its own auth posture" — reasonable to batch into one documentation/schema-hardening pass.

**10. Implementation complexity: MEDIUM.** Requires either (a) wrapping `require_api_key`'s header-reading logic
inside a proper `fastapi.security.HTTPBearer`-based dependency (touches the dependency's signature and every
route's `dependencies=` wiring, though behavior can remain identical), or (b) manually patching the generated
OpenAPI schema post-hoc in `install_openapi_version_policy` or an equivalent hook. Option (a) is more idiomatic
but touches more call sites; option (b) is more contained but more fragile to future FastAPI upgrades. This choice
should be made deliberately, not incidentally, hence MEDIUM rather than SMALL.

---

## F12 — Authoritative phase and release documents contradict one another

**1. Exact issue:** `PROJECT_STATUS.md` and `README.md` make mutually inconsistent claims about whether Phase 11
is complete or "locked and undefined," and the retained risk-acceptance evidence gives different counts of
accepted Critical/High findings in different places.

**2. Affected file(s):** `PROJECT_STATUS.md`, `PHASE_HISTORY.md`, `PHASES.md`, `README.md`,
`release_evidence/v1.0.0/OWNER_RISK_ACCEPTANCE.md`

**3. Affected function/class:** N/A — documentation only, not code.

**4. Actual failure mechanism (confirmed by direct read this pass, independent of the prior audit's citation):**
- `README.md` line 5 states: "Phases 0–10 are complete... Phase 11 is locked and undefined."
- `PROJECT_STATUS.md` lines 6-10 (the very next section down, in the same document) state: "**Active phase:**
  Phase 11 — IN PROGRESS (Prompt 2 complete)... **Active prompt:** Phase 11.2 — COMPLETE / OWNER AUTHORIZED...
  Phase 11.3 (rate limiting) is NOT STARTED... **Next permitted work:** ...Phase 11 is locked and undefined."
  This is **self-contradictory within one document**: it labels Phase 11 both "IN PROGRESS" with a completed
  sub-prompt, and, four lines later, "locked and undefined" — both statements are presented as current fact with
  no reconciling language (e.g., "was locked, then re-authorized for 11.2 only").
- The risk-acceptance/finding counts (26 vs 24, and a separate 1-Critical/9-High figure) were not independently
  re-tallied line-by-line in this pass (would require parsing `OWNER_RISK_ACCEPTANCE.md`'s full finding table) —
  **UNVERIFIED at the exact-number level**, but the qualitative claim (documents disagree with each other) is
  independently confirmed by the README/PROJECT_STATUS.md read above, which alone is sufficient to substantiate
  this finding regardless of the exact-count discrepancy.

**5. Confirmed still present in `d983bce`:** **YES** — these are the current contents of both files, re-read
directly in this pass, not carried over unread from the prior audit.

**6. Existing test coverage:** None expected — this is a documentation-coherence issue; the codebase's own
`test_phase*_contract_freeze.py` tests check **source-code markers** for phase boundaries (per the original
audit's own framing, confirmed plausible given the file naming convention), not narrative-document consistency.

**7. Regression test(s) to add:** Not a unit-test candidate in the traditional sense. If ongoing prevention is
desired, consider a lightweight doc-lint script that extracts a single "current phase" token from each of
`README.md`/`PROJECT_STATUS.md`/`PHASES.md` and fails CI if they disagree — but this is a process/tooling
recommendation, not a code regression test, and should be scoped separately if wanted at all.

**8. Severity: MEDIUM.** Process/operational risk (ambiguous authorization state for whoever picks this project
back up), not a runtime defect.

**9. Dependencies on other findings:** Should be the **last** finding reconciled, after F01-F11 are fixed or
explicitly triaged — because the accurate "current status" statement this finding calls for should describe the
state *after* those fixes, not require a second rewrite once they land.

**10. Implementation complexity: SMALL.** Pure documentation edit: pick one authoritative status statement, update
the others to reference it (or remove the duplication), and reconcile the finding-count discrepancy by
re-deriving it directly from `OWNER_RISK_ACCEPTANCE.md`'s own table.

---

## Cross-Finding Dependency Map

```
F01 ──┬── shares evidence.py / classify() with ──── F02   (fix together; F02 is materially larger — see below)
      │
F03 ──── shares execution-result pipeline with ──── F04   (coordinate; independent root causes)
      │
F05 ──── independent (SEC-adapter-only)
      │
F06 ──── independent (Compose-only)
      │
F07 ──── should be fixed BEFORE any post-fix release-evidence re-scan (gates F01-F06's "done" definition
      │   for release purposes, not for the code fixes themselves)
      │
F08 ──── independent (auth-store-only)
F09 ──── independent (readiness-only), thematically paired with F11 (auth self-description)
F10 ──── independent (single-condition fix)
F11 ──── independent, thematically paired with F09
      │
F12 ──── should be fixed LAST (describes the post-remediation state)
```

No finding blocks another at the *code* level except the F01/F02 shared-function overlap. F07 and F12 are
sequencing concerns (do X before re-scanning / do Y after everything else is known), not code dependencies.

---

## Recommended Implementation Order

Ordered by (a) severity, (b) whether a fix is a prerequisite for trusting a later fix's evidence, and (c) grouping
same-file changes to minimize repeated review of the same function:

1. **F01 + F02 together** (CRITICAL) — same function (`_values_match`/`classify`), same test file
   (`test_verification_engine.py`) — the verification engine's correctness is the system's core safety claim and
   should not be left partially fixed. Add the regression tests from §F01.7/F02.7 **before** changing the
   implementation, per the prior audit's own recommendation, which this pass endorses.
   - Note going in: F02's real fix is scope-larger than F01's (see F02.10) — budget them as separate line items
     even though they land in the same change.
2. **F03** (HIGH) — workflow-cancellation race; fix the state-check/atomicity gap first (smaller), then evaluate
   whether control-signal propagation into the executor (larger) is needed in the same pass or a follow-up.
3. **F04** (HIGH) — small, isolated, no dependency on F03 but naturally reviewed alongside it since both touch
   execution-result handling.
4. **F05** (HIGH) — SEC provenance fix; independent, but re-read the upstream fact-parsing loop first to confirm
   the MEDIUM complexity estimate before committing to a plan.
5. **F08, F09, F10, F11** (MEDIUM, auth/deploy hardening cluster) — each is small-to-medium and independent; can
   be done in any order within the cluster, but doing them together avoids re-opening `security/auth.py`,
   `config/settings.py`, and `api/app.py` repeatedly.
6. **F06, F07** (MEDIUM, deployment/build hardening) — fix Compose binding (F06) and Dockerfile/lock parity (F07)
   together since both are pre-release infrastructure hygiene; **F07 must land before any new release-evidence
   scan is generated**, so sequence it just before any planned re-release, not necessarily immediately after F01.
7. **F12** (MEDIUM, documentation) — reconcile status documents **last**, once the actual post-remediation state
   of items 1-6 is known, so the reconciled document is accurate rather than requiring a second edit.

This order matches the prior audit's own recommended sequencing and this independent pass found no code-level
evidence to justify reordering it — the one refinement this pass adds is flagging F02 as a larger, more
open-ended effort than F01 despite sharing a fix location, and flagging F07 as a release-gating step rather than
a pure code fix to be done "in order" with the others.

---

## Verification Method Note (for the record)

This pass read the exact current-HEAD source for every finding's cited file(s) and, where the citation named
specific line numbers, confirmed the code at those lines still matches the described defect. It did not re-run
the prior audit's live HTTP reproduction steps (that would require standing up a running server instance, which
is a heavier action than this read-only verification pass called for) with one exception: F08's core mechanism
was confirmed with a single, isolated, read-only Python interpreter call to the standard-library `secrets` module
(no application code executed, no files modified). Several existing-test-coverage claims in this document are
marked **UNVERIFIED** where a named test file was located by name/grep but not read in full — those are flagged
explicitly above rather than assumed, and should be closed out (by reading the named test in full) before writing
the corresponding regression test, to avoid duplicating or contradicting existing coverage.
