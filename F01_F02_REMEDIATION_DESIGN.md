# F01 / F02 Remediation Design

**Status:** DESIGN ONLY — no source code modified, no branch changed, no commit made, no dependency added or
installed. Two read-only interpreter checks were run against already-installed standard-library (`decimal`) and
already-installed project dependency (`pydantic`) code to empirically confirm root causes; no application code
was executed and no new package was installed.
**Scope:** F01 (numeric verification bypass) and F02 (negation-blind verification) only, per instruction. F03–F12
are out of scope for this document.
**Verified against:** HEAD `d983bce` (unchanged since prior passes).

---

# PART A — F01: Numeric verification bypass

## A.1 Complete trace: input claim → normalization/parsing → comparison → verification result

```
HTTP POST /research/synthesis (or equivalent verification route)
  │
  ▼
Pydantic request models (api/routes/synthesis.py)
  SynthesisClaimBody.expected_value:      str | Decimal | datetime | None   (line 95)
  SynthesisEvidenceBody.extracted_value:  str | Decimal | datetime | None   (line 72)
  │  ── Pydantic v2 "smart" union mode resolves a JSON string to `str`, NEVER to `Decimal`.
  │     Empirically confirmed this pass (see A.3) for "100", "NaN", "Infinity", "100.0" — all
  │     remain Python `str` after validation. There is NO parsing/normalization step anywhere
  │     between the HTTP boundary and the domain layer.
  ▼
Domain construction (application layer converts SynthesisClaimBody/-EvidenceBody into
  Claim / EvidenceRef — exact converter not re-read this pass, but its output type for
  expected_value/extracted_value is whatever Pydantic produced: `str`, unchanged)
  │
  ▼
Claim (domain/verification/claim.py)
  expected_value: str | Decimal | datetime | None      (line 63)
  __post_init__ validates timezone-awareness for datetime values only (lines 76-79);
  performs NO numeric parsing, NO finiteness check, NO type normalization on expected_value.
  │
  ▼
EvidenceRef (domain/verification/evidence.py)
  extracted_value: str | Decimal | datetime | None     (line 26)
  __post_init__ validates evidence_id/source_id/claim_type/timestamps/url/snippet bounds
  (lines 35-67); likewise performs NO numeric parsing or finiteness check on extracted_value.
  │
  ▼
EvidenceBundle.classify(claim, evidence_refs)             (evidence.py:168-193)
  for each ref: EvidenceRef.supports_claim(...)            (evidence.py:69-122)
      — pure claim_type match + bag-of-words keyword overlap, no numeric awareness at all
  then:        EvidenceBundle._values_match(claim, ref)    (evidence.py:195-238)   ◄── DEFECT HERE
  │
  ▼
VerificationEngine.verify(claim, bundle, now)              (engine.py:67-127)
  bundle = EvidenceBundle.classify(...)                     (line 82, re-classifies)
  confidence, factors = self._compute_confidence(...)       (line 102; engine.py:168-270)
  status = self._determine_status(...)                     (line 105; engine.py:272-305)
  → VerificationResult(status=..., confidence_score=..., ...)
```

**The entire failure is contained in one function**: `EvidenceBundle._values_match`
(`domain/verification/evidence.py:195-238`). Every layer above and below it (Pydantic models, `Claim`,
`EvidenceRef`, `VerificationEngine`) passes the value through unmodified; none of them parses, normalizes, or
validates it as a number at any point before `_values_match` compares it.

## A.2 Exact affected files/classes/functions

| Layer | File | Class/Function |
|---|---|---|
| API boundary (type declaration only, no logic) | `src/financial_intelligence/api/routes/synthesis.py` | `SynthesisClaimBody.expected_value` (line 95), `SynthesisEvidenceBody.extracted_value` (line 72) |
| Domain model (no logic, just storage) | `src/financial_intelligence/domain/verification/claim.py` | `Claim.expected_value` (line 63) |
| Domain model (no logic, just storage) | `src/financial_intelligence/domain/verification/evidence.py` | `EvidenceRef.extracted_value` (line 26) |
| **Defect location** | `src/financial_intelligence/domain/verification/evidence.py` | `EvidenceBundle._values_match` (lines 195-238) |
| Consumer of the defect's output | `src/financial_intelligence/domain/verification/evidence.py` | `EvidenceBundle.classify` (lines 168-193) |
| Consumer of classification result | `src/financial_intelligence/domain/verification/engine.py` | `VerificationEngine._determine_status` (lines 272-305), `VerificationEngine._compute_confidence` (lines 168-270) |

## A.3 Current failure mechanism (empirically confirmed this pass, not just re-read)

Two independent, read-only checks were run this pass against already-installed code (no new packages):

**Check 1 — Pydantic union resolution** (confirms the value never becomes `Decimal` at the API boundary):
```python
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

class M(BaseModel):
    v: str | Decimal | datetime | None = None

M.model_validate({'v': '100'}).v       # → '100'      (str)
M.model_validate({'v': 'NaN'}).v       # → 'NaN'       (str)
M.model_validate({'v': 'Infinity'}).v  # → 'Infinity'  (str)
M.model_validate({'v': '100.0'}).v     # → '100.0'     (str)
```
**Result: every case stayed `str`.** The `str | Decimal | datetime | None` union is not a "try Decimal, fall back
to str" union in practice — Pydantic v2's default smart-union mode matches a JSON string to `str` before it ever
tries `Decimal`, for *any* string value, not just malformed ones. This means `isinstance(x, Decimal)` is **false
for every value that arrives over this API**, making the finiteness guards in `_values_match` (lines 203, 205)
dead code for real HTTP traffic — this is a stronger and more precise statement than the prior audit's framing
("numeric strings bypass number validation"): the bypass is not an edge case, it is the *universal* case for this
field over HTTP.

**Check 2 — string-equality is wrong even for genuine `Decimal` values** (a second, independent root cause):
```python
from decimal import Decimal
Decimal('100') == Decimal('100.0')          # → True   (correct numeric equality)
str(Decimal('100')) == str(Decimal('100.0'))  # → False  (str(...) gives '100' vs '100.0')
```
`_values_match` (evidence.py:219-220) does `ev_val = str(evidence_ref.extracted_value).strip().lower()` and
`exp_val = str(claim.expected_value).strip().lower()`, then compares with `==` (line 223). **This is wrong even
if both sides were properly-typed `Decimal` instances** — `str()` formatting is not numeric normalization.
This is a **second, independent defect** inside the same function, not merely a consequence of the type-bypass
issue: fixing only the Pydantic/type-coercion problem (Check 1) would still leave "100" vs "100.0" broken, because
the comparison itself needs to become numeric, not textual.

**Combined mechanism producing F01's two symptoms:**
- *False "verified" on non-numbers* (`"NaN"`/`"Infinity"`/`"not-a-number"` submitted on both sides): both remain
  `str` (Check 1), the `isinstance(..., Decimal)` finiteness guard never fires, and `str("NaN") == str("NaN")` is
  trivially `True` → classified `supporting` → can reach `VERIFIED`.
- *False "contradicted" on equal numbers* (`"100"` vs `"100.0"`): even if a future fix makes both sides real
  `Decimal`, the current `str(...) == str(...)` comparison (Check 2) still reports them unequal → classified
  `contradicting` → `CONTRADICTED`.

## A.4 Why the current implementation incorrectly accepts non-numeric input

Three compounding design gaps, in order of causal primacy:

1. **No trust-boundary normalization.** Nothing between "JSON arrives over HTTP" and "value is compared" ever
   attempts `Decimal(value)` parsing. The system was designed to accept `str | Decimal | datetime` presumably so
   callers *could* send a pre-parsed `Decimal`, but nothing requires or coerces that, and Pydantic's union
   resolution (A.3, Check 1) means a well-behaved JSON client sending a numeric-looking string never gets
   upgraded to `Decimal` automatically.
2. **The finiteness guard is type-gated, not value-gated.** `isinstance(x, Decimal) and not x.is_finite()`
   silently no-ops for any other type instead of first attempting to interpret the value as a number and *then*
   checking finiteness. A type-gated guard is inherently bypassable by construction for any union type wider than
   the guarded type — this is the architectural root cause, not a one-off oversight.
3. **The value-equality check is string-based, not numeric.** Independent of (1)/(2), the actual equality test at
   line 223 was written as a generic "stringify and compare" helper (it also handles non-numeric claim types
   through the same code path — dates, text — where string comparison is reasonable), but it was never split into
   a numeric-aware path for `ClaimType.NUMERIC` versus a textual path for other claim types.

## A.5 Smallest safe architectural fix

**Principle:** normalize once, at the earliest point the value is known to be a numeric claim, into a bounded,
finite `Decimal`; reject (not silently pass through) anything that cannot be so normalized; then compare
numerically, never textually, for numeric claims.

**Minimal-diff design** (single function, no new files, no new dependency):

1. Add a private helper `_coerce_numeric(value: str | Decimal | datetime | None) -> Decimal | None` inside
   `evidence.py`:
   - `None` → `None` (unchanged "no value supplied" semantics)
   - `Decimal` → return as-is
   - `str` → attempt `Decimal(value.strip())`; on `decimal.InvalidOperation` (raised for `"not-a-number"`, empty
     string, etc.) return a **sentinel distinct from `None`** (e.g. raise a dedicated `NonNumericValueError`, or
     return a `Decimal` subtype flag) so "could not parse" is distinguishable from "no value was supplied" —
     these must not be conflated, because "no value supplied" today means "trust the text/keyword match" (a
     separate, F02-relevant branch) while "value supplied but garbage" must always fail closed.
   - `datetime` → return `None` (not applicable to numeric comparison; unchanged from today, this path is for
     `ClaimType.DATE`/other, not `NUMERIC`)
2. In `_values_match`, when `claim.claim_type == ClaimType.NUMERIC` (or when either side is being compared for a
   numeric claim — need to confirm exact claim/evidence typing convention from `supports_claim`'s existing
   `claim_type` gate, which already restricts comparison to same-claim-type evidence):
   - Coerce both `claim.expected_value` and `evidence_ref.extracted_value` via `_coerce_numeric`.
   - If either coercion fails (non-numeric string) **or** either resulting `Decimal` is not `.is_finite()`, return
     `False` (i.e., **not a value match** — this already produces `contradicting`, which is the closest existing
     status; whether "malformed input" should instead be surfaced as a new, more honest status, e.g.
     `UNVERIFIABLE` with a distinct rationale, is a product decision — see A.6 and the Definition of Done).
   - Otherwise compare `Decimal == Decimal` directly (Decimal's own `__eq__` already performs correct numeric
     equality per A.3 Check 2 — no custom tolerance/rounding logic is needed for exact-value claims).
3. Leave the non-numeric (`claim.expected_value is None` → text-reliant) branch (lines 199-201) untouched by this
   fix — that branch is F02's territory, not F01's, and mixing the two fixes in one diff would make the change
   harder to review and roll back independently.

This fix touches **one function** (`_values_match`) plus one new small private helper in the **same file**. It
requires no change to `Claim`, `EvidenceRef`, the Pydantic models, or `VerificationEngine` — the type declarations
(`str | Decimal | datetime | None`) can remain as-is; normalization happens at comparison time, not at
construction/deserialization time. (An alternative, larger design — normalizing at the Pydantic-model boundary via
a custom validator — was considered and rejected for this "smallest safe fix" pass; see A.6 for why.)

## A.6 Could the fix break existing valid verification behavior?

**Risk assessment, by existing test:**

| Existing test | Current expectation | Behavior under proposed fix | Risk |
|---|---|---|---|
| `test_verify_numeric_claim_with_complete_evidence` | Decimal-typed matching values → VERIFIED | Decimal `_coerce_numeric` is a no-op passthrough for `Decimal` inputs → unchanged | None |
| `test_numeric_claim_currency_mismatch_does_not_support` | Decimal-typed, currency differs → CONTRADICTED | Value coercion unaffected; currency check happens after value-match in unchanged code (lines 224-236) → unchanged | None |
| `test_numeric_claim_unit_mismatch`, `_scale_mismatch`, `_period_mismatch`, `_fiscal_year_mismatch` | Decimal-typed, various mismatches → CONTRADICTED | Same reasoning — value coercion is a no-op for already-Decimal inputs, mismatch logic downstream unchanged | None |
| `test_numeric_claim_percentage_vs_ratio` | Decimal `20` vs Decimal `0.2`, unit mismatch → CONTRADICTED, confidence 0 | Unit mismatch still triggers after value match is now correctly `True` (both are numerically comparable) — **need to re-check**: currently this test relies on values *not* matching as a side door to reach CONTRADICTED; if the fix makes value-matching purely numeric, `20 == 0.2` is still `False` numerically, so status is unaffected. Confirmed safe by inspection, not re-run. | Low — confirm by running this exact test after implementation |
| `test_numeric_claim_negative_values`, `_zero_values` | Decimal-typed equal values → VERIFIED | Unaffected — `Decimal(-50) == Decimal(-50)` and `Decimal(0) == Decimal(0)` both correctly `True` under numeric comparison, as they were under string comparison too (str reprs already matched) | None |
| `test_numeric_claim_missing_expected_values` | `expected_value=None` → falls into the untouched "no expected value" branch → CONTRADICTED (evidence has type NUMERIC, so `claim.claim_type != ClaimType.NUMERIC` is False → returns False → contradicting) | Untouched by this fix (branch not modified) | None |
| `test_numeric_claim_nan_infinity` | `Decimal("NaN")`/`Decimal("Infinity")` on both sides → CONTRADICTED | `_coerce_numeric` passthrough for `Decimal`, then `.is_finite()` check (still present, now reachable) → still `False` → still CONTRADICTED | None |

**New behavior that did not exist before (intended, not a regression):**
- `"100"` vs `"100.0"` (as strings) will change from CONTRADICTED to a value-match `True` (subject to
  unit/currency/period still matching) — this is the **intended fix**, not a break, but it is a **behavior
  change** that should be called out explicitly in the change's description, since any downstream caller that
  (incorrectly) relied on the old "differently-formatted numbers never match" behavior would be affected. No such
  reliance was found in the current test suite.
- `"NaN"`/`"Infinity"`/`"not-a-number"` (as strings) will change from VERIFIED/supporting to
  CONTRADICTED-or-a-new-explicit-failure-status — this is the **intended fix**.

**Conclusion: the fix is backward-compatible with every existing passing test by inspection.** This should still
be confirmed by actually running the full `test_verification_engine.py` file (and `test_synthesis_api.py`,
`test_synthesis_domain.py`) after implementation, per the Definition of Done below — inspection is not a
substitute for execution, but no test was found this pass whose *current* expected outcome depends on the
buggy behavior being fixed.

## A.7 Existing tests related to this path

- `tests/unit/test_verification_engine.py` — `VerificationEngineTests` class, all `test_numeric_claim_*` methods
  (lines 156-473 per earlier read) — **all construct `Decimal` instances directly at the domain layer**, never a
  `str`. None of them exercises the actual Pydantic-boundary bypass.
- `tests/unit/test_synthesis_api.py` — `_claim()` helper (lines 28-90) **already sends `expected_value`/
  `extracted_value` as JSON strings** (`value: str = "100"` default, line 38) through the full HTTP path. Existing
  golden tests (`test_apple_golden_flow_preserves_nasdaq_identity_and_evidence`, etc.) pass today because both
  sides use the **identical string** `"100"` — this incidentally proves the string-typed path already flows
  end-to-end through the real API without error, it just isn't given a value that exposes the bug (no test sends
  `"NaN"`, `"Infinity"`, or a differently-formatted-but-equal pair like `"100.0"`).
- `tests/unit/test_synthesis_domain.py` — covers synthesis assembly (confidence bounding, advice-language
  exclusion, citation integrity) — not the verification-comparison logic itself; not directly relevant to F01.

**No existing test — domain or API level — currently exercises the actual bypass.** This confirms the earlier
audit passes' assessment: the bug is real, current, and untested.

## A.8 Missing regression tests

1. Domain-level, `_values_match` via `str`-typed inputs (closing the domain/API test-shape gap directly):
   - `expected_value="NaN"`, `extracted_value="NaN"` (both `str`) → must NOT be `supporting`/VERIFIED.
   - `expected_value="Infinity"`, `extracted_value="Infinity"` (both `str`) → must NOT be `supporting`/VERIFIED.
   - `expected_value="not-a-number"`, `extracted_value="not-a-number"` (both `str`) → must NOT be
     `supporting`/VERIFIED (and ideally should be distinguishable from a legitimate numeric mismatch — see DoD).
   - `expected_value="100"`, `extracted_value="100.0"` (both `str`, numerically equal) → **should** be
     `supporting`/VERIFIED once fixed (this flips an existing incorrect expectation implicitly, since no test
     currently encodes the *old*, wrong behavior as "expected" — confirmed by A.7/A.6).
2. API-level (`test_synthesis_api.py`), extending the existing `_claim()` helper pattern:
   - POST with `value="NaN"` on both `expected_value`/`extracted_value` → assert the response's verification
     status/confidence is not `verified`.
   - POST with `expected_value="100"`, evidence `extracted_value="100.0"` (mismatched helper args) → assert the
     response reflects a match, not a contradiction, once fixed.
3. A dedicated adversarial-input test class mirroring the existing `*_hardening.py` naming convention used
   elsewhere in this repo (e.g. `test_financial_domain_hardening.py`) — this repo's own test-organization
   convention suggests a `test_verification_hardening.py`-style file would be the idiomatic location for the new
   adversarial cases, rather than appending them ad hoc to the existing golden-flow test file.

## A.9 At least 5 adversarial test cases + A.9-cont. expected behavior

| # | Input (`expected_value` / `extracted_value`, both as JSON strings unless noted) | Current (buggy) result | Expected result after fix |
|---|---|---|---|
| 1 | `"NaN"` / `"NaN"` | VERIFIED, confidence up to 1.0 | NOT verified/supporting — either CONTRADICTED or a distinct "malformed value" outcome (see DoD for which) |
| 2 | `"Infinity"` / `"Infinity"` | VERIFIED, confidence up to 1.0 | NOT verified/supporting, same as #1 |
| 3 | `"-Infinity"` / `"-Infinity"` | VERIFIED (same string-equality bypass; not explicitly in prior audit but same mechanism) | NOT verified/supporting, same as #1 |
| 4 | `"not-a-number"` / `"not-a-number"` | VERIFIED (string equality; type mismatch with claim_type=NUMERIC is a separate `supports_claim` gate that does not block this, since claim_type strings can still match) | NOT verified/supporting — this is not a number at all, must fail closed at the coercion step, ideally with a clear "value is not numeric" rationale distinct from "value mismatch" |
| 5 | `"100"` / `"100.0"` | CONTRADICTED, confidence 0 | supporting/VERIFIED (subject to unit/currency/period matching, unchanged) |
| 6 | `"1e2"` / `"100"` (scientific notation vs plain) | CONTRADICTED (string mismatch) | supporting/VERIFIED — both parse to `Decimal("100")` under correct coercion; **this is a new edge case not in the prior audit's F01 citation, surfaced by this pass's root-cause analysis** — must be explicitly decided whether scientific notation is in-scope for the coercion helper (recommend: yes, `Decimal()` parses it natively, no extra code needed) |
| 7 | `""` (empty string) / `"100"` | Falls through to `return False` today (empty string fails `ev_val == exp_val` trivially) → CONTRADICTED | Should remain a non-match, but via the "unparsable" path (empty string is not a valid `Decimal`), not via coincidental string inequality — verify the new code path produces the same outward status even though the internal reason changes |
| 8 | `"100"` / `Decimal("100.0")` (mixed types — one side pre-parsed by a caller, one side a plain string) | CONTRADICTED today (string comparison of `"100"` vs `"100.0"`) | supporting/VERIFIED — the coercion helper must accept `Decimal` passthrough as well as `str` parsing so mixed-type inputs are handled uniformly |

## A.10 Root cause / proposed behavior / algorithm (F01, consolidated)

**Root cause:** two independent bugs sharing one function — (a) a type-gated finiteness check that is dead code
for the actual (all-`str`) shape of API-boundary input, and (b) a string-formatting equality check used where
numeric equality was intended.

**Proposed behavior:** for any claim of `ClaimType.NUMERIC`, both the expected and extracted values must be
coerced to a finite `Decimal` before comparison; if either side cannot be coerced (not parseable, or parses to a
non-finite value), the pair is never treated as a value match, and the failure mode should be observable/testable
as distinct from "parsed but numerically different" (exact status TBD — see Definition of Done).

**Proposed algorithm** (pseudocode, `evidence.py`):
```python
def _coerce_finite_decimal(value: str | Decimal | datetime | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return None  # not applicable to numeric comparison
    if isinstance(value, Decimal):
        candidate = value
    else:  # str
        try:
            candidate = Decimal(value.strip())
        except (InvalidOperation, AttributeError):
            return None  # unparsable — treated as "no usable numeric value"
    return candidate if candidate.is_finite() else None

# inside _values_match, ClaimType.NUMERIC branch:
expected_num = _coerce_finite_decimal(claim.expected_value)
extracted_num = _coerce_finite_decimal(evidence_ref.extracted_value)
if expected_num is None or extracted_num is None:
    return False  # cannot confirm a numeric match; caller may want a distinct signal — see DoD
if expected_num != extracted_num:
    return False
# ... existing unit/currency/period checks, unchanged ...
```

Note: collapsing "unparsable" and "parseable-but-different" into the same `return False` is the **smallest** safe
fix (preserves the existing boolean contract of `_values_match` and therefore every call site). Whether the system
should instead surface a *third* outcome (e.g., a new `VerificationStatus` or a `ConfidenceFactor`/rationale flag
meaning "input was malformed, not merely different") is a legitimate follow-up but is **not required** to close
the security-relevant part of F01 (preventing false VERIFIED) and is flagged as an open design question in the
Definition of Done rather than bundled into this minimal fix.

---

# PART B — F02: Negation-blind verification

## B.1 Complete trace: semantic verification path

```
Claim (claim_type=FACTUAL, expected_value=None, text="Apple acquired ExampleCorp")
  │
  ▼
EvidenceRef (claim_type="factual", raw_snippet="Apple did not acquire ExampleCorp")
  │
  ▼
EvidenceBundle.classify(claim, (evidence_ref,))                    (evidence.py:168-193)
  for ref in evidence_refs:
      if ref.supports_claim(claim.text, claim.claim_type):         (evidence.py:69-122)
          — claim_type match: "factual" == "factual" → passes gate
          — bag-of-words overlap (stopwords removed) between
            "apple acquired examplecorp" and "apple did not acquire examplecorp"
          — shares "apple" (content word) at minimum; "acquired"/"acquire" may or may
            not overlap depending on exact tokenization (no stemming is performed, so
            "acquired" != "acquire" as tokens — this specific pair may or may not clear
            the overlap threshold depending on exact wording, but ANY sufficiently
            paraphrased negation will, by construction, since the check only counts
            shared words, never their logical relationship)
          — "not"/"did" are NOT in the stopword list (evidence.py:76-116) but this does
            not matter: they simply add to (or fail to reduce) the overlap count; there
            is no negation-detection logic of any kind
          if True:
              if cls._values_match(claim, ref):                    (evidence.py:195-238)
                  — claim.expected_value is None (factual claim, no expected value
                    supplied) → line 199-201: `return claim.claim_type != ClaimType.NUMERIC`
                    → claim_type is FACTUAL, not NUMERIC → returns True, UNCONDITIONALLY,
                    with NO inspection of the snippet's actual polarity/meaning
                  supporting.append(ref)              ◄── DEFECT: negated evidence lands here
              else:
                  contradicting.append(ref)
          else:
              neutral.append(ref)
  │
  ▼
VerificationEngine._compute_confidence / _determine_status         (engine.py:168-305)
  has_supporting=True, has_contradicting=False (nothing routed evidence to `contradicting`
  for this case — the negation never triggers the `_values_match → False` branch, because
  that branch is only reachable when `expected_value is not None`)
  → confidence can reach 1.0 with a single Tier-1 source (see engine.py:182-187, 210-213)
  → status = VERIFIED  (engine.py:294, confidence >= 0.7 threshold)
```

## B.2 Exact affected files/classes/functions

| File | Class/Function | Role in the defect |
|---|---|---|
| `src/financial_intelligence/domain/verification/evidence.py` | `EvidenceRef.supports_claim` (lines 69-122) | Bag-of-words overlap gate — has no negation awareness, is the "does this even look related" filter |
| `src/financial_intelligence/domain/verification/evidence.py` | `EvidenceBundle._values_match` (lines 195-201, the `expected_value is None` early return) | **Primary defect location** — unconditionally treats any type-matched, keyword-overlapping factual evidence as a **value match** with no polarity check |
| `src/financial_intelligence/domain/verification/evidence.py` | `EvidenceBundle.classify` (lines 168-193) | Routes the above into `supporting`, feeding the engine |
| `src/financial_intelligence/domain/verification/engine.py` | `_compute_confidence` / `_determine_status` | Downstream consumer; not itself defective, but has no independent check that would catch what `classify` got wrong |

## B.3 How a negated claim can currently be treated as verified

Fully traced in B.1. In one sentence: **the system has exactly one gate for factual (non-numeric) claims —
"do the claim text and the evidence snippet share enough words" — and that gate cannot distinguish agreement from
negation, because it only counts shared vocabulary, never relationships between words** (subject/verb/object,
polarity, tense of an assertion vs. its denial).

## B.4 Does the current system have any semantic/NLU capability?

**No.** Confirmed by direct code reading across this and prior passes:
- No LLM client, no prompt template, no embedding model, no vector similarity, no dependency on any NLP library
  (`pyproject.toml`'s full dependency list is `fastapi`, `pydantic`, `pydantic-settings`, `uvicorn`, `tzdata` —
  no `spacy`, `nltk`, `transformers`, or similar was found in this or the prior audit passes).
- `EvidenceRef.supports_claim` is literally `set(text.lower().split())` intersection arithmetic — this is the
  entire "semantic" capability of the system: a bag-of-words Jaccard-style overlap ratio with a fixed stopword
  list. It has no part-of-speech awareness, no negation handling, no synonym handling, no entity linking.
- The numeric path (`ClaimType.NUMERIC`) sidesteps this limitation entirely by requiring an `expected_value` to
  compare — that is a **structured**, not semantic, comparison, and it is the system's only genuinely reliable
  verification mechanism today.

## B.5 Deterministic parsing/rules vs. LLM/NLI vs. other architecture

**Recommendation: deterministic parsing/rules, NOT an LLM/NLI component, and NOT "solve negation."** Reasoning:

- **An LLM does not actually fix this class of bug — it relocates it.** Swapping bag-of-words overlap for an LLM
  judgment ("does this evidence support this claim?") replaces one unreliable heuristic with another that is
  *harder to test deterministically*, *harder to reproduce*, *adds a runtime dependency and cost* (this codebase
  currently has `ALLOW_PAID_MODELS=false` and zero LLM calls anywhere — introducing one here would be the single
  largest architectural change in the codebase's history, for one bug), and — critically — **general negation
  handling is a known-hard NLI problem even for LLMs** (double negatives, scope ambiguity, hedged language,
  sarcasm, "not unlike", counterfactuals). An LLM would reduce the *frequency* of this specific failure mode
  without eliminating the *class* of failure mode (an LLM can also be confidently wrong), and — unlike the current
  deterministic engine — its errors would not be exhaustively unit-testable, which conflicts directly with this
  codebase's stated design principle ("No LLM calls. All logic is code-derived and reproducible." — verbatim
  docstring, `engine.py:29`).
- **A targeted deterministic rule set can close the specific, demonstrated failure mode** (single-word negation
  markers directly modifying the claim's asserted relationship) without claiming to solve general NLI. This is
  consistent with the "smallest safe fix that preserves the current deterministic architecture" instruction.
- **The real fix is not "detect negation correctly" — it is "stop letting keyword overlap alone produce a VERIFIED
  factual claim at all."** The system does not need to become smarter about language; it needs to become more
  honest about the limits of what bag-of-words matching can certify. This reframes the fix from an NLP problem
  into a **policy/boundary problem** (see B.8), which is deterministically solvable today.

## B.6 Smallest safe fix that preserves the current deterministic architecture

**Two complementary layers, both deterministic, no new dependency:**

**Layer 1 — cheap, high-precision negation-marker rule (reduces obvious cases immediately):**
Maintain a small, fixed set of negation markers (`"not"`, `"n't"`, `"never"`, `"no longer"`, `"fails to"`,
`"did not"`, `"does not"`, `"cannot"`, `"denies"`, `"denied"`, `"false"`, `"incorrect"` — a bounded, explicit,
testable list, not a learned model). In `supports_claim` or a new sibling check, count negation-marker occurrences
in the **claim text** versus in the **evidence snippet**; if they differ (evidence has a negation marker directly
adjacent to/governing the shared predicate and the claim does not, or vice versa), treat the snippet as
**contradicting**, not supporting, regardless of keyword overlap. This is a **precision-oriented, conservative
rule**: it will catch clean single-negation cases (exactly the F02 reproduction case: "acquired" vs "did not
acquire") and will deliberately under-catch subtler cases (see B.7) rather than risk false positives from a more
aggressive heuristic.

**Layer 2 — tighten the verification-status boundary itself (the more important, more general fix):**
Regardless of how good the negation rule in Layer 1 is, **keyword-overlap-only evidence for a factual claim with
no `expected_value` should never be capable of reaching `VERIFIED`** — only a bounded, lower-confidence outcome
(e.g. `PARTIALLY_VERIFIED` at most, or a new explicit status distinguishing "textually related evidence found,
polarity/entailment not independently confirmed" from genuine verification). Concretely: `_determine_status` or
`_compute_confidence` should cap the achievable confidence/status for `ClaimType.FACTUAL` claims whose match came
only from `supports_claim`'s bag-of-words path (i.e., `_values_match` returned `True` via the
`expected_value is None` branch specifically, not via a real structured comparison) — this can be tracked with a
boolean flag threaded from `_values_match`'s return value (e.g., return an enum/tuple instead of a bare `bool`
distinguishing "structurally confirmed match" from "text-only match", or a new `ConfidenceFactor` that Layer 2
checks before allowing `VERIFIED`).

**Why both layers, not just one:** Layer 1 alone still leaves the door open to any negation phrasing outside the
fixed marker list (paraphrase, double negation, hedging) reaching full `VERIFIED` confidence — a false sense of
security. Layer 2 alone (capping factual-claim confidence) is the real safety fix and would be sufficient on its
own to prevent the *worst* outcome (maximum-confidence false verification of a negated claim) even with zero
negation-detection code — but Layer 1 improves the practical accuracy of the common case (users see fewer
`PARTIALLY_VERIFIED`/"needs more evidence" results for genuinely-supporting evidence) without weakening the safety
boundary Layer 2 establishes.

**Recommendation: implement Layer 2 unconditionally (it is the safety-relevant fix and is small); implement
Layer 1 as a precision improvement, explicitly scoped as best-effort and documented as such (it is not, and must
not be presented as, general negation understanding).**

## B.7 Cases that cannot be reliably handled without semantic reasoning

These must be explicitly acknowledged as **out of scope** for any deterministic fix, and the system's stated
guarantees must not imply otherwise:

1. **Multi-hop negation / double negatives**: "It is not true that Apple failed to acquire ExampleCorp" (a double
   negation that actually *supports* the claim) — a fixed negation-marker count would misfire here (two markers →
   treated as "differs from claim's zero markers" → wrongly flagged as contradicting, when it actually agrees).
2. **Scope ambiguity**: "Apple acquired ExampleCorp, not TargetCorp" — negates the *object*, not the *event*;
   simple marker-counting cannot distinguish "the event didn't happen" from "a different detail is being
   corrected."
3. **Hedged/uncertain language**: "Apple may have acquired ExampleCorp, sources say" — neither clearly supports
   nor contradicts with certainty; a bag-of-words or marker-count approach will treat this identically to a firm
   assertion.
4. **Synonym/paraphrase without shared vocabulary**: "Apple purchased ExampleCorp outright" (claim: "Apple
   acquired ExampleCorp") — zero negation involved, but also low literal word overlap; this is the *opposite*
   failure mode (false non-match) and is a pre-existing limitation of `supports_claim`, not something this fix
   should attempt to solve.
5. **Temporal qualification**: "Apple was in talks to acquire ExampleCorp" vs. claim "Apple acquired ExampleCorp"
   — a fundamentally different factual assertion (intent vs. completed action) that shares almost all keywords
   and contains no negation marker at all.
6. **Sarcasm, quotation, reported speech**: "Critics joked that Apple 'acquired' ExampleCorp" — no deterministic
   rule can reliably detect that this is not an assertion of fact.

**None of these can be handled by Layer 1's rule set, and this must be stated plainly rather than implied away.**
This is precisely why Layer 2 (capping the achievable status/confidence for any claim verified only via
keyword-overlap-plus-optional-negation-check) is the fix that actually matters for safety — it is the mechanism
that remains correct even when Layer 1's rules are (inevitably) incomplete.

## B.8 Explicit boundary: what may the verification engine claim as "VERIFIED"?

Proposed boundary (this is the central deliverable of the F02 design — a policy statement, not just code):

> **The verification engine may only return `VerificationStatus.VERIFIED` for a claim when the match between
> claim and evidence was confirmed through a structured, typed comparison of values that does not depend solely
> on textual/keyword resemblance.** Concretely:
> - `ClaimType.NUMERIC` claims: `VERIFIED` requires a successful numeric-value match (post-F01-fix) with
>   compatible unit/currency/period, as today.
> - `ClaimType.DATE` claims: `VERIFIED` should likewise require a structured value comparison (an actual date
>   equality/tolerance check), not textual overlap — **not itself part of F02's cited defect, but the same
>   architectural principle applies; flagged for consistency, not required by this fix.**
> - `ClaimType.FACTUAL` claims **with an `expected_value` supplied** (e.g. a specific asserted detail): may reach
>   `VERIFIED` via structured comparison, same as numeric.
> - `ClaimType.FACTUAL` claims **with no `expected_value`** (pure prose assertions, e.g. "Apple acquired
>   ExampleCorp"): **must be capped below `VERIFIED`** — the best achievable outcome from keyword-overlap
>   evidence alone (even after Layer 1's negation rule is applied) is `PARTIALLY_VERIFIED` or a new, more honestly
>   named status (e.g. `TEXTUALLY_CONSISTENT` / `UNCONFIRMED_TEXT_MATCH` — naming is an implementation decision,
>   not fixed here) that a consumer cannot mistake for a confirmed fact.
> - `ClaimType.SOURCE_AUTHORITY` claims: not examined in this pass — flagged **UNVERIFIED, out of scope**, same
>   principle likely applies but was not traced.

This boundary is deliberately conservative: it accepts a reduction in how often the system can say "verified" for
prose claims, in exchange for eliminating the possibility that keyword overlap alone — with or without a negation
rule — can produce a maximum-confidence false positive. This trade fits the project's own stated design
philosophy ("incomplete research should stop transparently instead of becoming confident prose" — `README.md`).

## B.9 Existing tests (F02)

- `tests/unit/test_verification_engine.py::test_superficial_keyword_overlap_does_not_support_claim` (line 316) —
  **read in full this pass; it does NOT test negation.** It tests a **claim_type mismatch** (evidence tagged
  `NUMERIC`, claim tagged `FACTUAL`, identical text) and confirms the type-gate in `supports_claim` (line 72)
  correctly returns `False` in that case. This is a different, already-correctly-handled guard, not F02's defect.
- No test anywhere in `test_verification_engine.py`, `test_synthesis_api.py`, or `test_synthesis_domain.py`
  supplies a negated evidence snippet against a positive factual claim, or vice versa. **Confirmed: F02 has zero
  existing regression coverage.**

## B.10 Missing regression tests (design)

1. **Direct reproduction** (domain level): claim `ClaimType.FACTUAL`, text "Apple acquired ExampleCorp",
   `expected_value=None`; evidence snippet "Apple did not acquire ExampleCorp", `claim_type="factual"`,
   Tier-1 source. Assert: **after fix**, result is NOT in `bundle.supporting`, and `result.status` is NOT
   `VERIFIED`.
2. **Boundary-cap test** (the Layer 2 fix, independent of Layer 1's rule quality): claim `ClaimType.FACTUAL`,
   `expected_value=None`, evidence snippet that **agrees** with the claim (no negation) from a Tier-1 source.
   Assert: `result.status` is capped at whatever the new maximum is for this claim shape (e.g.
   `PARTIALLY_VERIFIED`, not `VERIFIED`) — this test is what actually proves the safety boundary from B.8 is
   enforced, independent of negation-detection quality, and should be written **before** the negation rule itself,
   since it is the higher-priority, lower-complexity part of the fix.
3. **Negation-marker rule unit tests** (Layer 1, once implemented): a small table of (claim, evidence) pairs
   covering `"not"`, `"never"`, `"n't"`, `"cannot"`, etc., each asserting the evidence is NOT classified as
   supporting.
4. **Explicit non-goal test / documentation test**: at least one test from B.7's list (e.g. the double-negation
   case) with a comment explicitly stating this case is **known to be unhandled** and asserting only that the
   result is not silently `VERIFIED` with high confidence (i.e., asserting the Layer 2 boundary still holds even
   when Layer 1's rule gives the wrong polarity signal) — this documents the acknowledged limitation as a test
   rather than as a comment that can silently go stale.
5. **Regression guard for the existing correct behavior**: a same-polarity, high-keyword-overlap, non-negated case
   (e.g. today's implicit "happy path") should still reach whatever the new capped-but-positive status is (not
   regress to `UNVERIFIABLE`) — ensures the fix doesn't overcorrect into uselessness.

---

# Test Strategy (F01 + F02 combined)

1. Add the new/updated domain-level tests (A.8, B.10) to `tests/unit/test_verification_engine.py` first, run them
   against the **current, unfixed** code to confirm they fail (proving they actually exercise the bug — a
   regression test that passes before the fix is worthless).
2. Implement F01's fix in `_values_match` (A.5/A.10). Re-run the full `test_verification_engine.py` file; all
   pre-existing tests must still pass (A.6); the new F01 tests must now pass.
3. Implement F02's Layer 2 boundary cap first (higher priority, lower complexity, the actual safety fix), then
   Layer 1's negation-marker rule (precision improvement). Re-run the full file again after each layer separately,
   not just at the end, so a regression can be attributed to the specific layer that caused it.
4. Add the API-level tests (A.8 item 2) to `tests/unit/test_synthesis_api.py` using the existing `_claim()`/
   `_body()` helper pattern, confirming the fix is reachable end-to-end through the real HTTP boundary, not just
   at the domain layer — this closes the exact gap (A.7) that let F01 ship untested despite domain coverage.
5. Run the **entire** existing suite (`pytest -q`, currently 705 passed) after all changes, not just the modified
   files, since `test_synthesis_domain.py` and any workflow/synthesis integration tests could indirectly depend on
   verification status values.

---

# Edge Cases (consolidated, F01 + F02)

- Scientific notation (`"1e2"`) and locale-formatted numbers (`"1,000"`, `"1.000,50"` European format) — F01's
  `Decimal()` parser handles plain scientific notation natively but will reject comma-thousands-separators and
  European decimal-comma format as `InvalidOperation`; whether this should be pre-processed is a scope decision
  not resolved here (recommend: reject for now, document as unsupported, revisit if real evidence sources ever
  produce such formats — none currently do, per the fixture-only nature of most data sources).
- Whitespace/unicode variants of "NaN" (e.g. `"nan"`, `" NaN "`, full-width digits) — `Decimal()` itself
  case-normalizes `"nan"`/`"NaN"`/`"NAN"` identically (all parse to a non-finite Decimal), so this is
  automatically handled by the proposed fix without extra code; not independently verified this pass with a
  live check — **recommend confirming with a quick interpreter check during implementation**, not deferring
  silently.
- Extremely long numeric strings (potential resource-exhaustion vector via `Decimal()` parsing of a
  multi-megabyte string) — the existing Pydantic field already bounds string length indirectly via other
  constraints on the request body; not independently confirmed whether `expected_value`/`extracted_value` have an
  explicit `max_length` — **flagged UNVERIFIED, worth a quick check during implementation**, since an unbounded
  `Decimal()` parse of attacker-controlled input is a mild DoS surface if no length bound exists upstream.
- F02's negation markers must be matched as whole words/phrases, not substrings (`"cannot"` should not spuriously
  match inside an unrelated word) — use word-boundary-aware tokenization consistent with the existing
  `text.lower().split()` approach already used in `supports_claim`, not a naive substring search.

---

# Backward Compatibility Considerations

- **F01:** No API contract change (same Pydantic field types, same response shape). The only externally-visible
  change is that some previously-`CONTRADICTED` results become `VERIFIED`-eligible (equal-value differently
  formatted numbers) and some previously-`VERIFIED` results become non-`VERIFIED` (non-numeric strings). Both are
  correctness fixes, not contract changes — no version bump should be needed, but the change should be called out
  in `CHANGELOG.md` given it changes observable output for specific inputs.
- **F02:** The Layer 2 fix **is** an observable behavior change for any factual claim with no `expected_value`
  that previously reached `VERIFIED` via keyword overlap alone (a **broader** set than just negated claims —
  every keyword-overlap-only factual claim, negated or not, is affected by the boundary cap, per B.8's design).
  This is the single largest behavior change proposed in this document and should be flagged prominently to
  whoever approves implementation: **any existing caller relying on prose factual claims reaching `VERIFIED`
  status (not just numeric ones) will see those claims capped at a lower status after this fix.** This is the
  correct and intended outcome per B.8's safety boundary, but it is a bigger blast radius than F01's fix and
  should be reviewed/approved as its own explicit decision, separate from approving F01.

---

# Security / Safety Considerations

- Both fixes are **fail-closed by design**: unparseable numeric input (F01) and unstructured factual claims (F02)
  both move *toward* lower-confidence/non-verified outcomes, never toward higher confidence. Neither fix
  introduces a new way to reach `VERIFIED` that does not already exist; both only *remove* incorrect paths to it.
- Neither fix introduces a new dependency, network call, or LLM — the attack surface does not grow.
- The F01 `Decimal(value)` parsing call is the only new "parse untrusted input" surface introduced; `Decimal`'s
  parser is pure-Python, does not execute code, and raises a catchable `InvalidOperation`/`ValueError`-family
  exception on malformed input (no arbitrary-code-execution risk, unlike e.g. `eval`).

---

# Implementation Files (both findings, no other files touched)

| File | Change |
|---|---|
| `src/financial_intelligence/domain/verification/evidence.py` | F01: add `_coerce_finite_decimal` helper + rewrite numeric branch of `_values_match`. F02 Layer 1: add negation-marker check, likely as a new method or inline in `supports_claim`/`classify`. |
| `src/financial_intelligence/domain/verification/engine.py` | F02 Layer 2: modify `_determine_status` (and/or `_compute_confidence`) to cap status for factual/keyword-overlap-only matches. Requires `classify`/`_values_match` to expose *how* a match was determined (structured vs. text-only) — likely a small signature/return-type change threaded through `EvidenceBundle`. |
| `src/financial_intelligence/domain/verification/result.py` | Possibly: new `VerificationStatus` / `ConfidenceFactor` value if Layer 2 introduces a distinct status name rather than reusing `PARTIALLY_VERIFIED` — **decision needed before implementation**, see Definition of Done. |
| `tests/unit/test_verification_engine.py` | New adversarial tests (A.8, B.10), added to the existing class or a new dedicated hardening file per this repo's convention (recommend: new `tests/unit/test_verification_hardening.py`, matching `test_financial_domain_hardening.py`-style naming already used elsewhere in this repo). |
| `tests/unit/test_synthesis_api.py` | New API-level tests extending the existing `_claim()`/`_body()` helpers (A.8 item 2). |
| `CHANGELOG.md` | Document both behavior changes per Backward Compatibility section above. |

No changes to: Pydantic model field types, `Claim`/`EvidenceRef` dataclass shapes (beyond possibly threading a new
internal flag through `EvidenceBundle`'s construction — not its public field set, unless the status-naming
decision requires a new public status value), `api/routes/synthesis.py` route logic, `composition/__init__.py`,
or any file outside the verification domain package plus its two named test files.

---

# Implementation Order

1. Write the new regression tests (A.8, B.10) against **current** code; confirm they fail (proves they test the
   real bug).
2. Implement F01 fix (`_coerce_finite_decimal` + numeric branch rewrite). Re-run full suite.
3. Implement F02 Layer 2 (status/confidence boundary cap) — the safety-relevant half of F02, and the lower-effort
   half. Re-run full suite.
4. Implement F02 Layer 1 (negation-marker rule) as a precision improvement on top of Layer 2's now-safe boundary.
   Re-run full suite.
5. Add API-level regression tests (A.8 item 2) proving the fix is reachable through the real HTTP boundary, not
   only the domain layer.
6. Update `CHANGELOG.md` documenting both behavior changes explicitly, per Backward Compatibility above.
7. Run the entire existing test suite (currently 705 tests) once more as a final gate before considering this
   closed.

This order fixes F01 before F02 because F01 is smaller, fully scoped, and shares no ambiguity about the intended
outcome; F02 (especially Layer 2's status-naming decision) has one open design question (below) that should not
block F01's clearly-scoped fix.

---

# Definition of Done

- [ ] `EvidenceBundle._values_match` rejects any `ClaimType.NUMERIC` comparison where either side cannot be
      coerced to a finite `Decimal`, and compares coerced values numerically (not textually).
- [ ] All 5+ adversarial cases in A.9 produce the documented expected outcome, verified by an executed test, not
      by inspection.
- [ ] `ClaimType.FACTUAL` claims with no `expected_value` can no longer reach `VerificationStatus.VERIFIED` through
      keyword-overlap evidence alone (B.8's boundary), verified by an executed test.
- [ ] At least one deterministic negation-marker case (B.6 Layer 1) is correctly reclassified as non-supporting.
- [ ] At least one case from B.7 (acknowledged-unsolvable) is covered by a test asserting the *safety boundary*
      still holds even though the *negation detection* is known to be wrong for that case.
- [ ] All 705 pre-existing tests still pass, confirmed by an actual `pytest -q` run, not by inspection.
- [ ] New API-level tests (`test_synthesis_api.py`) prove both fixes are reachable through the real HTTP boundary.
- [ ] `CHANGELOG.md` documents both behavior changes as explicit, intentional corrections.
- [ ] **Open design decision, to be made explicitly before implementation, not implicitly during it:** whether
      F02's Layer 2 cap reuses the existing `VerificationStatus.PARTIALLY_VERIFIED` value or introduces a new,
      more precisely-named status. This document does not resolve this — it is a naming/API-surface decision for
      whoever approves implementation, not a technical blocker.

---

# Final Answers

## Can F01 be fixed deterministically?

**YES.**

**Evidence:** F01 is a data-normalization and comparison bug, not a language-understanding bug. Both root causes
were empirically reproduced this pass using only already-installed, deterministic, pure-function standard-library
and dependency code:
- `Decimal(value)` is a deterministic, pure parser: given the same string, it always either produces the same
  `Decimal` or raises the same `InvalidOperation` — no ambiguity, no model, no external call.
- `Decimal.is_finite()` and `Decimal.__eq__` are deterministic, exact, well-defined operations on a well-defined
  type — confirmed this pass that `Decimal('100') == Decimal('100.0')` is unambiguously `True`.
- The entire fix (A.5/A.10) is a rewrite of one function using only stdlib `decimal`, already imported in the
  file being changed. No new dependency, no heuristic, no probabilistic component is required at any point.

## Can F02 be fixed safely without introducing an LLM?

**YES — but only if "fixed" is scoped correctly.** General natural-language negation/entailment understanding
**cannot** be solved deterministically (B.7 lists concrete, real cases — double negation, scope ambiguity,
hedging, paraphrase without negation, temporal qualification, sarcasm — that no fixed rule set can reliably
handle, and an LLM would not reliably handle all of them either). But the **safety-relevant** part of F02 — "stop
a factual claim with no structured expected value from ever reaching maximum-confidence `VERIFIED` status based
on keyword overlap alone" (B.8) — **is** a deterministic policy/boundary change, fully specifiable and testable
with ordinary code, with zero dependence on language understanding. Layer 2 (the boundary cap) closes the actual
vulnerability deterministically today. Layer 1 (the negation-marker rule) is a deterministic, bounded, explicitly
best-effort precision improvement that reduces false negatives (evidence wrongly demoted despite genuinely
agreeing) without weakening Layer 2's safety guarantee when it (inevitably, per B.7) misfires.

**Evidence:** the fix that actually prevents the reported harm (a negated claim reaching VERIFIED with confidence
1.0) is not "understand negation correctly" — it is "stop treating unstructured text agreement as sufficient for
VERIFIED at all," which is a pure status/threshold change requiring no semantic reasoning whatsoever.

## What should the verification engine do when semantic certainty is insufficient?

**Report a bounded, explicitly lower-confidence status that a downstream consumer cannot mistake for a confirmed
fact — never fail open into `VERIFIED`.** Concretely, per B.8: any claim whose only support is textual/keyword
resemblance (no structured value comparison, no typed relation) should cap out at `PARTIALLY_VERIFIED` or a new,
more honestly-named status communicating "text found that appears related; polarity/entailment not independently
confirmed" — paired, ideally, with a `critic_request`/rationale entry that surfaces *why* it was capped, consistent
with the engine's existing critic-request mechanism for other non-`VERIFIED` outcomes (`engine.py`'s
`_generate_critic_requests`, not modified by this design but a natural integration point). This mirrors the
project's own stated design philosophy verbatim: *"incomplete research should stop transparently instead of
becoming confident prose"* (`README.md`) — the fix for F02 is, at its core, an application of a principle the
project already claims to follow but does not yet enforce for this specific code path.
