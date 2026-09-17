# F05 — SEC Filing-Date Fabrication: Audit & Remediation Plan

**Status: AUDIT ONLY. No source or test files were modified for this defect.**

## 1. Executive Summary

The system does **not** invent a filing date out of thin air (e.g. `datetime.now()`), but it does **unconditionally substitute the fiscal *period-end* date for the SEC filing (acceptance) date** in every code path that builds a `FilingMetadata` object — including the live SEC EDGAR adapter. This happens even when the underlying SEC XBRL payload contains a genuine, authoritative `filed` date that differs from the period end. The `filed` field is read from the source payload but is used *only* as a tie-breaker for selecting the most-recently-amended fact row; its value is then discarded and never written into `FilingMetadata.filed_at`. The result is a **confirmed date conflation** (`filing_date ← period_end_date`), not a "missing → fabricated" case in the sense of inventing a value with no source basis — the danger is subtler: a *real, differently-named* date is presented as if it were the filing date, so it looks authoritative and is silently wrong.

**Verdict: CONFIRMED** — filing date and fiscal period-end date are conflated across all adapters (live SEC adapter, US fixture generator, India fixture generator), and this fabricated value is serialized to the API/report layer as an authoritative SEC filing date.

## 2. Scope

In scope: SEC filing metadata construction, parsing, normalization, domain modeling, serialization, and existing test coverage, as reached from:
- `src/financial_intelligence/infrastructure/financial/sec_company_facts.py` (live SEC EDGAR adapter)
- `src/financial_intelligence/infrastructure/financial/reference_dataset.py` (US fixture data)
- `src/financial_intelligence/infrastructure/financial/india_filings.py` (India fixture parser)
- `src/financial_intelligence/domain/financial/filings.py` (`FilingMetadata`, `FilingId`)
- `src/financial_intelligence/domain/financial/periods.py` (`ReportingPeriod`)
- `src/financial_intelligence/application/filing_pipeline.py`
- `src/financial_intelligence/application/financial_contracts.py` (API-facing serialization)
- `src/financial_intelligence/application/capability_result_adapters.py` (evidence attribution)
- `src/financial_intelligence/api/routes/financials.py`
- Related tests: `tests/unit/test_financial_sec_hardening.py`, `tests/unit/test_financial_domain.py`, `tests/unit/test_financial_domain_hardening.py`, `tests/unit/test_phase4_contract_freeze.py`, `tests/unit/test_financial_prompt2_infra.py`

Out of scope (not touched, not re-examined): F01–F04 fixes (verification engine, evidence, cancellation, exception leakage) — confirmed untouched by this audit.

## 3. Baseline

- Branch: `main`
- HEAD commit at audit start: `d983bcea152488c1005168c22f2766fc9dd24056` ("feat(phase-11.2): implement API key authentication foundation")
- Working tree: pre-existing uncommitted changes from F01–F04 remediation work (application/domain verification files, workflow store, capability executor, two test files) plus numerous untracked `.md` audit/report files from prior phases. None of these were modified by this audit.
- Test baseline observed (re-run at start of this audit): **773 passed, 130 subtests passed** — matches the reported baseline. Ruff/Mypy were not re-run in this audit pass (no source was changed that would affect them); the prior F04 baseline reported both as PASS.

## 4. Data-Flow Trace

| Stage | Component | Filing-date handling |
|---|---|---|
| 1. SEC/source adapter | `SecCompanyFactsFinancialDataAdapter._extract_fact` ([sec_company_facts.py:309-390](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:309)) | Reads `end` (period end) and `start` (period start) from each XBRL fact row via `date.fromisoformat`. Reads `filed` (real SEC acceptance date) **only inside `_select_fy_row`'s sort key** ([sec_company_facts.py:427-434](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:427)) to pick the latest-filed/amended observation. The chosen row's `filed` value is never propagated onward — it is not stored on the `FinancialFact`, not passed to `_parse_package`, and not attached to `FilingMetadata`. |
| 2. HTTP/client layer | `BoundedHttpClient` | No date semantics; passthrough JSON. Not implicated. |
| 3. Parser/normalizer | `_extract_fact` / `_select_fy_row` | See above — `filed` is read but dropped after use. |
| 4. Domain models/schemas | `FilingMetadata` ([filings.py:59-115](src/financial_intelligence/domain/financial/filings.py:59)) | Has distinct, correctly-named fields: `filed_at: date \| None`, `published_at: date \| None`, plus `retrieved_at`, `accession_or_reference`. The schema itself is sound and provider-neutral. No `__post_init__` invariant relates `filed_at` to `reporting_period.period_end` (i.e. the domain model does not *require* the conflation — callers introduce it). |
| 5. Repositories/services | `_parse_package` ([sec_company_facts.py:265-278](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:265)) | **Root cause site.** Constructs `FilingMetadata(..., filed_at=reporting_period.period_end, published_at=reporting_period.period_end, ...)`. `reporting_period` is the *fiscal period end*, not a filing/acceptance date. Same pattern in `reference_dataset.py:362-363` and `:568-569`, and `india_filings.py:197-198`. |
| 6. Research workflow | `manage_research_workflow.py` | No filing-date handling found (grep confirmed no `filed_at`/`filing_date` references); not implicated. |
| 7. Evidence objects | `capability_result_adapters.py:200-213` | `TaskEvidenceRef` uses `pkg.filing.retrieved_at` (correct — literal ingestion timestamp) for evidence chronology, **not** `filed_at`. Evidence-object chronology is therefore not corrupted by this defect; only the filing-metadata contract exposed downstream is. |
| 8. Report/synthesis layer | `financial_contracts.py:116-127` | `payload["package"] = self.package.to_dict()` and `payload["filing"] = self.package.filing.to_dict()` both surface the fabricated `filed_at`. |
| 9. API serialization | `api/routes/financials.py` (`filing: dict[str, Any] \| None` field) + `CompanyFinancialPackage.to_dict()` ([statements.py:328-343](src/financial_intelligence/domain/financial/statements.py:328)) | The fabricated `filed_at` reaches the externally-serializable contract as `filing.filed_at` and inside `package.filing.filed_at`, with no marker distinguishing it from a genuine source-provided value. |
| 10. Tests/fixtures | `test_financial_sec_hardening.py` fixture `_payload()` ([test_financial_sec_hardening.py:36-102](tests/unit/test_financial_sec_hardening.py:36)) | Fixture *already contains* realistic, distinct `filed` dates (`"2023-11-03"`, `"2024-11-01"`, `"2024-11-15"`) separate from `end` (period end, e.g. `"2024-09-28"`). No existing test reads or asserts on this field's propagation into `FilingMetadata.filed_at` — the fixture's most valuable signal is currently unused by any assertion. |

### Field inventory (what each date field actually means today)

| Field | Declared meaning | Actual source of value |
|---|---|---|
| `ReportingPeriod.period_end` | Fiscal period end date | Source-provided (`end` in SEC payload / `period_end` in fixtures) — correct |
| `ReportingPeriod.period_start` | Fiscal period start date | Source-provided (`start` in SEC payload) — correct |
| `FilingMetadata.filed_at` | *Should be* SEC filing/acceptance date | **Always** `reporting_period.period_end` — conflated with period end, in all 4 construction sites |
| `FilingMetadata.published_at` | *Should be* publication date (may legitimately equal filed_at in many cases) | **Always** `reporting_period.period_end` — same conflation |
| `FilingMetadata.retrieved_at` | Ingestion/HTTP-fetch timestamp | Correctly derived from adapter clock / caller-supplied clock — not implicated |
| `FilingMetadata.accession_or_reference` | Accession number / fixture reference | Correctly source-derived (`payload["cik"]` combined with CIK, or fixture literal) — not implicated |
| SEC payload `filed` (per fact row) | Authoritative SEC acceptance date for that XBRL fact | Read only for amendment tie-breaking; **discarded**, never stored anywhere |

No evidence was found of: `filing_date ← current date`, `filing_date ← unrelated field` (e.g. accession number), or NaN/garbage dates reaching the output. The conflation is specifically and exclusively `filing_date ← period_end_date`.

## 5. Relevant Files / Functions

- [src/financial_intelligence/infrastructure/financial/sec_company_facts.py:265-278](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:265) — `_parse_package`, root cause in the live adapter
- [src/financial_intelligence/infrastructure/financial/sec_company_facts.py:309-390](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:309) — `_extract_fact`, where `filed` is parsed but not retained on the fact
- [src/financial_intelligence/infrastructure/financial/sec_company_facts.py:392-434](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:392) — `_select_fy_row`, where `filed` is read only for sort ordering
- [src/financial_intelligence/infrastructure/financial/reference_dataset.py:355-367](src/financial_intelligence/infrastructure/financial/reference_dataset.py:355) and [:560-572](src/financial_intelligence/infrastructure/financial/reference_dataset.py:568) — same conflation in US fixture generator
- [src/financial_intelligence/infrastructure/financial/india_filings.py:190-205](src/financial_intelligence/infrastructure/financial/india_filings.py:190) — same conflation in India fixture parser
- [src/financial_intelligence/domain/financial/filings.py](src/financial_intelligence/domain/financial/filings.py) — `FilingMetadata` schema (sound; not the defect)
- [src/financial_intelligence/domain/financial/periods.py](src/financial_intelligence/domain/financial/periods.py) — `ReportingPeriod` (sound; not the defect)
- [src/financial_intelligence/application/financial_contracts.py:116-127](src/financial_intelligence/application/financial_contracts.py:116) — serialization surface where the fabricated date reaches API/report output
- [src/financial_intelligence/application/capability_result_adapters.py:195-220](src/financial_intelligence/application/capability_result_adapters.py:195) — evidence attribution (uses `retrieved_at`, not affected)
- [tests/unit/test_financial_sec_hardening.py:36-102](tests/unit/test_financial_sec_hardening.py:36) — fixture already has the data needed to catch this; no assertion currently uses it

## 6. Root Cause

`SecCompanyFactsFinancialDataAdapter._parse_package` (and the two fixture-based filing constructors) build `FilingMetadata` with:

```python
filed_at=reporting_period.period_end,
published_at=reporting_period.period_end,
```

`reporting_period.period_end` is the **fiscal period end date** (e.g. Apple's FY2024 10-K period end `2024-09-28`), not the date the filing was submitted/accepted by the SEC (e.g. `2024-11-01` or the amended `2024-11-15`, both of which are present in the same payload under each fact row's `filed` key and are actively read by `_select_fy_row` for a *different* purpose — selecting the most recent amendment). The real filing date is available in the source data and is simply never wired into the field meant to hold it. This is a data-flow/mapping bug (period end mapped to the wrong output field), not a missing-data-handling bug and not a live invented value — but the practical effect for anyone consuming `filing.filed_at` is identical to fabrication: a date is reported as "SEC filed" that the source never asserted as such.

## 7. Reproduction Steps

Non-destructive, deterministic, offline (`FakeTransport`, no network, no test/source files modified). Script location: session scratchpad, not committed to the repo.

```python
# Construct a payload with the exact shape test_financial_sec_hardening.py already
# uses, where "filed" (SEC acceptance date) differs from "end" (period end).
payload = {
  "cik": "0000320193",
  "facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
      {"start": "2023-10-01", "end": "2024-09-28", "fy": 2024, "fp": "FY",
       "val": 391035000000, "filed": "2024-11-01"},
      {"start": "2023-10-01", "end": "2024-09-28", "fy": 2024, "fp": "FY",
       "val": 391035000000, "filed": "2024-11-15"},  # authoritative (latest amendment)
    ]}},
    "NetIncomeLoss": {"units": {"USD": [
      {"start": "2023-10-01", "end": "2024-09-28", "fy": 2024, "fp": "FY",
       "val": 93736000000, "filed": "2024-11-15"}]}},
    "Assets": {"units": {"USD": [
      {"end": "2024-09-28", "fy": 2024, "fp": "FY",
       "val": 364980000000, "filed": "2024-11-15"}]}},
  }},
}
pkg = SecCompanyFactsFinancialDataAdapter(http_with_fake_transport).get_financial_package(APPLE_ID, fiscal_year=2024)
print(pkg.filing.filed_at)             # what the app reports as the SEC filing date
print(pkg.reporting_period.period_end) # actual fiscal period end
print(pkg.filing.to_dict()["filed_at"])# what the API/report layer would serialize
```

Case B (missing filing date at the source) was reproduced by re-running the same payload with every `filed` key stripped.

## 8. Reproduction Evidence

Actual captured output (current implementation, unmodified):

```
=== Case A/C: source has real 'filed' dates ===
reporting_period.period_end : 2024-09-28
actual SEC 'filed' (latest) : 2024-11-15
FilingMetadata.filed_at     : 2024-09-28
FilingMetadata.published_at : 2024-09-28
filed_at == period_end?     : True
filed_at == real SEC filed? : False

Serialized FilingMetadata.to_dict()['filed_at']: 2024-09-28

=== Case B: source omits 'filed' entirely ===
FilingMetadata.filed_at (no source filed date): 2024-09-28
-> Same as period_end even with zero filing-date evidence: True
```

Interpretation per case required by the task:

- **Case A (valid filing date provided by source):** FAILS the invariant. The source's authoritative filing date (`2024-11-15`) never reaches `filed_at`; `period_end` (`2024-09-28`) is reported instead. A 48-day discrepancy in this example, but the gap is generally weeks-to-months for real 10-K/10-Q filings.
- **Case B (source omits filing date):** The application does not preserve `None` and does not reject the record — it silently derives `filed_at` from `period_end` regardless of whether real filing-date evidence exists at all. This is the most severe sub-case: the field is populated with 100% confidence-presenting output even with zero source evidence for a filing date.
- **Case C (conflicting dates — filing vs report vs period-end):** The existing domain model does not carry a separate "report date" distinct from period end in the SEC path, so the specific conflict tested is filing-vs-period-end; the application unconditionally exposes period-end as the filing date, i.e. period-end wins by construction, not by any date-comparison logic.
- **Case D (malformed date):** A malformed `end`/`start` value is correctly rejected via `date.fromisoformat` raising `ValueError`, caught and converted to `return None` at [sec_company_facts.py:352](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:349) and [:361](src/financial_intelligence/infrastructure/financial/sec_company_facts.py:358) — the fact row is dropped, not silently coerced. A malformed `filed` value cannot be observed at all in current behavior because `filed` is never parsed as a date (only compared as a raw string for sort ordering at line 430), so malformed-`filed` cannot corrupt anything today — but this also means a well-formed, correct `filed` value is equally never used for its intended purpose.
- **Case E (API serialization):** Confirmed — `FilingMetadata.to_dict()["filed_at"]` and by extension `financial_contracts.py`'s `payload["filing"]["filed_at"]` / `payload["package"]["filing"]["filed_at"]` expose the fabricated (period-end) date with no field or flag indicating it is not a true filing date.

## 9. Current vs Expected Behavior

| | Current | Expected |
|---|---|---|
| Source provides filing date | Discarded; `filed_at` = `period_end` | `filed_at` = source filing date |
| Source omits filing date | `filed_at` = `period_end` (never `None`) | `filed_at` = `None` (or a status flag such as `FinancialDataAvailability` marking the filing date itself as unavailable), never silently defaulted |
| `published_at` | Same conflation as `filed_at` (also = `period_end`) | Distinct from `filed_at` where the source distinguishes them; `None` when unknown |
| API/report consumer | Cannot tell the difference between a real filing date and a period-end fallback | Should be able to trust `filed_at` is either a genuine source-attested filing date or explicitly `None` |

## 10. Data Integrity / Security Impact

**Confirmed behavior:**
- `FilingMetadata.filed_at`/`published_at` do not represent SEC filing/acceptance dates; they always equal the fiscal period end. This is exposed through the API/report serialization layer (`financial_contracts.py`, `api/routes/financials.py`) as if it were authoritative filing metadata.
- This does not corrupt financial *values* (revenue, net income, assets are all correctly sourced and, per `test_amended_filing_prefers_later_filed`, correctly prefer the latest amendment). It corrupts *filing metadata about* those values.
- Evidence chronology used by the verification engine (`TaskEvidenceRef.retrieved_at`) is **not** affected — it uses the adapter's ingestion clock, not `filed_at`. F01–F04 verification-engine remediations are not implicated by this defect.

**Potential downstream impact (not confirmed, plausible given the above):**
- Incorrect research chronology: a report referencing "as filed on {filed_at}" would cite the period-end date instead of the true filing date, understating the lag between period close and public disclosure (in this example ~48 days; for real 10-Ks typically 30–75 days).
- Misleading financial research reports if any narrative synthesis surfaces `filing.filed_at` as "filed on" text (this audit did not find synthesis-layer prose that currently does so, but the API contract exposes the field for any consumer, including the frontend or LLM-drafted commentary, to use this way).
- Auditability: an analyst trying to verify "was this the correct EDGAR filing revision" cannot use `filed_at` to distinguish an original filing from a 10-K/A amendment, since both would show the identical period-end value.

**Not exaggerated:** No evidence of fabricated *financial figures*, no evidence of `datetime.now()`-style invented dates, no evidence this leaks into evidence-chronology/verification correctness used by prior F01–F04 fixes.

## 11. Existing Test Coverage

- `tests/unit/test_financial_sec_hardening.py::test_valid_payload_parses_instant_and_duration` — asserts `package.filing.authority_tier == 1` only; does not check `filed_at`.
- `tests/unit/test_financial_sec_hardening.py::test_amended_filing_prefers_later_filed` — despite its name, asserts only that the **revenue value** from the latest-filed row wins; does not assert anything about `filing.filed_at`, even though the fixture already encodes distinct `filed` dates per row.
- `tests/unit/test_financial_domain_hardening.py::test_filing_rejects_javascript_url` — validates URL sanitization on `FilingMetadata`, unrelated to date correctness.
- No test anywhere in the suite asserts that `FilingMetadata.filed_at` corresponds to a source-provided filing/acceptance date, that it differs from `period_end` when the source provides a distinct value, or that it is `None`/absent when the source provides no filing date.
- `tests/unit/test_phase4_contract_freeze.py::test_sec_instant_assets_do_not_require_start` covers instant-period parsing shape, not filing-date semantics.

## 12. Test Gaps

1. No test proves `filed_at` reflects the source's `filed` value rather than `period_end`.
2. No test proves `filed_at` is `None` (or otherwise explicitly marked unavailable) when the source provides no filing date — current behavior silently defaults, and nothing would fail if that default were removed or changed.
3. No test asserts `published_at` independently of `filed_at`, or documents that they are presently identical by construction.
4. No API-level (`financial_contracts.py` / `api/routes/financials.py`) test asserts the serialized `filing.filed_at` value against an authoritative source date.
5. No test covers the fixture generators (`reference_dataset.py`, `india_filings.py`) for filing-date correctness at all — only the live SEC adapter fixture even contains a `filed` field.

## 13. Recommended Remediation (NOT implemented — plan only)

Smallest architecture-consistent fix, staged:

1. **Live SEC adapter (`sec_company_facts.py`):** In `_extract_fact`, parse the row's `filed` value (when present and a valid ISO date) and return it alongside the fact/period data (e.g. via a small internal tuple or by threading it through `_select_fy_row`'s return value, which already reads it). In `_parse_package`, set `filed_at` from the selected row's actual `filed` value instead of `reporting_period.period_end`; set `filed_at=None` when `filed` is absent or fails to parse — do not fall back to `period_end`. Leave `published_at` as a separate, honestly-`None`-when-unknown field rather than mirroring `filed_at`.
2. **Fixture generators (`reference_dataset.py`, `india_filings.py`):** These are demo/fixture data with no independent "filed" concept in their payload shape today. Two acceptable options, smallest first:
   - (a) Keep `filed_at`/`published_at` as explicit, clearly-labeled fixture constants distinct from `period_end` (i.e. give the fixtures a real, plausible filing date a few weeks after period end) so fixtures stop modeling the exact bug being fixed, or
   - (b) Set `filed_at=None`/`published_at=None` in fixtures that have no genuine filing-date source, since `FilingMetadata` already supports `None` for both fields.
   Given these are demonstration fixtures (not live SEC data), option (a) with clearly-commented plausible dates is likely more useful for downstream consumers/tests than `None`, but this is a product decision, not a technical constraint — flagging for user input during implementation planning.
3. **No change needed** to `FilingMetadata`, `ReportingPeriod`, `filing_pipeline.py`, `capability_result_adapters.py`, or the verification engine — the schema is sound and evidence chronology is unaffected.
4. **Optional hardening:** add a `__post_init__` sanity check in `FilingMetadata` that warns/rejects when `filed_at is not None and filed_at < reporting period start` type inconsistencies are introduced later — deferred, not required to fix this specific defect, and risks scope creep beyond F05.

This keeps the existing API contract shape (`filing.filed_at` remains a `date | None` field) — only the *value* changes, and it can become `None` in more cases than before, which is a compatible, more-honest contract, not a breaking schema change.

## 14. Regression Test Plan

**File: `tests/unit/test_financial_sec_hardening.py`** (extend existing fixture-based class)
- `test_filed_at_reflects_source_filed_date_not_period_end`: using the existing `_payload()` fixture (already has `filed: "2024-11-15"` distinct from `end: "2024-09-28"`), assert `package.filing.filed_at == date(2024, 11, 15)` and `package.filing.filed_at != package.reporting_period.period_end`.
- `test_filed_at_none_when_source_omits_filed_date`: strip `filed` from all rows in a payload copy; assert `package.filing.filed_at is None` (post-fix) rather than assuming any non-`None` default.
- `test_amended_filing_filed_at_uses_latest_amendment`: extend `test_amended_filing_prefers_later_filed` (or add alongside it) to also assert `filing.filed_at == date(2024, 11, 15)` (the later of the two `filed` values already in the fixture), proving both the fact value *and* the filing date pick the latest amendment consistently.
- `test_malformed_filed_date_does_not_corrupt_filing_metadata`: set `filed` to a malformed string (e.g. `"not-a-date"`) on the selected row; assert the fact is still accepted (value/period unaffected) but `filing.filed_at is None` rather than any coerced/guessed date.

**File: `tests/unit/test_financial_domain.py` or `test_financial_domain_hardening.py`**
- `test_filing_metadata_filed_at_independent_of_period_end`: construct `FilingMetadata` directly with `filed_at` deliberately different from `reporting_period.period_end` and assert both round-trip independently through `to_dict()`.
- `test_filing_metadata_allows_none_filed_at`: construct with `filed_at=None` and assert `to_dict()["filed_at"] is None` (already supported by the schema; documents the contract explicitly).

**API-level coverage: `tests/unit/test_synthesis_api.py` or a new `tests/unit/test_financial_contracts_api.py`**
- `test_financial_contract_serializes_authoritative_filed_at`: build a `CompanyFinancialPackage` with a filing whose `filed_at` differs from `reporting_period.period_end`; assert the serialized contract's `payload["filing"]["filed_at"]` and `payload["package"]["filing"]["filed_at"]` both equal the authoritative value, not the period end.

**Negative / edge cases to include across the above:**
- Missing filing date at source → `None`, not a default.
- Malformed filing date at source → `None` with the surrounding fact/statement still valid (isolate failure to the metadata field only).
- Two conflicting `filed` values across amendments → latest wins consistently for both fact selection and filing-date reporting.
- Fixture-path packages (`reference_dataset.py`, `india_filings.py`) — add coverage once the remediation decision for fixtures (Section 13, item 2) is made, asserting whatever the chosen fixture behavior (explicit plausible date vs `None`) actually is.

## 15. Risks / Compatibility Considerations

- **API contract:** `filing.filed_at` may become `None` more often than today (e.g., for fixture data if option 2(b) is chosen, or for any live payload lacking `filed`). Any frontend/consumer currently assuming `filed_at` is always populated must tolerate `None`. This audit found no consumer in this repo that fails on `None` (the field is already declared `date | None` everywhere), so this is a low-risk, compatible change — but it should be called out to any external API consumers.
- **Fixture behavior decision:** Section 13 item 2 needs a product decision (plausible synthetic filing date vs `None`) before implementation; the two paths have different test-assertion shapes (Section 14 file 1 tests should be revisited once decided).
- **Do not conflate with F01–F04:** `capability_result_adapters.py`'s evidence chronology already correctly uses `retrieved_at`; remediation must not touch that path.
- **No live-network dependency:** all reproduction and proposed tests use `FakeTransport`/fixture payloads; no change to CI's no-live-SEC-dependency guarantee.

## 16. Files Expected to Change During Implementation

- `src/financial_intelligence/infrastructure/financial/sec_company_facts.py` (root cause fix)
- `src/financial_intelligence/infrastructure/financial/reference_dataset.py` (fixture fix, pending product decision)
- `src/financial_intelligence/infrastructure/financial/india_filings.py` (fixture fix, pending product decision)
- `tests/unit/test_financial_sec_hardening.py` (new/extended regression tests)
- `tests/unit/test_financial_domain.py` or `tests/unit/test_financial_domain_hardening.py` (new domain-level regression tests)
- `tests/unit/test_synthesis_api.py` or a new `tests/unit/test_financial_contracts_api.py` (API-level regression test)

No changes expected to: `filings.py`, `periods.py`, `filing_pipeline.py`, `capability_result_adapters.py`, verification engine/evidence/result (F01–F04 territory), API route request/response models beyond existing `filing: dict[str, Any] | None`.

## 17. Final Audit Verdict

**CONFIRMED.**

The system substitutes the fiscal period-end date for the SEC filing date in every `FilingMetadata` construction path, including the live SEC EDGAR adapter, unconditionally and regardless of whether the source provides a genuine, differing filing date. This was reproduced deterministically and non-destructively using the project's own existing test fixture (which already contains the necessary distinguishing data but is not asserted on). The financial *values* themselves (revenue, net income, assets, amendment selection) are correctly sourced and not affected. Evidence chronology used by the verification engine is not affected. The defect is isolated to filing *metadata* — specifically `FilingMetadata.filed_at` and `FilingMetadata.published_at` — reaching the API/report serialization layer as if authoritative when it is in fact always a derived period-end value.
