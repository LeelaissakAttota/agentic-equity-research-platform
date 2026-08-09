"""Adversarial Phase 9 Prompt 2 synthesis and report hardening tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.report import ReportFormat, ResearchReportGenerationRequest
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.synthesis import (
    CitationSourceContext,
    ClaimDisposition,
    DeterministicSynthesisAssembler,
    FreshnessClassification,
    LanguagePreference,
    MaterialClaimKind,
    MissingDataReason,
    ResearchSectionType,
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
from financial_intelligence.infrastructure.reporting import DeterministicResearchReportGenerator

NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
RUN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CLAIM_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ROOT = Path(__file__).resolve().parents[2]


def _company(name: str = "Apple"):  # type: ignore[no-untyped-def]
    return next(company for company in build_reference_companies() if company.display_name == name)


def _identity(name: str = "Apple") -> tuple[str, str]:
    security = _company(name).securities[0]
    return security.security_id.as_text(), security.listings[0].listing_id.as_text()


def _item(
    *,
    kind: MaterialClaimKind = MaterialClaimKind.REVENUE,
    as_of: datetime = NOW,
    value: Decimal | None = Decimal("100"),
    evidence_values: tuple[Decimal, ...] = (Decimal("100"),),
    evidence_tiers: tuple[SourceAuthorityTier, ...] | None = None,
    text: str = "Apple revenue was 100 billion",
    missing: MissingDataReason | None = None,
    section: ResearchSectionType = ResearchSectionType.FINANCIAL_PERFORMANCE,
) -> VerifiedClaimInput:
    company = _company()
    security_id, listing_id = _identity()
    numeric = value is not None
    claim = Claim(
        claim_id=ClaimId.from_string(CLAIM_ID),
        claim_type=ClaimType.NUMERIC if numeric else ClaimType.FACTUAL,
        text=text,
        company_id=company.company_id.as_text(),
        research_run_id=RUN_ID,
        expected_value=value,
        expected_unit="billion" if numeric else None,
        expected_currency="USD" if numeric else None,
        expected_period="FY2026" if numeric else None,
        expected_as_of=as_of,
        created_at=NOW,
    )
    tiers = evidence_tiers or tuple(
        SourceAuthorityTier.TIER_1_AUTHORITATIVE for _ in evidence_values
    )
    refs = tuple(
        EvidenceRef(
            evidence_id=f"evidence-{index}",
            source_id=f"source-{index}",
            authority_tier=tiers[index - 1],
            data_origin=DataOrigin.FIXTURE,
            claim_type=claim.claim_type.value,
            extracted_value=evidence_value,
            extracted_unit=claim.expected_unit,
            extracted_currency=claim.expected_currency,
            extracted_period=claim.expected_period,
            as_of=as_of,
            retrieved_at=NOW,
            raw_snippet=text,
            url=f"https://example.test/evidence-{index}",
        )
        for index, evidence_value in enumerate(evidence_values, 1)
    )
    bundle = EvidenceBundle.classify(claim, refs)
    verification = VerificationEngine().verify(claim, bundle, now=NOW)
    contexts = tuple(
        CitationSourceContext(
            evidence_id=ref.evidence_id,
            source_id=ref.source_id,
            provider="official-fixture",
            url=ref.url,
            published_at=as_of,
            company_id=company.company_id.as_text(),
            security_id=security_id,
            listing_id=listing_id,
        )
        for ref in refs
    )
    return VerifiedClaimInput(
        claim=claim,
        evidence_bundle=bundle,
        verification=verification,
        section=section,
        materiality=1,
        material_claim_kind=kind,
        security_id=security_id,
        listing_id=listing_id,
        missing_reason=missing,
        source_contexts=contexts,
    )


def _synthesis(*items: VerifiedClaimInput, generated_at: datetime = NOW):  # type: ignore[no-untyped-def]
    return DeterministicSynthesisAssembler().assemble(
        company=_company(),
        verified_claims=tuple(items),
        language=LanguagePreference(),
        generated_at=generated_at,
    )


def test_forged_phase8_confidence_and_status_cannot_enter_synthesis() -> None:
    item = _item()
    forged = replace(item.verification, confidence_score=Decimal("0.01"))
    with pytest.raises(ValueError, match="deterministic Phase 8 policy"):
        replace(item, verification=forged)
    contradicted = replace(item.verification, status=VerificationStatus.CONTRADICTED)
    with pytest.raises(ValueError, match="requires contradicting evidence"):
        replace(item, verification=contradicted)


def test_semantically_duplicate_evidence_cannot_increase_report_confidence() -> None:
    item = _item()
    original = item.evidence_bundle.evidence_refs[0]
    duplicate = replace(original, evidence_id="evidence-copy")
    duplicate_bundle = EvidenceBundle.classify(item.claim, (original, duplicate))
    duplicate_result = VerificationEngine().verify(item.claim, duplicate_bundle, now=NOW)
    assert duplicate_result.confidence_score == item.verification.confidence_score
    with pytest.raises(ValueError, match="duplicate semantic evidence"):
        replace(item, evidence_bundle=duplicate_bundle, verification=duplicate_result)


def test_cross_company_and_cross_listing_citation_context_is_rejected() -> None:
    item = _item()
    context = item.source_contexts[0]
    with pytest.raises(ValueError, match="company_id mismatch"):
        replace(item, source_contexts=(replace(context, company_id="other-company"),))
    with pytest.raises(ValueError, match="listing_id mismatch"):
        replace(item, source_contexts=(replace(context, listing_id="other-listing"),))


def test_material_claim_shapes_are_bounded_but_missing_material_data_remains_explicit() -> None:
    verified = _item(kind=MaterialClaimKind.MARKET_PRICE)
    with pytest.raises(ValueError, match="market price claim requires"):
        replace(verified, claim=replace(verified.claim, expected_as_of=None))
    unavailable = _item(
        kind=MaterialClaimKind.REGULATORY_ACTION,
        value=None,
        evidence_values=(),
        text="Apple regulatory action was unavailable",
        missing=MissingDataReason.UNAVAILABLE,
        section=ResearchSectionType.REGULATORY_CONTEXT,
    )
    output = _synthesis(unavailable).to_dict()
    assert output["missing_data"][0]["reason"] == "unavailable"  # type: ignore[index]
    structured = output["sections"][0]["claims"][0]["structured_value"]  # type: ignore[index]
    assert structured["value"] is None


def test_market_currentness_and_historical_financial_period_use_distinct_policies() -> None:
    old = NOW - timedelta(days=2)
    market = _item(kind=MaterialClaimKind.MARKET_PRICE, as_of=old)
    market_claim = _synthesis(market).document.sections[0].claims[0]
    assert market_claim.freshness.classification is FreshnessClassification.STALE
    assert market_claim.disposition is ClaimDisposition.STALE
    financial = _item(kind=MaterialClaimKind.REVENUE, as_of=old)
    financial_claim = _synthesis(financial).document.sections[0].claims[0]
    assert financial_claim.freshness.classification is FreshnessClassification.HISTORICAL
    assert financial_claim.disposition is ClaimDisposition.FACTUAL


def test_conflicts_retain_competing_evidence_and_never_select_a_winner() -> None:
    conflicting = _item(evidence_values=(Decimal("100"), Decimal("90")))
    claim = _synthesis(conflicting).document.sections[0].claims[0]
    assert claim.disposition is ClaimDisposition.CONFLICT
    assert len(claim.citation_ids) == 2
    assert claim.contradiction_ids


def test_low_authority_evidence_never_upgrades_phase8_confidence() -> None:
    item = _item(evidence_tiers=(SourceAuthorityTier.TIER_4_GENERAL_WEB,))
    synthesis = _synthesis(item)
    claim = synthesis.document.sections[0].claims[0]
    assert claim.verification_status is item.verification.status
    assert claim.disposition is ClaimDisposition.INSUFFICIENT
    assert claim.confidence.score == item.verification.confidence_score


@pytest.mark.parametrize("reason", list(MissingDataReason))
def test_missing_states_remain_distinct_and_never_become_zero(reason: MissingDataReason) -> None:
    item = _item(
        kind=MaterialClaimKind.OTHER,
        value=None,
        evidence_values=(),
        text=f"Apple data was {reason.value}",
        missing=reason,
    )
    payload = _synthesis(item).to_dict()
    assert payload["missing_data"][0]["reason"] == reason.value  # type: ignore[index]
    assert payload["sections"][0]["claims"][0]["structured_value"]["value"] is None  # type: ignore[index]


def test_json_and_markdown_reports_are_stable_bounded_and_inert() -> None:
    hostile = _item(
        kind=MaterialClaimKind.OTHER,
        value=None,
        evidence_values=(),
        text='<script>alert("secret")</script> BUY Apple; will rise',
    )
    synthesis = _synthesis(hostile)
    renderer = DeterministicResearchReportGenerator()
    json_request = ResearchReportGenerationRequest(
        synthesis_id=synthesis.synthesis_id,
        report_format=ReportFormat.STRUCTURED_JSON,
        language=synthesis.language,
    )
    first = renderer.generate(json_request, synthesis)
    second = renderer.generate(json_request, synthesis)
    assert first.to_dict() == second.to_dict()
    payload = json.loads(first.content or "")
    assert payload["report_metadata"]["confidence_aggregation"] == "none_per_claim_only"
    assert len(payload["section_availability"]) == 8
    assert payload["omissions"]["zero_substitution"] is False
    markdown_request = replace(json_request, report_format=ReportFormat.MARKDOWN)
    markdown = renderer.generate(markdown_request, synthesis).content or ""
    assert "<script>" not in markdown
    assert 'alert("secret")' not in markdown
    assert "BUY Apple" not in markdown
    assert "will rise" not in markdown
    assert "## Verification and Confidence" in markdown
    assert "Unavailable: no verified" in markdown
    docx = renderer.generate(replace(json_request, report_format=ReportFormat.DOCX), synthesis)
    assert docx.content_encoding == "base64"
    assert docx.filename == "apple-research-report.docx"


def test_phase9_runtime_surface_has_no_execution_fetch_or_file_write_primitives() -> None:
    package = ROOT / "src" / "financial_intelligence"
    paths = [
        *(package / "domain" / "synthesis").glob("*.py"),
        package / "infrastructure" / "reporting" / "deterministic.py",
        package / "api" / "routes" / "synthesis.py",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    forbidden = (
        "eval(",
        "exec(",
        "subprocess",
        "os.system",
        "shell=true",
        "requests.get",
        "httpx",
        "open(",
        "write_text(",
        "write_bytes(",
        "openrouter",
    )
    assert [marker for marker in forbidden if marker in joined] == []
