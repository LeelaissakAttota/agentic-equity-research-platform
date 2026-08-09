"""Phase 9 Prompt 3 semantic contract freeze and acceptance audit tests."""

from __future__ import annotations

import ast
import base64
import io
import json
import zipfile
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from financial_intelligence.api.app import create_app
from financial_intelligence.domain.report import ReportFormat, ResearchReportGenerationRequest
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.synthesis import (
    ClaimDisposition,
    DeterministicSynthesisAssembler,
    FreshnessClassification,
    LanguagePreference,
    MaterialClaimKind,
    OutputLanguage,
    ResearchSectionType,
    SynthesisStatus,
)
from financial_intelligence.domain.verification import (
    ClaimId,
    EvidenceBundle,
    VerificationEngine,
)
from financial_intelligence.infrastructure.reporting import DeterministicResearchReportGenerator
from tests.unit.test_phase9_prompt2_hardening import NOW, _company, _item, _synthesis
from tests.unit.test_synthesis_api import (
    APPLE_COMPANY_ID,
    APPLE_LISTING_ID,
    APPLE_SECURITY_ID,
    RELIANCE_COMPANY_ID,
    RELIANCE_NSE_LISTING_ID,
    RELIANCE_SECURITY_ID,
    _body,
    _claim,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "financial_intelligence"


def _artifact(report_format: ReportFormat, *items: object):  # type: ignore[no-untyped-def]
    synthesis = _synthesis(*items)  # type: ignore[arg-type]
    request = ResearchReportGenerationRequest(
        synthesis_id=synthesis.synthesis_id,
        report_format=report_format,
        language=synthesis.language,
        title="Evidence-Linked Equity Research",
    )
    return synthesis, DeterministicResearchReportGenerator().generate(request, synthesis)


def test_external_synthesis_and_report_contracts_have_semantic_required_fields() -> None:
    synthesis, artifact = _artifact(ReportFormat.STRUCTURED_JSON, _item())
    payload = synthesis.to_dict()
    assert {
        "synthesis_id",
        "research_run_id",
        "status",
        "company",
        "language",
        "generated_at",
        "sections",
        "executive_summary",
        "confidence_contexts",
        "contradictions",
        "missing_data",
        "citations",
    } <= payload.keys()
    claim = payload["sections"][0]["claims"][0]  # type: ignore[index]
    assert {
        "claim_id",
        "company_id",
        "security_id",
        "listing_id",
        "verification_status",
        "confidence",
        "citation_ids",
        "contradiction_ids",
        "freshness",
        "structured_value",
    } <= claim.keys()
    report = json.loads(artifact.content or "")
    assert {
        "report_metadata",
        "section_availability",
        "omissions",
        "as_of_context",
        "synthesis",
    } == report.keys()
    assert report["report_metadata"]["confidence_aggregation"] == "none_per_claim_only"
    assert artifact.to_dict()["content_encoding"] == "utf-8"


def test_api_rejects_attempted_verification_and_policy_bypass_fields() -> None:
    client = TestClient(create_app())
    claim = _claim(
        company_id=APPLE_COMPANY_ID,
        company_name="Apple",
        currency="USD",
        security_id=APPLE_SECURITY_ID,
        listing_id=APPLE_LISTING_ID,
        source_id="SEC-EDGAR",
        provider="SEC EDGAR",
        url="https://www.sec.gov/Archives/apple-fy2026",
    )
    claim["verification"] = {"status": "verified", "confidence_score": 1}
    claim["remove_conflicts"] = True
    response = client.post(
        "/research/synthesis",
        json=_body(q="Apple", country="US", exchange="NASDAQ", ticker="AAPL", claim=claim),
    )
    assert response.status_code == 422
    assert "verified" not in response.text.lower()
    assert "Traceback" not in response.text


def test_conflicting_values_authority_and_period_remain_visible_in_all_reports() -> None:
    item = _item(evidence_values=(Decimal("100"), Decimal("90")))
    second = replace(
        item.evidence_bundle.evidence_refs[1],
        authority_tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
        extracted_period="FY2025",
    )
    refs = (item.evidence_bundle.evidence_refs[0], second)
    bundle = EvidenceBundle.classify(item.claim, refs)
    result = VerificationEngine().verify(item.claim, bundle, now=NOW)
    conflicting = replace(item, evidence_bundle=bundle, verification=result)
    synthesis = _synthesis(conflicting)
    claim = synthesis.document.sections[0].claims[0]
    assert claim.disposition is ClaimDisposition.CONFLICT
    assert len(claim.citation_ids) == 2
    assert synthesis.document.contradictions
    for report_format in (ReportFormat.STRUCTURED_JSON, ReportFormat.MARKDOWN, ReportFormat.DOCX):
        _, artifact = _artifact(report_format, conflicting)
        if report_format in {ReportFormat.STRUCTURED_JSON, ReportFormat.MARKDOWN}:
            rendered = artifact.content or ""
        else:
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(artifact.content or ""))) as archive:
                rendered = archive.read("word/document.xml").decode("utf-8")
        assert "conflict" in rendered.lower() or "sources disagree" in rendered.lower()
        normalized = rendered.replace("\\", "")
        assert "evidence-1" in normalized
        assert "evidence-2" in normalized


def test_stale_current_and_historical_claims_keep_distinct_semantics() -> None:
    stale = _item(kind=MaterialClaimKind.MARKET_PRICE, as_of=NOW - timedelta(days=2))
    current = _item(kind=MaterialClaimKind.MARKET_PRICE, as_of=NOW)
    current_claim = replace(
        current.claim,
        claim_id=ClaimId.from_string("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
    )
    current_bundle = EvidenceBundle.classify(current_claim, current.evidence_bundle.evidence_refs)
    current = replace(
        current,
        claim=current_claim,
        evidence_bundle=current_bundle,
        verification=VerificationEngine().verify(current_claim, current_bundle, now=NOW),
    )
    financial = _item(kind=MaterialClaimKind.REVENUE, as_of=NOW - timedelta(days=180))
    financial_claim = replace(
        financial.claim,
        claim_id=ClaimId.from_string("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
    )
    financial_bundle = EvidenceBundle.classify(
        financial_claim,
        financial.evidence_bundle.evidence_refs,
    )
    financial = replace(
        financial,
        claim=financial_claim,
        evidence_bundle=financial_bundle,
        verification=VerificationEngine().verify(financial_claim, financial_bundle, now=NOW),
    )
    synthesis = _synthesis(stale, current, financial)
    classifications = {
        claim.freshness.classification
        for section in synthesis.document.sections
        for claim in section.claims
    }
    assert classifications == {
        FreshnessClassification.STALE,
        FreshnessClassification.CURRENT,
        FreshnessClassification.HISTORICAL,
    }
    assert synthesis.status is SynthesisStatus.PARTIAL


def test_reports_degrade_usefully_with_incomplete_and_unavailable_research() -> None:
    unavailable = _item(
        kind=MaterialClaimKind.OTHER,
        value=None,
        evidence_values=(),
        text="Market, qualitative, and regulatory research was unavailable",
        section=ResearchSectionType.MARKET_CONTEXT,
    )
    synthesis, markdown = _artifact(ReportFormat.MARKDOWN, unavailable)
    assert synthesis.status is SynthesisStatus.INSUFFICIENT
    assert "Insufficient evidence" in (markdown.content or "")
    assert "## Regulatory" in (markdown.content or "")
    assert "Unavailable: no verified" in (markdown.content or "")
    _, structured = _artifact(ReportFormat.STRUCTURED_JSON, unavailable)
    payload = json.loads(structured.content or "")
    unavailable_sections = payload["omissions"]["unavailable_sections"]
    assert "regulatory_context" in unavailable_sections
    assert payload["omissions"]["zero_substitution"] is False


def test_language_preference_is_preserved_without_claiming_narrative_translation() -> None:
    item = _item()
    synthesis = DeterministicSynthesisAssembler().assemble(
        company=_company(),
        verified_claims=(item,),
        language=LanguagePreference(OutputLanguage.TELUGU, "te-IN"),
        generated_at=NOW,
    )
    assert synthesis.language.to_dict() == {
        "language_code": "te",
        "rendering_locale": "te-IN",
        "translation_status": "not_applied",
    }
    assert synthesis.document.sections[0].claims[0].rendered_text == item.claim.text


def test_docx_is_deterministic_valid_safe_and_contains_evidence_linkage() -> None:
    hostile = _item(text="<script>run()</script> Apple revenue was 100 billion")
    synthesis, first = _artifact(ReportFormat.DOCX, hostile)
    _, second = _artifact(ReportFormat.DOCX, hostile)
    assert first.content == second.content
    assert first.filename == "apple-research-report.docx"
    assert first.content_encoding == "base64"
    content = base64.b64decode(first.content or "", validate=True)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert set(archive.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            "docProps/app.xml",
            "docProps/core.xml",
            "word/document.xml",
            "word/styles.xml",
            "word/_rels/document.xml.rels",
        }
        for name in archive.namelist():
            ElementTree.fromstring(archive.read(name))
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Evidence-Linked Equity Research" in document_xml
    assert synthesis.research_run_id in document_xml
    assert synthesis.document.citations[0].citation_id in document_xml
    assert "&lt;script&gt;" in document_xml
    assert "<script>" not in document_xml


@pytest.mark.parametrize("unsafe", ("../report.docx", "folder/report.docx", "report..docx"))
def test_report_artifact_contract_rejects_unsafe_filenames(unsafe: str) -> None:
    synthesis, artifact = _artifact(ReportFormat.DOCX, _item())
    with pytest.raises(ValueError, match="filename is unsafe"):
        replace(artifact, filename=unsafe, synthesis_id=synthesis.synthesis_id)


def test_apple_and_reliance_api_goldens_freeze_identity_not_whitespace() -> None:
    client = TestClient(create_app())
    fixtures = (
        (
            _body(
                q="Apple",
                country="US",
                exchange="NASDAQ",
                ticker="AAPL",
                claim=_claim(
                    company_id=APPLE_COMPANY_ID,
                    company_name="Apple",
                    currency="USD",
                    security_id=APPLE_SECURITY_ID,
                    listing_id=APPLE_LISTING_ID,
                    source_id="SEC-EDGAR",
                    provider="SEC EDGAR",
                    url="https://www.sec.gov/Archives/apple-fy2026",
                ),
            ),
            APPLE_COMPANY_ID,
            APPLE_LISTING_ID,
            "USD",
        ),
        (
            _body(
                q="Reliance Industries",
                country="IN",
                exchange="NSE",
                ticker="RELIANCE",
                claim=_claim(
                    company_id=RELIANCE_COMPANY_ID,
                    company_name="Reliance Industries",
                    currency="INR",
                    security_id=RELIANCE_SECURITY_ID,
                    listing_id=RELIANCE_NSE_LISTING_ID,
                    source_id="NSE-FILING",
                    provider="NSE",
                    url="https://www.nseindia.com/reliance-fy2026",
                ),
            ),
            RELIANCE_COMPANY_ID,
            RELIANCE_NSE_LISTING_ID,
            "INR",
        ),
    )
    for body, company_id, listing_id, currency in fixtures:
        body["report_format"] = "docx"
        response = client.post("/research/synthesis", json=body)
        assert response.status_code == 200
        payload = response.json()
        claim = payload["sections"][0]["claims"][0]
        assert payload["company"]["company_id"] == company_id
        assert claim["listing_id"] == listing_id
        assert claim["structured_value"]["currency"] == currency
        assert payload["report"]["status"] == "ready"


def test_phase9_reuses_cross_phase_contracts_without_importing_capability_implementations() -> None:
    paths = [
        *(PACKAGE / "domain" / "synthesis").glob("*.py"),
        PACKAGE / "application" / "generate_research_synthesis.py",
        PACKAGE / "infrastructure" / "reporting" / "deterministic.py",
    ]
    imports: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
    assert "financial_intelligence.domain.identity" in imports
    assert any(name.startswith("financial_intelligence.domain.verification") for name in imports)
    forbidden_capabilities = {
        "market",
        "financial",
        "news",
        "industry",
        "regulatory",
        "orchestration",
        "workflow",
        "memory",
    }
    assert not any(
        any(f".{capability}" in imported for capability in forbidden_capabilities)
        for imported in imports
    )
    synthesis_source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "VerificationEngine().verify" in synthesis_source
    assert "calculate_ratio" not in synthesis_source
    assert "get_market_snapshot" not in synthesis_source


def test_phase9_surface_has_no_model_network_execution_or_file_write_dependency() -> None:
    paths = [
        *(PACKAGE / "domain" / "synthesis").glob("*.py"),
        PACKAGE / "application" / "generate_research_synthesis.py",
        PACKAGE / "infrastructure" / "reporting" / "deterministic.py",
        PACKAGE / "api" / "routes" / "synthesis.py",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    forbidden = (
        "openrouter",
        "langgraph",
        "langchain",
        "pgvector",
        "requests.get",
        "httpx",
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "open(",
        "write_text(",
        "write_bytes(",
        "python-docx",
    )
    assert [marker for marker in forbidden if marker in joined] == []
