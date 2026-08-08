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
        """RAG/report/trading/verification markers must remain absent.

        Phase 7 Prompt 1 may introduce workflow foundation modules, but must not
        introduce embeddings, vector stores, report generators, or Phase 8 engines.
        """
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

    def test_phase8_verification_not_started(self) -> None:
        phase8_markers = (
            "verification_engine",
            "critic_workflow",
            "confidence_rubric",
            "reflection_loop",
        )
        violations: list[str] = []
        for path in PACKAGE.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for marker in phase8_markers:
                if marker in text:
                    violations.append(f"{path.relative_to(ROOT)}:{marker}")
        self.assertEqual(violations, [])
