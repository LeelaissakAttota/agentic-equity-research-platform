# Agentic Financial Intelligence & Equity Research Platform

Production-oriented, evidence-first equity research infrastructure for publicly listed companies in India and the United States.

> **Current status:** Phases 0–10 are complete and released. Phase 10 Prompts 1–4 are owner approved. Versioned REST, selected MCP, deterministic evaluations, bounded local reliability/load, threat/operations, rollback, local deployment, and supply-chain evidence (local SBOM and Trivy container scan) all pass. Production auth/rate decisions remain deployment-dependent. Phase 11 is locked and undefined.

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

| Implemented through Phase 10 Prompt 3A | Planned/required before Phase 10 closure |
|---|---|
| Governance, Master Architecture, ADRs, phase gates and source/evidence/model/security contracts | Live market/filing providers and broader research capabilities |
| Typed settings, fail-closed production host/header/body/correlation policy, safe telemetry, legacy REST plus selected `/v1` aliases, and minimal read-only/offline MCP facade | Approved dependency/container vulnerability scan and SBOM evidence; target-deployment auth/rate decisions remain deferred |
| Company resolution; market, financial, news/event, industry, and regulatory foundations; deterministic research planning/execution and governed workflows | Broader live provider coverage and production-grade durable persistence |
| Structured in-memory research history/watchlists; deterministic verification/synthesis/reporting; bounded offline production evaluations; local reliability/load, threat, SLO/runbook, deployment, and rollback evidence | Follow-up conversation, evaluated English/Telugu narrative rendering, charts, Streamlit, advanced report templates, and durable artifact storage |

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

For ordered continuation context and prompt-level evidence, see [PHASE_HISTORY.md](PHASE_HISTORY.md). `PROJECT_STATUS.md` remains authoritative for the current gate.

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
- `POST /research/plans` — create deterministic research plan (Phase 6; does not execute)
- `POST /research/execute` — create-and-execute a bounded plan synchronously (Phase 6; plans not persisted)
- `POST /research/synthesis` — verify supplied typed claim evidence and return deterministic evidence-linked synthesis, optionally with an in-memory structured JSON, safe Markdown, or base64 DOCX report (Phase 9 Prompts 1–3; no LLM, translation, report-side fetching, or file writes)
- `POST /research/workflows` — create a persistent research workflow (Phase 7; in-memory store)
- `GET /research/workflows` — bounded dashboard listing (`limit`/`offset`/`status_filter`/`company_id`)
- `GET /research/workflows/{workflow_id}` — load workflow status/result
- `POST /research/workflows/{workflow_id}/execute|pause|resume|cancel|approval` — govern execution
- `GET /research/workflows/{workflow_id}/memory` — structured research-memory records
- `POST /research/workflows/{workflow_id}/report` — report-request contract (rendering deferred)
- `POST /watchlists`, `GET /watchlists/{id}`, `POST /watchlists/{id}/checks` — watchlist + explicit monitoring check

Phase 10 Prompt 1 production settings:

- `ALLOWED_HOSTS` — comma-separated production host allowlist; wildcard, empty, malformed values, and production `DEBUG` logging fail closed.
- `API_MAX_REQUEST_BODY_BYTES` — whole-request limit from 4 KiB through 10 MiB; default 1 MiB. Declared and chunked oversized bodies receive a safe `413` response.
- Production request logs contain correlation ID, route template, method, status category/code, and duration only. Bodies, query values, exception messages, stack traces, credentials, and secrets are not emitted.
- Authentication and rate limiting are deferred until a target deployment and enforcement policy are owner-approved.

Phase 10 Prompt 2 hardening rejects duplicate/ambiguous Host, Content-Length, and correlation headers; malformed host ports; excessive chunk counts; secret-bearing HTTP exception details; and unbounded watchlist/memory collection requests. Prompt 3 freezes these contracts and additionally fails closed on Host outer whitespace/control, extreme numeric Host/Content-Length values, and whitespace/control correlation IDs. Prompt 3A adds the approved `/v1` aliases, a static two-capability MCP facade, offline evaluations, bounded local reliability/load evidence, threat/operations guidance, and local deployment/rollback evidence. See [the Prompt 3A blocker matrix](PHASE_10_BLOCKING_GAPS_MATRIX.md); supply-chain scan/SBOM evidence remains blocking.

See [CONTRIBUTING.md](CONTRIBUTING.md), [PROJECT_RULES.md](PROJECT_RULES.md), and [GIT_WORKFLOW.md](GIT_WORKFLOW.md) before changing the repository.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
