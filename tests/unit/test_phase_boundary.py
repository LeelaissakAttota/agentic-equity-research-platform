"""Phase-boundary absence checks for research intelligence capabilities."""

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
    """Confirm Phase 4+ research/agent capabilities were not introduced early."""

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

    def test_phase4_filing_intelligence_not_started(self) -> None:
        filing_markers = ("sec edgar", "10-k parser", "income_statement", "balance_sheet")
        violations: list[str] = []
        for path in PACKAGE.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for marker in filing_markers:
                if marker in text:
                    violations.append(f"{path.relative_to(ROOT)}:{marker}")
        self.assertEqual(violations, [])
