"""Phase 8 Prompt 3 acceptance audit and verification contract freeze.

Frozen Phase 8 acceptance:
- material claims retain verification and confidence context;
- confidence factors are explainable and authority-aware;
- conflicts, stale evidence, and unsupported claims remain visible;
- critic requests are targeted and bounded;
- research-memory summaries are not silently promoted to evidence;
- Phase 9 synthesis and presentation remain outside this contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import TestCase

from financial_intelligence.application.verification_contracts import VerifyClaimQuery
from financial_intelligence.application.verify_claims import VerifyClaimUseCase
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.data_origin import DataOrigin as SharedDataOrigin
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.verification.claim import Claim, ClaimId, ClaimType
from financial_intelligence.domain.verification.engine import VerificationEngine
from financial_intelligence.domain.verification.evidence import (
    AuthorityTier,
    DataOrigin,
    EvidenceBundle,
    EvidenceRef,
)
from financial_intelligence.domain.verification.result import (
    ConfidenceFactor,
    CriticAssessmentStatus,
    CriticRequest,
    VerificationStatus,
)


class Phase8VerificationContractTests(TestCase):
    """Freeze the owner-approved deterministic Phase 8 foundation."""

    def setUp(self) -> None:
        self.now = datetime(2025, 1, 15, tzinfo=UTC)
        self.engine = VerificationEngine()

    def _claim(
        self,
        *,
        claim_type: ClaimType = ClaimType.FACTUAL,
        expected_value: str | Decimal | datetime | None = "filed",
        expected_unit: str | None = None,
        expected_currency: str | None = None,
        expected_period: str | None = None,
    ) -> Claim:
        return Claim(
            claim_id=ClaimId.new(),
            claim_type=claim_type,
            text="Company filed the annual report",
            company_id="company-1",
            research_run_id="run-1",
            expected_value=expected_value,
            expected_unit=expected_unit,
            expected_currency=expected_currency,
            expected_period=expected_period,
            created_at=self.now,
        )

    def _evidence(
        self,
        *,
        evidence_id: str,
        claim_type: ClaimType = ClaimType.FACTUAL,
        value: str | Decimal | datetime | None = "filed",
        authority: AuthorityTier = AuthorityTier.TIER_1_AUTHORITATIVE,
        retrieved_at: datetime | None = None,
        as_of: datetime | None = None,
        unit: str | None = None,
        currency: str | None = None,
        period: str | None = None,
        snippet: str = "Company filed the annual report",
        url: str | None = "https://example.com/evidence",
    ) -> EvidenceRef:
        return EvidenceRef(
            evidence_id=evidence_id,
            source_id=f"source-{evidence_id}",
            authority_tier=authority,
            data_origin=DataOrigin.FIXTURE,
            claim_type=claim_type.value,
            extracted_value=value,
            extracted_unit=unit,
            extracted_currency=currency,
            extracted_period=period,
            as_of=as_of,
            retrieved_at=retrieved_at or self.now,
            raw_snippet=snippet,
            url=url,
        )

    def _verify(self, claim: Claim, *refs: EvidenceRef):
        bundle = EvidenceBundle.classify(claim, tuple(refs))
        return bundle, self.engine.verify(claim, bundle, now=self.now)

    def test_application_missing_evidence_remains_unverifiable(self) -> None:
        claim = self._claim()

        operation = VerifyClaimUseCase(self.engine).execute(
            VerifyClaimQuery(claim=claim, evidence_refs=())
        )

        self.assertEqual(operation.status, "ok")
        self.assertIsNotNone(operation.verification)
        assert operation.verification is not None
        self.assertEqual(operation.verification.status, VerificationStatus.UNVERIFIABLE)
        self.assertFalse(operation.verification.is_verified)

    def test_bundle_claim_identity_mismatch_is_rejected(self) -> None:
        claim = self._claim()
        bundle = EvidenceBundle(
            claim_id=ClaimId.new().as_text(),
            evidence_refs=(self._evidence(evidence_id="ev-1"),),
        )

        with self.assertRaisesRegex(ValueError, "claim_id"):
            self.engine.verify(claim, bundle, now=self.now)

    def test_duplicate_evidence_identity_is_rejected(self) -> None:
        claim = self._claim()
        first = self._evidence(evidence_id="duplicate")
        second = self._evidence(evidence_id="duplicate")

        with self.assertRaisesRegex(ValueError, "duplicate evidence_id"):
            EvidenceBundle.classify(claim, (first, second))

    def test_required_numeric_metadata_must_be_explicit(self) -> None:
        claim = self._claim(
            claim_type=ClaimType.NUMERIC,
            expected_value=Decimal("100"),
            expected_unit="million",
            expected_currency="USD",
            expected_period="FY2024",
        )
        evidence = self._evidence(
            evidence_id="ev-numeric",
            claim_type=ClaimType.NUMERIC,
            value=Decimal("100"),
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.supporting, ())
        self.assertEqual(bundle.contradicting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertEqual(result.confidence_score, Decimal("0"))

    def test_date_claim_matches_timezone_aware_datetime(self) -> None:
        expected = datetime(2024, 9, 30, tzinfo=UTC)
        claim = self._claim(claim_type=ClaimType.DATE, expected_value=expected)
        evidence = self._evidence(
            evidence_id="ev-date",
            claim_type=ClaimType.DATE,
            value=expected,
        )

        bundle, result = self._verify(claim, evidence)

        self.assertEqual(bundle.supporting, (evidence,))
        self.assertEqual(result.status, VerificationStatus.VERIFIED)

    def test_future_retrieval_timestamp_cannot_verify_claim(self) -> None:
        claim = self._claim()
        future = self._evidence(
            evidence_id="ev-future",
            retrieved_at=self.now + timedelta(days=1),
        )

        _, result = self._verify(claim, future)

        self.assertEqual(result.status, VerificationStatus.UNVERIFIABLE)
        self.assertEqual(result.confidence_score, Decimal("0"))
        self.assertNotIn(ConfidenceFactor.EVIDENCE_RECENCY, result.confidence_factors)

    def test_fresh_neutral_evidence_cannot_mask_stale_support(self) -> None:
        claim = self._claim()
        stale_support = self._evidence(
            evidence_id="ev-stale",
            retrieved_at=self.now - timedelta(days=500),
            as_of=self.now - timedelta(days=500),
        )
        fresh_neutral = self._evidence(
            evidence_id="ev-neutral",
            claim_type=ClaimType.DATE,
            retrieved_at=self.now,
        )

        _, result = self._verify(claim, stale_support, fresh_neutral)

        self.assertEqual(result.status, VerificationStatus.STALE)

    def test_cross_source_agreement_requires_supporting_sources(self) -> None:
        claim = self._claim()
        supporting = self._evidence(evidence_id="ev-support")
        neutral = self._evidence(
            evidence_id="ev-neutral",
            claim_type=ClaimType.DATE,
            authority=AuthorityTier.TIER_2_STRUCTURED_FINANCIAL,
        )

        _, result = self._verify(claim, supporting, neutral)

        self.assertNotIn(ConfidenceFactor.CROSS_SOURCE_AGREEMENT, result.confidence_factors)

    def test_source_authority_increases_confidence_monotonically(self) -> None:
        claim = self._claim()
        general = self._evidence(
            evidence_id="ev-general",
            authority=AuthorityTier.TIER_4_GENERAL_WEB,
        )
        authoritative = self._evidence(
            evidence_id="ev-authoritative",
            authority=AuthorityTier.TIER_1_AUTHORITATIVE,
        )

        _, general_result = self._verify(claim, general)
        _, authoritative_result = self._verify(claim, authoritative)

        self.assertGreater(
            authoritative_result.confidence_score,
            general_result.confidence_score,
        )

    def test_confidence_result_exposes_policy_version_and_factors(self) -> None:
        claim = self._claim()
        _, result = self._verify(claim, self._evidence(evidence_id="ev-versioned"))

        payload = result.to_dict()

        self.assertEqual(payload["score_version"], "phase8-deterministic-v1")
        self.assertTrue(payload["confidence_factors"])

    def test_contradicted_result_consistently_needs_critic(self) -> None:
        claim = self._claim(expected_value="filed")
        contradiction = self._evidence(evidence_id="ev-refute", value="not-filed")

        _, result = self._verify(claim, contradiction)

        self.assertEqual(result.status, VerificationStatus.CONTRADICTED)
        self.assertTrue(result.needs_critic)
        self.assertEqual(len(result.critic_requests), 1)

    def test_critic_request_rejects_unbounded_values(self) -> None:
        arguments = {
            "request_id": "request-1",
            "claim_id": "claim-1",
            "reason": "More evidence is required",
            "suggested_capability": "financials",
            "suggested_query": "Find authoritative evidence",
        }

        with self.assertRaisesRegex(ValueError, "priority"):
            CriticRequest(**arguments, priority=0)
        with self.assertRaisesRegex(ValueError, "max_attempts"):
            CriticRequest(**arguments, max_attempts=0)

    def test_critic_assessment_converges_on_sufficient_evidence(self) -> None:
        claim = self._claim()
        _, result = self._verify(claim, self._evidence(evidence_id="ev-verified"))

        assessment = self.engine.assess_critic(result, attempts_used=0, max_attempts=2)

        self.assertEqual(assessment.status, CriticAssessmentStatus.SUFFICIENT_EVIDENCE)
        self.assertFalse(assessment.should_research)
        self.assertEqual(assessment.requests, ())

    def test_critic_assessment_stops_when_attempts_are_exhausted(self) -> None:
        claim = self._claim()
        _, result = self._verify(claim)

        initial = self.engine.assess_critic(result, attempts_used=0, max_attempts=2)
        exhausted = self.engine.assess_critic(result, attempts_used=2, max_attempts=2)

        self.assertEqual(initial.status, CriticAssessmentStatus.RESEARCH_REQUIRED)
        self.assertTrue(initial.should_research)
        self.assertEqual(initial.remaining_attempts, 2)
        self.assertEqual(len(initial.requests), 1)
        self.assertEqual(exhausted.status, CriticAssessmentStatus.ATTEMPTS_EXHAUSTED)
        self.assertFalse(exhausted.should_research)
        self.assertEqual(exhausted.remaining_attempts, 0)
        self.assertEqual(exhausted.requests, ())

    def test_engine_rejects_invalid_policy_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_evidence_age_days"):
            VerificationEngine(max_evidence_age_days=-1)
        with self.assertRaisesRegex(ValueError, "confidence thresholds"):
            VerificationEngine(
                min_confidence_for_verified=Decimal("0.4"),
                min_confidence_for_partially_verified=Decimal("0.7"),
            )

    def test_invalid_evidence_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "url"):
            self._evidence(evidence_id="ev-url", url="file:///etc/passwd")

    def test_workflow_memory_is_not_implicitly_upgraded_to_evidence(self) -> None:
        self.assertNotIn("verify_workflow_claims", AppContainer.__dataclass_fields__)

    def test_verification_reuses_canonical_provenance_vocabularies(self) -> None:
        self.assertIs(DataOrigin, SharedDataOrigin)
        self.assertIs(AuthorityTier, SourceAuthorityTier)
