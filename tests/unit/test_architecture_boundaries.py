"""Architecture boundary tests for Phase 1."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "financial_intelligence"
DOMAIN_ROOT = PACKAGE_ROOT / "domain"
APPLICATION_ROOT = PACKAGE_ROOT / "application"

FORBIDDEN_DOMAIN_IMPORT_PREFIXES = (
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "pydantic_settings",
    "openai",
    "langgraph",
    "langchain",
    "redis",
    "psycopg",
    "sqlalchemy",
    "streamlit",
    "mcp",
    "financial_intelligence.api",
    "financial_intelligence.infrastructure",
    "financial_intelligence.composition",
    "financial_intelligence.config",
    "financial_intelligence.observability",
    "financial_intelligence.security",
)

FORBIDDEN_APPLICATION_IMPORT_PREFIXES = (
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "financial_intelligence.api",
    "financial_intelligence.infrastructure",
    "financial_intelligence.composition",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


class ArchitectureBoundaryTests(TestCase):
    """Ensure dependency direction stays within the frozen architecture."""

    def test_domain_modules_do_not_import_forbidden_packages(self) -> None:
        violations: list[str] = []
        for path in DOMAIN_ROOT.rglob("*.py"):
            for name in _imported_modules(path):
                if any(
                    name == prefix or name.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_DOMAIN_IMPORT_PREFIXES
                ):
                    violations.append(f"{path.name}:{name}")
        self.assertEqual(violations, [])

    def test_application_modules_do_not_import_delivery_adapters(self) -> None:
        violations: list[str] = []
        for path in APPLICATION_ROOT.rglob("*.py"):
            for name in _imported_modules(path):
                if any(
                    name == prefix or name.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_APPLICATION_IMPORT_PREFIXES
                ):
                    violations.append(f"{path.name}:{name}")
        self.assertEqual(violations, [])
