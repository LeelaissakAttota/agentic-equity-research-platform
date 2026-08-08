"""Deterministic repository-baseline tests for Phase 0/1 control surfaces."""

from hashlib import sha256
from pathlib import Path
from tomllib import load
from unittest import TestCase

from financial_intelligence import __version__

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ARCHITECTURE_SHA256 = "c0f7b98d3b2c335828c58428d7c3b4abea00cfbf418fed5ed19d2a1427f2c83a"
REQUIRED_CONTROL_FILES = (
    "README.md",
    "PROJECT_RULES.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "PHASES.md",
    "AGENTS.md",
    "DATA_SOURCES.md",
    "MODEL_POLICY.md",
    "EVIDENCE_MODEL.md",
    "SECURITY_GUIDELINES.md",
    "TESTING_STRATEGY.md",
    "GIT_WORKFLOW.md",
    "CODING_STANDARDS.md",
    "DECISIONS.md",
    "DEPLOYMENT_PLAN.md",
    "PROJECT_STATUS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    ".env.example",
    ".gitignore",
)
BLANK_CONFIGURATION_FIELDS = (
    "OPENROUTER_API_KEY",
    "PRIMARY_FREE_MODEL",
    "FALLBACK_FREE_MODEL_1",
    "FALLBACK_FREE_MODEL_2",
    "DATABASE_URL",
    "REDIS_URL",
    "ALPHA_VANTAGE_API_KEY",
    "FINNHUB_API_KEY",
)
PHASE1_RUNTIME_DEPENDENCIES = {
    "fastapi>=0.115,<1",
    "pydantic>=2.10,<3",
    "pydantic-settings>=2.7,<3",
    "uvicorn[standard]>=0.34,<1",
}
FORBIDDEN_DEPENDENCY_FRAGMENTS = (
    "langgraph",
    "langchain",
    "openai",
    "openrouter",
    "streamlit",
    "psycopg",
    "pgvector",
    "redis",
    "mcp",
    "yfinance",
    "finnhub",
    "alpha-vantage",
)
FORBIDDEN_PHASE3PLUS_MODULE_NAMES = {
    "nse.py",
    "bse.py",
    "sebi.py",
    "edgar.py",
    "yahoo.py",
    "market_provider.py",
    "filing_provider.py",
    "news_provider.py",
    "openrouter.py",
    "model_router.py",
    "langgraph_workflow.py",
    "rag.py",
    "embeddings.py",
    "research_memory.py",
    "verification_engine.py",
    "critic.py",
    "synthesis.py",
    "docx_report.py",
    "streamlit_app.py",
    "mcp_server.py",
    "trading.py",
}


def _environment_example() -> dict[str, str]:
    """Return non-comment assignments from the safe example environment file."""

    assignments: dict[str, str] = {}
    content = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in content.splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", maxsplit=1)
            assignments[name] = value
    return assignments


class RepositoryBaselineTests(TestCase):
    """Protect approved repository control and phase boundaries."""

    def test_required_control_files_exist_and_are_not_empty(self) -> None:
        """Every mandatory control file should be present and meaningful."""

        for relative_path in REQUIRED_CONTROL_FILES:
            file_path = REPOSITORY_ROOT / relative_path
            with self.subTest(relative_path=relative_path):
                self.assertTrue(file_path.is_file())
                self.assertGreater(file_path.stat().st_size, 0)

    def test_project_and_package_versions_match(self) -> None:
        """The package export and project metadata should use one version."""

        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as pyproject_file:
            project_metadata = load(pyproject_file)

        dependencies = set(project_metadata["project"]["dependencies"])
        self.assertEqual(project_metadata["project"]["name"], "agentic-financial-intelligence")
        self.assertEqual(project_metadata["project"]["version"], __version__)
        self.assertEqual(dependencies, PHASE1_RUNTIME_DEPENDENCIES)
        joined = " ".join(dependencies).lower()
        for fragment in FORBIDDEN_DEPENDENCY_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, joined)

    def test_example_configuration_is_free_first_and_secret_free(self) -> None:
        """Secret/model placeholders stay blank and paid models stay disabled."""

        environment = _environment_example()

        self.assertEqual(environment["ALLOW_PAID_MODELS"], "false")
        for field in BLANK_CONFIGURATION_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(environment[field], "")

    def test_architecture_image_matches_the_approved_baseline(self) -> None:
        """The preserved architecture reference should not change accidentally."""

        image_path = (
            REPOSITORY_ROOT
            / "docs"
            / "architecture"
            / "agentic-financial-intelligence-platform.png"
        )
        actual_hash = sha256(image_path.read_bytes()).hexdigest()

        self.assertEqual(actual_hash, EXPECTED_ARCHITECTURE_SHA256)

    def test_phase_three_plus_runtime_modules_are_absent(self) -> None:
        """Live providers and Phase 3+ research modules must not exist yet."""

        package_root = REPOSITORY_ROOT / "src" / "financial_intelligence"
        present = {
            path.name
            for path in package_root.rglob("*.py")
            if path.name in FORBIDDEN_PHASE3PLUS_MODULE_NAMES
        }
        self.assertEqual(present, set())
