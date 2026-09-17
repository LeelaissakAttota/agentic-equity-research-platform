# F12 — SEC Filing `accession_or_reference` Still Populated With the Company CIK, Not the Real Accession Number

**Audit date:** 2026-09-17
**Verified against:** HEAD `d983bce` (working tree unchanged by this audit — see §13)
**Method:** Read the current `sec_company_facts.py` implementation in full, cross-checked it against every F01–F11
audit/implementation document, independently reproduced the defect against the live adapter code with a synthetic
SEC XBRL payload (no network access, no external systems, no real credentials), and inspected all existing test
coverage that touches the affected field.

---

## 1. Executive Summary

- **F12 finding:** `SecCompanyFactsFinancialDataAdapter._parse_package` still sets
  `FilingMetadata.accession_or_reference` to the company's **CIK** (`payload.get("cik")`), not the filing's real
  **SEC accession number** (the per-fact `accn` field the SEC XBRL `companyfacts` API actually returns). This is
  the exact "category error" the F05 audit originally described ("a CIK identifies the filer across all filings; an
  accession number identifies one specific filing") — F05's remediation fixed `filed_at`/`published_at` (now a real
  per-fact filing date, no longer borrowed from `period_end`) but left `accession_or_reference` untouched. The F05
  remediation plan explicitly (and incorrectly) recorded this field as "Correctly source-derived ... not
  implicated," which is why it was never fixed.
- **Severity:** **Medium** (data-integrity / provenance defect in the platform's one live authoritative data
  source; not a security-boundary or access-control issue).
- **Affected component:** `src/financial_intelligence/infrastructure/financial/sec_company_facts.py`
  (`SecCompanyFactsFinancialDataAdapter._parse_package`, lines 280–293), surfaced to API consumers via
  `src/financial_intelligence/application/financial_contracts.py:125` as `source.accession_or_reference` in the
  financial-package response payload.
- **Concise explanation:** Every SEC-sourced filing this adapter returns reports the company's permanent CIK
  (e.g. `"0000320193"`) as its "accession or reference" instead of the actual filing-specific accession number
  (e.g. `"0000320193-24-000123"`). Since a company files many documents under the same CIK over time, this value
  cannot be used to locate or cite the specific SEC filing the returned figures came from — it degrades exactly the
  provenance guarantee this project states as its core differentiator ("every material claim should resolve to
  time-aware evidence").

---

## 2. Baseline

- **Branch:** `main`
- **HEAD:** `d983bce152488c1005168c22f2766fc9dd24056` ("feat(phase-11.2): implement API key authentication
  foundation")
- **Working tree:** 26 tracked files modified (the F01–F11 remediation diff) + 33 untracked audit/report files,
  unchanged by this audit — see §13 for the re-check.
- **Tests:** `842 passed, 130 subtests passed` (`pytest tests`, 27.17s) — matches the expected baseline exactly.
- **Ruff:** `All checks passed!`
- **Mypy:** `Found 2 errors in 1 file` — both in `src/financial_intelligence/domain/orchestration/graph.py:149,152`
  (`Non-overlapping identity check`), matching the documented pre-existing, unrelated errors.

All four match the expected baseline stated in the audit brief exactly.

---

## 3. Prior-Audit Cross-Check

`DEFECT_REMEDIATION_PLAN.md` (§F05) originally described **two** distinct defects in the same
`FilingMetadata` construction: (a) `filed_at`/`published_at` fabricated from `reporting_period.period_end` instead
of the real filing date, and (b) `accession_or_reference` populated from the company's **CIK** instead of the
filing's real **accession number** — explicitly calling this "a category error: a CIK identifies the filer across
all filings; an accession number identifies one specific filing."

`F05_SEC_FILING_DATE_REMEDIATION_PLAN.md` (the scoping document that preceded implementation) re-examined the
domain model and asserted, in its field-by-field table (line 58):

> `FilingMetadata.accession_or_reference` | Accession number / fixture reference | **Correctly source-derived
> (`payload["cik"]` combined with CIK, or fixture literal) — not implicated**

and its conclusion (line 61): "No evidence was found of: ... `filing_date ← unrelated field` (e.g. accession
number) ... The conflation is specifically and exclusively `filing_date ← period_end_date`."

This scoping decision is where the defect was dropped from F05's actual fix. Reading the **current** code (§4
below) shows the scoping document's own premise was wrong: `payload["cik"]` is not "correctly source-derived" as
an accession number — it is the same identifier used everywhere else in the file as the company-level CIK (see
`sec_company_facts.py:81-84`, `_SEC_COMPANYFACTS_BASE}CIK{cik}.json`), not a filing-specific accession. The
implementation report for F05 (`F05_SEC_FILING_DATE_IMPLEMENTATION_REPORT.md`) and the current diff (`git diff --
src/financial_intelligence/infrastructure/financial/sec_company_facts.py`) confirm only `filed_at`/`published_at`
were actually changed; `accession_or_reference` at line 280–292 is untouched from the pre-F05 code the original
`PRODUCT_AUDIT_2026-09-15.md`/`DEFECT_REMEDIATION_PLAN.md` findings described.

No other F01–F11 finding or implementation report references `accession_or_reference` or `accn` at all — this was
never picked up, reassigned, or explicitly deferred elsewhere. It is a genuine, independently-verified remaining
gap, not a re-labeling of an already-closed item.

---

## 4. Root Cause

**File:** `src/financial_intelligence/infrastructure/financial/sec_company_facts.py`
**Function:** `SecCompanyFactsFinancialDataAdapter._parse_package`
**Lines:** 280–293 (current HEAD, confirmed by direct read this pass)

```python
accession = payload.get("cik")
accession_text = str(accession).strip() if accession is not None else None
filing = FilingMetadata(
    ...
    filed_at=filed_at,
    published_at=filed_at,
    retrieved_at=retrieved_at,
    accession_or_reference=accession_text or cik,
    source_url=f"{_SEC_COMPANYFACTS_BASE}CIK{cik}.json",
    provider_name=self.provider_name,
)
```

`accession_or_reference` is built from `payload.get("cik")` — the **top-level company identifier** in the SEC
`companyfacts` response — with a fallback to the `cik` function parameter if that key is absent. Both branches
resolve to the same CIK value; neither ever reads a filing-specific identifier.

The real SEC XBRL `companyfacts` per-fact row (the same `fy_row` dict already being read at
`_extract_fact`/`_select_fy_row`, lines 330–459) carries an `"accn"` field alongside `"filed"`, `"fy"`, `"fp"`, and
`"form"` — this is the standard, documented shape of `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
(consistent with the file's own docstring reference to that endpoint, and with the `"filed"` field this same code
already parses via `_parse_filed_date`/`filed_dates`, lines 150-219). The F05 fix threaded `fy_row.get("filed")`
through to `filed_at`, but no equivalent `fy_row.get("accn")` threading exists for the accession number — it is
read nowhere in the file (confirmed: `grep -n "accn" sec_company_facts.py` finds zero matches).

---

## 5. Expected vs Actual Behavior

- **Expected:** `FilingMetadata.accession_or_reference` for an SEC-sourced filing should be the specific filing's
  accession number (e.g. `"0000320193-24-000123"`), which uniquely identifies the exact 10-K/10-Q document the
  reported figures came from, matching the same selection logic already used for `filed_at` (the accession
  associated with the fact(s) making up the selected `reporting_period`).
- **Actual:** `FilingMetadata.accession_or_reference` is always the company's CIK (e.g. `"0000320193"`) — the same
  value for every filing year of the same company, and not derivable from it back to a specific SEC filing.

---

## 6. Reproduction

Reproduced directly against the current adapter code (no network access; no application state modified), using a
synthetic two-year SEC `companyfacts`-shaped payload with distinct `filed` and `accn` values per year (matching the
real SEC schema):

```python
# src on PYTHONPATH; synthetic payload with per-fact "accn" fields for FY2023/FY2024
package = SecCompanyFactsFinancialDataAdapter(fake_http).get_financial_package(APPLE_ID)
print("filed_at:", package.filing.filed_at)
print("accession_or_reference:", package.filing.accession_or_reference)
```

**Observed output:**

```
filed_at: 2024-11-01
accession_or_reference: 0000320193
expected real accession (from payload accn): 0000320193-24-000123
```

`filed_at` correctly resolves to the real per-fact filing date (`2024-11-01`, distinct from `period_end`
`2024-09-28`) — confirming F05's actual fix works as intended. `accession_or_reference` resolves to the bare CIK
(`0000320193`), not the accession number present in the same synthetic payload (`0000320193-24-000123`) that
`filed_at`'s own selection logic (`_select_fy_row`) already reads from the identical row.

---

## 7. Existing Test Coverage

- `tests/unit/test_financial_sec_hardening.py` has 8 tests asserting `filed_at`/`published_at` correctness
  (`test_filed_at_reflects_source_filed_date_not_period_end`, `test_filed_at_uses_latest_amendment_consistently...`,
  `test_filed_at_none_when_source_omits_filed_date`, `test_published_at_mirrors_filed_at_not_period_end`,
  `test_filing_contract_serializes_authoritative_filed_at`, etc.) — this is genuine, effective F05 coverage for the
  part of F05 that was fixed.
- The only test touching `accession_or_reference` is `test_missing_accession_still_uses_cik`
  (`test_financial_sec_hardening.py:330-337`), which **deletes** the `"cik"` key from the payload and asserts only
  that `accession_or_reference` is truthy (falls back to the adapter's resolved `cik` parameter). This test
  actively **encodes the CIK-as-accession behavior as the intended fallback contract** — it does not assert
  anything about a real filing-specific accession number, and none of the test fixtures in this file (including
  the shared `_payload()` builder, lines 36-100+) include an `"accn"` field at all, so no existing test could ever
  observe this defect.
- Regression test needed once fixed: a test asserting that when the payload's per-fact rows carry an `"accn"`
  value, `FilingMetadata.accession_or_reference` reflects that filing-specific accession (matching the row selected
  for `filed_at`/`reporting_period`), not the CIK — and that it falls back to CIK (or `None`) only when no `accn`
  is present anywhere in the source data, with that fallback behavior explicitly documented as degraded, not
  silently indistinguishable from a real accession.

---

## 8. Impact Analysis

**Confirmed impact:**
- Every SEC-sourced `CompanyFinancialPackage` this adapter returns — the platform's only live, non-fixture,
  authoritative financial data source — reports a provenance identifier that cannot distinguish one filing year
  from another for the same company, and is not the SEC's own filing-level identifier.
- This value is exposed directly to API consumers: `financial_contracts.py:125` serializes it as
  `payload["source"]["accession_or_reference"]` in the financial-package response — an external caller or
  downstream evidence/citation consumer relying on this field to cite or re-fetch the specific SEC filing
  (e.g. to construct `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&...` or an EDGAR filing-index URL)
  would be citing the wrong identifier.

**Possible downstream impact (not independently confirmed this pass):**
- Any evidence-verification or citation-rendering logic that treats `accession_or_reference` as a unique filing
  key (e.g. for deduplication across multiple years of the same company, or for constructing a filing-specific
  source URL) would silently collapse multiple distinct filings to the same "reference," though no such
  deduplication/URL-construction logic was found reading `accession_or_reference` outside
  `financial_contracts.py`'s pass-through serialization (see the full-codebase `grep` in the investigation — the
  only non-definition, non-test call site is the API contract serializer).

**Not a security-boundary or authentication issue** — no credential, host-allowlist, or access-control code path is
touched by this finding.

---

## 9. Severity

**Medium.**

Justification:
- It is a **data-integrity/provenance** defect in the one domain (F05's own framing) where the system has a real
  live authoritative source, directly undermining the "time-aware evidence" / "material claim should resolve to
  time-aware evidence" claims the project states as its core differentiator (README "Why this project exists").
- It is not exploitable for unauthorized access, does not corrupt financial figures themselves (`filed_at`, the
  actual monetary facts, and `reporting_period` are all correct), and does not affect verification pass/fail
  outcomes — it only degrades the trustworthiness of one provenance field.
- It is a straightforward, narrowly-scoped defect with a bounded fix (structurally identical to the `filed_at` fix
  already implemented in the same function), not a systemic design flaw — consistent with Medium rather than High.

---

## 10. Recommended Remediation (plan only — not implemented)

**Files likely to change:**
- `src/financial_intelligence/infrastructure/financial/sec_company_facts.py`
- `tests/unit/test_financial_sec_hardening.py`

**Proposed design:**
1. Extend the existing `filed_dates: dict[int, date | None]` pattern (or add a parallel
   `accession_numbers: dict[int, str | None]`) to also capture `fy_row.get("accn")` per fact, mirroring
   `_parse_filed_date` with a new `_parse_accession(raw: object) -> str | None` (validate it is a non-empty
   string; do not fabricate or normalize beyond stripping).
2. At the same point `filed_at` is selected from `filed_at_candidates` (lines 213-219), select the accession
   number associated with the same selected fact(s)/reporting period — the accession tied to the fact whose
   `filed` date was chosen (not an independent "latest accession across all facts" selection, to keep the
   accession and filed date self-consistent for the same underlying document).
3. Replace `accession_text = str(accession).strip() if accession is not None else None` /
   `accession_or_reference=accession_text or cik` with the newly-threaded per-fact accession value, falling back
   to `None` (not CIK) when no accession is available in the source data — consistent with F05's own principle
   ("a missing or malformed value must surface as None, not a fabricated" stand-in), rather than silently
   substituting a different, incorrect-but-non-null identifier.
4. Update `test_missing_accession_still_uses_cik` (which currently pins the CIK-fallback as intended behavior) to
   reflect the corrected contract — this existing test will need to change, not just be supplemented, per the
   audit brief's non-vacuous-evidence guidance.

**Expected behavior after the fix:** `FilingMetadata.accession_or_reference` for a live SEC-sourced filing equals
the real per-filing SEC accession number (e.g. `"0000320193-24-000123"`) when present in the source payload, and
`None` (not the CIK) when the source data provides no accession — never a company-level CIK masquerading as a
filing-level accession.

**Regression tests required:**
- A payload-shape test (extending the existing `_payload()` fixture pattern) with distinct `accn` values per fiscal
  year, asserting `accession_or_reference` matches the accession tied to the **selected** reporting period, not an
  arbitrary or unrelated year's accession.
- A test asserting `accession_or_reference` is `None` (not CIK) when the source payload's per-fact rows omit
  `accn` entirely, replacing the current `test_missing_accession_still_uses_cik` assertion.
- A test on the API-contract boundary (`financial_contracts.py`) confirming the corrected accession value (not
  CIK) appears in the serialized `source.accession_or_reference` field.

**Non-vacuous validation strategy:** Before writing the fix, extend the reproduction script used in §6 of this
report (or a pytest equivalent) with a payload where CIK and accession are deliberately different-looking
(as in the real SEC schema, where CIK is numeric-only and accession is `##########-YY-######`), so a
fixed-vs-broken implementation is trivially distinguishable by asserting the returned value contains the `-YY-`
pattern rather than matching the raw CIK — the same technique already applied for `filed_at` vs `period_end` in
`test_filed_at_reflects_source_filed_date_not_period_end`.

**Compatibility/regression risks:** Low. The change is additive (one new optional field threaded through the same
existing per-fact extraction path already used for `filed_at`); it does not alter `filed_at`, monetary fact
values, `reporting_period` selection, or any other field. The one behavioral change or existing test consumers
should expect is: `accession_or_reference` will change from "always the CIK" to either a real accession or `None`
— any code or test currently relying on it always being non-null-and-equal-to-CIK (only
`test_missing_accession_still_uses_cik`, per §7) will need updating.

---

## 11. Non-Vacuous Evidence

The defect was independently demonstrated by constructing a synthetic SEC `companyfacts`-shaped payload (§6) that
includes a real per-fact `"accn"` field distinct from the company's `"cik"` — a payload shape deliberately closer to
the true SEC API response than any existing fixture in the repository (none of which include `"accn"` at all,
confirmed by `grep`). Running this payload through the unmodified, current `SecCompanyFactsFinancialDataAdapter`
produced `accession_or_reference == "0000320193"` (the CIK) instead of the payload's own `"0000320193-24-000123"`
accession value — a direct, reproducible mismatch between expected and actual behavior, not an inference from
reading code alone.

The future regression test described in §10 distinguishes fixed vs. pre-fix behavior identically: assert
`accession_or_reference` equals the fixture's `accn` value (fixed) rather than its `cik` value (pre-fix) — the two
values are deliberately given non-overlapping formats in the reproduction fixture so the assertion cannot pass
vacuously for either implementation.

No pre-fix code was restored via `git stash` for this reproduction — none was needed, since the defect is present,
unmodified, in the current working tree; the synthetic-payload technique alone was sufficient and required no
changes to any tracked file.

---

## 12. F01–F11 Regression Safety

All ten prior fixes were spot-checked directly against current HEAD during this audit (read-only) and confirmed
intact:

- **F01/F02 (numeric verification / verification semantics):** `evidence.py` diff shows the `_values_match`
  rewrite (191 lines changed) is present; full suite (`test_verification_engine.py`, `test_synthesis_api.py`)
  passes.
- **F03 (cancellation race):** `manage_research_workflow.py` / `in_memory_store.py` diffs present; workflow tests
  pass.
- **F04 (exception leakage):** `capability_executor.py` diff present (23 lines changed).
- **F05 (SEC filing-date provenance):** `filed_at`/`published_at` fix confirmed correct and independently
  reproduced as working in §6 above — this audit's finding is that F05's *accession* half was never completed, not
  that its *date* half regressed.
- **F06 (Docker loopback binding):** `docker-compose.yml` confirmed bound to `127.0.0.1:${API_HOST_PORT:-8000}:8000`
  (§ inline check, this pass).
- **F07 (dependency/lock reproducibility):** `Dockerfile` diff present (not independently re-verified by a build
  this pass, per the read-only audit mandate — consistent with the original finding's own note that this requires
  an actual image build to fully verify).
- **F08 (non-ASCII Bearer handling):** `in_memory_api_key_store.py` diff present; `test_auth.py` additions present
  and passing.
- **F09 (readiness/authentication check):** `composition/__init__.py:399` confirmed to gate readiness on
  `api_key_store.has_keys` for enforced environments (§ inline check, this pass).
- **F10 (staging host allowlist enforcement):** `app.py:78` confirmed to use
  `resolved_container.settings.app_env in _HOST_ENFORCEMENT_ENVIRONMENTS` (production **and** staging), not a
  single `== "production"` comparison (§ inline check, this pass).
- **F11 (OpenAPI security scheme):** `security/auth.py` confirmed to use `fastapi.security.HTTPBearer` (line 21,
  44), not a raw `Request.headers` read (§ inline check, this pass).

Full suite: `842 passed, 130 subtests passed`, Ruff clean, mypy at the expected 2 pre-existing unrelated errors —
identical to the stated baseline, confirming no regression.

---

## 13. Final Audit Verdict

**Working tree check (this audit made zero source/test changes):**

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

This is identical, file-for-file, to the pre-audit snapshot recorded at the start of this session — the only
change made by this audit is the addition of this report file itself (plus a scratch reproduction script written
to the session's temp scratchpad directory outside the repository, not the working tree). No `src/`, `tests/`,
Docker, dependency, CI, or configuration file was modified.

**F12 FINDING CONFIRMED**
