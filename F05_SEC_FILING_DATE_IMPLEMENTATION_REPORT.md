# F05 — SEC Filing-Date Fabrication: Implementation Report

**Status: IMPLEMENTED. Not committed, not pushed.**

Scope: F05 only. No F01–F04 behavior was touched (verified below). No F06 work started.

## 1. Old Behavior

`FilingMetadata.filed_at` and `FilingMetadata.published_at` were unconditionally set to `reporting_period.period_end` (the fiscal period end date) in three places:

- `SecCompanyFactsFinancialDataAdapter._parse_package` (live SEC EDGAR adapter) — despite the SEC XBRL payload carrying a genuine `filed` (acceptance) date per fact row, which was read only for amendment tie-breaking and then discarded.
- `reference_dataset.py` (`_apple_package`, `_reliance_package` — US/India demo fixtures).
- `india_filings.py` (`parse_india_results_fixture` — India fixture parser).

Confirmed reproduction from the audit: source `filed = 2024-11-15`, `period_end = 2024-09-28` → application reported `filed_at = 2024-09-28`. Removing `filed` from the source entirely still produced `filed_at = 2024-09-28`.

## 2. New Behavior

- **Live SEC adapter:** `filed_at` is now the actual SEC `filed` value from the XBRL fact row(s) underlying the selected reporting period, parsed via `date.fromisoformat`. When multiple duration facts share the reporting period (e.g. Revenues and NetIncomeLoss), the latest of their `filed` dates is used, consistent with the existing "prefer later filed/amended observation" selection semantics for fact values. `published_at` mirrors `filed_at` (SEC EDGAR has no separate publication-date field distinct from the acceptance date — accepting a filing *is* what makes it public — so this is an honest reuse of the one authoritative timestamp the source provides, not a new conflation).
- **Missing or malformed `filed`:** `filed_at` (and `published_at`) is `None`. No fallback to `period_end`, `retrieved_at`, or any other field. Malformed strings are caught by `date.fromisoformat`'s `ValueError` and treated identically to "absent" — never coerced or guessed.
- **Fixture generators** (`reference_dataset.py`, `india_filings.py`): both are explicitly documented as REFERENCE/DEMO data with no authoritative filing-date field in their payload shape (confirmed by re-reading their module docstrings and expected-payload documentation — neither carries a genuine filing/disclosure date anywhere, so there was no "already-available authoritative value" to preserve). Per the task's fixture guidance, `filed_at`/`published_at` are now explicitly `None` rather than borrowing `period_end`. This decision is documented inline at each of the three call sites.

## 3. Files Changed

**Source (3 files):**
- [`src/financial_intelligence/infrastructure/financial/sec_company_facts.py`](src/financial_intelligence/infrastructure/financial/sec_company_facts.py)
- [`src/financial_intelligence/infrastructure/financial/reference_dataset.py`](src/financial_intelligence/infrastructure/financial/reference_dataset.py)
- [`src/financial_intelligence/infrastructure/financial/india_filings.py`](src/financial_intelligence/infrastructure/financial/india_filings.py)

No changes to `filings.py`, `periods.py`, `filing_pipeline.py`, `statements.py`, `capability_result_adapters.py`, `financial_contracts.py`, or any verification/evidence module — the existing schema and evidence-chronology path were already sound (per audit §4/§6) and required no changes.

**Tests (4 files: 3 extended, 1 new):**
- [`tests/unit/test_financial_sec_hardening.py`](tests/unit/test_financial_sec_hardening.py) — 6 new tests
- [`tests/unit/test_financial_domain_hardening.py`](tests/unit/test_financial_domain_hardening.py) — 2 new tests
- [`tests/unit/test_financial_prompt2_infra.py`](tests/unit/test_financial_prompt2_infra.py) — 2 new tests
- [`tests/unit/test_financial_contracts_api.py`](tests/unit/test_financial_contracts_api.py) — new file, 2 tests

(Note: `tests/unit/test_synthesis_api.py` and `tests/unit/test_verification_engine.py` shown in `git diff --stat` below were already modified before this F05 session as part of prior F01–F04 work; this session made no further changes to either.)

## 4. Detailed Change Description

### `sec_company_facts.py`

- Added `_parse_filed_date(raw: object) -> date | None`: parses the SEC XBRL `filed` field; returns `None` for anything that isn't a valid ISO date string (missing, wrong type, or malformed) — never raises, never substitutes another field.
- `_extract_fact` now returns `tuple[FinancialFact, date | None] | None` instead of `FinancialFact | None`, threading the row's parsed filed date alongside the fact it was extracted from. This is a private-method signature change internal to the adapter (both call sites are in the same class); it does not touch `FinancialFact` or any shared domain model.
- `_parse_package` collects `filed_dates: dict[int, date | None]` keyed by fact identity (`id(fact)`) as facts are extracted. After the reporting period is selected (unchanged selection logic), it computes `filed_at` as the latest non-`None` filed date among the duration facts whose period equals the selected `reporting_period`, or `None` if none of them have a parseable filed date. `FilingMetadata(filed_at=filed_at, published_at=filed_at, ...)` replaces the old `period.period_end` fallback.

### `reference_dataset.py` / `india_filings.py`

- `filed_at=period.period_end` / `filed_at=period_end` → `filed_at=None`, with matching `published_at=None`, and an inline comment explaining these are reference/demo fixtures with no authoritative filing-date source, per the fixture-decision requirement in the task.

## 5. Tests Added / Changed

All new tests are additive; no existing assertion was weakened, relaxed, or removed.

**`test_financial_sec_hardening.py`** (extends `SecCompanyFactsHardeningTests`, uses the existing `_payload()` fixture which already carries `filed: "2023-11-03"/"2024-11-01"/"2024-11-15"` distinct from `end: "2024-09-28"`):
1. `test_filed_at_reflects_source_filed_date_not_period_end` — real source `filed` date preserved exactly; differs from `period_end`.
2. `test_filed_at_uses_latest_amendment_consistently_with_value_selection` — two amendment rows (`filed=2024-11-01` / `2024-11-15`) resolve to the later date, matching existing revenue-value amendment semantics.
3. `test_filed_at_none_when_source_omits_filed_date` — strips `filed` from every row; `filed_at`/`published_at` are `None`; explicitly asserts `filed_at != period_end` (the exact defect being regression-tested).
4. `test_malformed_filed_date_does_not_fall_back_to_period_end` — corrupts `filed` to `"not-a-date"` on all matching duration rows; fact values remain correct; `filed_at` is `None`, not `period_end`.
5. `test_published_at_mirrors_filed_at_not_period_end` — `published_at == filed_at` and both `!= period_end`.
6. `test_filing_contract_serializes_authoritative_filed_at` — `FilingMetadata.to_dict()["filed_at"]` (the API-facing serialization) carries the authoritative date, not `period_end`.

**`test_financial_domain_hardening.py`** (domain-level, no adapter involved):
7. `test_filing_metadata_filed_at_independent_of_period_end` — constructing `FilingMetadata` with `filed_at` distinct from `reporting_period.period_end` round-trips correctly through `to_dict()`.
8. `test_filing_metadata_allows_none_filed_at` — `filed_at=None`/`published_at=None` round-trip as `None` through `to_dict()`.

**`test_financial_prompt2_infra.py`** (fixture generators):
9. `test_fixture_parser_leaves_filed_at_none_without_source_date` (India fixture parser) — confirms `filed_at`/`published_at` are `None`, not `period_end`.
10. `test_reference_fixtures_do_not_fabricate_filed_at` (`build_reference_financial_packages()`, both Apple and Reliance) — confirms neither reference fixture reports a fabricated `filed_at`.

**`test_financial_contracts_api.py`** (new file — API/report-layer contract):
11. `test_serialized_contract_exposes_authoritative_filed_at` — `FinancialSnapshotResult.to_dict()`'s `payload["filing"]["filed_at"]` and `payload["package"]["filing"]["filed_at"]` both carry the authoritative date.
12. `test_serialized_contract_leaves_filed_at_none_when_unknown` — same contract path with `filed_at=None`, confirming the API never backfills `period_end`.

## 6. Non-Vacuous Validation

To prove these 12 tests actually exercise the fixed logic (rather than passing vacuously), the three source-file fixes were temporarily reverted (`git stash` on exactly `sec_company_facts.py`, `reference_dataset.py`, `india_filings.py`, restoring the pre-fix vulnerable behavior) and the new/extended test modules were re-run:

```
8 failed, 50 passed in 0.66s
```

All 8 tests that depend on the adapter/fixture fix failed against the vulnerable implementation, with failures exactly matching the defect:
- `test_filed_at_reflects_source_filed_date_not_period_end`
- `test_filed_at_uses_latest_amendment_consistently_with_value_selection`
- `test_filed_at_none_when_source_omits_filed_date`
- `test_malformed_filed_date_does_not_fall_back_to_period_end`
- `test_published_at_mirrors_filed_at_not_period_end`
- `test_filing_contract_serializes_authoritative_filed_at`
- `test_fixture_parser_leaves_filed_at_none_without_source_date`
- `test_reference_fixtures_do_not_fabricate_filed_at`

Example failure captured against the vulnerable code:
```
AssertionError: datetime.date(2024, 9, 28) is not None   # filed_at wrongly equals period_end
```

The remaining 4 new tests (`test_filing_metadata_filed_at_independent_of_period_end`, `test_filing_metadata_allows_none_filed_at`, and the two `test_financial_contracts_api.py` tests) exercise the `FilingMetadata`/contract schema directly, which was already correct before this fix (the audit found the schema itself sound — see audit §4/§6) — these passed both before and after, which is expected and correctly documents that the domain model never needed to change.

The three fixed source files were then restored (`git stash pop`) and the full suite re-run to confirm the fix (below).

## 7. Targeted Test Result (after fix restored)

```
python -m pytest -q tests/unit/test_financial_sec_hardening.py tests/unit/test_financial_domain.py \
  tests/unit/test_financial_domain_hardening.py tests/unit/test_financial_prompt2_infra.py \
  tests/unit/test_phase4_contract_freeze.py tests/unit/test_financial_contracts_api.py

84 passed in 1.46s
```

## 8. Full Test Suite Result

```
python -m pytest -q

785 passed, 130 subtests passed in 10.94s
```

(Baseline before F05 implementation: 773 passed, 130 subtests passed. The +12 is exactly the new regression tests added; no test was removed, skipped, or weakened.)

## 9. Ruff Result

```
python -m ruff check src tests
All checks passed!

python -m ruff format --check src tests
256 files already formatted
```

(`sec_company_facts.py` required one `ruff format` pass after the initial edit — applied, then re-verified clean. Several pre-existing untracked `*.md` audit report files from prior phases, and this session's own `F05_SEC_FILING_DATE_REMEDIATION_PLAN.md`, are flagged by `ruff format --check .` at the repo root because they contain fenced Python code blocks; this is markdown formatting noise, not a source-code issue, and is out of scope for F05 — confirmed by scoping the check to `src tests`, which is clean.)

## 10. Mypy Result

The project's mypy config (`pyproject.toml`, `[tool.mypy]`) scopes strict checking to `packages = ["financial_intelligence"]`, i.e. `src/` only — tests are not part of the strict-mypy contract, consistent with how F04's baseline was reported.

```
PYTHONPATH=src python -m mypy
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check ...
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check ...
Found 2 errors in 1 file (checked 190 source files)
```

Both errors are in `domain/orchestration/graph.py`, a file this session never touched. Verified pre-existing: re-running the identical `mypy` invocation against a clean stash of *all* working-tree changes (i.e. the original `d983bce` HEAD state) reproduces the exact same 2 errors in the exact same file — confirming they predate F05 (and predate this session's F01–F04 working-tree changes too) and are unrelated to filing-date handling. No F05-changed file (`sec_company_facts.py`, `reference_dataset.py`, `india_filings.py`) contributes any mypy error.

## 11. Reproduction-After-Fix

Re-ran the exact audit reproduction script (unchanged from the F05 audit) against the fixed code:

```
=== Case A/C: source has real 'filed' dates ===
reporting_period.period_end : 2024-09-28
actual SEC 'filed' (latest) : 2024-11-15
FilingMetadata.filed_at     : 2024-11-15
FilingMetadata.published_at : 2024-11-15
filed_at == period_end?     : False
filed_at == real SEC filed? : True

Serialized FilingMetadata.to_dict()['filed_at']: 2024-11-15

=== Case B: source omits 'filed' entirely ===
FilingMetadata.filed_at (no source filed date): None
-> Same as period_end even with zero filing-date evidence: False
```

The original defect (`filed_at == period_end` regardless of source data) is confirmed no longer reproducible: `filed_at` now equals the authoritative SEC date when present (`2024-11-15`, not `2024-09-28`), and is `None` (not `2024-09-28`) when the source provides no filing date at all.

## 12. F01–F04 Regression Check

- `git diff --stat` (below) shows `manage_research_workflow.py`, `verification/engine.py`, `verification/evidence.py`, `verification/result.py`, `orchestration/capability_executor.py`, `workflow/in_memory_store.py`, `test_synthesis_api.py`, and `test_verification_engine.py` all present with the same change sizes as at the start of this F05 session — this implementation touched none of them.
- Full suite (785 passed) includes all F01–F04 regression tests (`test_capability_executor_hardening.py`, `test_verification_hardening.py`, `test_verification_semantics_hardening.py`, `test_workflow_cancellation_race.py`, plus the modified `test_synthesis_api.py`/`test_verification_engine.py`) — all still passing.
- `capability_result_adapters.py` (the F01–F04-relevant evidence-chronology path that uses `retrieved_at`, not `filed_at`) was inspected during the audit and confirmed unaffected; it was not modified in this implementation.

## 13. Compatibility Considerations

- `FilingMetadata.filed_at`/`published_at` are unchanged `date | None` fields — no schema/type change. Consumers that already handle `None` (all current in-repo consumers do; confirmed no code dereferences these fields without a null check) are unaffected.
- `filed_at`/`published_at` will now be `None` more often than before:
  - Always `None` for the reference/demo fixtures (`reference_dataset.py`, `india_filings.py`) — previously these always returned a (fabricated) date; any test or downstream code that assumed a non-`None` value from these specific fixtures would need to tolerate `None`. No such assumption was found in the existing test suite (verified via the full-suite run) or in application code (verified via the earlier grep for `filed_at` consumers in the audit).
  - `None` for live SEC data whenever the XBRL payload's `filed` field is absent or malformed for every duration fact matching the selected period — previously this always returned `period_end`.
- No API contract shape change: `financial_contracts.py`'s `payload["filing"]["filed_at"]` / `payload["package"]["filing"]["filed_at"]` remain in the same place with the same JSON type (`str | None`), only the *value* is now honest instead of a period-end substitute.
- No new dependencies introduced.

## Final Validation Summary

| Check | Result |
|---|---|
| Targeted F05 tests | 84 passed |
| Full test suite | 785 passed, 130 subtests passed (baseline 773 + 12 new) |
| Ruff check (src, tests) | All checks passed |
| Ruff format check (src, tests) | Clean (256 files) |
| Mypy strict (`src`, project-configured scope) | 2 pre-existing errors, confirmed unrelated to F05 and present on clean HEAD |
| Reproduction after fix | Original defect no longer reproducible |
| Non-vacuous test proof | 8/12 new tests fail against reverted (vulnerable) source; 4/12 correctly pass both before and after since they test the already-sound domain schema |
| F01–F04 files | Unmodified this session; all F01–F04 regression tests still passing |
