# Final Validation Report — F01–F12 Remediation Phase

**Validation date:** 2026-09-18
**Validated against:** working tree on branch `main`, HEAD `d983bce152488c1005168c22f2766fc9dd24056`
**Method:** Read-only validation. No source, test, configuration, dependency, or CI/CD file was modified during
this pass. The only file created is this report.

---

## 1. Executive Summary

F01–F12 pass final validation. The complete test suite (847 passed / 130 subtests), Ruff (clean), and Mypy (the
same 2 pre-existing, unrelated `graph.py` errors) all match the expected post-F12 baseline exactly. The F12 diff
was re-inspected line-by-line and confirmed to use the real per-filing SEC accession number, never the CIK, with
the accession tied to the same fact selected for `filed_at`, and `None` on missing/malformed source data. The
F12 regression tests were re-confirmed non-vacuous (12 failed / 14 passed against the pre-fix adapter, restored via
`git stash`/`git stash pop`; 26/26 passed against the fixed adapter). No prior remediation (F01–F11) shows any
sign of regression. The repository's working tree contains zero changes attributable to this validation pass
beyond the new report file itself.

---

## 2. Repository State

- **Branch:** `main`
- **HEAD:** `d983bce152488c1005168c22f2766fc9dd24056`
- **Staged files:** none
- **Unstaged (modified) files:** 26 — identical to the file set present at the start of this validation session
  (the cumulative F01–F12 remediation diff):
  `Dockerfile`, `docker-compose.yml`, `docs/development/README.md`, `src/financial_intelligence/api/app.py`,
  `src/financial_intelligence/application/manage_research_workflow.py`,
  `src/financial_intelligence/composition/__init__.py`,
  `src/financial_intelligence/domain/verification/{engine,evidence,result}.py`,
  `src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py`,
  `src/financial_intelligence/infrastructure/financial/{india_filings,reference_dataset,sec_company_facts}.py`,
  `src/financial_intelligence/infrastructure/orchestration/capability_executor.py`,
  `src/financial_intelligence/infrastructure/workflow/in_memory_store.py`,
  `src/financial_intelligence/security/auth.py`, and 11 test files under `tests/unit/`.
- **Untracked files:** the cumulative set of F01–F12 audit/implementation/plan `.md` reports, project-status audit
  docs, `test_results.txt`, and 8 untracked-but-present new test files (`test_capability_executor_hardening.py`,
  `test_docker_compose_config.py`, `test_docker_lock_dependency_drift.py`, `test_financial_contracts_api.py`,
  `test_openapi_security_contract.py`, `test_verification_hardening.py`, `test_verification_semantics_hardening.py`,
  `test_workflow_cancellation_race.py`) — all pre-existing from the F01–F11 implementation work, unchanged by this
  validation, plus this report itself.

`git diff --stat` total: **26 files changed, 1227 insertions(+), 85 deletions(-)** — identical to the total
recorded at the end of the F12 implementation session.

---

## 3. Test Results

**Full suite (`pytest tests`):**

```
847 passed, 1 warning, 130 subtests passed in 176.52s
```

- **Passed:** 847
- **Failed:** 0
- **Skipped:** 0
- **xfailed:** 0
- **Subtests:** 130

Matches the expected post-F12 result exactly (baseline 842 + 5 net-new F12 tests).

The single warning is a `PytestUnhandledThreadExceptionWarning` / `UnicodeDecodeError: 'charmap' codec can't
decode byte 0x81` originating from a background subprocess-output-reader thread, consistent with a Windows
`cp1252`-console decoding issue in one of the untracked Docker/dependency-lock sanity tests
(`test_docker_compose_config.py` / `test_docker_lock_dependency_drift.py`, both of which shell out to external
tooling and capture its stdout). It does not fail any test, does not affect the pass count, and is unrelated to
F12 — see §9.

Focused re-runs performed this session, all passing:
- `tests/unit/test_financial_sec_hardening.py` — 26/26 (F12 + F05)
- `tests/unit/test_verification_engine.py`, `test_synthesis_api.py`, `test_financial_domain_hardening.py`,
  `test_auth.py`, `test_readiness_registry.py`, `test_phase10_prompt1_production.py`,
  `test_phase10_prompt2_hardening.py`, `test_phase10_prompt3_acceptance.py` — 220/220
- `tests/unit/test_workflow_cancellation_race.py`, `test_openapi_security_contract.py`,
  `test_capability_executor_hardening.py`, `test_docker_compose_config.py`,
  `test_docker_lock_dependency_drift.py` — 48/48

---

## 4. Ruff

```
All checks passed!
```

---

## 5. Mypy

```
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check
    (left operand type: "Literal[TaskStatus.PENDING, TaskStatus.READY]", right operand type: "Literal[TaskStatus.BLOCKED]")
    [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check
    (left operand type: "Literal[TaskStatus.PENDING, TaskStatus.READY]", right operand type: "Literal[TaskStatus.SKIPPED]")
    [comparison-overlap]
Found 2 errors in 1 file (checked 183 source files)
```

Identical to the documented pre-existing, unrelated baseline. `sec_company_facts.py` and
`test_financial_sec_hardening.py` (the two F12-touched files) introduce zero mypy errors.

---

## 6. F01–F12 Validation Matrix

| Finding | Result | Evidence |
|---|---|---|
| F01 — Numeric verification bypass | **PASS** | `evidence.py`'s `_values_match` rewrite present in diff (191 lines changed); `test_verification_engine.py` (28/28 relevant assertions) and `test_synthesis_api.py` API-boundary tests pass. |
| F02 — Negation-blind verification | **PASS** | Same `evidence.py`/`classify()` diff; `test_verification_engine.py` polarity/negation assertions pass. |
| F03 — Workflow cancellation race | **PASS** | `manage_research_workflow.py` / `in_memory_store.py` diffs present; `test_workflow_cancellation_race.py` — 100% pass (threaded cancel-during-execution scenario). |
| F04 — Exception information leakage | **PASS** | `capability_executor.py` diff present (23 lines changed); `test_capability_executor_hardening.py` — 100% pass, asserting synthetic secret markers never reach `TaskExecutionResult.message`. |
| F05 — SEC filing-date provenance | **PASS** | `filed_at`/`published_at` derive from the real per-fact `filed` value (`_parse_filed_date`), never `period_end`; 8 dedicated tests in `test_financial_sec_hardening.py` pass, including malformed/missing-date and amendment-selection cases. |
| F06 — Docker interface exposure | **PASS** | `docker-compose.yml` confirmed bound to `127.0.0.1:${API_HOST_PORT:-8000}:8000` (inline read this session); comment explicitly documents the loopback rationale. |
| F07 — Dependency/lock reproducibility | **PASS** | `Dockerfile` diff present (`requirements-lock.txt`-based install); `test_docker_lock_dependency_drift.py` — 100% pass. (Full container build/pip-freeze diff was not re-executed this pass, consistent with the original finding's own note that this requires an actual image build — outside a read-only validation's scope.) |
| F08 — Non-ASCII Bearer handling | **PASS** | `in_memory_api_key_store.py` diff present; `test_auth.py` non-ASCII bearer tests (`test_non_ascii_accented_bearer_returns_401_not_500`, CJK, currency-symbol, response-shape, no-exception-leak variants) — all pass, returning 401 not 500. |
| F09 — Readiness with empty API key set | **PASS** | `composition/__init__.py:399` gates readiness on `api_key_store.has_keys` for enforced environments (inline read this session); `test_readiness_registry.py` — 100% pass. |
| F10 — Staging host allowlist | **PASS** | `app.py:78` uses `app_env in _HOST_ENFORCEMENT_ENVIRONMENTS` (production **and** staging), confirmed by inline read this session; relevant staging-host test coverage passes. |
| F11 — OpenAPI security scheme | **PASS** | `security/auth.py` uses `fastapi.security.HTTPBearer` (confirmed inline this session); live `/openapi.json` fetch this session shows `components.securitySchemes` present and `/companies/resolve` carrying a `security` requirement; `test_openapi_security_contract.py` — 100% pass. |
| F12 — SEC accession provenance | **PASS** | See §7 below for full detail. |

No FAIL. No regression detected in any prior finding.

---

## 7. F12 Detailed Validation

- **Real SEC `accn` used, not the CIK:** Confirmed by direct diff read (`git diff -- sec_company_facts.py`) — the
  old `accession = payload.get("cik")` / `accession_text or cik` construction was removed entirely; a new
  `_parse_accession(fy_row.get("accn"))` reads the filing-level identifier from the same per-fact row already used
  for `filed`. Confirmed at runtime with a synthetic SEC-shaped payload (`accn="0000320193-24-000123"`,
  `cik="0000320193"`): the adapter returned `accession_or_reference == "0000320193-24-000123"`, matching the
  fixture's `accn`, not its `cik`.
- **Same-fact relationship with `filed_at`:** Confirmed by diff read — `filing_filed_at` and
  `filing_accession_number` are both read off a single `selected_fact` (the duration fact with the latest parsed
  `filed` date for the chosen reporting period), never independently selected. The dedicated regression test
  `test_accession_or_reference_matches_the_same_fact_as_filed_at` (re-run this session, passing) proves this: a
  competing fact with an earlier `filed` date and a deliberately mismatched accession does not "win" — the
  returned accession matches the fact whose `filed_at` was actually selected.
- **Missing `accn` → `None`:** Confirmed by `test_accession_or_reference_none_when_source_omits_accession` and
  `test_missing_cik_and_accession_yields_none_not_cik` (both re-run this session, passing) — removing every `accn`
  value from the source payload yields `accession_or_reference is None`, never a substituted value.
- **No CIK fallback under any circumstance:** Confirmed by `test_missing_cik_does_not_affect_accession_or_reference`
  (removing the top-level `cik` key has zero effect on the — correct — accession value) and
  `test_malformed_accession_does_not_fall_back_to_cik` (a non-string `accn` yields `None`, not the CIK). No code
  path in the current `sec_company_facts.py` reads `payload.get("cik")` for any purpose other than `source_url`
  construction (confirmed by `grep`).
- **Non-vacuous regression test, re-confirmed this session:** `git stash push -- sec_company_facts.py` (isolating
  only the F12/F05 source fix), re-running `test_financial_sec_hardening.py`, produced:
  ```
  12 failed, 14 passed in 2.55s
  ```
  with representative failures `AssertionError: '0000320193' != '0000320193-24-000123'` and
  `AssertionError: '0000320193' is not None` — the pre-fix adapter demonstrably returns the CIK where the fixed
  adapter returns the real accession or `None`. `git stash pop` restored the fix; the full 26-test file then
  passed clean again, and the full 847-test suite/Ruff/Mypy results above were captured on the fully restored
  working tree.

---

## 8. Regression Assessment

No regression was found in F01–F11. Evidence:
- The full-suite pass count (847) is exactly the expected baseline (842) plus the 5 net-new F12 tests — no other
  test count moved, meaning no previously-passing test now fails and no previously-covered behavior silently lost
  coverage.
- `git diff --stat` shows only `sec_company_facts.py` and `test_financial_sec_hardening.py` changed relative to
  the F11-complete baseline that existed at the start of the F12 implementation session (confirmed both by this
  session's `git diff --stat -- src tests` at F12 implementation time and by this validation's fresh read of the
  same).
- Each F01–F11 finding's own dedicated test file was independently re-run this session (§3, §6) and passed in
  full, not merely inferred from the aggregate count.
- Mypy and Ruff both remain at their exact documented pre-existing baselines, with zero new findings anywhere in
  the codebase, including outside the two F12-touched files.

---

## 9. Remaining Known Issues (pre-existing, unrelated — not new findings)

- **`graph.py` mypy errors (documented, pre-existing):** `domain/orchestration/graph.py:149,152` —
  non-overlapping identity-check errors, unchanged since before F01, explicitly out of scope for this remediation
  phase.
- **Flaky Windows console-decoding warning in Docker/dependency-lock tests:** `test_docker_compose_config.py`
  and/or `test_docker_lock_dependency_drift.py` occasionally emit a `PytestUnhandledThreadExceptionWarning` /
  `UnicodeDecodeError` from a subprocess stdout-reader thread on this Windows/`cp1252` environment. It does not
  fail any test and was observed intermittently (present in one full-suite run this session, absent in another).
  This is an environment/test-infrastructure characteristic of those two untracked test files, unrelated to F01–F12
  and not touched by any remediation in this phase. Worth a backlog item (e.g., force UTF-8 subprocess output
  capture) but explicitly not actioned here per the review-only mandate.
- **Stale narrative status documentation:** `PROJECT_STATUS.md` (line 6-8) still states "Active phase: Phase 11 —
  IN PROGRESS ... All 705 tests pass (658 original + 47 authentication)," which predates the entire F01–F12
  remediation phase and the current 847-test baseline. This is the same class of documentation-consistency gap
  the project's own `DEFECT_REMEDIATION_PLAN.md` previously flagged (as its own internal "F12" candidate, distinct
  from the SEC-accession F12 confirmed and implemented in this phase) and explicitly deferred to be reconciled
  last, after all code-level findings are known. It remains open and unactioned — a backlog/documentation item,
  not a code defect, and out of scope for this validation per the review-only mandate.
- **F07 container-build verification:** As noted in the F07 audit finding itself, full confirmation requires
  actually building the Docker image and diffing `pip freeze` against `requirements-lock.txt` — this was not
  re-executed during this (or the original) audit pass, consistent with the read-only/no-build validation scope.
  Flagged as a standing backlog item for whenever a build environment is available, not a finding of this review.

No new F-numbered finding was created during this validation, per the review-only mandate.

---

## 10. Final Verdict

**FINAL VALIDATION PASSED**
