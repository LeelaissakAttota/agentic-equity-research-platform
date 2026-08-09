"""Unit tests for the deterministic verification engine."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.domain.verification.claim import (
    Claim,
    ClaimId,
    ClaimType,
)
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.domain.verification.evidence import (
    AuthorityTier,
    DataOrigin,
    EvidenceBundle,
    EvidenceRef,
)
from financial_intelligence.domain.verification.result import (
    ConfidenceFactor,
    VerificationResult,
    VerificationStatus,
)


class VerificationEngineTests(TestCase):
    """Exercise verification, confidence, conflicts, and critic requests."""

    def setUp(self) -> None:
        self.engine = VerificationEngine()
        self.now = datetime(2025, 1, 15, tzinfo=UTC)
        self._evidence_index = 0

    def _claim(
        self,
        *,
        claim_type: ClaimType,
        text: str,
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
        self,
        *,
        claim_type: ClaimType,
        snippet: str,
        extracted_value: str | Decimal | datetime | None = None,
        extracted_unit: str | None = None,
        extracted_currency: str | None = None,
        extracted_period: str | None = None,
        authority_tier: AuthorityTier = AuthorityTier.TIER_1_AUTHORITATIVE,
        source_id: str = "Official",
        as_of: datetime | None = None,
        retrieved_at: datetime | None = None,
    ) -> EvidenceRef:
        self._evidence_index += 1
        return EvidenceRef(
            evidence_id=f"ev-{self._evidence_index}",
            source_id=source_id,
            authority_tier=authority_tier,
            data_origin=DataOrigin.FIXTURE,
            claim_type=claim_type.value,
            extracted_value=extracted_value,
            extracted_unit=extracted_unit,
            extracted_currency=extracted_currency,
            extracted_period=extracted_period,
            as_of=as_of if as_of is not None else self.now,
            retrieved_at=retrieved_at if retrieved_at is not None else self.now,
            raw_snippet=snippet,
            url="https://example.com/evidence",
        )

    def _verify(
        self,
        claim: Claim,
        *evidence_refs: EvidenceRef,
        engine: VerificationEngine | None = None,
        now: datetime | None = None,
    ) -> tuple[EvidenceBundle, VerificationResult]:
        bundle = EvidenceBundle.classify(claim, tuple(evidence_refs))
        verifier = engine if engine is not None else self.engine
        result = verifier.verify(claim, bundle, now=now if now is not None else self.now)
        return bundle, result

    def _numeric_claim(
        self,
        *,
        value: Decimal | None = Decimal("100"),
        unit: str | None = "million USD",
        currency: str | None = "USD",
        period: str | None = "2024",
        text: str = "Revenue was reported for the fiscal period",
    ) -> Claim:
        return self._claim(
            claim_type=ClaimType.NUMERIC,
            text=text,
            expected_value=value,
            expected_unit=unit,
            expected_currency=currency,
            expected_period=period,
        )

    def _numeric_evidence(
        self,
        claim: Claim,
        *,
        value: Decimal,
        unit: str | None = "million USD",
        currency: str | None = "USD",
        period: str | None = "2024",
    ) -> EvidenceRef:
        return self._evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=claim.text,
            extracted_value=value,
            extracted_unit=unit,
            extracted_currency=currency,
            extracted_period=period,
        )

    def test_verify_factual_claim_with_authoritative_evidence(self) -> None:
        claim = self._claim(
            claim_type=ClaimType.FACTUAL,
            text="Apple filed its annual report on 2024-10-27",
        )
        evidence = self._evidence(
            claim_type=ClaimType.FACTUAL,
            snippet="Apple filed its annual report on 2024-10-27",
            extracted_value="Apple filed its annual report on 2024-10-27",
        )

        _, result = self._verify(claim, evidence)

        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertGreaterEqual(result.confidence_score, Decimal("0.7"))
        self.assertIn(ConfidenceFactor.SOURCE_AUTHORITY, result.confidence_factors)
        self.assertIn(ConfidenceFactor.EVIDENCE_RECENCY, result.confidence_factors)
        self.assertIn(ConfidenceFactor.NO_CONTRADICTIONS, result.confidence_factors)

    def test_verify_numeric_claim_with_complete_evidence(self) -> None:
        claim = self._numeric_claim(value=Decimal("383.285"), unit="billion USD")
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("383.285"),
            unit="billion USD",
        )

        _, result = self._verify(claim, evidence)

        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertGreaterEqual(result.confidence_score, Decimal("0.8"))
        self.assertIn(ConfidenceFactor.EVIDENCE_COMPLETENESS, result.confidence_factors)
        self.assertIn(ConfidenceFactor.EXPLICIT_PERIOD_MATCH, result.confidence_factors)
        self.assertIn(
            ConfidenceFactor.EXPLICIT_UNIT_CURRENCY_MATCH,
            result.confidence_factors,
        )

    def test_detect_conflicting_evidence(self) -> None:
        claim = self._numeric_claim()
        supporting = self._numeric_evidence(claim, value=Decimal("100"))
        contradicting = self._numeric_evidence(claim, value=Decimal("150"))

        _, result = self._verify(claim, supporting, contradicting)

        self.assertEqual(result.status, VerificationStatus.CONFLICTING)
        self.assertEqual(len(result.contradictions), 1)
        self.assertIn("100", result.contradictions[0].description)
        self.assertIn("150", result.contradictions[0].description)

    def test_stale_evidence_results_in_stale_status(self) -> None:
        old = datetime(2022, 1, 1, tzinfo=UTC)
        now = datetime(2024, 1, 1, tzinfo=UTC)
        claim = self._numeric_claim(period="2021")
        evidence = self._evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=claim.text,
            extracted_value=Decimal("100"),
            extracted_unit="million USD",
            extracted_currency="USD",
            extracted_period="2021",
            as_of=old,
            retrieved_at=old,
        )

        _, result = self._verify(claim, evidence, now=now)

        self.assertEqual(result.status, VerificationStatus.STALE)
        self.assertGreater(result.confidence_score, Decimal("0"))
        self.assertNotIn(ConfidenceFactor.EVIDENCE_RECENCY, result.confidence_factors)

    def test_no_evidence_results_in_unverifiable(self) -> None:
        claim = self._claim(
            claim_type=ClaimType.FACTUAL,
            text="The company announced a new product",
        )

        bundle, result = self._verify(claim)

        self.assertEqual(bundle.evidence_refs, ())
        self.assertEqual(result.status, VerificationStatus.UNVERIFIABLE)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_evidence_classification_works_correctly(self) -> None:
        claim = self._numeric_claim()
        supporting = self._numeric_evidence(claim, value=Decimal("100"))
        contradicting = self._numeric_evidence(claim, value=Decimal("125"))
        neutral = self._evidence(
            claim_type=ClaimType.FACTUAL,
            snippet=claim.text,
            extracted_value="unrelated fact",
        )

        bundle = EvidenceBundle.classify(claim, (supporting, contradicting, neutral))

        self.assertEqual(bundle.supporting, (supporting,))
        self.assertEqual(bundle.contradicting, (contradicting,))
        self.assertEqual(bundle.neutral, (neutral,))

    def test_critic_requests_generated_for_unverifiable(self) -> None:
        claim = self._claim(
            claim_type=ClaimType.FACTUAL,
            text="The company entered a new market",
        )

        _, result = self._verify(claim)

        self.assertEqual(result.status, VerificationStatus.UNVERIFIABLE)
        self.assertEqual(len(result.critic_requests), 1)
        self.assertEqual(result.critic_requests[0].suggested_capability, "general")

    def test_critic_requests_generated_for_conflicting(self) -> None:
        claim = self._numeric_claim()
        supporting = self._numeric_evidence(claim, value=Decimal("100"))
        contradicting = self._numeric_evidence(claim, value=Decimal("150"))

        _, result = self._verify(claim, supporting, contradicting)

        self.assertEqual(result.status, VerificationStatus.CONFLICTING)
        self.assertEqual(len(result.critic_requests), 1)
        self.assertEqual(result.critic_requests[0].suggested_capability, "financials")

    def test_critic_requests_generated_for_stale(self) -> None:
        old = datetime(2021, 1, 1, tzinfo=UTC)
        claim = self._numeric_claim(period="2021")
        evidence = self._evidence(
            claim_type=ClaimType.NUMERIC,
            snippet=claim.text,
            extracted_value=Decimal("100"),
            extracted_unit="million USD",
            extracted_currency="USD",
            extracted_period="2021",
            as_of=old,
            retrieved_at=old,
        )

        _, result = self._verify(
            claim,
            evidence,
            now=datetime(2024, 1, 1, tzinfo=UTC),
        )

        self.assertEqual(result.status, VerificationStatus.STALE)
        self.assertEqual(len(result.critic_requests), 1)
        self.assertEqual(result.critic_requests[0].suggested_capability, "financials")

    def test_critic_requests_generated_for_contradicted(self) -> None:
        claim = self._numeric_claim()
        evidence = self._numeric_evidence(claim, value=Decimal("150"))

        _, result = self._verify(claim, evidence)

        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(len(result.critic_requests), 1)
        self.assertEqual(result.critic_requests[0].suggested_capability, "financials")

    def test_no_critic_requests_for_verified_or_partial(self) -> None:
        claim = self._claim(
            claim_type=ClaimType.FACTUAL,
            text="The company filed its annual report",
        )
        evidence = self._evidence(
            claim_type=ClaimType.FACTUAL,
            snippet=claim.text,
            authority_tier=AuthorityTier.TIER_4_GENERAL_WEB,
        )
        strict_engine = VerificationEngine(
            min_confidence_for_verified=Decimal("0.9"),
            min_confidence_for_partially_verified=Decimal("0.4"),
        )

        _, verified = self._verify(claim, evidence)
        _, partial = self._verify(claim, evidence, engine=strict_engine)

        self.assertEqual(verified.status, VerificationStatus.VERIFIED)
        self.assertEqual(partial.status, VerificationStatus.PARTIALLY_VERIFIED)
        self.assertEqual(verified.critic_requests, ())
        self.assertEqual(partial.critic_requests, ())

    def test_superficial_keyword_overlap_does_not_support_claim(self) -> None:
        claim = self._claim(
            claim_type=ClaimType.FACTUAL,
            text="Revenue increased during the fiscal year",
        )
        wrong_type = self._evidence(
            claim_type=ClaimType.NUMERIC,
            snippet="Revenue increased during the fiscal year",
            extracted_value=Decimal("10"),
        )

        bundle, result = self._verify(claim, wrong_type)

        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.neutral, (wrong_type,))
        self.assertEqual(result.status, VerificationStatus.UNVERIFIABLE)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_currency_mismatch_does_not_support(self) -> None:
        claim = self._numeric_claim()
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("100"),
            unit="million EUR",
            currency="EUR",
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_unit_mismatch(self) -> None:
        claim = self._numeric_claim(unit="million")
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("100"),
            unit="billion",
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_scale_mismatch(self) -> None:
        claim = self._numeric_claim(value=Decimal("100"), unit="million")
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("0.1"),
            unit="billion",
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_period_mismatch(self) -> None:
        claim = self._numeric_claim(period="2024")
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("100"),
            period="2023",
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_fiscal_year_mismatch(self) -> None:
        claim = self._numeric_claim(period="FY2024")
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("100"),
            period="FY2023",
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_percentage_vs_ratio(self) -> None:
        claim = self._numeric_claim(
            value=Decimal("20"),
            unit="percent",
            currency=None,
        )
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("0.2"),
            unit="ratio",
            currency=None,
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_negative_values(self) -> None:
        claim = self._numeric_claim(value=Decimal("-50"))
        evidence = self._numeric_evidence(claim, value=Decimal("-50"))

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertGreaterEqual(result.confidence_score, Decimal("0.8"))

    def test_numeric_claim_zero_values(self) -> None:
        claim = self._numeric_claim(value=Decimal("0"))
        evidence = self._numeric_evidence(claim, value=Decimal("0"))

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertGreaterEqual(result.confidence_score, Decimal("0.8"))

    def test_numeric_claim_missing_expected_values(self) -> None:
        claim = self._numeric_claim(value=None, unit=None, currency=None, period=None)
        evidence = self._numeric_evidence(
            claim,
            value=Decimal("100"),
            unit="million EUR",
            currency="EUR",
            period="2024",
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_numeric_claim_nan_infinity(self) -> None:
        for non_finite in (Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(non_finite=str(non_finite)):
                claim = self._numeric_claim(value=non_finite)
                evidence = self._numeric_evidence(claim, value=non_finite)

                bundle, result = self._verify(claim, evidence)

                self.assertEqual(bundle.supporting, ())
                self.assertEqual(bundle.contradicting, (evidence,))
                self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
                self.assertEqual(result.confidence_score, Decimal("0"))
