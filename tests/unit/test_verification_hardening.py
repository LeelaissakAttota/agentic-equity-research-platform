"""Adversarial verification-engine hardening for F01 (numeric bypass) and F02
(negation-blind verification).

See F01_F02_REMEDIATION_DESIGN.md and F01_F02_IMPLEMENTATION_REPORT.md for the
root-cause analysis and fix design these tests pin down.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.verification.claim import Claim, ClaimId, ClaimType
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.domain.verification.evidence import (
    AuthorityTier,
    DataOrigin,
    EvidenceBundle,
    EvidenceRef,
)
from financial_intelligence.domain.verification.result import VerificationStatus

NOW = datetime(2025, 1, 15, tzinfo=UTC)


def _claim(
    *,
    claim_type: ClaimType = ClaimType.NUMERIC,
    text: str = "Revenue was reported for the fiscal period",
    expected_value: str | Decimal | datetime | None = None,
    expected_unit: str | None = None,
    expected_currency: str | None = None,
    expected_period: str | None = None,
) -> Claim:
    return Claim(
        claim_id=ClaimId.new(),
        claim_type=claim_type,
        text=text,
        company_id="TEST",
        research_run_id="test-run",
        expected_value=expected_value,
        expected_unit=expected_unit,
        expected_currency=expected_currency,
        expected_period=expected_period,
    )


def _evidence(
    *,
    claim_type: ClaimType,
    snippet: str,
    extracted_value: str | Decimal | datetime | None = None,
    extracted_unit: str | None = None,
    extracted_currency: str | None = None,
    extracted_period: str | None = None,
    authority_tier: AuthorityTier = AuthorityTier.TIER_1_AUTHORITATIVE,
    evidence_id: str = "ev-1",
) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source_id="Official",
        authority_tier=authority_tier,
        data_origin=DataOrigin.FIXTURE,
        claim_type=claim_type.value,
        extracted_value=extracted_value,
        extracted_unit=extracted_unit,
        extracted_currency=extracted_currency,
        extracted_period=extracted_period,
        as_of=NOW,
        retrieved_at=NOW,
        raw_snippet=snippet,
        url="https://example.com/evidence",
    )


def _classify(claim: Claim, *evidence_refs: EvidenceRef) -> EvidenceBundle:
    return EvidenceBundle.classify(claim, tuple(evidence_refs))


def _verify(claim: Claim, *evidence_refs: EvidenceRef) -> VerificationStatus:
    bundle = _classify(claim, *evidence_refs)
    engine = VerificationEngine()
    return engine.verify(claim, bundle, now=NOW).status


class F01NumericVerificationHardeningTests(TestCase):
    """F01: numeric values must be parsed and compared as Decimal, never as text."""

    def _numeric_claim(self, value: str | Decimal | None) -> Claim:
        return _claim(
            claim_type=ClaimType.NUMERIC,
            expected_value=value,
            expected_unit="million USD",
            expected_currency="USD",
            expected_period="2024",
        )

    def _numeric_evidence(self, value: str | Decimal | None) -> EvidenceRef:
        return _evidence(
            claim_type=ClaimType.NUMERIC,
            snippet="Revenue was reported for the fiscal period",
            extracted_value=value,
            extracted_unit="million USD",
            extracted_currency="USD",
            extracted_period="2024",
        )

    # -- valid integer strings --------------------------------------------------
    def test_valid_integer_strings_match(self) -> None:
        claim = self._numeric_claim("100")
        evidence = self._numeric_evidence("100")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- valid decimal strings ----------------------------------------------------
    def test_valid_decimal_strings_match(self) -> None:
        claim = self._numeric_claim("383.285")
        evidence = self._numeric_evidence("383.285")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- equivalent numeric representations ---------------------------------------
    def test_equivalent_numeric_representations_match_as_strings(self) -> None:
        """The original F01 bypass: '100' vs '100.0' must be recognized as equal."""
        claim = self._numeric_claim("100")
        evidence = self._numeric_evidence("100.0")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(bundle.contradicting, ())
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_equivalent_numeric_representations_match_scientific_notation(self) -> None:
        claim = self._numeric_claim("100")
        evidence = self._numeric_evidence("1e2")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_equivalent_numeric_representations_mixed_decimal_and_string(self) -> None:
        """A pre-parsed Decimal on one side and a JSON string on the other must
        still compare numerically, not textually."""
        claim = self._numeric_claim("100")
        evidence = self._numeric_evidence(Decimal("100.0"))
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- non-numeric strings --------------------------------------------------------
    def test_non_numeric_string_both_sides_is_not_verified(self) -> None:
        """The original F01 bypass: 'not-a-number' == 'not-a-number' must not verify."""
        claim = self._numeric_claim("not-a-number")
        evidence = self._numeric_evidence("not-a-number")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- malformed numeric strings ("NaN" / "Infinity" as JSON strings) -------------
    def test_nan_string_both_sides_is_not_verified(self) -> None:
        claim = self._numeric_claim("NaN")
        evidence = self._numeric_evidence("NaN")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_infinity_string_both_sides_is_not_verified(self) -> None:
        claim = self._numeric_claim("Infinity")
        evidence = self._numeric_evidence("Infinity")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_negative_infinity_string_both_sides_is_not_verified(self) -> None:
        claim = self._numeric_claim("-Infinity")
        evidence = self._numeric_evidence("-Infinity")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- empty strings ----------------------------------------------------------------
    def test_empty_string_expected_value_is_not_verified(self) -> None:
        claim = self._numeric_claim("")
        evidence = self._numeric_evidence("100")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- whitespace ---------------------------------------------------------------------
    def test_whitespace_only_string_is_not_verified(self) -> None:
        claim = self._numeric_claim("   ")
        evidence = self._numeric_evidence("100")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_surrounding_whitespace_is_tolerated_for_valid_numbers(self) -> None:
        claim = self._numeric_claim("  100  ")
        evidence = self._numeric_evidence("100")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- non-finite genuine Decimal instances (domain-level, bypassing Pydantic) -----
    def test_genuine_decimal_nan_is_not_verified(self) -> None:
        claim = self._numeric_claim(Decimal("NaN"))
        evidence = self._numeric_evidence(Decimal("NaN"))
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.CONTRADICTED)

    def test_genuine_decimal_infinity_is_not_verified(self) -> None:
        claim = self._numeric_claim(Decimal("Infinity"))
        evidence = self._numeric_evidence(Decimal("Infinity"))
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertEqual(_verify(claim, evidence), VerificationStatus.CONTRADICTED)

    def test_genuine_decimal_instances_still_match_exactly(self) -> None:
        """Regression guard: two real Decimal instances must still work as before."""
        claim = self._numeric_claim(Decimal("100"))
        evidence = self._numeric_evidence(Decimal("100"))
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- mixed / malformed edge cases ------------------------------------------------
    def test_unparseable_string_with_units_is_not_verified(self) -> None:
        claim = self._numeric_claim("100")
        evidence = self._numeric_evidence("$100 million")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_thousands_separator_is_not_silently_accepted(self) -> None:
        """Documents current scope: locale-formatted numbers are rejected, not
        silently misparsed. See F01_F02_REMEDIATION_DESIGN.md Edge Cases."""
        claim = self._numeric_claim("1000")
        evidence = self._numeric_evidence("1,000")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    def test_numerically_different_values_remain_contradicted(self) -> None:
        """Regression guard: genuinely different numbers must still contradict."""
        claim = self._numeric_claim("100")
        evidence = self._numeric_evidence("150")
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.CONTRADICTED)


class F02NegationHardeningTests(TestCase):
    """F02: keyword overlap alone must never produce VERIFIED when claim polarity
    cannot be established."""

    # -- direct positive claim / positive evidence (must remain VERIFIED) ----------
    def test_direct_positive_claim_with_supporting_evidence_is_verified(self) -> None:
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple acquired ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple acquired ExampleCorp",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- direct negative claim, consistently negated evidence -----------------------
    def test_direct_negative_claim_with_matching_negated_evidence_is_not_verified(
        self,
    ) -> None:
        """Both claim and evidence negate the same event. This is a genuine
        agreement a human would recognize, but this deterministic engine cannot
        reliably resolve negation parity (see F01_F02_REMEDIATION_DESIGN.md B.7) --
        it must fail toward non-VERIFIED rather than assume agreement."""
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple did not acquire ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple did not acquire ExampleCorp",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- negative evidence contradicting a positive claim (the original F02 repro) --
    def test_negated_evidence_against_positive_claim_is_not_verified(self) -> None:
        """Exact reproduction of the original F02 finding: evidence negates the
        claim's assertion and must be classified as contradicting, never
        supporting."""
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple acquired ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple did not acquire ExampleCorp",
        )
        bundle = _classify(claim, evidence)
        self.assertNotIn(evidence, bundle.supporting)
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.CONTRADICTED)

    # -- negated claim with overlapping keywords, non-negated (opposing) evidence ---
    def test_negated_claim_contradicted_by_non_negated_evidence(self) -> None:
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple did not acquire ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple acquired ExampleCorp",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(_verify(claim, evidence), VerificationStatus.CONTRADICTED)

    # -- evidence containing negation (claim/evidence polarity mismatch) -----------
    def test_claim_evidence_polarity_mismatch_never_supports(self) -> None:
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple filed its annual report on 2024-10-27",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple never filed its annual report on 2024-10-27",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertEqual(_verify(claim, evidence), VerificationStatus.CONTRADICTED)

    # -- double negation / ambiguous wording -----------------------------------------
    def test_double_negation_is_not_verified(self) -> None:
        """Claim and evidence each carry their own negation marker ('never denied'
        vs 'did not deny') and, read together, actually agree -- but this engine
        has no reliable way to resolve negation parity across two independently
        negated texts. When both sides carry a negation marker, the result must
        land in a non-VERIFIED, safe state rather than assert false certainty in
        either direction."""
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple never denied acquiring ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple did not deny acquiring ExampleCorp",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertNotIn(evidence, bundle.contradicting)
        self.assertIn(evidence, bundle.neutral)
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- hedged / uncertain wording ---------------------------------------------------
    def test_hedged_evidence_is_not_verified(self) -> None:
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple acquired ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple allegedly acquired ExampleCorp according to sources",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertIn(evidence, bundle.neutral)
        self.assertNotEqual(_verify(claim, evidence), VerificationStatus.VERIFIED)

    # -- keyword overlap without semantic support (acknowledged, unsolved limitation) --
    def test_keyword_overlap_with_reversed_meaning_is_a_known_unsolved_limitation(
        self,
    ) -> None:
        """Documents an explicitly acknowledged limitation (see
        F01_F02_REMEDIATION_DESIGN.md B.7): this deterministic, negation-marker-only
        fix does not detect reversed subject/object or otherwise-unrelated
        assertions that merely share vocabulary. This test does NOT claim the
        defect is fixed for this case -- it pins down that the current, known-
        incomplete behavior is unchanged, so a future change to this area cannot
        silently regress it further without this test being updated deliberately.
        """
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple acquired ExampleCorp in 2024",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="ExampleCorp acquired Apple technology licenses in 2019",
        )
        bundle = _classify(claim, evidence)
        # Known limitation: no negation marker is present on either side, so this
        # reversed-meaning snippet is still treated as a clean match today.
        self.assertEqual(bundle.supporting, (evidence,))

    # -- regression guard: unrelated evidence remains neutral, not supporting ------
    def test_unrelated_evidence_stays_neutral(self) -> None:
        claim = _claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple acquired ExampleCorp",
        )
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Microsoft released a new version of Windows",
        )
        bundle = _classify(claim, evidence)
        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, ())
        self.assertIn(evidence, bundle.neutral)
