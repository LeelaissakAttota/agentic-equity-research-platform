"""Focused Phase 9 deterministic synthesis domain tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyIdentity
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.synthesis import (
    CitationSourceContext,
    ClaimDisposition,
    ConfidenceLabel,
    DeterministicSynthesisAssembler,
    LanguagePreference,
    MissingDataReason,
    OutputLanguage,
    ResearchSectionType,
    SynthesisStatus,
    VerifiedClaimGate,
    VerifiedClaimInput,
)
from financial_intelligence.domain.verification import (
    Claim,
    ClaimId,
    ClaimType,
    EvidenceBundle,
    EvidenceRef,
    VerificationEngine,
    VerificationStatus,
)
from financial_intelligence.infrastructure.company.reference_dataset import (
    build_reference_companies,
)

NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
RUN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _company(name: str) -> CompanyIdentity:
    return next(company for company in build_reference_companies() if company.display_name == name)


def _verified_input(
    *,
    company_name: str = "Apple",
    section: ResearchSectionType = ResearchSectionType.FINANCIAL_PERFORMANCE,
    value: Decimal | None = Decimal("100"),
    evidence_values: tuple[Decimal, ...] = (Decimal("100"),),
    evidence_tiers: tuple[SourceAuthorityTier, ...] | None = None,
    as_of: datetime = NOW,
    materiality: int = 1,
    security_id: str | None = None,
    listing_id: str | None = None,
    text: str | None = None,
    missing_reason: MissingDataReason | None = None,
) -> VerifiedClaimInput:
    company = _company(company_name)
    claim_text = text or f"{company.display_name} revenue was {value} billion"
    claim = Claim(
        claim_id=ClaimId.new(),
        claim_type=ClaimType.NUMERIC if value is not None else ClaimType.FACTUAL,
        text=claim_text,
        company_id=company.company_id.as_text(),
        research_run_id=RUN_ID,
        expected_value=value,
        expected_unit="billion" if value is not None else None,
        expected_currency="USD"
        if company.country.as_text() == "US" and value is not None
        else ("INR" if value is not None else None),
        expected_period="FY2026" if value is not None else None,
        expected_as_of=as_of,
        created_at=NOW,
    )
    tiers = evidence_tiers or tuple(
        SourceAuthorityTier.TIER_1_AUTHORITATIVE for _ in evidence_values
    )
    currency = claim.expected_currency
    refs = tuple(
        EvidenceRef(
            evidence_id=f"evidence-{index}",
            source_id=f"source-{index}",
            authority_tier=tiers[index - 1],
            data_origin=DataOrigin.FIXTURE,
            claim_type=claim.claim_type.value,
            extracted_value=evidence_value,
            extracted_unit=claim.expected_unit,
            extracted_currency=currency,
            extracted_period=claim.expected_period,
            as_of=as_of,
            retrieved_at=NOW,
            raw_snippet=f"{company.display_name} revenue was {evidence_value} billion",
            url=f"https://example.test/source-{index}",
        )
        for index, evidence_value in enumerate(evidence_values, 1)
    )
    bundle = EvidenceBundle.classify(claim, refs)
    result = VerificationEngine().verify(claim, bundle, now=NOW)
    contexts = tuple(
        CitationSourceContext(
            evidence_id=ref.evidence_id,
            source_id=ref.source_id,
            provider="fixture-provider",
            source_name=f"Official source {index}",
            url=ref.url,
            published_at=as_of,
            reference_id=f"REF-{index}",
        )
        for index, ref in enumerate(refs, 1)
    )
    return VerifiedClaimInput(
        claim=claim,
        evidence_bundle=bundle,
        verification=result,
        section=section,
        materiality=materiality,
        security_id=security_id,
        listing_id=listing_id,
        missing_reason=missing_reason,
        source_contexts=contexts,
    )


def test_language_contract_defaults_to_english_and_accepts_telugu_hindi() -> None:
    assert LanguagePreference().to_dict() == {
        "language_code": "en",
        "rendering_locale": "en-US",
        "translation_status": "not_applied",
    }
    assert LanguagePreference(OutputLanguage.TELUGU, "te-IN").language_code is OutputLanguage.TELUGU
    assert LanguagePreference(OutputLanguage.HINDI, "hi-IN").language_code is OutputLanguage.HINDI
    with pytest.raises(ValueError, match="match language_code"):
        LanguagePreference(OutputLanguage.TELUGU, "en-US")


def test_verified_claim_input_requires_phase8_identity_alignment() -> None:
    item = _verified_input()
    mismatched = replace(item.verification, claim_id=ClaimId.new().as_text())
    with pytest.raises(ValueError, match="verification result does not belong"):
        replace(item, verification=mismatched)


def test_forged_verified_status_without_supporting_evidence_is_rejected() -> None:
    item = _verified_input(value=None, evidence_values=())
    forged = replace(
        item.verification,
        status=VerificationStatus.VERIFIED,
        confidence_score=Decimal("1"),
    )
    with pytest.raises(ValueError, match="requires supporting evidence"):
        replace(item, verification=forged)


def test_verified_claim_gate_renders_only_strong_result_as_fact() -> None:
    company = _company("Apple")
    gated = VerifiedClaimGate().evaluate(_verified_input(), company)
    assert gated.claim.disposition is ClaimDisposition.FACTUAL
    assert gated.claim.verification_status is VerificationStatus.VERIFIED
    assert gated.claim.confidence.label is ConfidenceLabel.HIGH
    assert gated.claim.citation_ids


def test_conflicting_claim_preserves_both_evidence_sides_and_context() -> None:
    item = _verified_input(evidence_values=(Decimal("100"), Decimal("90")))
    gated = VerifiedClaimGate().evaluate(item, _company("Apple"))
    assert gated.claim.disposition is ClaimDisposition.CONFLICT
    assert gated.claim.rendered_text.startswith("Sources disagree")
    assert gated.claim.confidence.label is ConfidenceLabel.CONFLICTING
    assert {citation.evidence_id for citation in gated.citations} == {
        "evidence-1",
        "evidence-2",
    }
    assert gated.contradictions
    assert gated.missing is not None
    assert gated.missing.reason is MissingDataReason.CONFLICTING


def test_contradicted_claim_never_becomes_positive_fact() -> None:
    item = _verified_input(evidence_values=(Decimal("90"),))
    gated = VerifiedClaimGate().evaluate(item, _company("Apple"))
    assert gated.claim.disposition is ClaimDisposition.CONTRADICTED
    assert gated.claim.rendered_text.startswith("Available evidence contradicts")
    assert gated.claim.verification_status is VerificationStatus.CONTRADICTED


def test_unverifiable_claim_is_explicit_and_missing_value_is_not_zero() -> None:
    item = _verified_input(value=None, evidence_values=())
    gated = VerifiedClaimGate().evaluate(item, _company("Apple"))
    assert gated.claim.disposition is ClaimDisposition.INSUFFICIENT
    assert gated.claim.expected_value is None
    assert gated.missing is not None
    assert gated.missing.reason is MissingDataReason.INSUFFICIENT_EVIDENCE
    assert gated.claim.to_dict()["structured_value"] != {"value": "0"}


def test_stale_claim_retains_temporal_qualification() -> None:
    stale_as_of = datetime(2024, 1, 1, tzinfo=UTC)
    item = _verified_input(as_of=stale_as_of)
    gated = VerifiedClaimGate().evaluate(item, _company("Apple"))
    assert gated.claim.disposition is ClaimDisposition.STALE
    assert "2024-01-01" in gated.claim.rendered_text
    assert gated.claim.confidence.label is ConfidenceLabel.STALE


def test_explicit_missing_reason_is_preserved() -> None:
    item = _verified_input(
        value=None,
        evidence_values=(),
        missing_reason=MissingDataReason.NOT_REPORTED,
    )
    gated = VerifiedClaimGate().evaluate(item, _company("Apple"))
    assert gated.missing is not None
    assert gated.missing.reason is MissingDataReason.NOT_REPORTED


def test_advice_language_is_excluded_from_narrative_and_summary() -> None:
    item = _verified_input(text="BUY Apple and set a price target of 250")
    synthesis = DeterministicSynthesisAssembler().assemble(
        company=_company("Apple"),
        verified_claims=(item,),
        language=LanguagePreference(),
        generated_at=NOW,
    )
    output = synthesis.to_dict()
    rendered = output["sections"][0]["claims"][0]["text"]  # type: ignore[index]
    assert "BUY" not in rendered
    assert "price target" not in rendered
    assert output["status"] == SynthesisStatus.INSUFFICIENT.value


def test_assembler_order_and_identity_are_stable_across_input_order() -> None:
    company = _company("Apple")
    market = _verified_input(section=ResearchSectionType.MARKET_CONTEXT, materiality=2)
    risk = _verified_input(section=ResearchSectionType.RISKS_AND_UNCERTAINTIES, materiality=1)
    first = DeterministicSynthesisAssembler().assemble(
        company=company,
        verified_claims=(risk, market),
        language=LanguagePreference(),
        generated_at=NOW,
    )
    second = DeterministicSynthesisAssembler().assemble(
        company=company,
        verified_claims=(market, risk),
        language=LanguagePreference(),
        generated_at=NOW,
    )
    assert first.synthesis_id == second.synthesis_id
    assert [section.section_type for section in first.document.sections] == [
        ResearchSectionType.MARKET_CONTEXT,
        ResearchSectionType.RISKS_AND_UNCERTAINTIES,
    ]
    assert first.document.to_dict() == second.document.to_dict()


def test_summary_is_bounded_and_traceable_to_claims_and_citations() -> None:
    items = tuple(
        _verified_input(
            section=ResearchSectionType.COMPANY_OVERVIEW,
            materiality=(index % 3) + 1,
            text=f"Apple verified operational fact {index}",
            value=None,
            evidence_values=(),
        )
        for index in range(7)
    )
    synthesis = DeterministicSynthesisAssembler(max_summary_items=3).assemble(
        company=_company("Apple"),
        verified_claims=items,
        language=LanguagePreference(),
        generated_at=NOW,
    )
    assert len(synthesis.document.executive_summary.items) == 3
    claim_ids = {item.claim.claim_id.as_text() for item in items}
    assert all(item.claim_id in claim_ids for item in synthesis.document.executive_summary.items)


def test_citation_retains_authority_origin_provider_dates_and_reference() -> None:
    gated = VerifiedClaimGate().evaluate(_verified_input(), _company("Apple"))
    citation = gated.citations[0].to_dict()
    assert citation["authority_tier"] == 1
    assert citation["data_origin"] == "fixture"
    assert citation["provider"] == "fixture-provider"
    assert citation["url"] == "https://example.test/source-1"
    assert citation["published_at"] == "2026-08-10T08:00:00Z"
    assert citation["reference_id"] == "REF-1"


def test_security_and_listing_must_belong_to_resolved_company() -> None:
    item = _verified_input(
        security_id="32222222-2222-4222-8222-222222222003",
        listing_id="42222222-2222-4222-8222-222222222003",
    )
    with pytest.raises(ValueError, match="security_id does not belong"):
        VerifiedClaimGate().evaluate(item, _company("Apple"))


def test_confidence_score_051_is_not_presented_as_certain() -> None:
    label = VerifiedClaimGate().confidence_label(
        VerificationStatus.PARTIALLY_VERIFIED,
        Decimal("0.51"),
    )
    assert label is ConfidenceLabel.LOW
