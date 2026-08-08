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
    """Confirm Phase 7+ and deferred frameworks were not introduced early."""

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
        """Phase 7+ RAG/report/trading markers must remain absent."""
        phase7_markers = (
            "verification_engine",
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
