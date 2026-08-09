"""Deterministic JSON and safe Markdown rendering for verified synthesis artifacts."""

from __future__ import annotations

import base64
import html
import io
import json
import re
import zipfile
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5
from xml.sax.saxutils import escape as xml_escape

from financial_intelligence.domain.report import (
    ReportArtifact,
    ReportArtifactStatus,
    ReportFormat,
    ResearchReportGenerationRequest,
)
from financial_intelligence.domain.synthesis import (
    SECTION_ORDER,
    ResearchSectionType,
    ResearchSynthesis,
)

_MARKDOWN_META = re.compile(r"([\\`*_{}\[\]()#+.!|>~-])")
_SECTION_TITLES: dict[ResearchSectionType, str] = {
    ResearchSectionType.COMPANY_OVERVIEW: "Company Overview",
    ResearchSectionType.MARKET_CONTEXT: "Market Intelligence",
    ResearchSectionType.FINANCIAL_PERFORMANCE: "Financial Performance and Health",
    ResearchSectionType.NEWS_AND_EVENTS: "News and Events",
    ResearchSectionType.INDUSTRY_CONTEXT: "Industry",
    ResearchSectionType.COMPETITIVE_CONTEXT: "Competitive Context",
    ResearchSectionType.REGULATORY_CONTEXT: "Regulatory",
    ResearchSectionType.RISKS_AND_UNCERTAINTIES: "Risks and Uncertainties",
}


def _safe_text(value: object) -> str:
    """Render untrusted strings as inert text, never executable markup."""

    escaped = html.escape(str(value), quote=True)
    return _MARKDOWN_META.sub(r"\\\1", escaped)


@dataclass(frozen=True, slots=True)
class DeterministicResearchReportGenerator:
    """Render bounded reports in memory without network, LLM, or file access."""

    def generate(
        self,
        request: ResearchReportGenerationRequest,
        synthesis: ResearchSynthesis,
    ) -> ReportArtifact:
        if request.synthesis_id != synthesis.synthesis_id:
            raise ValueError("report request synthesis_id mismatch")
        if request.language != synthesis.language:
            raise ValueError("report language must match synthesis language")
        artifact_id = str(
            uuid5(
                NAMESPACE_URL,
                f"financial-intelligence/report/{synthesis.synthesis_id.as_text()}/"
                f"{request.report_format.value}",
            )
        )
        if request.report_format is ReportFormat.STRUCTURED_JSON:
            return ReportArtifact(
                artifact_id=artifact_id,
                synthesis_id=synthesis.synthesis_id,
                report_format=request.report_format,
                status=ReportArtifactStatus.READY,
                media_type="application/json",
                content=self._json_content(artifact_id, request, synthesis),
                filename=self._safe_filename(synthesis.company.display_name, "json"),
            )
        if request.report_format is ReportFormat.MARKDOWN:
            return ReportArtifact(
                artifact_id=artifact_id,
                synthesis_id=synthesis.synthesis_id,
                report_format=request.report_format,
                status=ReportArtifactStatus.READY,
                media_type="text/markdown",
                content=self._markdown_content(request, synthesis),
                filename=self._safe_filename(synthesis.company.display_name, "md"),
            )
        if request.report_format is ReportFormat.DOCX:
            return ReportArtifact(
                artifact_id=artifact_id,
                synthesis_id=synthesis.synthesis_id,
                report_format=request.report_format,
                status=ReportArtifactStatus.READY,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                content=self._docx_content(request, synthesis),
                content_encoding="base64",
                filename=self._safe_filename(synthesis.company.display_name, "docx"),
            )
        raise ValueError("unsupported report format")

    @staticmethod
    def _safe_filename(company_name: str, extension: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", company_name).strip("-").lower()
        slug = slug[:80] or "company"
        return f"{slug}-research-report.{extension}"

    @staticmethod
    def _json_content(
        artifact_id: str,
        request: ResearchReportGenerationRequest,
        synthesis: ResearchSynthesis,
    ) -> str:
        available = {section.section_type for section in synthesis.document.sections}
        unavailable = [section for section in SECTION_ORDER if section not in available]
        payload: dict[str, object] = {
            "report_metadata": {
                "artifact_id": artifact_id,
                "format": request.report_format.value,
                "title": request.title,
                "generated_at": synthesis.generated_at.isoformat().replace("+00:00", "Z"),
                "translation_status": "not_applied",
                "confidence_aggregation": "none_per_claim_only",
                "renderer": "phase9-deterministic-v1",
            },
            "section_availability": [
                {
                    "section_type": section.value,
                    "title": _SECTION_TITLES[section],
                    "status": "available" if section in available else "unavailable",
                }
                for section in SECTION_ORDER
            ],
            "omissions": {
                "unavailable_sections": [section.value for section in unavailable],
                "claim_contexts": [
                    context.to_dict() for context in synthesis.document.missing_data
                ],
                "zero_substitution": False,
            },
            "as_of_context": [
                {
                    "citation_id": citation.citation_id,
                    "as_of": citation.to_dict()["as_of"],
                    "retrieved_at": citation.to_dict()["retrieved_at"],
                }
                for citation in synthesis.document.citations
            ],
            "synthesis": synthesis.to_dict(),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _markdown_content(
        request: ResearchReportGenerationRequest,
        synthesis: ResearchSynthesis,
    ) -> str:
        document = synthesis.document
        sections = {section.section_type: section for section in document.sections}
        lines = [
            f"# {_safe_text(request.title)}",
            "",
            f"**Company:** {_safe_text(synthesis.company.display_name)}",
            f"**Research run:** {_safe_text(synthesis.research_run_id)}",
            f"**Synthesis:** {_safe_text(synthesis.synthesis_id.as_text())}",
            f"**Status:** {_safe_text(synthesis.status.value)}",
            f"**Generated:** {_safe_text(synthesis.generated_at.isoformat())}",
            f"**Language:** {_safe_text(synthesis.language.language_code.value)} "
            f"({_safe_text(synthesis.language.rendering_locale)}; translation not applied)",
            "**Confidence:** per claim only; no aggregate report confidence is calculated.",
            "",
            "## Executive Summary",
            "",
        ]
        if document.executive_summary.items:
            for item in document.executive_summary.items:
                citations = ", ".join(_safe_text(value) for value in item.citation_ids) or "none"
                lines.append(
                    f"- {_safe_text(item.text)} "
                    f"[claim: {_safe_text(item.claim_id)}; "
                    f"confidence: {_safe_text(item.confidence_label.value)}; "
                    f"evidence: {citations}]"
                )
        else:
            lines.append("_Unavailable: no accepted claims met the summary policy._")
        for section_type in SECTION_ORDER:
            lines.extend(("", f"## {_SECTION_TITLES[section_type]}", ""))
            section = sections.get(section_type)
            if section is None or not section.claims:
                lines.append(
                    "_Unavailable: no verified or explicitly qualified claim was supplied._"
                )
                continue
            for claim in section.claims:
                citation_text = (
                    ", ".join(_safe_text(value) for value in claim.citation_ids) or "none"
                )
                lines.append(
                    f"- {_safe_text(claim.rendered_text)} "
                    f"[claim: {_safe_text(claim.claim_id)}; "
                    f"verification: {_safe_text(claim.verification_status.value)}; "
                    f"confidence: {_safe_text(claim.confidence.label.value)}; "
                    f"freshness: {_safe_text(claim.freshness.classification.value)}; "
                    f"evidence: {citation_text}]"
                )
        lines.extend(("", "## Verification and Confidence", ""))
        for confidence in document.confidence_contexts:
            lines.append(
                f"- Claim {_safe_text(confidence.claim_id)}: "
                f"{_safe_text(confidence.label.value)} "
                f"(score {_safe_text(confidence.score)}, "
                f"policy {_safe_text(confidence.score_version)})."
            )
        lines.extend(("", "## Conflicts and Uncertainties", ""))
        if document.contradictions:
            for contradiction in document.contradictions:
                lines.append(
                    f"- {_safe_text(contradiction.description)} "
                    f"[conflict: {_safe_text(contradiction.contradiction_id)}]"
                )
        else:
            lines.append("_No recorded evidence conflicts._")
        lines.extend(("", "## Missing and Unavailable Data", ""))
        if document.missing_data:
            for missing in document.missing_data:
                lines.append(
                    f"- Claim {_safe_text(missing.claim_id)}: {_safe_text(missing.reason.value)} "
                    f"— {_safe_text(missing.detail)}"
                )
        else:
            lines.append("_No explicit missing-data records._")
        lines.extend(("", "## Sources and Evidence", ""))
        if document.citations:
            for citation in document.citations:
                locator = citation.url or citation.locator or "not provided"
                lines.append(
                    f"- {_safe_text(citation.citation_id)}: "
                    f"source {_safe_text(citation.source_id)}, "
                    f"provider {_safe_text(citation.provider or 'not provided')}, "
                    f"authority tier {_safe_text(citation.authority_tier)}, "
                    f"origin {_safe_text(citation.data_origin)}, locator {_safe_text(locator)}, "
                    f"company {_safe_text(citation.company_id)}, "
                    f"security {_safe_text(citation.security_id or 'not provided')}, "
                    f"listing {_safe_text(citation.listing_id or 'not provided')}."
                )
        else:
            lines.append("_No source references were supplied._")
        return "\n".join(lines) + "\n"

    @classmethod
    def _docx_content(
        cls,
        request: ResearchReportGenerationRequest,
        synthesis: ResearchSynthesis,
    ) -> str:
        """Return a deterministic minimal OOXML document encoded as base64."""

        body = cls._docx_body(request, synthesis)
        generated = synthesis.generated_at.isoformat().replace("+00:00", "Z")
        parts = (
            ("[Content_Types].xml", cls._content_types_xml()),
            ("_rels/.rels", cls._package_relationships_xml()),
            ("docProps/app.xml", cls._app_properties_xml()),
            ("docProps/core.xml", cls._core_properties_xml(request.title, generated)),
            ("word/document.xml", cls._document_xml(body)),
            ("word/styles.xml", cls._styles_xml()),
            ("word/_rels/document.xml.rels", cls._document_relationships_xml()),
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for name, content in parts:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, content.encode("utf-8"))
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    @classmethod
    def _docx_body(
        cls,
        request: ResearchReportGenerationRequest,
        synthesis: ResearchSynthesis,
    ) -> str:
        document = synthesis.document
        sections = {section.section_type: section for section in document.sections}
        paragraphs = [
            cls._paragraph(request.title, "Title"),
            cls._paragraph(synthesis.company.display_name, "Subtitle"),
            cls._paragraph(f"Research Run ID: {synthesis.research_run_id}"),
            cls._paragraph(f"Synthesis ID: {synthesis.synthesis_id.as_text()}"),
            cls._paragraph(f"Generated: {synthesis.generated_at.isoformat()}"),
            cls._paragraph(
                f"Language: {synthesis.language.language_code.value} "
                f"({synthesis.language.rendering_locale}; translation not applied)"
            ),
            cls._paragraph("Confidence is reported per claim; no aggregate is calculated."),
            cls._page_break(),
            cls._paragraph("Executive Summary", "Heading1"),
        ]
        if document.executive_summary.items:
            paragraphs.extend(
                cls._paragraph(
                    f"{item.text} [claim {item.claim_id}; "
                    f"confidence {item.confidence_label.value}]",
                    "ListBullet",
                )
                for item in document.executive_summary.items
            )
        else:
            paragraphs.append(cls._paragraph("Unavailable: no accepted summary claims."))
        for section_type in SECTION_ORDER:
            paragraphs.append(cls._paragraph(_SECTION_TITLES[section_type], "Heading1"))
            section = sections.get(section_type)
            if section is None or not section.claims:
                paragraphs.append(
                    cls._paragraph(
                        "Unavailable: no verified or explicitly qualified claim was supplied."
                    )
                )
                continue
            paragraphs.extend(
                cls._paragraph(
                    f"{claim.rendered_text} [claim {claim.claim_id}; "
                    f"verification {claim.verification_status.value}; "
                    f"confidence {claim.confidence.label.value}; "
                    f"freshness {claim.freshness.classification.value}; "
                    f"evidence {', '.join(claim.citation_ids) or 'none'}]",
                    "ListBullet",
                )
                for claim in section.claims
            )
        paragraphs.append(cls._paragraph("Verification and Confidence", "Heading1"))
        paragraphs.extend(
            cls._paragraph(
                f"Claim {context.claim_id}: {context.label.value}; score {context.score}; "
                f"policy {context.score_version}.",
                "ListBullet",
            )
            for context in document.confidence_contexts
        )
        paragraphs.append(cls._paragraph("Conflicts and Uncertainties", "Heading1"))
        if document.contradictions:
            paragraphs.extend(
                cls._paragraph(
                    f"{context.description} [conflict {context.contradiction_id}]",
                    "ListBullet",
                )
                for context in document.contradictions
            )
        else:
            paragraphs.append(cls._paragraph("No recorded evidence conflicts."))
        paragraphs.append(cls._paragraph("Missing and Unavailable Data", "Heading1"))
        if document.missing_data:
            paragraphs.extend(
                cls._paragraph(
                    f"Claim {context.claim_id}: {context.reason.value} - {context.detail}",
                    "ListBullet",
                )
                for context in document.missing_data
            )
        else:
            paragraphs.append(cls._paragraph("No explicit missing-data records."))
        paragraphs.append(cls._paragraph("Sources and Evidence", "Heading1"))
        if document.citations:
            paragraphs.extend(
                cls._paragraph(
                    f"{citation.citation_id}: source {citation.source_id}; "
                    f"provider {citation.provider or 'not provided'}; "
                    f"authority tier {citation.authority_tier}; origin {citation.data_origin}; "
                    f"locator {citation.url or citation.locator or 'not provided'}; "
                    f"company {citation.company_id}; "
                    f"security {citation.security_id or 'not provided'}; "
                    f"listing {citation.listing_id or 'not provided'}.",
                    "ListBullet",
                )
                for citation in document.citations
            )
        else:
            paragraphs.append(cls._paragraph("No source references were supplied."))
        return "".join(paragraphs)

    @staticmethod
    def _paragraph(text: object, style: str | None = None) -> str:
        style_xml = f'<w:pStyle w:val="{style}"/>' if style is not None else ""
        return (
            f'<w:p><w:pPr>{style_xml}</w:pPr><w:r><w:t xml:space="preserve">'
            f"{xml_escape(str(text))}</w:t></w:r></w:p>"
        )

    @staticmethod
    def _page_break() -> str:
        return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'

    @staticmethod
    def _document_xml(body: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}"
            '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/>'
            "</w:sectPr></w:body></w:document>"
        )

    @staticmethod
    def _styles_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
            '<w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/>'
            '<w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:rPr><w:sz w:val="28"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
            '<w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/>'
            '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>'
            "</w:style></w:styles>"
        )

    @staticmethod
    def _content_types_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="'
            'application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="'
            'application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        )

    @staticmethod
    def _package_relationships_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="'
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="'
            "http://schemas.openxmlformats.org/package/2006/relationships/metadata/"
            'core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="'
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
            'extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _document_relationships_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="'
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _core_properties_xml(title: str, generated: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="'
            'http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{xml_escape(title)}</dc:title>"
            "<dc:creator>Agentic Financial Intelligence Platform</dc:creator>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{xml_escape(generated)}</dcterms:created>'
            "</cp:coreProperties>"
        )

    @staticmethod
    def _app_properties_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="'
            'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Agentic Financial Intelligence Platform</Application>"
            "</Properties>"
        )
