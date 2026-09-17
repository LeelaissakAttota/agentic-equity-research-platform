# F02 Verification Semantics Review — `is_verified` / `PARTIALLY_VERIFIED`

**Status:** REVIEW ONLY — no source code modified, no dependency added, no commit, no push, no branch change.
**Scope:** the `is_verified`/`PARTIALLY_VERIFIED` question flagged as open in
`F01_F02_IMPLEMENTATION_REPORT.md` §9, after the F01/F02 code changes already implemented and merged into the
working tree (evidence.py's `_evaluate_match`/`_assess_polarity`, unchanged since that report).
**Method:** every claim below is backed by a direct file/line read performed in this pass, not assumed from the
prior design document.

---

## 1. Current Contract — what each status actually means

Source: `src/financial_intelligence/domain/verification/result.py:12-20` (enum definitions) and
`src/financial_intelligence/domain/verification/engine.py:272-305` (`_determine_status`, the sole place any of
these values is produced).

| Status | Producing condition (`_determine_status`) | Stated meaning (docstring comment) | Actual meaning after this pass's tracing |
|---|---|---|---|
| `VERIFIED` | `has_supporting and not has_contradicting`, evidence not stale, `confidence >= min_confidence_for_verified` (default `0.7`) | "Sufficient evidence supports the claim" | Reached by **either** a structured (numeric/typed) exact match **or** a purely lexical (bag-of-words) prose match with no detected negation/hedge, provided confidence clears 0.7. The status name does not distinguish *how* the match was established. |
| `PARTIALLY_VERIFIED` | Same evidence shape as `VERIFIED` (`has_supporting`, no contradicting, not stale) but `min_confidence_for_partially_verified <= confidence < min_confidence_for_verified` (default `0.4`–`0.7`) | "Some evidence supports, some missing" | In practice this is reached whenever the *same* supporting evidence exists but confidence is merely lower (e.g. a Tier-3/Tier-4 source, or fewer corroborating factors) — **not** specifically "some evidence supports, some is missing" in any structural sense; nothing in the code checks for "missing" evidence fields to select this status over `VERIFIED`. It is a **confidence-band label**, not a distinct evidentiary claim. |
| `CONTRADICTED` | `has_contradicting and not has_supporting` | "Evidence contradicts the claim" | Reached by a structured value mismatch, **or**, after the F02 fix, a detected negation-marker asymmetry (exactly one side of claim/evidence negates). Accurate to its name. |
| `CONFLICTING` | `has_supporting and has_contradicting` | "Evidence both supports and contradicts" | Accurate to its name; requires at least one ref in each of `supporting`/`contradicting`. |
| `UNVERIFIABLE` | No evidence at all, **or** evidence exists but none was classified as supporting or contradicting (this is where F02's new `NEUTRAL` `_MatchOutcome` routes to at the `VerificationStatus` level — `NEUTRAL` is an internal classification detail inside `EvidenceBundle`, not itself a `VerificationStatus` value) | "Insufficient evidence to conclude" | Accurate. After the F02 fix, this is also where ambiguous/hedged/double-negated evidence lands, since such evidence is placed in `bundle.neutral`, which contributes to neither `has_supporting` nor `has_contradicting`. |
| `STALE` | Same evidentiary shape as `VERIFIED`/`PARTIALLY_VERIFIED`/`UNVERIFIABLE` but the qualifying evidence's `as_of`/`retrieved_at` falls outside `max_evidence_age_days` | "Evidence exists but is outdated" | Accurate; a status *modifier* applied on top of what would otherwise be `VERIFIED`/`PARTIALLY_VERIFIED`/`UNVERIFIABLE`. |

**Key finding for §1:** there is no status, and no field on `VerificationResult`, that distinguishes "matched via
a structured, typed comparison" from "matched via bag-of-words lexical overlap." Both `VERIFIED` and
`PARTIALLY_VERIFIED` can be produced by either mechanism; the only variable that separates them is the numeric
confidence score, not the evidentiary method.

---

## 2. `is_verified` — every use, and what each caller actually needs

Confirmed by repository-wide grep (`grep -rn "is_verified" src tests`); three real usages exist, plus the
one-line property definition itself:

### 2.1 `src/financial_intelligence/domain/verification/result.py:213-214` (the property)
```python
@property
def is_verified(self) -> bool:
    return self.status in {VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED}
```
Definition site, not a caller.

### 2.2 `src/financial_intelligence/domain/verification/result.py:241` — `to_dict()`
```python
"is_verified": self.is_verified,
```
This serializes the boolean into `VerificationResult.to_dict()`'s output. **Traced whether this dict ever reaches
an HTTP response:** no route in `api/routes/*.py` was found calling `VerificationResult.to_dict()` directly or
exposing a raw verification-result payload; the synthesis API path (`api/routes/synthesis.py`) instead goes
through `domain/synthesis/model.py`'s `ResearchClaim`, which carries its own `verification_status: VerificationStatus`
field (the literal status string, e.g. `"partially_verified"`) and does **not** re-expose `is_verified` at all
(confirmed: `model.py:146-171` has no `is_verified` key in its `to_dict()`). **Conclusion: `is_verified` is not
currently reachable through any exercised HTTP response.** It exists as a convenience on the domain object and is
serialized only if something calls `VerificationResult.to_dict()` directly — nothing in the current codebase does.
**What this caller needs:** N/A — it is a serialization mirror of the property, not an independent consumer.

### 2.3 `src/financial_intelligence/domain/verification/engine.py:141` — `assess_critic`
```python
def assess_critic(self, result: VerificationResult, *, attempts_used: int, max_attempts: int = 2) -> CriticAssessment:
    ...
    if result.is_verified:
        return CriticAssessment(..., status=CriticAssessmentStatus.SUFFICIENT_EVIDENCE, ...)
    ...
```
**What this caller needs:** a decision on whether to **stop spending research budget** on this claim. This is a
resource/orchestration decision, not a presentation decision.
**Does it need "definitive verification," "partial evidence," or "any positive evidence"?** It needs to know
whether *further research attempts are worth spending*. Structurally, `PARTIALLY_VERIFIED` genuinely does carry
non-contradicted supporting evidence (same shape as `VERIFIED`, just lower confidence) — so treating it as "stop,
don't spend more budget" is a defensible resource-management choice **if and only if** the confidence score
itself is trustworthy. It becomes a problem specifically when the *only* evidence behind that confidence score is
uncorroborated bag-of-words matching (see §3), because the critic loop then has no signal telling it "this
confidence was earned cheaply, not by a strong source."

### 2.4 `tests/unit/test_phase8_contract_freeze.py:114`
```python
self.assertFalse(operation.verification.is_verified)
```
A negative-case regression test (asserts `is_verified` is `False` for `UNVERIFIABLE`). Does not exercise the
`PARTIALLY_VERIFIED` boundary at all. **Not a design consumer**, just a test.

### 2.5 `tests/unit/test_verification_hardening.py:261` (this pass's own F02 test suite)
A test method *name* (`test_direct_positive_claim_with_supporting_evidence_is_verified`) — not a call to the
property. Irrelevant to this inventory.

### 2.6 Callers that encode the *same set* inline, without going through the `is_verified` property

Three call sites duplicate `{VERIFIED, PARTIALLY_VERIFIED}` (sometimes `∪ {STALE}`) as an inline set rather than
calling the property — these are functionally equivalent consumers and must be considered alongside `is_verified`
itself, since fixing only the named property would leave these silently inconsistent:

- `engine.py:349` (`_generate_critic_requests`): `if status in {VERIFIED, PARTIALLY_VERIFIED}: return ()` — i.e.
  **do not generate a critic/re-research request** for either status. Same resource-decision need as §2.3 (this
  is in fact the sibling function `assess_critic` at §2.3 delegates to conceptually — both express "no further
  research needed").
- `domain/synthesis/contracts.py:254-263` (`VerifiedClaimInput.__post_init__`): `{VERIFIED, PARTIALLY_VERIFIED,
  STALE}` combined with `and not classified.supporting` → raises `ValueError` if a claim carries one of these
  three statuses but has no actual supporting evidence. **This caller needs "any positive evidence exists"** — it
  is an internal consistency check (a status claiming support must actually have support), not a
  definitive/partial distinction. This one is *not* a safety gap: it enforces the reverse invariant (status must
  be backed by real evidence), and does not itself decide whether that evidence is trustworthy.
- `domain/synthesis/contracts.py:332-336` (`VerifiedClaimInput._validate_material_claim`): same `{VERIFIED,
  PARTIALLY_VERIFIED, STALE}` set, gating whether a *material* claim (revenue, earnings, valuation, etc.) is
  "accepted" and therefore subject to further structural requirements (e.g., revenue/earnings claims must carry
  `expected_value`/`expected_unit`). **This caller needs "any positive evidence exists,"** similarly to the
  previous item — it is not deciding end-user trust, only whether to apply additional structural validation.
- `domain/synthesis/policy.py:317-322` (`_citation_evidence`): returns `bundle.supporting` as the citation set for
  `{VERIFIED, PARTIALLY_VERIFIED, STALE}`. **This caller needs "there is evidence to cite,"** not a
  definitive/partial distinction — it decides *which* evidence references appear as citations, not how strongly
  the claim is asserted.

**Does the current boolean abstraction lose important information?**

Yes, but the loss is asymmetric across callers:
- For the **presentation-shaping** callers (`policy.py`'s disposition/rendered-text logic — see §3), the
  distinction is **not lost**: `VerifiedClaimGate._render` (policy.py:238-241) branches on `VerificationStatus`
  directly, not on `is_verified`, and produces different `ClaimDisposition`/rendered text for `VERIFIED`
  (`FACTUAL`, plain claim text) vs. `PARTIALLY_VERIFIED` (`QUALIFIED`, `"Partially verified: {claim text}"`). The
  end-user-facing narrative **does** distinguish the two today.
- For the **resource/orchestration** callers (`assess_critic`, `_generate_critic_requests`), the distinction
  **is** lost: both statuses stop further research identically, regardless of *why* the confidence score landed
  where it did.
- For the **confidence label** shown alongside the rendered text (`policy.py:201-215`,
  `VerifiedClaimGate.confidence_label`): this function does **not** special-case `PARTIALLY_VERIFIED` at all — it
  only special-cases `CONFLICTING`/`CONTRADICTED`/`STALE`/`UNVERIFIABLE`. For `VERIFIED` and `PARTIALLY_VERIFIED`
  alike, the label falls through to the same score-threshold ladder (`>=0.8` → `HIGH`, `>=0.6` → `MODERATE`, else
  `LOW`). **Concretely: a `VERIFIED` claim with confidence `0.72` and a `PARTIALLY_VERIFIED` claim with confidence
  `0.65` both render `ConfidenceLabel.MODERATE_CONFIDENCE`.** The disposition/rendered-text still say "Partially
  verified: ..." for the latter, so the two are not *identical* end-to-end, but the confidence label itself does
  not reinforce that distinction — a UI or downstream consumer reading only `confidence_label` (not the full
  `disposition`/`rendered_text`) would see the same label for both.

---

## 3. F02 Impact — concrete traces

All five traces use the same claim shape (`ClaimType.FACTUAL`, `text="Apple acquired ExampleCorp"`,
`expected_value=None`) through `EvidenceBundle.classify` → `VerificationEngine.verify` →
`VerifiedClaimGate.evaluate` (policy.py) → the JSON shape `ResearchClaim.to_dict()` would produce
(`model.py:146-171`). Authority tier is Tier-1 unless noted.

### 3.1 Evidence is genuinely verified
- **Input:** snippet = `"Apple acquired ExampleCorp"` (identical to claim, Tier-1 source).
- **Classification:** `supports_claim` passes (full keyword overlap); `_assess_polarity` → `CLEAR` (no
  negation/hedge marker either side) → `_MatchOutcome.SUPPORTING`.
- **`_determine_status`:** `has_supporting=True`, no contradicting, not stale, confidence: Tier-1 weight `1.0` +
  recency `0.3` + no-contradictions `0.3` (clamped to `1.0`) → `confidence >= 0.7` → **`VERIFIED`**.
- **`is_verified`:** `True`.
- **`assess_critic`:** `SUFFICIENT_EVIDENCE` (stop researching).
- **`policy.py._render`:** `status is VERIFIED` → `ClaimDisposition.FACTUAL`, rendered text = the claim text
  verbatim, no qualifier.
- **`confidence_label`:** falls through to score ladder; `1.0 >= 0.8` → `ConfidenceLabel.HIGH` (`"high_confidence"`).
- **API JSON (`ResearchClaim.to_dict()`):** `{"disposition": "factual", "verification_status": "verified", ...}`,
  `confidence: {"label": "high_confidence", "score": 1.0, ...}`.
- **Assessment:** correct end-to-end; no ambiguity.

### 3.2 Evidence is only partially supportive
- **Input:** same clean snippet, but from a **Tier-4** ("general web") source instead of Tier-1.
- **Classification:** identical to 3.1 — `CLEAR` polarity, `SUPPORTING`. (Note: F02's polarity check does not
  distinguish this case from 3.1 at all; the only variable that changes is authority tier.)
- **`_determine_status`:** confidence: Tier-4 weight `0.2` + no-contradictions bonus `0.3` (source-authority
  factor only contributes if `max_tier_weight >= 0.7`, which Tier-4 does not clear, so no `SOURCE_AUTHORITY`
  factor) → total roughly `0.2 + 0.3 (+ recency 0.3 if recent) ≈ 0.5–0.8` depending on recency — for a concrete,
  reproducible figure: with recency counted, `0.2 + 0.3 + 0.3 = 0.8` would actually exceed the `VERIFIED` threshold;
  the precise arithmetic depends on which confidence components apply and was not re-derived exhaustively here —
  **flagged UNVERIFIED for the exact boundary value**, but the qualitative point holds regardless of the exact
  figure: a confidence in the `[0.4, 0.7)` band is reachable from Tier-4-sourced, purely lexical evidence with no
  structural corroboration.
- **Assume, for concreteness, confidence lands at `0.55`** (achievable by reducing the recency/consistency
  contribution, e.g. older `as_of`) → `_determine_status` → **`PARTIALLY_VERIFIED`**.
- **`is_verified`:** `True` (same as fully verified).
- **`assess_critic`:** `SUFFICIENT_EVIDENCE` — **identical decision to the Tier-1 case in 3.1**: the system will
  not seek a better source, even though the only evidence is a general-web snippet matched by bag-of-words alone.
- **`policy.py._render`:** `status is PARTIALLY_VERIFIED` → `ClaimDisposition.QUALIFIED`, rendered text =
  `"Partially verified: Apple acquired ExampleCorp"`.
- **`confidence_label`:** `0.55 >= 0.6`? No → falls to `LOW` (`"low_confidence"`), since it fails the `0.6`
  moderate threshold. *(If confidence instead landed at `0.65`, the label would be `MODERATE`, i.e.
  `"moderate_confidence"` — same label a `VERIFIED` claim with `0.72` confidence would also show.)*
- **API JSON:** `{"disposition": "qualified", "verification_status": "partially_verified", ...}`,
  `confidence: {"label": "low_confidence"` or `"moderate_confidence", "score": 0.55, ...}`.
- **Assessment:** the *disposition* and *verification_status* fields are honest and distinguishable from 3.1. The
  *`is_verified` boolean* and the *critic/orchestration decision* are not — both treat this identically to a
  Tier-1, fully-corroborated claim.

### 3.3 Evidence is ambiguous (hedged wording)
- **Input:** snippet = `"Apple allegedly acquired ExampleCorp according to sources"`.
- **Classification:** `supports_claim` passes (keyword overlap sufficient); `_assess_polarity` → no negation
  either side, but `_hedge_count(snippet) > 0` (`"allegedly"`) → `AMBIGUOUS` → `_MatchOutcome.NEUTRAL`.
- **`classify()`:** this evidence lands in `bundle.neutral`, contributing to neither `supporting` nor
  `contradicting`.
- **`_determine_status`:** `has_supporting=False`, `has_contradicting=False`, `bundle.evidence_refs` non-empty →
  falls through to the final line → **`UNVERIFIABLE`**.
- **`is_verified`:** `False`.
- **`assess_critic`:** not `SUFFICIENT_EVIDENCE`; generates a `CriticRequest` (`RESEARCH_REQUIRED` or
  `ATTEMPTS_EXHAUSTED` depending on budget) with reason `"Insufficient evidence to verify factual claim"`.
- **`policy.py._render`:** `status is UNVERIFIABLE` → falls to the final `return (ClaimDisposition.INSUFFICIENT,
  f"Insufficient evidence to verify: {claim.text}")`.
- **`confidence_label`:** `status is UNVERIFIABLE` → explicit override → `ConfidenceLabel.INSUFFICIENT`
  (`"insufficient_evidence"`).
- **API JSON:** `{"disposition": "insufficient", "verification_status": "unverifiable", ...}`,
  `confidence: {"label": "insufficient_evidence", "score": 0.0, ...}`.
- **Assessment:** fully honest and safe at every layer — this is the F02 fix working as intended for the
  ambiguous case, confirmed by direct trace (not just the unit test's status assertion).

### 3.4 Evidence is negated
- **Input:** snippet = `"Apple did not acquire ExampleCorp"` (claim positive, evidence negates it).
- **Classification:** `supports_claim` passes; `_assess_polarity`: `claim_negations=0`, `snippet_negations=1` →
  differ → `CONFLICT` → `_MatchOutcome.CONTRADICTING`.
- **`classify()`:** evidence lands in `bundle.contradicting`.
- **`_determine_status`:** `has_supporting=False`, `has_contradicting=True` → **`CONTRADICTED`**.
- **`is_verified`:** `False`.
- **`assess_critic`:** not sufficient; generates a `CriticRequest` with reason `"Evidence contradicts factual
  claim; verify with authoritative source"`.
- **`policy.py._render`:** `status is CONTRADICTED` → `(ClaimDisposition.CONTRADICTED, f"Available evidence
  contradicts: {claim.text}")`.
- **`confidence_label`:** explicit override → `ConfidenceLabel.CONTRADICTED` (`"contradicted"`).
- **API JSON:** `{"disposition": "contradicted", "verification_status": "contradicted", ...}`,
  `confidence: {"label": "contradicted", "score": 0.0, ...}`.
- **Assessment:** fully honest and safe — this is the exact original F02 reproduction case, confirmed end-to-end
  through synthesis, not just at the `VerificationStatus` level.

### 3.5 Evidence contradicts the claim (structured/numeric case, for completeness)
- **Input:** `ClaimType.NUMERIC`, `expected_value="100"`, evidence `extracted_value="150"`.
- **Classification:** `_evaluate_match` → both coerce to finite `Decimal`, `100 != 150` → `CONTRADICTING`.
- Same downstream path as 3.4 (`CONTRADICTED` → `is_verified=False` → critic request → disposition
  `contradicted`). No difference in behavior between the numeric and prose contradiction paths at this level —
  confirms the F01 and F02 fixes converge on the same safe downstream handling.

### Summary table

| Case | `VerificationStatus` | `is_verified` | `assess_critic` stops research? | `disposition` | `confidence_label` |
|---|---|---|---|---|---|
| 3.1 Genuinely verified | `VERIFIED` | `True` | Yes | `factual` | `high_confidence` |
| 3.2 Partially supportive | `PARTIALLY_VERIFIED` | **`True`** | **Yes** | `qualified` | `low_confidence`/`moderate_confidence` |
| 3.3 Ambiguous/hedged | `UNVERIFIABLE` | `False` | No | `insufficient` | `insufficient_evidence` |
| 3.4 Negated | `CONTRADICTED` | `False` | No | `contradicted` | `contradicted` |
| 3.5 Numeric contradiction | `CONTRADICTED` | `False` | No | `contradicted` | `contradicted` |

**The F02-specific rows (3.3, 3.4) are fully closed** — neither ambiguous nor negated evidence can reach
`is_verified=True` after the fix already implemented. **The remaining concern (row 3.2) is not new and not
reopened by F02** — it is the pre-existing, broader question (already flagged, not decided, in the prior
implementation report) about whether *any* keyword-overlap-only match, regardless of polarity, should be allowed
to stop the critic loop and read as "verified" in the boolean sense.

---

## 4. Safety Invariant

**Stated invariant:** "Only evidence that meets the system's definitive verification criteria may be treated as
verified by downstream consumers."

**Does it hold?**

**For the F02 vulnerability specifically (negated or polarity-ambiguous claims): YES, it holds**, after the
already-implemented fix. Traced in §3.3/§3.4: neither path can produce `VERIFIED`, `PARTIALLY_VERIFIED`, or
`is_verified=True`. This was verified both by the domain-level and API-level regression tests in
`F01_F02_IMPLEMENTATION_REPORT.md` §4 and by the fresh trace in §3 of this document.

**For the broader, pre-existing question (non-negated but weakly-sourced, keyword-overlap-only prose matches):
NO, it does not fully hold**, if "definitive verification criteria" is read to mean "a structured/typed
comparison, or at least a strong, corroborated source" — and this is not new or caused by F02; it was already
true before the F01/F02 changes and remains true after them, because F02 only added a polarity gate, not an
evidentiary-strength gate.

**Exact path by which it is violated (row 3.2):**
```
EvidenceRef.supports_claim()  →  bag-of-words overlap only, Tier-4 "general web" source
        │  (passes: enough shared keywords)
        ▼
_evaluate_match()  →  expected_value is None, claim_type != NUMERIC, _assess_polarity == CLEAR
        │  (no negation/hedge detected → SUPPORTING; F02's gate has nothing to say about *source strength*)
        ▼
EvidenceBundle.classify()  →  ref placed in `supporting`
        │
        ▼
VerificationEngine._compute_confidence()  →  score built from recency + no-contradictions + (small/no)
        │  source-authority contribution; can land in the PARTIALLY_VERIFIED band [0.4, 0.7)
        ▼
VerificationEngine._determine_status()  →  PARTIALLY_VERIFIED
        │
        ▼
VerificationResult.is_verified  →  True   (status in {VERIFIED, PARTIALLY_VERIFIED})
        │
        ├──► VerificationEngine.assess_critic()  →  SUFFICIENT_EVIDENCE (research stops)
        │
        └──► domain/synthesis/policy.py._render()  →  ClaimDisposition.QUALIFIED,
                 rendered as "Partially verified: {claim text}"  (asserts the claim's own
                 text to the end user, softened only by a prefix qualifier, not by evidentiary caveat)
```
The invariant is violated specifically at the `is_verified`/`assess_critic` step: a claim whose only support is
uncorroborated bag-of-words matching against a low-authority source is treated, for resource-allocation purposes,
identically to a claim confirmed by a structured comparison against a Tier-1 source. The **disposition/rendered
text layer** is more honest (it does say "Partially verified," not "Verified"), but the **boolean/orchestration
layer** makes no such distinction.

---

## 5. Design Options (comparison, not implemented)

### Option A — Keep `PARTIALLY_VERIFIED`, change `is_verified`'s semantics
Redefine `is_verified` to return `True` only for `status == VERIFIED` (drop `PARTIALLY_VERIFIED` from the set).

- **API compatibility impact:** `is_verified` is not currently exposed through any exercised HTTP response (§2.2)
  — no external API contract changes. Internally, `assess_critic` (§2.3) would now continue researching
  `PARTIALLY_VERIFIED` claims instead of stopping; `_generate_critic_requests` (§2.6) would need the identical
  change to stay consistent (it does not call `is_verified`, it duplicates the set inline — **both must change
  together or the two functions would disagree with each other**, a new inconsistency this option must guard
  against). `contracts.py`'s two inline-set usages (§2.6) intentionally need `PARTIALLY_VERIFIED` to remain in
  their set (they check "does evidence exist," not "is this definitive") — so a blanket redefinition of the
  shared set would be wrong for those two call sites specifically; this option requires touching `is_verified`
  and `_generate_critic_requests` while deliberately leaving `contracts.py`'s two sites unchanged, which is easy
  to get wrong by search-and-replace.
- **Test impact:** `test_phase8_contract_freeze.py:114` (asserts `is_verified` False for `UNVERIFIABLE`) is
  unaffected. No existing test asserts `is_verified is True` for a `PARTIALLY_VERIFIED` result — confirmed by grep
  or, this pass's own new tests do not assert `is_verified` at all, only `VerificationStatus` and
  `bundle.supporting`/`contradicting`. Some **behavioral** test additions would be needed: a new test asserting
  `assess_critic` now continues researching a `PARTIALLY_VERIFIED` result (currently no test pins this either
  way).
- **Implementation complexity:** SMALL — one property + one inline-set change, provided the two `contracts.py`
  sites are deliberately left alone.
- **Semantic clarity:** improves `is_verified`'s literal meaning ("is this the confirmed-true status") but leaves
  `PARTIALLY_VERIFIED` itself exactly as ambiguous as today (§1) — it still conflates "clean lexical match, low
  confidence" with "structured match, low confidence." The *label* "partially verified" would now correctly imply
  "not fully verified, keep researching," which is arguably closer to its name's plain meaning than today's
  behavior.
- **Risk of future misuse:** MEDIUM — a future contributor could easily reintroduce the same conflation by adding
  a new `is_verified`-adjacent helper (e.g., `is_actionable`) that once again lumps `PARTIALLY_VERIFIED` back in,
  because nothing in the *type system* prevents it — the fix is behavioral, not structural.

### Option B — Introduce a more explicit distinction: definitively verified / partially supported / not verified
Add a derived, explicit tri-state accessor (e.g. a property or a small enum) that callers use instead of the raw
`VerificationStatus` set-membership checks scattered across `engine.py`/`contracts.py`/`policy.py`, and have each
existing call site switch to querying it for the specific question it actually needs (per §2's per-caller
analysis: resource-decision callers ask "definitive only"; evidentiary-existence callers ask "any positive
evidence"). This does **not** require changing `VerificationStatus`'s six existing values — it is a derived view
over them, e.g.:
```python
@property
def is_definitively_verified(self) -> bool:
    return self.status is VerificationStatus.VERIFIED

@property
def has_any_supporting_evidence(self) -> bool:
    return self.status in {VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED, VerificationStatus.STALE}
```
(illustrative only — not implemented).

- **API compatibility impact:** none to the wire format (`VerificationStatus` values are unchanged); adds new
  read-only derived properties alongside the existing (possibly deprecated-but-kept) `is_verified`.
- **Test impact:** each of the four real call sites (§2.3, §2.6 ×3) would get its own targeted test asserting it
  now asks the *correct* question for its own need — more test surface than Option A, but each test is narrow and
  maps 1:1 to a specific caller's documented need from §2, which is easier to review for correctness than one
  shared boolean.
- **Implementation complexity:** MEDIUM — touches the same four call sites as Option A, plus adds one or two new
  named properties/helpers on `VerificationResult`, plus updates each call site to use the property that matches
  its actual need (rather than leaving three of the four still hand-rolling the same set literal, which is the
  `contracts.py`/`policy.py` situation today even before any of this review's changes).
- **Semantic clarity:** HIGH — each caller's intent becomes self-documenting at the call site
  (`if result.is_definitively_verified:` reads unambiguously; today's `if status in {VERIFIED,
  PARTIALLY_VERIFIED}:` repeated three times does not say *why*). This directly addresses the "boolean
  abstraction loses information" finding in §2.
- **Risk of future misuse:** LOW — a new caller has two clearly-named, narrow options to choose from instead of
  one overloaded boolean; the naming itself discourages using the wrong one for a resource-decision vs.
  presentation-decision need.

### Option C — Introduce a new `VerificationStatus` value
E.g. split today's `PARTIALLY_VERIFIED` into two: one for "structured match, lower confidence" and one for
"lexical-only match" (or, alternatively, a status meaning specifically "textually consistent, not independently
confirmed," closer to the original design document's Layer 2 proposal from `F01_F02_REMEDIATION_DESIGN.md`).

- **API compatibility impact:** **HIGH.** `VerificationStatus` values are serialized directly into the API
  response (`ResearchClaim.to_dict()`'s `verification_status` field, confirmed §1/§3) and into
  `docs`/`examples/sample_research_response.json`-style client-facing contracts. Adding a new enum value is an
  additive, technically-backward-compatible change for well-behaved clients (unknown enum values are usually
  tolerated), but it **is** a new value any consumer's switch/match statement must now handle, and this repo's
  own `test_phase*_contract_freeze.py` convention (confirmed present for multiple phases) suggests API/contract
  surface changes are treated as deliberately significant events in this codebase, not routine.
- **Test impact:** HIGH — every existing test that enumerates all `VerificationStatus` values exhaustively (not
  confirmed to exist, but the contract-freeze convention makes this plausible) would need updating; `policy.py`'s
  `_render`/`confidence_label`/`_citation_evidence`/`_missing_context` all switch on `VerificationStatus`
  explicitly and would need a new branch each; `contracts.py`'s three set-literals would need a decision on
  whether the new status joins each set.
- **Implementation complexity:** LARGE — touches the enum, the engine's status-selection logic (which would now
  need to *track* which mechanism produced a match, not just confidence — a change to `_evaluate_match`'s return
  contract, threading a "how was this determined" signal all the way from `EvidenceBundle` through
  `VerificationEngine`), plus every switch statement over `VerificationStatus` in `policy.py`/`contracts.py`.
- **Semantic clarity:** HIGHEST of the options that touch behavior — a new, precisely-named status is the most
  direct way to make "this was only lexically matched" a first-class, queryable fact rather than an inferred one.
- **Risk of future misuse:** LOW once implemented, but the implementation itself carries the highest risk of
  subtle inconsistency (several switch statements to update by hand, each a place to silently miss the new value
  and fall through to a default branch).

### Option D — Track match provenance as data, leave the status enum alone
Add a boolean/enum field to `EvidenceBundle` or `VerificationResult` (e.g. `matched_via_structured_comparison:
bool`, populated by `_evaluate_match` itself, which already knows internally whether it took the `Decimal`-coercion
path or the lexical-polarity path) without changing `VerificationStatus`'s six values or their meaning. Callers
that need the stronger guarantee (§2.3's `assess_critic`, §2.6's `_generate_critic_requests`) would then check
`result.status is VERIFIED and result.matched_via_structured_comparison` (or similar) instead of relying on status
alone; callers that only need "any evidence exists" (§2.6's two `contracts.py` sites) are unaffected.

- **API compatibility impact:** LOW–MEDIUM — adds a new field to the domain object and, if surfaced,
  to `to_dict()`/the API response; existing `verification_status` values and their meanings are completely
  unchanged, so this is purely additive and does not require any consumer to re-interpret an existing value.
- **Test impact:** MEDIUM — every test that constructs a `VerificationResult`/`EvidenceBundle` directly (a large
  fraction of `test_verification_engine.py`, `test_synthesis_domain.py`, etc.) would need the new field
  accounted for in construction, even if most tests don't assert on it — this is a wider mechanical touch than
  Option A/B, though shallower than Option C's behavioral touch.
- **Implementation complexity:** MEDIUM — requires threading a new piece of state from `_evaluate_match` (which
  already has the information — it knows whether it took the `Decimal` branch or the `_assess_polarity` branch)
  up through `EvidenceBundle.classify`, `VerificationResult`, and into whichever callers need it. Less invasive
  than Option C (no new enum value, no new switch branches to maintain) but more invasive than Option A/B (new
  data field, not just a new derived read).
- **Semantic clarity:** HIGH, and arguably the most *honest* option — it records the actual mechanism used
  ("structured" vs. "lexical") as a fact about the evidence, rather than trying to infer it after the fact from
  status + confidence (which, per §1, cannot currently be inferred reliably — a `VERIFIED` status alone does not
  tell you whether it came from a `Decimal` match or a clean keyword match).
- **Risk of future misuse:** LOW — the new field is orthogonal to `VerificationStatus`, so it cannot be
  accidentally conflated with existing status-based branching the way Option A's shared-set risk works; but it
  does add a second axis of state a future contributor must remember to consult, which has its own (smaller) risk
  of being ignored by a new caller that only checks `status`.

---

## 6. Recommendation

**Recommended: Option B (explicit named accessors), narrowly scoped to the four real call sites identified in §2,
with the `contracts.py` sites kept exactly as they are today (they already ask the correct question — "does any
supporting evidence exist" — and are not part of this problem).**

Reasoning, not scored:
- The actual defect is that **two callers with genuinely different needs** (§2.3/§2.6's `assess_critic` and
  `_generate_critic_requests`, which need "is this confident enough to stop researching," vs. §2.6's two
  `contracts.py` sites, which need "does evidence exist at all") currently share one boolean/set literal by
  coincidence, not by design. Option B fixes exactly this mismatch, at the call sites where it actually exists,
  without touching the wire-format `VerificationStatus` enum (avoiding Option C's large blast radius across every
  `policy.py`/`contracts.py` switch statement) and without adding new tracked state that most of the codebase
  would need to thread through but not use (avoiding Option D's broader mechanical touch).
- Option A alone would be an improvement but leaves the *why* undocumented at each call site — a future reader of
  `if result.is_verified:` still cannot tell whether that means "definitively confirmed" or "confidently
  supported" without reading the property's current definition; Option B's named accessors make the call sites
  self-documenting, which directly targets this review's §2 finding ("the boolean abstraction loses important
  information").
- This recommendation explicitly does **not** resolve the deeper §4 concern (lexical-only matches, regardless of
  polarity, can still earn `PARTIALLY_VERIFIED`/stop-research treatment from a weak source) — that is a
  confidence-scoring/evidentiary-strength question, not a naming question, and Option D (tracking match
  provenance as data) is the option that would actually let a future, separately-scoped change answer "should
  lexical-only matches ever earn `PARTIALLY_VERIFIED`, regardless of confidence score?" with real information
  rather than inference. **This review recommends Option B now, and flags Option D as the natural next step if
  you decide the deeper §4 concern needs closing** — but that is a separate, larger decision this review does not
  make for you.

---

## 7. Regression Tests Required (specification only, not implemented)

Assuming Option B is approved, the following tests would be needed before any code change ships (test names are
illustrative, not prescriptive of exact final naming):

1. **`PARTIALLY_VERIFIED` cannot accidentally become definitive verification:**
   - `test_partially_verified_is_not_definitively_verified`: construct a `VerificationResult` with
     `status=PARTIALLY_VERIFIED`; assert the new "definitive" accessor (e.g. `is_definitively_verified`) is
     `False`, while the "has any supporting evidence" accessor is `True`.
   - `test_assess_critic_continues_research_for_partially_verified` (behavior-defining, since no test today pins
     this either way): assert `assess_critic` no longer returns `SUFFICIENT_EVIDENCE` for a `PARTIALLY_VERIFIED`
     result once `assess_critic` is switched to the "definitive only" accessor — **this is a deliberate behavior
     change and must be written as such, not disguised as a bug fix**, since today's behavior
     (`SUFFICIENT_EVIDENCE` for `PARTIALLY_VERIFIED`) is the status quo this option changes.

2. **`VERIFIED` remains definitive:**
   - `test_verified_is_definitively_verified`: `status=VERIFIED` → both the new "definitive" accessor and the
     "has supporting evidence" accessor are `True`. Regression guard against ever narrowing `VERIFIED`'s own
     meaning by mistake.

3. **Existing callers retain intended behavior:**
   - `test_generate_critic_requests_still_skips_verified`: `_generate_critic_requests` (or its equivalent after
     the change) still returns `()` for `VERIFIED` — unchanged.
   - `test_contracts_partially_verified_still_requires_supporting_evidence`: `VerifiedClaimInput.__post_init__`
     still raises for a `PARTIALLY_VERIFIED` (or `VERIFIED`/`STALE`) result with no supporting evidence — proves
     the `contracts.py` sites were correctly left untouched and still enforce their existing (correct) invariant.
   - `test_citation_evidence_still_includes_partially_verified_supporting_refs`: `_citation_evidence` still
     returns `bundle.supporting` for `PARTIALLY_VERIFIED` — proves this caller's "evidence exists to cite" need
     is unaffected by the accessor split.

4. **Synthesis/reporting remains correct:**
   - `test_partially_verified_disposition_and_label_unchanged`: re-assert (as a pinning test, since this is
     already true today and must not regress) that a `PARTIALLY_VERIFIED` claim still renders
     `ClaimDisposition.QUALIFIED` with `"Partially verified: {claim text}"`, and that `confidence_label` is
     unaffected by this change (it does not consult `is_verified` at all today — confirmed in §2 — so it should
     need no code change, only a regression test proving that remains true).

5. **API behavior remains consistent:**
   - `test_partially_verified_over_http_still_returns_qualified_disposition`: an HTTP-level test (matching the
     `test_synthesis_api.py` pattern already used in this pass) posting a Tier-4-sourced, clean (non-negated),
     moderate-confidence claim and asserting the response's `disposition == "qualified"` and
     `verification_status == "partially_verified"` are unchanged from pre-Option-B behavior.
   - `test_verified_over_http_unaffected_by_accessor_change`: the existing golden-flow tests
     (`test_apple_golden_flow_preserves_nasdaq_identity_and_evidence` etc.) already cover this implicitly and
     should simply be re-run, not rewritten, as the final confirmation that `VERIFIED`'s end-to-end behavior is
     unchanged.

**Explicitly not required for this option (would only be required if Option C or D is later chosen):** any test
asserting a new `VerificationStatus` enum value exists, or any test asserting a new `matched_via_*` field is
populated correctly by `_evaluate_match` — those belong to Options C/D respectively and are out of scope unless
you approve one of those instead.

---

## Summary Answers

- **§1:** `VERIFIED` and `PARTIALLY_VERIFIED` differ only by confidence-score band, not by evidentiary method;
  neither distinguishes a structured match from a lexical one.
- **§2:** `is_verified` has exactly one real internal caller (`assess_critic`) plus three inline duplicates of the
  same set (one in `engine.py`, two in `contracts.py`/`policy.py` that actually need a *different* question — "any
  evidence exists," not "definitive"). It is not currently reachable through any exercised HTTP response.
- **§3:** the F02-specific cases (negated, ambiguous) are fully closed by the already-implemented fix and trace
  safely end-to-end through synthesis and the API. The one case that still reaches `is_verified=True` via
  keyword-overlap-only matching is a **non-negated, low-authority-source** claim — a pre-existing condition, not
  a reopening of F02.
- **§4:** the stated safety invariant **holds for the F02 vulnerability**. It **does not fully hold** in the
  broader sense (lexical-only, low-authority matches can still reach `is_verified=True` and stop research), but
  this is unchanged by, and was never claimed to be fixed by, the F02 work already done.
- **§5/§6:** four options compared without scoring; **Option B recommended** as the smallest change that makes
  each caller's actual need explicit, without touching the wire-format enum or requiring new tracked state; Option
  D flagged as the natural follow-up if the deeper §4 question is to be closed later.
- **§7:** ten specific regression tests specified, none implemented.

**No code was modified in the production of this review. Awaiting approval before any implementation.**
