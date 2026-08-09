"""Deterministic verification engine — Phase 8 Prompt 1 foundation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from financial_intelligence.domain.verification.claim import Claim, ClaimType
from financial_intelligence.domain.verification.evidence import (
    AuthorityTier,
    EvidenceBundle,
)
from financial_intelligence.domain.verification.result import (
    ConfidenceFactor,
    ContradictionRecord,
    CriticAssessment,
    CriticAssessmentStatus,
    CriticRequest,
    VerificationResult,
    VerificationStatus,
)


@dataclass(frozen=True, slots=True)
class VerificationEngine:
    """Deterministic claim verification engine.

    No LLM calls. All logic is code-derived and reproducible.
    """

    # Configuration
    max_evidence_age_days: int = 365  # Evidence older than this is stale
    min_confidence_for_verified: Decimal = Decimal("0.7")
    min_confidence_for_partially_verified: Decimal = Decimal("0.4")
    score_version: str = "phase8-deterministic-v1"
    tier_weights: dict[AuthorityTier, Decimal] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.max_evidence_age_days < 0:
            raise ValueError("max_evidence_age_days must be non-negative")
        if not self.score_version.strip() or len(self.score_version) > 128:
            raise ValueError("score_version empty or exceeds bounds")
        if not (
            Decimal("0")
            <= self.min_confidence_for_partially_verified
            <= self.min_confidence_for_verified
            <= Decimal("1")
        ):
            raise ValueError("confidence thresholds must be ordered within 0 and 1")
        if self.tier_weights is None:
            object.__setattr__(
                self,
                "tier_weights",
                {
                    AuthorityTier.TIER_1_AUTHORITATIVE: Decimal("1.0"),
                    AuthorityTier.TIER_2_STRUCTURED_FINANCIAL: Decimal("0.7"),
                    AuthorityTier.TIER_3_REPUTABLE_NEWS: Decimal("0.5"),
                    AuthorityTier.TIER_4_GENERAL_WEB: Decimal("0.2"),
                },
            )
        elif not self.tier_weights:
            raise ValueError("tier_weights must not be empty")
        if any(not Decimal("0") <= weight <= Decimal("1") for weight in self.tier_weights.values()):
            raise ValueError("tier_weights must be between 0 and 1")

    def verify(
        self,
        claim: Claim,
        evidence_bundle: EvidenceBundle,
        now: datetime | None = None,
    ) -> VerificationResult:
        """Verify a claim against its evidence bundle."""
        if now is None:
            now = datetime.now(UTC)
        elif now.tzinfo is None:
            raise ValueError("verification time must be timezone-aware")
        if evidence_bundle.claim_id != claim.claim_id.as_text():
            raise ValueError("evidence bundle claim_id does not match claim")

        # Classify evidence
        bundle = EvidenceBundle.classify(claim, evidence_bundle.evidence_refs)
        future_ids = {ref.evidence_id for ref in bundle.evidence_refs if ref.retrieved_at > now}
        if future_ids:
            bundle = EvidenceBundle(
                claim_id=bundle.claim_id,
                evidence_refs=bundle.evidence_refs,
                supporting=tuple(
                    ref for ref in bundle.supporting if ref.evidence_id not in future_ids
                ),
                contradicting=tuple(
                    ref for ref in bundle.contradicting if ref.evidence_id not in future_ids
                ),
                neutral=tuple(
                    ref
                    for ref in bundle.evidence_refs
                    if ref.evidence_id in future_ids or ref in bundle.neutral
                ),
            )

        # Compute confidence
        confidence, factors = self._compute_confidence(claim, bundle, now)

        # Determine status
        status = self._determine_status(claim, bundle, confidence, now)

        # Detect contradictions
        contradictions = self._detect_contradictions(claim, bundle)

        # Generate critic requests if needed
        critic_requests = self._generate_critic_requests(claim, bundle, status)

        # Build rationale
        rationale = self._build_rationale(claim, bundle, confidence, factors, status)

        return VerificationResult(
            claim_id=claim.claim_id.as_text(),
            status=status,
            confidence_score=confidence,
            confidence_factors=factors,
            evidence_bundle_id=bundle.claim_id,
            contradictions=contradictions,
            critic_requests=critic_requests,
            rationale=rationale,
            score_version=self.score_version,
            verified_at=now,
        )

    def assess_critic(
        self,
        result: VerificationResult,
        *,
        attempts_used: int,
        max_attempts: int = 2,
    ) -> CriticAssessment:
        """Return a deterministic bounded stop/research decision."""
        if not 1 <= max_attempts <= 10:
            raise ValueError("critic max_attempts must be between 1 and 10")
        if not 0 <= attempts_used <= max_attempts:
            raise ValueError("critic attempts_used is outside the budget")
        if result.is_verified:
            return CriticAssessment(
                claim_id=result.claim_id,
                status=CriticAssessmentStatus.SUFFICIENT_EVIDENCE,
                attempts_used=attempts_used,
                max_attempts=max_attempts,
            )
        if attempts_used == max_attempts:
            return CriticAssessment(
                claim_id=result.claim_id,
                status=CriticAssessmentStatus.ATTEMPTS_EXHAUSTED,
                attempts_used=attempts_used,
                max_attempts=max_attempts,
            )
        requests = tuple(
            replace(request, max_attempts=max_attempts) for request in result.critic_requests
        )
        if not requests:
            raise ValueError("non-terminal verification result has no critic request")
        return CriticAssessment(
            claim_id=result.claim_id,
            status=CriticAssessmentStatus.RESEARCH_REQUIRED,
            attempts_used=attempts_used,
            max_attempts=max_attempts,
            requests=requests,
        )

    def _compute_confidence(
        self,
        claim: Claim,
        bundle: EvidenceBundle,
        now: datetime,
    ) -> tuple[Decimal, tuple[ConfidenceFactor, ...]]:
        """Compute confidence score and contributing factors."""
        if not bundle.supporting:
            return Decimal("0"), ()

        factors = []
        score_components = []

        # 1. Source authority factor (based on supporting evidence)
        max_tier_weight = max(
            self.tier_weights.get(ref.authority_tier, Decimal("0")) for ref in bundle.supporting
        )
        score_components.append(max_tier_weight)
        if max_tier_weight >= Decimal("0.7"):
            factors.append(ConfidenceFactor.SOURCE_AUTHORITY)

        # 2. Evidence recency factor (based on supporting evidence)
        recent_count = 0
        for ref in bundle.supporting:
            as_of_age = (now - ref.as_of).days if ref.as_of else None
            retrieved_age = (now - ref.retrieved_at).days
            as_of_recent = as_of_age is not None and 0 <= as_of_age <= self.max_evidence_age_days
            retrieved_recent = 0 <= retrieved_age <= self.max_evidence_age_days
            if as_of_recent or retrieved_recent:
                recent_count += 1

        recency_ratio = Decimal(str(recent_count)) / Decimal(str(len(bundle.supporting)))
        score_components.append(recency_ratio * Decimal("0.3"))
        if recent_count > 0:
            factors.append(ConfidenceFactor.EVIDENCE_RECENCY)

        # 3. Evidence consistency (supporting vs contradicting)
        total = len(bundle.evidence_refs)
        supporting = len(bundle.supporting)
        contradicting = len(bundle.contradicting)

        if total > 0:
            consistency = Decimal(str(supporting)) / Decimal(str(total))
            if contradicting == 0:
                score_components.append(consistency * Decimal("0.3"))
                factors.append(ConfidenceFactor.NO_CONTRADICTIONS)
            else:
                score_components.append(consistency * Decimal("0.1"))

        # 4. Cross-source agreement (supporting evidence only)
        tier_1_sources = {
            ref.source_id
            for ref in bundle.supporting
            if ref.authority_tier == AuthorityTier.TIER_1_AUTHORITATIVE
        }
        tier_2_sources = {
            ref.source_id
            for ref in bundle.supporting
            if ref.authority_tier == AuthorityTier.TIER_2_STRUCTURED_FINANCIAL
        }
        if tier_1_sources and tier_2_sources:
            factors.append(ConfidenceFactor.CROSS_SOURCE_AGREEMENT)
            score_components.append(Decimal("0.1"))

        # 5. Evidence completeness (numeric claims)
        if claim.claim_type == ClaimType.NUMERIC:
            complete = all(
                ref.extracted_value is not None
                and (ref.extracted_unit or claim.expected_unit)
                and (ref.extracted_currency or claim.expected_currency)
                for ref in bundle.supporting
            )
            if complete and bundle.supporting:
                factors.append(ConfidenceFactor.EVIDENCE_COMPLETENESS)
                score_components.append(Decimal("0.1"))

        # 6. Explicit period match
        if claim.expected_period:
            period_matches = any(
                ref.extracted_period == claim.expected_period for ref in bundle.supporting
            )
            if period_matches:
                factors.append(ConfidenceFactor.EXPLICIT_PERIOD_MATCH)
                score_components.append(Decimal("0.05"))

        # 7. Explicit unit/currency match
        if claim.expected_unit or claim.expected_currency:
            unit_matches = all(
                (not claim.expected_unit or ref.extracted_unit == claim.expected_unit)
                and (
                    not claim.expected_currency or ref.extracted_currency == claim.expected_currency
                )
                for ref in bundle.supporting
            )
            if unit_matches and bundle.supporting:
                factors.append(ConfidenceFactor.EXPLICIT_UNIT_CURRENCY_MATCH)
                score_components.append(Decimal("0.05"))

        # Sum and clamp
        final_score = sum(score_components, Decimal("0"))
        final_score = min(max(final_score, Decimal("0")), Decimal("1"))

        return final_score, tuple(factors)

    def _determine_status(
        self,
        claim: Claim,
        bundle: EvidenceBundle,
        confidence: Decimal,
        now: datetime,
    ) -> VerificationStatus:
        """Determine verification status from confidence and evidence."""
        if not bundle.evidence_refs:
            return VerificationStatus.UNVERIFIABLE

        has_supporting = len(bundle.supporting) > 0
        has_contradicting = len(bundle.contradicting) > 0

        if has_supporting and has_contradicting:
            return VerificationStatus.CONFLICTING

        if has_supporting:
            is_stale = not any(
                0 <= (now - (ref.as_of or ref.retrieved_at)).days <= self.max_evidence_age_days
                for ref in bundle.supporting
            )
            if confidence >= self.min_confidence_for_verified:
                return VerificationStatus.STALE if is_stale else VerificationStatus.VERIFIED
            if confidence >= self.min_confidence_for_partially_verified:
                return (
                    VerificationStatus.STALE if is_stale else VerificationStatus.PARTIALLY_VERIFIED
                )
            return VerificationStatus.STALE if is_stale else VerificationStatus.UNVERIFIABLE

        if has_contradicting:
            return VerificationStatus.CONTRADICTED

        return VerificationStatus.UNVERIFIABLE

    def _detect_contradictions(
        self,
        claim: Claim,
        bundle: EvidenceBundle,
    ) -> tuple[ContradictionRecord, ...]:
        """Detect and record contradictions."""
        if not bundle.supporting or not bundle.contradicting:
            return ()

        contradictions = []
        for s_ref in bundle.supporting:
            for c_ref in bundle.contradicting:
                # Check if they're actually contradicting on the same aspect
                if (
                    s_ref.claim_type == c_ref.claim_type
                    and s_ref.extracted_value is not None
                    and c_ref.extracted_value is not None
                    and s_ref.extracted_value != c_ref.extracted_value
                ):
                    contradictions.append(
                        ContradictionRecord(
                            claim_id=claim.claim_id.as_text(),
                            supporting_refs=(s_ref.evidence_id,),
                            contradicting_refs=(c_ref.evidence_id,),
                            description=(
                                f"Evidence {s_ref.evidence_id} ({s_ref.source_id}) claims "
                                f"{s_ref.extracted_value} but {c_ref.evidence_id} "
                                f"({c_ref.source_id}) claims {c_ref.extracted_value} "
                                f"for {claim.claim_type.value} claim"
                            ),
                        )
                    )

        return tuple(contradictions)

    def _generate_critic_requests(
        self,
        claim: Claim,
        bundle: EvidenceBundle,
        status: VerificationStatus,
    ) -> tuple[CriticRequest, ...]:
        """Generate bounded targeted re-research requests."""
        if status in {VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED}:
            return ()

        requests = []

        if status == VerificationStatus.UNVERIFIABLE:
            # Suggest gathering more evidence
            capability = self._claim_type_to_capability(claim.claim_type)
            requests.append(
                CriticRequest.new(
                    claim_id=claim.claim_id.as_text(),
                    reason=f"Insufficient evidence to verify {claim.claim_type.value} claim",
                    capability=capability,
                    query=f"Find evidence for: {claim.text}",
                )
            )

        elif status == VerificationStatus.CONFLICTING:
            # Suggest resolving contradiction
            capability = self._claim_type_to_capability(claim.claim_type)
            requests.append(
                CriticRequest.new(
                    claim_id=claim.claim_id.as_text(),
                    reason=(
                        f"Conflicting evidence found for {claim.claim_type.value} "
                        f"claim; need authoritative source"
                    ),
                    capability=capability,
                    query=f"Resolve contradiction for: {claim.text}",
                )
            )

        elif status == VerificationStatus.STALE:
            # Suggest refreshing evidence
            capability = self._claim_type_to_capability(claim.claim_type)
            requests.append(
                CriticRequest.new(
                    claim_id=claim.claim_id.as_text(),
                    reason=(
                        f"Evidence is older than {self.max_evidence_age_days} days; need fresh data"
                    ),
                    capability=capability,
                    query=f"Find recent data for: {claim.text}",
                )
            )

        elif status == VerificationStatus.CONTRADICTED:
            # Suggest verifying with higher authority
            capability = self._claim_type_to_capability(claim.claim_type)
            requests.append(
                CriticRequest.new(
                    claim_id=claim.claim_id.as_text(),
                    reason=(
                        f"Evidence contradicts {claim.claim_type.value} claim; "
                        f"verify with authoritative source"
                    ),
                    capability=capability,
                    query=f"Verify with authoritative source: {claim.text}",
                )
            )

        return tuple(requests)

    def _claim_type_to_capability(self, claim_type: ClaimType) -> str:
        """Map claim type to capability name."""
        mapping = {
            ClaimType.FACTUAL: "general",
            ClaimType.NUMERIC: "financials",
            ClaimType.DATE: "general",
            ClaimType.SOURCE_AUTHORITY: "general",
        }
        return mapping.get(claim_type, "general")

    def _build_rationale(
        self,
        claim: Claim,
        bundle: EvidenceBundle,
        confidence: Decimal,
        factors: tuple[ConfidenceFactor, ...],
        status: VerificationStatus,
    ) -> str:
        """Build human-readable rationale."""
        parts = [
            f"Evaluated claim '{claim.text[:100]}...' (type: {claim.claim_type.value})",
            f"Status: {status.value}",
            f"Confidence: {confidence:.2f}",
            (
                f"Evidence: {len(bundle.evidence_refs)} total "
                f"({len(bundle.supporting)} supporting, "
                f"{len(bundle.contradicting)} contradicting)"
            ),
        ]

        if factors:
            parts.append(f"Factors: {', '.join(f.value for f in factors)}")

        if bundle.contradicting:
            parts.append(f"Contradictions found: {len(bundle.contradicting)}")

        return " | ".join(parts)
