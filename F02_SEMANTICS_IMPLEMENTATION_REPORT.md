# F02 Verification Semantics Implementation Report

**Scope implemented:** Option B from `F02_VERIFICATION_SEMANTICS_REVIEW.md` — a narrow semantic cleanup
distinguishing "definitively verified" from "partially supported" from "evidence exists," at the specific call
sites where the ambiguity was a real (not merely cosmetic) problem.
**Git state before implementation:** branch `main`, HEAD `d983bce`, working tree matched the expected post-F01/F02
state exactly (`evidence.py` and `test_synthesis_api.py` modified from the prior task; `test_verification_hardening.py`
new; plus the session's untracked audit documents). Baseline test run confirmed **735 passed** before any change
in this task, matching the expected baseline stated in your instructions.
**Git state after implementation:** no branch change, no commit, no push.

---

## 1. Root Problem

`VerificationResult.is_verified` (and three inline duplicates of the same set literal elsewhere in the codebase)
answered two structurally different questions with one boolean:
1. "Is this claim confident enough that no further research is needed?" (a resource/orchestration decision)
2. "Does this claim have any supporting evidence at all, regardless of confidence?" (an evidentiary-existence
   check)

Because `PARTIALLY_VERIFIED` satisfies both questions' underlying evidentiary shape (some non-contradicted
supporting evidence exists) while differing sharply in the *strength* of that evidence, a single shared boolean
caused the critic/orchestration loop (`VerificationEngine.assess_critic`) to treat a weak, Tier-4,
keyword-overlap-only match exactly the same as a strong, Tier-1, structurally-confirmed match: both stopped
further research.

## 2. Why `is_verified` Was Ambiguous

Traced in `F02_VERIFICATION_SEMANTICS_REVIEW.md` §1-§2 and re-confirmed here: `VerificationStatus.VERIFIED` and
`PARTIALLY_VERIFIED` are produced by the exact same evidentiary shape (`has_supporting and not has_contradicting`,
not stale) and differ **only** by which side of a confidence-score threshold (`0.7` by default) the result lands
on. Nothing in the engine records *how* that confidence was earned — a clean bag-of-words match against a
low-authority source and a `Decimal`-exact match against a Tier-1 source can both produce `PARTIALLY_VERIFIED` at
a given score. `is_verified`'s definition (`status in {VERIFIED, PARTIALLY_VERIFIED}`) collapsed this distinction
for every caller that used it, even though, per the review, two of its real usages (`assess_critic`'s resource
decision) and two other inline duplicates (`contracts.py`'s evidentiary-existence checks) needed different
answers.

## 3. Changes Made

### 3.1 `src/financial_intelligence/domain/verification/result.py`
Added a new read-only property, `is_definitively_verified`, immediately after the existing `is_verified` property
(which is **unchanged**, kept for backward compatibility):
```python
@property
def is_definitively_verified(self) -> bool:
    return self.status is VerificationStatus.VERIFIED
```
No enum value was added, no existing property's behavior was changed, and no wire-format field was touched.

### 3.2 `src/financial_intelligence/domain/verification/engine.py`
- `assess_critic`: `if result.is_verified:` → `if result.is_definitively_verified:`. The critic loop now stops
  only for `VERIFIED`, never for `PARTIALLY_VERIFIED`.
- `_generate_critic_requests`: the guard `if status in {VERIFIED, PARTIALLY_VERIFIED}: return ()` was narrowed to
  `if status is VerificationStatus.VERIFIED: return ()`, and a new `elif status ==
  VerificationStatus.PARTIALLY_VERIFIED:` branch was added that generates an actual `CriticRequest` (reason:
  `"Evidence only partially supports {claim_type} claim; seek stronger or additional corroboration"`). **This
  second change was required, not optional**: `assess_critic`'s non-definitive branch raises `ValueError` if
  `result.critic_requests` is empty for a non-exhausted-budget, non-definitive result (existing invariant,
  `engine.py:158-159`, unchanged). Without this second edit, changing `assess_critic` alone would have made every
  `PARTIALLY_VERIFIED` result crash with `"non-terminal verification result has no critic request"`, since
  `_generate_critic_requests` previously returned `()` for that status. Both functions were changed together, as
  anticipated in the review's own Option A compatibility note.

### 3.3 Files intentionally left unchanged
- `src/financial_intelligence/domain/synthesis/contracts.py` — its three uses of
  `{VERIFIED, PARTIALLY_VERIFIED, STALE}` (in `VerifiedClaimInput.__post_init__` and `_validate_material_claim`)
  were **not** touched. Both already ask "does evidence exist for this claim shape," not "is this definitive" —
  confirmed correct by the review and re-confirmed in this pass by tracing their exact purpose (an internal
  consistency check that a claimed status is backed by real evidence, and a structural-completeness gate for
  material claims).
- `src/financial_intelligence/domain/synthesis/policy.py`'s `_citation_evidence` — same reasoning; it decides
  which evidence to cite, not how strongly to assert the claim, and `PARTIALLY_VERIFIED` claims correctly still
  cite their supporting evidence.
- **No shared "evidence exists" helper was introduced.** Your instructions made this explicitly optional ("if
  helpful... but only if minimal"). Introducing one would have required editing `contracts.py` and `policy.py` —
  two files with no bug in them — purely to rename an already-correct inline check, which conflicts with "narrow
  semantic cleanup" and "do not modify unrelated callers." This is a documented choice, not an oversight: if you
  want the shared helper for readability later, it is a small, low-risk follow-up, but it was not required to
  close the semantic ambiguity this task targets.
- `VerificationResult.needs_critic` (a separate, pre-existing, unused-in-production property, only referenced by
  one test) was left untouched — it was not named in your instructions or the review's four identified call
  sites, and changing it would be an unrelated-caller edit.
- `is_verified` itself was **not** removed or redefined, per your explicit instruction to add a new accessor
  rather than change existing status/enum semantics; it continues to mean exactly what it meant before.

## 4. Call Sites Changed

| File | Function | Before | After |
|---|---|---|---|
| `engine.py` | `VerificationEngine.assess_critic` | `if result.is_verified:` | `if result.is_definitively_verified:` |
| `engine.py` | `VerificationEngine._generate_critic_requests` | `if status in {VERIFIED, PARTIALLY_VERIFIED}: return ()` | `if status is VERIFIED: return ()`, plus new `PARTIALLY_VERIFIED` branch generating a critic request |

## 5. Call Sites Intentionally NOT Changed

| File | Function | Why unchanged |
|---|---|---|
| `domain/synthesis/contracts.py` | `VerifiedClaimInput.__post_init__` | Asks "does evidence exist for this status," an internal consistency invariant — correct as-is |
| `domain/synthesis/contracts.py` | `VerifiedClaimInput._validate_material_claim` | Asks "is this material claim's evidentiary shape acceptable," not "is it definitive" — correct as-is |
| `domain/synthesis/policy.py` | `VerifiedClaimGate._citation_evidence` | Asks "is there evidence to cite," correct as-is |
| `domain/verification/result.py` | `VerificationResult.needs_critic` | Not named in scope; pre-existing, effectively unused (one test only); left untouched to avoid an unrelated-caller edit |
| `domain/verification/result.py` | `VerificationResult.is_verified` | Kept unchanged for backward compatibility, per explicit instruction not to change existing status/enum semantics |
| `domain/verification/result.py` | `VerificationResult.to_dict()`'s `"is_verified"` field | Unchanged; not currently reachable through any exercised HTTP response (confirmed in the prior review, re-confirmed: no route calls `VerificationResult.to_dict()` directly) |

## 6. Tests Added

**New file: `tests/unit/test_verification_semantics_hardening.py` (12 tests)**

- `DefinitiveVerificationAccessorTests` (5 tests): `VERIFIED` → `is_definitively_verified == True`;
  `PARTIALLY_VERIFIED` → `False` (while `is_verified` remains `True`, proving the two accessors now genuinely
  differ); `CONTRADICTED` → `False`; the F02 "ambiguous polarity" case (which resolves to `UNVERIFIABLE` at the
  `VerificationStatus` level — there is no separate `NEUTRAL` status, only an internal `EvidenceBundle`
  classification bucket, documented explicitly in the test) → `False`; and a regression guard for
  `CONFLICTING`/`STALE` → `False`.
- `CriticLoopSemanticsTests` (4 tests): critic stops only for `is_definitively_verified` (`VERIFIED`); critic
  **continues** for `PARTIALLY_VERIFIED` (asserts `RESEARCH_REQUIRED`, not `SUFFICIENT_EVIDENCE`); the exact
  low-authority, keyword-overlap-only scenario from the review's §3.2 (Tier-4 source, clean lexical match) cannot
  stop the critic loop as if definitively verified; and a regression guard that `ATTEMPTS_EXHAUSTED` still fires
  correctly once the budget is spent on a still-partial claim (proving the new mandatory `PARTIALLY_VERIFIED`
  critic request doesn't break the exhaustion path).
- `ContractsEvidenceExistenceUnaffectedTests` (2 tests): `VerifiedClaimInput.__post_init__` still raises for a
  `PARTIALLY_VERIFIED`/no-evidence mismatch (unchanged behavior); `VerifiedClaimGate._citation_evidence` still
  returns supporting refs for a genuinely `PARTIALLY_VERIFIED` claim (unchanged behavior).
- `SynthesisReportingCompatibilityTests` (1 test): a `PARTIALLY_VERIFIED` claim run through the real
  `VerifiedClaimGate.evaluate` still produces `ClaimDisposition.QUALIFIED`, the exact rendered text `"Partially
  verified: {claim text}"`, and `verification_status == PARTIALLY_VERIFIED` in the gated output — unchanged.

**Existing file modified: `tests/unit/test_verification_engine.py`** — `test_no_critic_requests_for_verified_or_partial`
was split into two tests, **not weakened**:
- `test_no_critic_requests_for_verified` — retains the exact original `VERIFIED`-side assertion
  (`critic_requests == ()`), unchanged.
- `test_critic_request_generated_for_partially_verified` — **replaces** the old (now-incorrect)
  `partial.critic_requests == ()` assertion with the new, deliberately-changed expectation
  (`len(partial.critic_requests) == 1`, `is_definitively_verified is False`), documented in the test's own
  docstring as an intentional behavior change approved by this task, not a silently patched-over failure.

This split was necessary because the old test's name and assertion directly encoded the exact conflated behavior
this task was approved to change; per your instruction not to weaken or delete tests, the fix here is to make the
test assert the *new, correct, approved* behavior with full rigor (including a length and content check, not
merely removing the old assertion), not to delete or loosen it.

**API-level coverage (#9 "API verification status remains unchanged"):** no new API-level test was added for
this specific item. The existing `tests/unit/test_synthesis_api.py` suite already contains direct assertions on
`verification_status == "verified"` (golden flow, line ~140) and, from the prior F01/F02 task,
`verification_status == "partially_verified"`-adjacent checks were not present, so this was verified by
**re-running the full file** (16/16 pass, unchanged from before this task) rather than by adding a redundant new
test — the existing coverage already proves the wire-format status strings are unaffected by an internal
domain-object accessor change that never touches serialization.

## 7. Full Test Results

**Baseline (before this task's changes), confirmed first per your instructions:**
```
735 passed
```

**Targeted re-runs during implementation:**
```
tests/unit/test_verification_engine.py, test_phase8_contract_freeze.py, test_synthesis_domain.py,
test_synthesis_api.py, test_phase9_prompt2_hardening.py, test_phase9_prompt3_acceptance.py,
test_verification_hardening.py, test_verification_semantics_hardening.py
  → 140 passed, 0 failed
```

**Full suite after all changes:**
```
Tests collected: 748
Passed:          748
Failed:          0
Skipped:         0
Errors:          0
```
Exact command and output:
```
.venv/Scripts/python.exe -m pytest -q
748 passed in 9.83s
```
Arithmetic: 735 (baseline) + 12 (new `test_verification_semantics_hardening.py`) + 1 (net: one existing test split
into two, `test_no_critic_requests_for_verified_or_partial` → `test_no_critic_requests_for_verified` +
`test_critic_request_generated_for_partially_verified`) = 748.

**Quality gates:**
```
ruff check src tests        → All checks passed!
ruff format --check src tests → 253 files already formatted
mypy src (strict, project config) → Success: no issues found in 183 source files
```
(One transient `ruff check` failure — an unused `SourceAuthorityTier` import in the new test file — was found and
fixed during this pass, then re-verified clean.)

## 8. Compatibility Impact

- **Wire format:** unchanged. `VerificationStatus`'s six values and their string representations are untouched;
  `ResearchClaim.to_dict()`'s `verification_status` field continues to serialize the same enum values as before.
- **API response schemas:** unchanged. No route, response model, or serialization path was modified.
- **F01 implementation:** unchanged. `evidence.py`'s `_evaluate_match`/`_assess_polarity`/`_coerce_finite_decimal`
  were not touched in this task.
- **F02 polarity logic:** unchanged. The negation/hedge marker detection added in the prior task is untouched.
- **Behavioral change (intentional, approved by this task):** a claim that reaches `PARTIALLY_VERIFIED` will now
  **continue to generate a critic request** and the critic loop will **no longer treat it as sufficient to stop
  research**, whereas before this task it was treated identically to `VERIFIED` for that purpose. This is an
  internal orchestration-behavior change with no wire-format or schema impact — a workflow that previously
  stopped after reaching `PARTIALLY_VERIFIED` will now continue attempting research up to its existing attempt
  budget (`max_attempts`), which was already a pre-existing, bounded control — no new unbounded loop risk is
  introduced.

## 9. Remaining Confidence-Label Issue (Determination, Not Fixed)

**Determination: this is a reporting/labeling concern, not a safety-critical decision path.** Confirmed by tracing
every consumer of `ConfidenceLabel`/`VerifiedClaimGate.confidence_label` in this pass: it is produced once, in
`policy.py:201-215`, and consumed only for serialization into `ConfidenceContext.to_dict()` (`model.py:42`) and
`ExecutiveSummaryItem.confidence_label` (`model.py:214`, `policy.py:410`) — i.e., it flows only into
**human-readable output**. No branch anywhere in `engine.py`, `contracts.py`, or `policy.py` reads
`confidence_label` to make an orchestration, gating, or acceptance decision; that role is played entirely by
`VerificationStatus` and (now) `is_definitively_verified`, both of which this task already made correctly
distinct. Therefore, per your instruction, this was **not** redesigned in this task — it does not affect any
safety-critical path, only presentation.

**What the issue actually is, documented as a follow-up:** `confidence_label` does not special-case
`PARTIALLY_VERIFIED` the way it special-cases `CONFLICTING`/`CONTRADICTED`/`STALE`/`UNVERIFIABLE` — for both
`VERIFIED` and `PARTIALLY_VERIFIED`, it falls through to the same score-threshold ladder
(`>=0.8` → `HIGH`, `>=0.6` → `MODERATE`, else `LOW`). Since `PARTIALLY_VERIFIED`'s score is bounded below `0.7` by
construction, it can show `MODERATE` or `LOW` but never `HIGH` — so the *worst* mislabeling case (a merely-partial
claim shown as `high_confidence`) cannot currently occur. However, a `VERIFIED` claim at `0.72` and a
`PARTIALLY_VERIFIED` claim at `0.65` can both render `MODERATE`, even though the `disposition`/`rendered_text`
fields already correctly distinguish them (`"factual"`/plain text vs. `"qualified"`/`"Partially verified: ..."`).

**Recommended follow-up (not implemented, out of this task's scope):** if you want the confidence label itself to
reinforce the disposition distinction, `confidence_label` could gain its own `PARTIALLY_VERIFIED`-specific label
(e.g., a `QUALIFIED`/`PARTIAL` label distinct from `HIGH`/`MODERATE`/`LOW`), mirroring how
`CONFLICTING`/`CONTRADICTED`/`STALE`/`UNVERIFIABLE` already get their own dedicated labels rather than falling
through to the score ladder. This would be a small, additive change to `ConfidenceLabel` and
`VerifiedClaimGate.confidence_label` only — but it does add a new enum value to a wire-format-adjacent type
(`ConfidenceLabel` is serialized in API responses), so it should be scoped and approved separately, consistent
with your instruction to document rather than expand scope here.

## 10. Remaining F02 Limitations (carried forward, unchanged by this task)

Unchanged from `F01_F02_IMPLEMENTATION_REPORT.md` §7 — this task did not touch the F02 polarity logic:
- Reversed-meaning or scope-shifted evidence sharing vocabulary with no negation marker still reaches
  `SUPPORTING`/can reach `VERIFIED` (documented, tested-as-known-limitation, unchanged).
- Double-negation parity is not resolved; both-sides-negate cases land in `NEUTRAL`/`UNVERIFIABLE` rather than
  correctly recognizing agreement (deliberate, documented precision-for-safety trade-off, unchanged).
- Hedging markers are a fixed list; other hedge phrasings are not caught (unchanged).
- The broader "should any keyword-overlap-only prose match, regardless of polarity, be capped below `VERIFIED`"
  question (distinct from today's fix, which only prevents *polarity-uncertain* matches from reaching `VERIFIED`)
  remains open — this task's change (definitive-verification accessor for the critic loop) narrows its
  *consequence* (a weak match can no longer silently stop research) without resolving whether such a match should
  ever have been eligible for `VERIFIED`/`PARTIALLY_VERIFIED` in the first place.

---

## Final Status

**Definitive Verification Semantics**
PASS — `is_definitively_verified` is `True` only for `VERIFIED`, confirmed by 5 direct status-coverage tests.

**Existing API Contract**
PRESERVED — no `VerificationStatus` enum value, wire-format field, or response schema was changed; confirmed by
re-running all existing API-level tests (16/16 pass) and by tracing that no route serializes `is_verified` or
`is_definitively_verified` directly.

**Regression Tests**
PASS — 12 new tests (all passing) plus 1 existing test correctly split into 2 (both passing, one unchanged
assertion preserved, one updated to the approved new behavior with equal or greater rigor, not weakened).

**Full Suite**
PASS — 748/748 (735 baseline + 13 net new/changed), 0 failed, 0 skipped. `ruff check`, `ruff format --check`, and
`mypy --strict` all clean.

**Remaining Risks**
- LOW: the critic loop now continues researching `PARTIALLY_VERIFIED` claims up to the existing `max_attempts`
  budget instead of stopping immediately — this is the intended fix, bounded by a pre-existing budget control, not
  a new unbounded-loop risk, but it is a real behavior change for any orchestration flow that previously relied on
  `PARTIALLY_VERIFIED` stopping research early.
- LOW: `ConfidenceLabel` still does not visually distinguish `VERIFIED` from `PARTIALLY_VERIFIED` in the
  `MODERATE`/`LOW` bands (§9) — determined to be a presentation-only concern, not a safety-critical path;
  documented as a follow-up, not implemented.
- Unchanged from the prior task: F02's negation/hedge detection remains a bounded lexical heuristic, not general
  semantic entailment (§10).

No action was taken on F03–F12. Stopping here per your instruction.
