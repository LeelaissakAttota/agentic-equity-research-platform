# Agentic Financial Intelligence & Equity Research Platform

Production-oriented, evidence-first equity research infrastructure for publicly listed companies in India and the United States.

> **Current status:** Phase 6 — COMPLETE (Autonomous Research Planning & Dynamic Orchestration). Phase 0–5 are complete. Deterministic planning + controlled create-and-execute orchestration ship without LangGraph or an LLM planner (`POST /research/plans`, `POST /research/execute`). Phase 7+ (RAG, reports, Streamlit, MCP, trading) are **not started** and await owner authorization.

## Vision

The completed platform will turn conversational research requests into traceable research runs. It will resolve companies, plan and monitor specialist work, collect source evidence, verify important claims, preserve contradictions, synthesize findings, support follow-up questions, and produce multilingual answers and professional Microsoft Word reports.

## Why this project exists

Most stock chat experiences optimize for fluent answers. This platform is designed for research that can be inspected: every material claim should resolve to time-aware evidence, authoritative sources should outrank convenience sources, conflicts should remain visible, and incomplete research should stop transparently instead of becoming confident prose.

It is intended as a production-oriented AI engineering portfolio project demonstrating bounded agent orchestration, deterministic financial computation, verification/reflection, retrieval governance, operational traceability, security, and cost control—not merely prompt chaining.

## What makes it agentic and different

The planned system will understand intent, resolve company identity, build a dependency-aware Research Plan, select only necessary specialist capabilities, execute independent tasks in parallel where safe, verify coverage and contradictions, and request bounded targeted re-research before synthesis. Major planned reasoning capabilities cover market, financial, filing, news/events, industry/competitors, regulatory developments, risk, verification/critic and synthesis.

Not every capability is an agent. Calculations, ticker/date/number validation, parsing, retrieval, caching, persistence, charts and report formatting remain deterministic software. Models interpret evidence; they do not become the evidence.

## Target markets

- **India:** NSE and BSE companies, with NSE/BSE/SEBI and company Investor Relations as authoritative-source priorities.
- **United States:** NASDAQ and NYSE companies, with SEC EDGAR and company Investor Relations as authoritative-source priorities.

Company Identity is provider-neutral and accounts for exchange, country, currency, share class, aliases and listing history; ticker alone is not treated as globally unique.

## Planned evidence and reliability loop

```text
request -> company resolution -> research plan -> bounded tasks
        -> sources and evidence -> verification -> critic
        -> targeted re-research when needed -> findings -> synthesis
        -> English/Telugu answer, charts/tables and future DOCX report
```

Each substantial execution will use a globally unique Research Run ID so plans, tasks, sources, evidence, model/tool calls, verification, conflicts, metrics, findings and artifacts remain traceable. Confidence is a transparent quality/coverage signal, not truth or investment advice.

The platform is designed around these constraints:

- evidence is authoritative; an LLM is never the source of truth;
- development targets zero external API and LLM cost;
- OpenRouter model selection is configuration-driven and restricted to free models;
- deterministic software performs calculations, validation, storage, and formatting;
- India (NSE/BSE) and the United States (NASDAQ/NYSE) are first-class markets;
- research remains separate from trade execution;
- REST is the first integration surface, with MCP planned later;
- the service remains independently deployable from JARVIS or any trading system.

## Free-model and token-efficiency strategy

OpenRouter is the planned model gateway, with `ALLOW_PAID_MODELS=false`, configuration-driven free model IDs, bounded retry/free fallback and no paid escalation. Large documents will be validated, parsed, normalized, deduplicated and retrieved before only relevant context is sent for reasoning. Even free-model token/latency/cache/cost telemetry remains observable.

## Planned delivery and interoperability

REST is the first programmatic interface. Streamlit is the planned initial portfolio UI; selected MCP capabilities and optional JARVIS interoperability come later. The primary generated report artifact will be professional Microsoft Word `.docx`. Research language is separated from presentation language, initially English and Telugu, so translation cannot change canonical numbers, currencies, dates, company identity or citations.

The platform supplies structured intelligence only. Broker/MT5 orders, trading credentials, position management and trading risk controls belong to a separate trading system.

## Implemented versus planned

| Implemented in Phase 0–3 Prompt 1 | Planned in later phases |
|---|---|
| Governance, Master Architecture, ADRs, phase gates and source/evidence/model/security contracts | Live market/filing providers and broader research capabilities |
| Typed settings, FastAPI factory, health/readiness/version, correlation, structured logging, API errors | LangGraph orchestration, OpenRouter calls, PostgreSQL/pgvector, Redis and research memory |
| Company identity/resolution + source metadata foundation | Financial/filing intelligence, news/events, verification/critic, synthesis |
| Fixture + optional opt-in Yahoo chart market observations, deterministic metrics, `GET /market/snapshot` with data origin | Streamlit, multilingual synthesis, charts and `.docx` report generation |

No unimplemented runtime capability is represented as working today. See `PROJECT_STATUS.md` for the authoritative gate.

## Architecture reference

The supplied master diagram is preserved at [docs/architecture/agentic-financial-intelligence-platform.png](docs/architecture/agentic-financial-intelligence-platform.png). It is a **target-state concept**, not a statement of currently implemented functionality. [ARCHITECTURE.md](ARCHITECTURE.md) defines the authoritative written boundaries and phase ownership.

## Repository map

```text
src/financial_intelligence/   Python package and future bounded modules
tests/                        Unit, integration, contract, and evaluation tests
docs/                         Architecture, decisions, reports, and development notes
scripts/                      Future bounded development/operations scripts
data/                         Local development data placeholder; content ignored
reports/                      Generated artifact placeholder; content ignored
```

Planned internal boundaries include API, application, domain, infrastructure, orchestration, providers, evidence, memory, verification, reporting, observability, security, and configuration. Empty boundaries do not imply implemented capabilities.

## Phase-gated development

Work proceeds only through the approved phases in [ROADMAP.md](ROADMAP.md) and [PHASES.md](PHASES.md). A phase may begin only after the preceding phase satisfies its tests and acceptance criteria and the project owner explicitly authorizes the next prompt/phase.

## Development baseline

- Python 3.12
- UTF-8 source and documentation
- `src` package layout
- pytest test layout
- Phase 1 runtime dependencies are limited to FastAPI, Pydantic, pydantic-settings, and Uvicorn
- Phase 2 Prompt 1 adds no new runtime dependencies (stdlib fuzzy matching only)

Create a local environment file from `.env.example`; never commit `.env` or real credentials.

```powershell
Copy-Item .env.example .env
python -m pip install -e ".[dev]"
python -m pytest
python -m uvicorn financial_intelligence.main:app --reload
```

Health checks:

- `GET /health` — process liveness
- `GET /ready` — foundation readiness
- `GET /version` — service metadata
- `GET /companies/resolve?q=...` — local deterministic company resolution (Phase 2 Prompt 1)
- `GET /market/snapshot?q=...` — market observations and deterministic metrics (Phase 3)
- `GET /financials/snapshot?q=...` — financial fundamentals and deterministic metrics (Phase 4)
- `GET /news/events/snapshot?q=...` — news/event snapshot with evidence refs and conflicts (Phase 5; fixture-first)
- `GET /industry/context/snapshot?q=...` — industry classification + competitor relationships (Phase 5; fixture-first)
- `GET /regulatory/events/snapshot?q=...` — regulatory events with authority/allegation labels (Phase 5; fixture-first)
- `POST /research/plans` — create deterministic research plan (Phase 6 Prompt 1; does not execute)
- `POST /research/execute` — create-and-execute a bounded plan synchronously (Phase 6 Prompt 2; plans not persisted)

See [CONTRIBUTING.md](CONTRIBUTING.md), [PROJECT_RULES.md](PROJECT_RULES.md), and [GIT_WORKFLOW.md](GIT_WORKFLOW.md) before changing the repository.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
