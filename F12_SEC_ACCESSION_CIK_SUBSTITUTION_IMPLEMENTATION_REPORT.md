# F12 Implementation Report — SEC Accession Number / CIK Substitution

**Audit report:** [F12_SEC_ACCESSION_CIK_SUBSTITUTION_AUDIT_REPORT.md](F12_SEC_ACCESSION_CIK_SUBSTITUTION_AUDIT_REPORT.md)
**Status:** Implemented, not committed, not pushed. Left in the working tree for reviewer inspection.

---

## 1. Finding

`SecCompanyFactsFinancialDataAdapter._parse_package` set `FilingMetadata.accession_or_reference` — the field meant
to identify the exact SEC filing document a package's figures came from — to the company's **CIK**
(`payload.get("cik")`), a permanent, company-level identifier that is identical across every filing that company
has ever made. This is a category error: a CIK identifies *the filer*; an accession number identifies *one
specific filing*. The real SEC XBRL `companyfacts` per-fact rows already carry the filing-specific `accn` field
(alongside `filed`, which F05 correctly wired into `filed_at`), but nothing in the adapter ever read it.

This was the second half of the original F05 finding. F05's own remediation fixed `filed_at`/`published_at`
correctly, but its scoping document (`F05_SEC_FILING_DATE_REMEDIATION_PLAN.md:58`) incorrectly recorded
`accession_or_reference` as "Correctly source-derived ... not implicated," so the defect was carried forward
unfixed and unnoticed until this F12 audit.

## 2. Root Cause

**File:** `src/financial_intelligence/infrastructure/financial/sec_company_facts.py`
**Function:** `SecCompanyFactsFinancialDataAdapter._parse_package` (pre-fix lines 280–293)

```python
accession = payload.get("cik")
accession_text = str(accession).strip() if accession is not None else None
filing = FilingMetadata(
    ...
    accession_or_reference=accession_text or cik,
    ...
)
```

`payload.get("cik")` is the top-level company identifier from the SEC response envelope — the same value the
adapter already uses elsewhere for its own purposes (`sec_cik_for_company`, the `source_url`). It was never a
filing-level identifier, and the per-fact `accn` field (the actual accession number) was never parsed anywhere in
the file.

## 3. Implementation

Mirrored the existing F05 `filed_dates` per-fact-identity pattern for the accession number, and tightened the
selection logic so `filed_at` and `accession_or_reference` are always drawn from the **same** underlying fact:

1. **`_extract_fact`** now returns a 3-tuple `(fact, filed_at, accession_number)` instead of a 2-tuple. A new
   `_parse_accession(raw: object) -> str | None` static method parses `fy_row.get("accn")`, mirroring
   `_parse_filed_date`'s contract: any non-string or empty value yields `None`, never a fabricated/borrowed
   identifier.
2. **`_parse_package`** now tracks a parallel `accession_numbers: dict[int, str | None]` keyed by `id(fact)`,
   populated alongside the existing `filed_dates` dict in both the duration-tag and instant-tag extraction loops.
3. **Selection logic replaced.** The previous code independently computed `filed_at` as the max of all
   `filed`-date candidates among facts matching the selected `reporting_period` (a value, not a fact). The new
   code first identifies the single duration fact for that period with the latest `filed` date
   (`dated_period_facts` / `max(..., key=lambda pair: pair[0])`), then reads **both** `filed_at` and the
   accession number off that one selected fact (`filing_filed_at`, `filing_accession_number`). This guarantees the
   two values always describe one underlying SEC filing, never a mix of two different facts' dates/accessions.
   The resulting `filed_at` value is numerically identical to the prior selection logic (same max-by-`filed`
   comparison), so F05's existing behavior is unchanged — only how the winning fact's identity is retained changed.
4. **`FilingMetadata` construction:** `accession_or_reference=filing_accession_number` replaces the CIK-derived
   value entirely. The `accession = payload.get("cik")` / `accession_text` variables were removed — `cik` (the
   function parameter) is still used only for `source_url`, its legitimate purpose, never for the accession field.
5. When no fact in the selected period carries a parseable accession (or no fact carries a parseable `filed` date
   at all, so no fact is "selected"), `accession_or_reference` is `None` — never the CIK, never any other
   substitute value.

## 4. Data Provenance

- **CIK (Central Index Key):** SEC's permanent identifier for a *filer* (company). One CIK is shared by every
  filing that company has ever submitted — 10-Ks, 10-Qs, 8-Ks, across every fiscal year.
- **Accession Number:** SEC's identifier for one *specific filing submission* (format
  `##########-YY-######`), unique per document. It is the identifier actually needed to locate, cite, or
  cross-reference the exact filing that backs a given set of reported figures.

Using the CIK as a stand-in "accession or reference" is not merely imprecise — it is representationally incapable
of the field's purpose: every filing a company ever makes would report the identical "accession," making the
field useless for distinguishing which specific 10-K a given year's figures came from, and misleading for anyone
constructing a citation or filing-lookup URL from it. Consistent with the project's own evidence-provenance
principle (already applied to `filed_at` in F05: "a missing or malformed value must surface as `None`, not a
fabricated" stand-in), a missing accession must surface as `None`, not a different-but-wrong identifier.

## 5. Tests

**File:** `tests/unit/test_financial_sec_hardening.py`

Fixture change: `_payload()`'s base fixture now includes an `"accn"` field on every SEC row (distinct per
filing/amendment, matching the real SEC schema), so existing `filed_at`-focused tests continue to exercise
realistic payload shapes.

New/updated tests:

| Test | Purpose |
|---|---|
| `test_accession_or_reference_reflects_real_filing_not_cik` | Real accession preserved; explicitly asserts it is **not** the CIK. |
| `test_accession_or_reference_none_when_source_omits_accession` | Missing `accn` on every row → `None`, explicitly asserted **not** equal to the CIK. |
| `test_malformed_accession_does_not_fall_back_to_cik` | Non-string `accn` values → `None`, not a coerced/guessed value, not the CIK. |
| `test_accession_or_reference_matches_the_same_fact_as_filed_at` | Selection-consistency: a competing fact with an earlier `filed` date and a deliberately different, "wrong" accession must **not** win — the returned accession must match the fact whose `filed_at` was actually selected. |
| `test_missing_cik_does_not_affect_accession_or_reference` | Renamed/rewritten from the old `test_missing_accession_still_uses_cik`, which pinned the CIK-fallback as intended behavior. Now asserts that removing the top-level `cik` key has **no effect** on the (correct, `accn`-derived) accession value. |
| `test_missing_cik_and_accession_yields_none_not_cik` | With both `cik` and every `accn` absent, asserts `None` — the historical defect's exact scenario. |

All pre-existing `filed_at`/`published_at` tests (F05 coverage) were re-run unmodified and continue to pass,
confirming the selection-logic refactor preserved F05's behavior exactly.

## 6. Non-Vacuous Validation

The new tests were verified to fail against the pre-fix implementation, not just pass against the fix. Using
`git stash` to temporarily isolate only `src/financial_intelligence/infrastructure/financial/sec_company_facts.py`
back to its pre-F12 (and pre-F05, since F05's `filed_at` fix lives in the same file/diff) state, then re-running
`tests/unit/test_financial_sec_hardening.py`:

```
12 failed, 14 passed in 0.89s
```

Failures included the new F12 tests, e.g.:

```
AssertionError: '0000320193' != '0000320193-24-000123'
AssertionError: '0000320193' is not None
```

— i.e., the pre-fix code returns the raw CIK where the fixed code returns the real accession or `None`. (The
stash also reverted F05's `filed_at` fix, since both live in the same file; the F05 `filed_at` tests failed too,
for the pre-existing, already-audited F05 reason — this is expected and does not indicate any new regression.)
The stash was then popped, restoring the fix, and the full `test_financial_sec_hardening.py` suite was re-run
clean: `26 passed`.

## 7. Full Validation

- **Focused F12 tests:** `tests/unit/test_financial_sec_hardening.py` — **26 passed**.
- **Full suite:** `pytest tests` — **847 passed, 130 subtests passed** (baseline was 842 passed / 130 subtests;
  net +5 tests from this change: 4 new F12 tests + 1 net-new test replacing the old CIK-fallback test).
- **Ruff:** `All checks passed!`
- **Mypy:** `Found 2 errors in 1 file` — both in `src/financial_intelligence/domain/orchestration/graph.py:149,152`,
  identical to the documented pre-existing, unrelated baseline errors. (An intermediate version of the fix
  introduced 2 new mypy errors from an `Optional`-typed `max(..., key=...)` call; this was resolved by
  restructuring the selection as an explicit `list[tuple[date, FinancialFact]]` + guarded `max()`, which type-checks
  cleanly — see the diff.)
- **F01–F11 regression check:** No file outside `sec_company_facts.py` (source) and `test_financial_sec_hardening.py`
  (tests) was touched by this change. Spot-checked and confirmed unchanged/still passing: F01/F02
  (`test_verification_engine.py`, `test_synthesis_api.py`), F03 (`test_financial_domain_hardening.py`'s workflow
  coverage / `manage_research_workflow.py` untouched), F04 (`capability_executor.py` untouched),
  F06 (`docker-compose.yml` untouched), F07 (`Dockerfile` untouched), F08 (`test_auth.py` untouched),
  F09 (`test_readiness_registry.py` untouched), F10 (`app.py` untouched), F11 (`security/auth.py` untouched).
  Full-suite pass count (847, up only by the 5 new/changed F12 tests) confirms no other test regressed.

## 8. Files Changed

- `src/financial_intelligence/infrastructure/financial/sec_company_facts.py` (implementation)
- `tests/unit/test_financial_sec_hardening.py` (regression tests)

No other file was modified by this implementation. (`git diff --stat` for the full working tree shows the same 23
files as before this session — the F01–F11 remediation diff plus these two — with only these two files' line
counts changed by this change: `sec_company_facts.py` 49→88 lines changed, `test_financial_sec_hardening.py`
79→167 lines changed.)

## 9. Risk Assessment

- **Narrow scope:** The change is confined to one adapter function's accession-number handling and its dedicated
  test file. No route, schema, authentication, workflow, verification-semantics, Docker, dependency, or CI
  behavior was touched.
- **No behavior change to unrelated fields:** Monetary fact values, `reporting_period` selection,
  `filed_at`/`published_at` values (verified byte-for-byte identical via the unmodified F05 tests), `source_url`,
  and every other `FilingMetadata` field are unchanged.
- **One intentional, documented behavior change:** `accession_or_reference` for SEC-sourced filings now differs
  from before in exactly two ways: (a) it is the real accession number when the source provides one (previously
  always the CIK), and (b) it is `None`, not the CIK, when no accession is available. The only code that relied on
  the old (incorrect) contract was the one test now rewritten (`test_missing_accession_still_uses_cik` →
  `test_missing_cik_does_not_affect_accession_or_reference` / `test_missing_cik_and_accession_yields_none_not_cik`).
  No production code path was found (via full-codebase grep, documented in the audit report §8) that treats
  `accession_or_reference` as non-nullable or CIK-shaped, other than the pass-through JSON serialization in
  `financial_contracts.py`, which handles `str | None` already (Optional field).
- **Mypy discipline preserved:** The refactor was iterated until mypy returned to the exact documented 2
  pre-existing, unrelated baseline errors — no new type-checking regressions were left in place.

---

## Git Status (end of session)

```
$ git status --porcelain=v1 | grep -v '^??'
 M Dockerfile
 M docker-compose.yml
 M docs/development/README.md
 M src/financial_intelligence/api/app.py
 M src/financial_intelligence/application/manage_research_workflow.py
 M src/financial_intelligence/composition/__init__.py
 M src/financial_intelligence/domain/verification/engine.py
 M src/financial_intelligence/domain/verification/evidence.py
 M src/financial_intelligence/domain/verification/result.py
 M src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py
 M src/financial_intelligence/infrastructure/financial/india_filings.py
 M src/financial_intelligence/infrastructure/financial/reference_dataset.py
 M src/financial_intelligence/infrastructure/financial/sec_company_facts.py
 M src/financial_intelligence/infrastructure/orchestration/capability_executor.py
 M src/financial_intelligence/infrastructure/workflow/in_memory_store.py
 M src/financial_intelligence/security/auth.py
 M tests/unit/test_auth.py
 M tests/unit/test_financial_domain_hardening.py
 M tests/unit/test_financial_prompt2_infra.py
 M tests/unit/test_financial_sec_hardening.py
 M tests/unit/test_phase10_prompt1_production.py
 M tests/unit/test_phase10_prompt2_hardening.py
 M tests/unit/test_phase10_prompt3_acceptance.py
 M tests/unit/test_readiness_registry.py
 M tests/unit/test_synthesis_api.py
 M tests/unit/test_verification_engine.py
```

Untracked files: the pre-existing audit/report `.md` files from this session plus the new
`F12_SEC_ACCESSION_CIK_SUBSTITUTION_IMPLEMENTATION_REPORT.md` (this file) and
`F12_SEC_ACCESSION_CIK_SUBSTITUTION_AUDIT_REPORT.md`.

**No commit was made. No branch was created. No push was performed.** All changes remain unstaged in the working
tree for reviewer inspection.
