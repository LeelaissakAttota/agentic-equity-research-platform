"""Phase 9 architecture, report-port, and scope freeze tests."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Protocol

import pytest

from financial_intelligence.application.reporting_ports import ResearchReportGeneratorPort
from financial_intelligence.domain.report import (
    ReportArtifact,
    ReportArtifactStatus,
    ReportFormat,
    ResearchReportGenerationRequest,
)
from financial_intelligence.domain.synthesis import LanguagePreference, SynthesisId

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "financial_intelligence"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _synthesis_id() -> SynthesisId:
    return SynthesisId.from_components(
        research_run_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        company_id="22222222-2222-4222-8222-222222222001",
        claim_ids=("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",),
    )


def test_report_generation_contract_declares_bounded_formats_and_renderer() -> None:
    request = ResearchReportGenerationRequest(
        synthesis_id=_synthesis_id(),
        report_format=ReportFormat.STRUCTURED_JSON,
        language=LanguagePreference(),
        title="Apple Research Report",
    )
    assert request.report_format is ReportFormat.STRUCTURED_JSON
    assert ReportFormat.MARKDOWN.value == "markdown"
    assert ReportFormat.DOCX.value == "docx"
    renderer = PACKAGE / "infrastructure" / "reporting" / "deterministic.py"
    assert renderer.exists()
    source = renderer.read_text(encoding="utf-8").lower()
    assert "_docx_content" in source
    assert "open(" not in source
    assert "write_text(" not in source


def test_ready_report_artifact_requires_content_or_locator() -> None:
    with pytest.raises(ValueError, match="requires content or locator"):
        ReportArtifact(
            artifact_id="artifact-1",
            synthesis_id=_synthesis_id(),
            report_format=ReportFormat.MARKDOWN,
            status=ReportArtifactStatus.READY,
            media_type="text/markdown",
        )


def test_report_generator_is_an_application_port_protocol() -> None:
    assert issubclass(ResearchReportGeneratorPort, Protocol)
    imports = _imports(PACKAGE / "application" / "reporting_ports.py")
    assert not any("infrastructure" in name for name in imports)


def test_synthesis_domain_has_no_framework_provider_or_report_library_imports() -> None:
    forbidden = {
        "fastapi",
        "pydantic",
        "httpx",
        "openai",
        "langgraph",
        "langchain",
        "docx",
        "reportlab",
        "financial_intelligence.infrastructure",
    }
    violations: list[str] = []
    for path in (PACKAGE / "domain" / "synthesis").glob("*.py"):
        for imported in _imports(path):
            if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden):
                violations.append(f"{path.name}:{imported}")
    assert violations == []


def test_synthesis_application_has_no_concrete_infrastructure_dependency() -> None:
    path = PACKAGE / "application" / "generate_research_synthesis.py"
    imports = _imports(path)
    assert not any("infrastructure" in name for name in imports)
    source = path.read_text(encoding="utf-8")
    assert "ResolveCompany" in source
    assert "DeterministicSynthesisAssembler" in source


def test_phase9_foundation_has_no_runtime_model_or_external_call_surface() -> None:
    paths = [
        *(PACKAGE / "domain" / "synthesis").glob("*.py"),
        PACKAGE / "application" / "generate_research_synthesis.py",
        PACKAGE / "api" / "routes" / "synthesis.py",
    ]
    joined = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    for marker in (
        "openrouter",
        "chatopenai",
        "langgraph",
        "langchain",
        "requests.get",
        "httpx",
        "subprocess",
        "eval(",
        "exec(",
    ):
        assert marker not in joined
