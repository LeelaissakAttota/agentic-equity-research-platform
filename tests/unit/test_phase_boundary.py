"""Phase-boundary absence checks for later-phase capabilities."""

from __future__ import annotations

from pathlib import Path
from tomllib import load
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "financial_intelligence"

FORBIDDEN_CONTENT_MARKERS = (
    "langgraph",
    "ChatOpenAI",
    "openrouter.ai",
    "streamlit",
    "MetaTrader",
    "pgvector",
)


class PhaseBoundaryTests(TestCase):
    """Confirm only owner-authorized phase capabilities are present."""

    def test_no_forbidden_runtime_dependencies(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            metadata = load(handle)
        joined = " ".join(metadata["project"]["dependencies"]).lower()
        for marker in ("langgraph", "langchain", "openai", "streamlit", "redis", "psycopg"):
            self.assertNotIn(marker, joined)

    def test_source_tree_has_no_forbidden_markers(self) -> None:
        violations: list[str] = []
        for path in PACKAGE.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for marker in FORBIDDEN_CONTENT_MARKERS:
                if marker.lower() in text:
                    violations.append(f"{path.relative_to(ROOT)}:{marker}")
        self.assertEqual(violations, [])

    def test_phase7_rag_and_later_not_started(self) -> None:
        """RAG/report/trading markers must remain absent.

        Phase 7 introduced workflow foundation modules and Phase 8 introduced
        deterministic verification, but RAG, reports, UI, and trading stay locked.
        """
        phase7_markers = (
            "synthesis agent",
            "embedding_pipeline",
            "docx_report",
            "streamlit_app",
            "pgvector_store",
            "broker_execution",
        )
        violations: list[str] = []
        for path in PACKAGE.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for marker in phase7_markers:
                if marker in text:
                    violations.append(f"{path.relative_to(ROOT)}:{marker}")
        self.assertEqual(violations, [])

    def test_phase8_verification_foundation_is_present(self) -> None:
        """The authorized deterministic verification foundation must remain wired."""
        verification_module = PACKAGE / "domain" / "verification" / "engine.py"
        composition = (PACKAGE / "composition" / "__init__.py").read_text(encoding="utf-8")

        self.assertTrue(verification_module.is_file())
        self.assertIn("VerificationEngine", composition)
        self.assertIn("VerifyClaimUseCase", composition)
