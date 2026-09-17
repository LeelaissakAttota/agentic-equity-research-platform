"""Regression tests for the F02 verification-semantics cleanup (Option B).

Pins down the explicit distinction between:
  - VerificationResult.is_definitively_verified  (only VERIFIED)
  - VerificationResult.is_verified                (VERIFIED or PARTIALLY_VERIFIED,
                                                    kept unchanged for backward
                                                    compatibility)
  - "does any supporting evidence exist"          (contracts.py's own checks,
                                                    intentionally left untouched)

See F02_VERIFICATION_SEMANTICS_REVIEW.md and F02_SEMANTICS_IMPLEMENTATION_REPORT.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.synthesis import (
    ClaimDisposition,
    ResearchSectionType,
    VerifiedClaimGate,
    VerifiedClaimInput,
)
from financial_intelligence.domain.verification.claim import Claim, ClaimId, ClaimType
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.domain.verification.evidence import (
    AuthorityTier,
    EvidenceBundle,
    EvidenceRef,
)
from financial_intelligence.domain.verification.result import (
    CriticAssessmentStatus,
    VerificationResult,
    VerificationStatus,
)
from financial_intelligence.infrastructure.company.reference_dataset import (
    build_reference_companies,
)

NOW = datetime(2025, 1, 15, tzinfo=UTC)


def _company(name: str = "Apple") -> CompanyIdentity:
    return next(company for company in build_reference_companies() if company.display_name == name)


def _claim(
    *,
    claim_type: ClaimType = ClaimType.FACTUAL,
    text: str = "Apple filed its annual report",
    expected_value: str | Decimal | datetime | None = None,
    expected_unit: str | None = None,
    expected_currency: str | None = None,
    expected_period: str | None = None,
    company_id: str = "TEST",
) -> Claim:
    return Claim(
        claim_id=ClaimId.new(),
        claim_type=claim_type,
        text=text,
        company_id=company_id,
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


def _verify(engine: VerificationEngine, claim: Claim, *evidence_refs: EvidenceRef):
    bundle = EvidenceBundle.classify(claim, tuple(evidence_refs))
    result = engine.verify(claim, bundle, now=NOW)
    return bundle, result


class DefinitiveVerificationAccessorTests(TestCase):
    """1-4: is_definitively_verified must be True only for VERIFIED."""

    def setUp(self) -> None:
        self.engine = VerificationEngine()

    def test_verified_is_definitively_verified(self) -> None:
        claim = _claim(text="Apple filed its annual report")
        evidence = _evidence(claim_type=ClaimType.FACTUAL, snippet=claim.text)
        _, result = _verify(self.engine, claim, evidence)
        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertTrue(result.is_definitively_verified)
        self.assertTrue(result.is_verified)

    def test_partially_verified_is_not_definitively_verified(self) -> None:
        claim = _claim(text="Apple filed its annual report")
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet=claim.text,
            authority_tier=AuthorityTier.TIER_4_GENERAL_WEB,
        )
        strict_engine = VerificationEngine(
            min_confidence_for_verified=Decimal("0.9"),
            min_confidence_for_partially_verified=Decimal("0.4"),
        )
        _, result = _verify(strict_engine, claim, evidence)
        self.assertEqual(result.status, VerificationStatus.PARTIALLY_VERIFIED)
        self.assertFalse(result.is_definitively_verified)
        # is_verified is kept unchanged for backward compatibility -- it still
        # includes PARTIALLY_VERIFIED. The new accessor is what call sites that
        # need "definitive only" must use instead.
        self.assertTrue(result.is_verified)

    def test_contradicted_is_not_definitively_verified(self) -> None:
        claim = _claim(
            claim_type=ClaimType.NUMERIC,
            text="Revenue was reported",
            expected_value="100",
            expected_unit="million USD",
            expected_currency="USD",
        )
        evidence = _evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=claim.text,
            extracted_value="150",
            extracted_unit="million USD",
            extracted_currency="USD",
        )
        _, result = _verify(self.engine, claim, evidence)
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertFalse(result.is_definitively_verified)
        self.assertFalse(result.is_verified)

    def test_ambiguous_evidence_status_is_not_definitively_verified(self) -> None:
        """The F02 'NEUTRAL' EvidenceBundle classification (ambiguous polarity,
        e.g. hedged wording) resolves to VerificationStatus.UNVERIFIABLE at the
        engine level -- there is no separate 'NEUTRAL' VerificationStatus value.
        This test confirms is_definitively_verified is False for that resulting
        status."""
        claim = _claim(text="Apple acquired ExampleCorp")
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple allegedly acquired ExampleCorp according to sources",
        )
        bundle = EvidenceBundle.classify(claim, (evidence,))
        self.assertIn(evidence, bundle.neutral)
        result = self.engine.verify(claim, bundle, now=NOW)
        self.assertEqual(result.status, VerificationStatus.UNVERIFIABLE)
        self.assertFalse(result.is_definitively_verified)
        self.assertFalse(result.is_verified)

    def test_conflicting_and_stale_are_not_definitively_verified(self) -> None:
        """Regression guard for the remaining status values not explicitly
        listed in the task but covered by is_definitively_verified's contract."""
        claim = _claim(
            claim_type=ClaimType.NUMERIC,
            text="Revenue was reported",
            expected_value="100",
            expected_unit="million USD",
            expected_currency="USD",
        )
        supporting = _evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=claim.text,
            extracted_value="100",
            extracted_unit="million USD",
            extracted_currency="USD",
            evidence_id="ev-supporting",
        )
        contradicting = _evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=claim.text,
            extracted_value="150",
            extracted_unit="million USD",
            extracted_currency="USD",
            evidence_id="ev-contradicting",
        )
        _, conflicting_result = _verify(self.engine, claim, supporting, contradicting)
        self.assertEqual(conflicting_result.status, VerificationStatus.CONFLICTING)
        self.assertFalse(conflicting_result.is_definitively_verified)

        stale_claim = _claim(
            claim_type=ClaimType.NUMERIC,
            text="Revenue was reported",
            expected_value="100",
            expected_unit="million USD",
            expected_currency="USD",
        )
        old = datetime(2020, 1, 1, tzinfo=UTC)
        stale_evidence = _evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=stale_claim.text,
            extracted_value="100",
            extracted_unit="million USD",
            extracted_currency="USD",
        )
        object.__setattr__(stale_evidence, "as_of", old)
        object.__setattr__(stale_evidence, "retrieved_at", old)
        _, stale_result = _verify(self.engine, stale_claim, stale_evidence)
        self.assertEqual(stale_result.status, VerificationStatus.STALE)
        self.assertFalse(stale_result.is_definitively_verified)


class CriticLoopSemanticsTests(TestCase):
    """5-6, and the low-authority keyword-only scenario: the critic loop must
    stop only for definitive verification, and must keep researching partial
    evidence -- including a low-authority, keyword-overlap-only match that
    happens to clear the PARTIALLY_VERIFIED confidence band."""

    def test_critic_stops_only_for_definitively_verified(self) -> None:
        engine = VerificationEngine()
        claim = _claim(text="Apple filed its annual report")
        evidence = _evidence(claim_type=ClaimType.FACTUAL, snippet=claim.text)
        _, result = _verify(engine, claim, evidence)
        self.assertTrue(result.is_definitively_verified)

        assessment = engine.assess_critic(result, attempts_used=0, max_attempts=2)
        self.assertEqual(assessment.status, CriticAssessmentStatus.SUFFICIENT_EVIDENCE)

    def test_critic_continues_for_partially_verified(self) -> None:
        """The critic loop must NOT stop merely because evidence is
        PARTIALLY_VERIFIED -- this is the behavior this task changes."""
        claim = _claim(text="Apple filed its annual report")
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet=claim.text,
            authority_tier=AuthorityTier.TIER_4_GENERAL_WEB,
        )
        strict_engine = VerificationEngine(
            min_confidence_for_verified=Decimal("0.9"),
            min_confidence_for_partially_verified=Decimal("0.4"),
        )
        _, result = _verify(strict_engine, claim, evidence)
        self.assertEqual(result.status, VerificationStatus.PARTIALLY_VERIFIED)
        self.assertFalse(result.is_definitively_verified)
        # PARTIALLY_VERIFIED must now carry a critic request to act on.
        self.assertEqual(len(result.critic_requests), 1)

        assessment = strict_engine.assess_critic(result, attempts_used=0, max_attempts=2)
        self.assertNotEqual(assessment.status, CriticAssessmentStatus.SUFFICIENT_EVIDENCE)
        self.assertEqual(assessment.status, CriticAssessmentStatus.RESEARCH_REQUIRED)
        self.assertTrue(assessment.should_research)

    def test_low_authority_keyword_only_match_cannot_stop_critic_loop(self) -> None:
        """The exact scenario from F02_VERIFICATION_SEMANTICS_REVIEW.md section 3.2:
        a Tier-4, purely lexical (bag-of-words) match with no structural
        corroboration must not be able to make the critic loop behave as if the
        claim were definitively verified."""
        claim = _claim(text="Apple acquired ExampleCorp")
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple acquired ExampleCorp",
            authority_tier=AuthorityTier.TIER_4_GENERAL_WEB,
        )
        strict_engine = VerificationEngine(
            min_confidence_for_verified=Decimal("0.95"),
            min_confidence_for_partially_verified=Decimal("0.1"),
        )
        _, result = _verify(strict_engine, claim, evidence)
        self.assertIn(
            result.status,
            {VerificationStatus.PARTIALLY_VERIFIED, VerificationStatus.UNVERIFIABLE},
        )
        self.assertFalse(result.is_definitively_verified)
        assessment = strict_engine.assess_critic(result, attempts_used=0, max_attempts=2)
        self.assertNotEqual(assessment.status, CriticAssessmentStatus.SUFFICIENT_EVIDENCE)

    def test_attempts_exhausted_for_partial_when_budget_spent(self) -> None:
        """Regression guard: once the attempt budget is spent, a still-partial
        result correctly reports ATTEMPTS_EXHAUSTED rather than erroring, now
        that PARTIALLY_VERIFIED always carries a critic_request to reach this
        branch legitimately."""
        claim = _claim(text="Apple filed its annual report")
        evidence = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet=claim.text,
            authority_tier=AuthorityTier.TIER_4_GENERAL_WEB,
        )
        strict_engine = VerificationEngine(
            min_confidence_for_verified=Decimal("0.9"),
            min_confidence_for_partially_verified=Decimal("0.4"),
        )
        _, result = _verify(strict_engine, claim, evidence)
        assessment = strict_engine.assess_critic(result, attempts_used=2, max_attempts=2)
        self.assertEqual(assessment.status, CriticAssessmentStatus.ATTEMPTS_EXHAUSTED)


class ContractsEvidenceExistenceUnaffectedTests(TestCase):
    """7-8: contracts.py's evidence-existence checks must be unaffected by the
    new accessor -- they were never using is_verified and must not be migrated
    to is_definitively_verified, since they answer a different question ("does
    supporting evidence exist"), not "is this definitive"."""

    def _company_and_ids(self) -> tuple[CompanyIdentity, str, str]:
        company = _company("Apple")
        security = company.securities[0]
        return company, security.security_id.as_text(), security.listings[0].listing_id.as_text()

    @staticmethod
    def _partially_verified_bundle_and_result(
        claim: Claim,
    ) -> tuple[EvidenceBundle, VerificationResult]:
        """Build a genuinely PARTIALLY_VERIFIED result under the DEFAULT engine
        (VerifiedClaimInput recomputes with a fresh default-constructed engine,
        so a custom-threshold engine cannot be used here -- see
        F02_SEMANTICS_IMPLEMENTATION_REPORT.md for why). A Tier-4 supporting
        match plus one unrelated (type-mismatched, therefore neutral) evidence
        ref lowers the consistency component below the VERIFIED threshold
        without needing custom thresholds.
        """
        supporting = _evidence(
            claim_type=ClaimType.FACTUAL,
            snippet=claim.text,
            authority_tier=AuthorityTier.TIER_4_GENERAL_WEB,
            evidence_id="ev-supporting",
        )
        neutral = _evidence(
            claim_type=ClaimType.NUMERIC,  # type mismatch vs. FACTUAL claim -> neutral
            snippet="unrelated",
            extracted_value=Decimal("1"),
            evidence_id="ev-neutral",
        )
        engine = VerificationEngine()
        bundle = EvidenceBundle.classify(claim, (supporting, neutral))
        verification = engine.verify(claim, bundle, now=NOW)
        return bundle, verification

    def test_partially_verified_still_requires_supporting_evidence(self) -> None:
        """VerifiedClaimInput.__post_init__ must still raise when a
        PARTIALLY_VERIFIED status is paired with no supporting evidence --
        unchanged behavior, proves this check was left alone."""
        company, security_id, listing_id = self._company_and_ids()
        claim = _claim(
            text="Apple filed its annual report",
            company_id=company.company_id.as_text(),
        )
        _, verification = self._partially_verified_bundle_and_result(claim)
        self.assertEqual(verification.status, VerificationStatus.PARTIALLY_VERIFIED)

        empty_bundle = EvidenceBundle.classify(claim, ())
        from dataclasses import replace

        mismatched = replace(verification, evidence_bundle_id=empty_bundle.claim_id)
        with self.assertRaises(ValueError):
            VerifiedClaimInput(
                claim=claim,
                evidence_bundle=empty_bundle,
                verification=mismatched,
                section=ResearchSectionType.COMPANY_OVERVIEW,
                security_id=security_id,
                listing_id=listing_id,
            )

    def test_verified_claim_gate_still_cites_partially_verified_supporting_evidence(
        self,
    ) -> None:
        """_citation_evidence must still return supporting refs for
        PARTIALLY_VERIFIED -- proves this caller's 'evidence exists to cite'
        need is unaffected by the accessor split."""
        company, security_id, listing_id = self._company_and_ids()
        claim = _claim(
            text="Apple filed its annual report",
            company_id=company.company_id.as_text(),
        )
        bundle, verification = self._partially_verified_bundle_and_result(claim)
        self.assertEqual(verification.status, VerificationStatus.PARTIALLY_VERIFIED)

        item = VerifiedClaimInput(
            claim=claim,
            evidence_bundle=bundle,
            verification=verification,
            section=ResearchSectionType.COMPANY_OVERVIEW,
            security_id=security_id,
            listing_id=listing_id,
        )
        gate = VerifiedClaimGate()
        gated = gate.evaluate(item, company, generated_at=NOW)
        self.assertEqual(len(gated.citations), 1)


class SynthesisReportingCompatibilityTests(TestCase):
    """9-10: API verification_status strings and synthesis disposition/text
    rendering must remain unchanged by this semantics cleanup."""

    def test_partially_verified_disposition_and_text_unchanged(self) -> None:
        company = _company("Apple")
        security = company.securities[0]
        claim = _claim(
            text="Apple filed its annual report",
            company_id=company.company_id.as_text(),
        )
        bundle, verification = (
            ContractsEvidenceExistenceUnaffectedTests._partially_verified_bundle_and_result(claim)
        )
        self.assertEqual(verification.status, VerificationStatus.PARTIALLY_VERIFIED)
        item = VerifiedClaimInput(
            claim=claim,
            evidence_bundle=bundle,
            verification=verification,
            section=ResearchSectionType.COMPANY_OVERVIEW,
            security_id=security.security_id.as_text(),
            listing_id=security.listings[0].listing_id.as_text(),
        )
        gated = VerifiedClaimGate().evaluate(item, company, generated_at=NOW)
        self.assertEqual(gated.claim.disposition, ClaimDisposition.QUALIFIED)
        self.assertEqual(
            gated.claim.rendered_text,
            "Partially verified: Apple filed its annual report",
        )
        self.assertEqual(gated.claim.verification_status, VerificationStatus.PARTIALLY_VERIFIED)
