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

    def test_resolve_company_depends_on_port_not_concrete_catalog(self) -> None:
        resolve_path = APPLICATION_ROOT / "resolve_company.py"
        imports = _imported_modules(resolve_path)
        self.assertTrue(
            any(
                name.endswith("ports") or name == "financial_intelligence.application.ports"
                for name in imports
            )
            or "financial_intelligence.application.ports" in imports
        )
        self.assertFalse(
            any("infrastructure" in name for name in imports),
            msg="ResolveCompany must not import infrastructure adapters",
        )
        self.assertFalse(
            any("InMemoryCompanyCatalog" in resolve_path.read_text(encoding="utf-8") for _ in [0]),
        )
        source = resolve_path.read_text(encoding="utf-8")
        self.assertIn("CompanyCatalogPort", source)
        self.assertNotIn("InMemoryCompanyCatalog", source)
        self.assertNotIn("build_reference_companies", source)

    def test_market_snapshot_depends_on_port_not_concrete_adapter(self) -> None:
        snapshot_path = APPLICATION_ROOT / "market_snapshot.py"
        source = snapshot_path.read_text(encoding="utf-8")
        imports = _imported_modules(snapshot_path)
        self.assertIn("MarketDataPort", source)
        self.assertTrue(
            any(
                name.endswith("ports") or name == "financial_intelligence.application.ports"
                for name in imports
            )
        )
        self.assertFalse(any("infrastructure" in name for name in imports))
        self.assertNotIn("InMemoryMarketDataAdapter", source)
        self.assertNotIn("build_reference_market_series", source)

    def test_financial_snapshot_depends_on_port_not_concrete_adapter(self) -> None:
        snapshot_path = APPLICATION_ROOT / "financial_snapshot.py"
        source = snapshot_path.read_text(encoding="utf-8")
        imports = _imported_modules(snapshot_path)
        self.assertIn("FinancialDataPort", source)
        self.assertTrue(
            any(
                name.endswith("ports") or name == "financial_intelligence.application.ports"
                for name in imports
            )
        )
        self.assertFalse(any("infrastructure" in name for name in imports))
        self.assertNotIn("InMemoryFinancialDataAdapter", source)

    def test_news_event_snapshot_depends_on_port_not_concrete_adapter(self) -> None:
        snapshot_path = APPLICATION_ROOT / "news_event_snapshot.py"
        source = snapshot_path.read_text(encoding="utf-8")
        imports = _imported_modules(snapshot_path)
        self.assertIn("NewsEventPort", source)
        self.assertTrue(
            any(
                name.endswith("ports") or name == "financial_intelligence.application.ports"
                for name in imports
            )
        )
        self.assertFalse(any("infrastructure" in name for name in imports))
        self.assertNotIn("InMemoryNewsEventAdapter", source)

    def test_industry_and_regulatory_snapshots_depend_on_ports(self) -> None:
        for filename, port_name, forbidden_adapter in (
            ("industry_snapshot.py", "IndustryContextPort", "InMemoryIndustryAdapter"),
            ("regulatory_snapshot.py", "RegulatoryEventPort", "InMemoryRegulatoryAdapter"),
        ):
            snapshot_path = APPLICATION_ROOT / filename
            source = snapshot_path.read_text(encoding="utf-8")
            imports = _imported_modules(snapshot_path)
            self.assertIn(port_name, source)
            self.assertTrue(
                any(
                    name.endswith("ports") or name == "financial_intelligence.application.ports"
                    for name in imports
                )
            )
            self.assertFalse(any("infrastructure" in name for name in imports))
            self.assertNotIn(forbidden_adapter, source)

    def test_create_research_plan_depends_on_resolve_and_planner_port(self) -> None:
        path = APPLICATION_ROOT / "create_research_plan.py"
        source = path.read_text(encoding="utf-8")
        imports = _imported_modules(path)
        self.assertIn("ResolveCompany", source)
        self.assertIn("PlannerPort", source)
        self.assertNotIn("DeterministicPlanner", source)
        self.assertNotIn("DeterministicPlannerAdapter", source)
        self.assertFalse(any("infrastructure" in name for name in imports))
        self.assertNotIn("InMemoryCompanyCatalog", source)

    def test_deterministic_planner_adapter_lives_in_infrastructure_and_is_provider_free(
        self,
    ) -> None:
        path = (
            PACKAGE_ROOT / "infrastructure" / "orchestration" / "deterministic_planner_adapter.py"
        )
        self.assertTrue(path.is_file())
        imports = _imported_modules(path)
        self.assertFalse(
            any(
                any(token in name.lower() for token in ("openrouter", "openai", "llm", "http"))
                for name in imports
            ),
            msg="DeterministicPlannerAdapter must not import LLM/provider/HTTP modules",
        )
        # The adapter may depend inward (application/domain) but never on composition/api.
        self.assertFalse(
            any(
                name.startswith(
                    ("financial_intelligence.composition", "financial_intelligence.api")
                )
                for name in imports
            )
        )

    def test_execute_research_plan_depends_on_ports_not_adapters(self) -> None:
        path = APPLICATION_ROOT / "execute_research_plan.py"
        source = path.read_text(encoding="utf-8")
        imports = _imported_modules(path)
        self.assertIn("CreateResearchPlan", source)
        self.assertFalse(any("infrastructure" in name for name in imports))
        self.assertNotIn("Phase6CapabilityExecutor", source)
        self.assertNotIn("GetMarketSnapshot", source)

    def test_workflow_use_cases_depend_on_store_port_not_adapter(self) -> None:
        for filename in ("create_research_workflow.py", "manage_research_workflow.py"):
            path = APPLICATION_ROOT / filename
            source = path.read_text(encoding="utf-8")
            imports = _imported_modules(path)
            self.assertIn("ResearchWorkflowStorePort", source)
            self.assertFalse(any("infrastructure" in name for name in imports))
            self.assertNotIn("InMemoryResearchWorkflowStore", source)

    def test_research_synthesis_depends_on_domain_policy_not_adapters(self) -> None:
        path = APPLICATION_ROOT / "generate_research_synthesis.py"
        source = path.read_text(encoding="utf-8")
        imports = _imported_modules(path)
        self.assertIn("ResolveCompany", source)
        self.assertIn("DeterministicSynthesisAssembler", source)
        self.assertFalse(any("infrastructure" in name for name in imports))
        self.assertNotIn("FastAPI", source)

    def test_research_orchestrator_depends_on_planner_port_not_adapter(self) -> None:
        path = APPLICATION_ROOT / "research_orchestrator.py"
        source = path.read_text(encoding="utf-8")
        imports = _imported_modules(path)
        self.assertIn("PlannerPort", source)
        self.assertIn("CreateResearchWorkflow", source)
        self.assertFalse(any("infrastructure" in name for name in imports))
        # A concrete adapter (stub or future LLM-backed) may be *mentioned* in
        # prose/docstrings, but must never be imported or instantiated here.
        self.assertNotIn("import UnavailablePlannerAdapter", source)
        self.assertNotIn("UnavailablePlannerAdapter()", source)
        self.assertNotIn("OpenRouterAdapter", source)

    def test_planner_port_carries_no_provider_specific_types(self) -> None:
        path = APPLICATION_ROOT / "ports.py"
        source = path.read_text(encoding="utf-8")
        imports = _imported_modules(path)
        self.assertIn("class PlannerPort", source)
        # No provider-specific module may ever be imported into ports.py —
        # "OpenRouter" appearing in a docstring's flow diagram is fine.
        self.assertFalse(any("openrouter" in name.lower() for name in imports))
        self.assertFalse(any("openai" in name.lower() for name in imports))
        self.assertFalse(
            any(name.startswith("financial_intelligence.infrastructure") for name in imports)
        )

    def test_meta_step_type_is_not_registered_in_capability_registry(self) -> None:
        registry_path = APPLICATION_ROOT / "capability_registry.py"
        source = registry_path.read_text(encoding="utf-8")
        self.assertNotIn("MetaStepType", source)
        self.assertNotIn("PLAN = ", source)
        self.assertNotIn("EVIDENCE_COLLECTION", source)
        self.assertNotIn("CRITIQUE", source)
        self.assertNotIn("SYNTHESIS", source)
