# Phase Specifications

Each phase is a contract. Scope may be refined through investigation, but expanding it or changing architecture requires owner approval and an entry in `DECISIONS.md`. “Accepted” means all acceptance criteria pass with evidence and the owner authorizes progression.

## Phase 0 — Project Constitution & Repository Bootstrap

**Objective:** Establish governance, target architecture, a safe repository, and an auditable development plan.

**Scope:** Inspect and initialize the repository; preserve supplied architecture material; define principles, boundaries, sources, evidence, security, model, test, Git, coding, deployment, and contribution policies; add minimal package/import health scaffolding.

**Deliverables:** Required root documentation; safe `.env.example` and `.gitignore`; architecture asset; initial directory boundaries; `pyproject.toml`; package version; health test; Git repository on `main`.

**Tests:** Documentation/file inventory; UTF-8 and link review; secret-pattern and ignore checks; TOML parse; package import/version test; pytest collection/execution; Git status/remote audit.

**Acceptance criteria:** Phase 0 Prompts 1–4 are owner accepted; constitution/architecture/contracts are frozen; complete validation passes; no credential or paid dependency exists; supplied files are preserved; no later-phase behavior is implemented; the first approved Git checkpoint exists on clean `main` and is pushed to the owner-configured remote.

**Out of scope:** APIs, UI, agents, provider clients, model calls, databases, cache operations, retrieval, reports, MCP, deployment.

**Dependencies:** Owner vision and supplied architecture diagram.

## Phase 1 — Core Application Foundation

**Objective:** Establish production-quality application infrastructure without implementing financial research intelligence.

### Phase 1 entry checklist

Phase 1 remains locked until all items are true:

- [x] Phase 0 Prompts 1, 2 and 3 are owner approved.
- [x] Phase 0 Prompt 4 and its validation/Git checkpoint are complete.
- [x] The first commit exists and `main` is clean.
- [x] The owner-configured GitHub remote exists and `main` was pushed successfully.
- [x] Master Architecture, Project Rules, Phase 1 scope and Phase 1 acceptance criteria are frozen.
- [x] Repository secret, paid-model, test, lint, type and architecture gates pass.
- [x] The owner explicitly authorizes Phase 1.

### In scope

- production package/module foundation and composition root;
- Pydantic v2/pydantic-settings configuration and environment loading with fail-closed validation;
- deterministic FastAPI application factory, lifecycle, health endpoint and readiness endpoint where meaningful;
- structured secret-safe logging, request/correlation identifiers and initial observability primitives;
- base exception taxonomy and standard versioned API error contract;
- dependency wiring and infrastructure-neutral persistence/cache ports;
- UUIDv4 `research_run_id` value/generator primitive and deterministic tests;
- application/version metadata endpoint where appropriate;
- Dockerfile and Docker Compose local foundation where appropriate, without business schemas/operations;
- test infrastructure, reproducible dependency/locking strategy and baseline CI workflow where appropriate;
- baseline security headers/settings appropriate to the initial HTTP service.

### Deliverables

Runnable versioned service skeleton; configuration contract; health/readiness and error contracts; composition root; structured logging/correlation foundation; UUIDv4 Research Run ID primitive; initial infrastructure-neutral ports; Docker/Compose development baseline; test/dependency/CI foundation; updated documentation and ADRs.

### Tests

Configuration success/failure and secret-redaction cases; deterministic app-factory/lifecycle tests; health/readiness/API error contracts; correlation/logging tests; dependency-boundary tests; Research Run ID tests if implemented; Docker/container smoke validation when tooling is available; unit/integration separation and CI-equivalent checks.

### Acceptance criteria

- [x] Application starts successfully in the documented development setup.
- [x] FastAPI application creation is deterministic and import-safe.
- [x] Health endpoint works; readiness accurately represents only implemented dependencies.
- [x] Configuration validates success/failure cases and paid-model policy remains fail-closed.
- [x] Secrets are never logged or returned in errors.
- [x] Structured logging and request/correlation ID behavior work if included.
- [x] Standard API error and application version contracts work.
- [x] Application lifecycle and dependency composition are testable.
- [x] Domain imports contain no framework, provider or infrastructure dependencies.
- [x] Docker image builds and container health passes when Docker is available and included.
- [x] Unit and applicable integration/contract tests pass.
- [x] Ruff formatting/linting and strict mypy pass.
- [x] Security, dependency and documentation baselines pass.
- [x] No Phase 2 or later capability exists.
- [x] Git checkpoint created and pushed under Phase 1 Prompt 4 authorization.

### Explicitly out of scope

- company resolution or provider-specific company mappings;
- market/financial/filing/news/industry/regulatory/risk data or analysis;
- SEC, NSE, BSE, SEBI, Yahoo Finance, Alpha Vantage or Finnhub clients;
- OpenRouter calls, model routing, research agents or LangGraph research workflows;
- RAG, embeddings, pgvector business operations, research memory or evidence persistence;
- verification/critic implementation, report generation or Streamlit research UI;
- MCP, JARVIS or trading integration.

**Dependencies:** Accepted Phase 0 and approved Phase 1 ADRs.

## Phase 2 — Company Resolution & Source Foundation

**Objective:** Resolve company intent to canonical identities and establish governed source acquisition.

**Scope:** India/US company identity model; ticker/exchange/country normalization; ambiguity handling; source/provider ports; HTTP safety/rate-limit foundation; raw-source metadata/storage contracts; authoritative source discovery prototypes.

**Deliverables:** Company resolver, canonical identifiers, replaceable source adapters selected through investigation, acquisition policies, source registry, fixtures, and provider contract tests.

**Tests:** Known and ambiguous company resolution, ticker collisions, exchange/country validation, provider timeouts/rate limits/malformed responses, content limits, provenance completeness, offline fixtures.

**Acceptance criteria:**

- [x] Representative NSE/BSE/NASDAQ/NYSE identities resolve or return actionable ambiguity (fixture-backed offline resolver).
- [x] Source metadata is traceable (SourceMetadata + authority tiers + entity linkage).
- [~] Authoritative sources are prioritized — **DEFERRED BY DESIGN** for live acquisition; tier contracts exist (ADR-019) without live fetch/prioritization runtime.
- [~] Provider failures do not fabricate results — **DEFERRED BY DESIGN**; no live providers in authorized Phase 2 Prompt 1–4 scope.
- [x] Git checkpoint created and pushed under Phase 2 Prompt 4 authorization for the identity/source-foundation scope.

**Authorized Phase 2 Prompt 1–4 completion status:** COMPLETE for identity + source-foundation contracts. Live provider acquisition, HTTP rate-limit stacks, discovery prototypes, and complete market universes remain deferred future work and must not be treated as implemented.

**Out of scope:** Full market analysis, statement extraction, autonomous plans, embeddings, synthesis, reports.

**Dependencies:** Phase 1 service/config/observability foundations and provider terms investigation.

## Phase 3 — Market Intelligence

**Objective:** Produce traceable market datasets and deterministic market/valuation calculations.

**Scope:** Replaceable price/volume/history adapters; market calendars/time zones; corporate-action awareness; normalized market observations; selected statistics, indicators, and valuation metrics with explicit formulas.

**Deliverables:** Market intelligence use cases, normalized schemas, calculation library, cache/freshness policy, provider fallback behavior, evidence mapping, and API contracts appropriate to the phase.

**Tests:** Golden calculation cases, currencies/units/time zones, missing/stale data, splits/corporate actions where supported, provider conflicts, cache expiry, contract/integration fixtures.

**Acceptance criteria:** Calculations are reproducible and code-derived; every figure has as-of/source context; stale/conflicting values are visible; optional provider outage degrades safely.

**Authorized Phase 3 Prompt 1–4 completion status:** COMPLETE for Market Intelligence foundation (fixture + optional Yahoo chart live path, deterministic calculations, freshness/cache/fallback, explicit data origin). Documented limitations remain: live mode optional/default off; Yahoo is Tier-2 not Tier-1; no full holiday calendar; no full corporate-action engine; valuation multiples deferred to Phase 4 fundamentals; multi-provider conflict comparison beyond fallback provenance is limited.

**Out of scope:** Financial statements, filing parsing, broad qualitative research, autonomous orchestration, report generation.

**Dependencies:** Accepted Phase 2 identities, provider abstractions, and source provenance.

## Phase 4 — Financial & Filing Intelligence

**Objective:** Acquire, parse, normalize, and analyze authoritative filings and financial statements.

**Scope:** SEC and selected Indian filing paths; annual/quarterly reports and disclosures; safe document parsing; normalized income statement/balance sheet/cash flow concepts; deterministic ratios, trends, period/unit mapping.

**Deliverables:** Filing registry/adapters, document pipeline, statement models, calculation definitions, filing/financial intelligence use cases, evidence links, representative fixtures.

**Tests:** Parser safety and limits, form/report types, period/currency/unit consistency, restatements/amendments, ratio goldens, missing values, table extraction quality, authoritative-source precedence.

**Acceptance criteria:** Supported filings retain document provenance; normalized numbers reconcile within documented tolerances; amendments/conflicts remain explicit; no model performs arithmetic.

**Authorized Phase 4 Prompt 1–4 completion status:** COMPLETE for Financial & Filing Intelligence foundation (fixture fundamentals + optional SEC companyfacts live path, deterministic calculations with omissions, conflict handling, cache/fallback, explicit data origin, India fixture/authority foundation). Documented limitations remain: live SEC optional/default off and demo-scale; India live adapters deferred; valuation multiples deferred (ADR-030); TTM not implemented; fixture coverage is representative, not exhaustive.

**Out of scope:** Full news/industry/regulatory research, autonomous planner, vector memory, final Word reports.

**Dependencies:** Accepted Phase 3 plus safe source/document foundations.

## Phase 5 — News, Events, Industry & Regulatory Intelligence

**Objective:** Add source-grounded qualitative context and risk-relevant developments.

**Scope:** News/events, company announcements, investments/projects, industry/competitor context, government/regulatory developments, evidence-based sentiment; deduplication and temporal/event normalization.

**Deliverables:** Provider-neutral qualitative research capabilities, event taxonomy, source authority rules by claim type, competitor selection policy, sentiment/risk evidence contracts, evaluation corpus.

**Tests:** Event/date/entity extraction, duplication, source reliability, regulator precedence, conflicting coverage, prompt-injection resistance, sentiment grounding, unavailable/partial sources.

**Acceptance criteria:** Each material qualitative claim cites evidence; opinion is labeled; events are time-aware; general web never overrides authoritative records silently; incomplete coverage is disclosed.

**Authorized Phase 5 Prompt 1–4 completion status:** COMPLETE for News, Events, Industry & Regulatory Intelligence foundation (fixture-first news/events with conflict-aware dedupe, industry/competitor foundation, regulatory foundation, evidence/provenance, three snapshot APIs). Documented limitations remain: no live qualitative HTTP; no LLM sentiment; demo-scale fixtures; incomplete taxonomy; illustrative regulatory corpus; dedicated Risk agent and RAG/graph persistence deferred. Phase 6 remains not started and awaits explicit owner authorization.

**Out of scope:** Fully autonomous dynamic planning, persistent vector memory, critic loop, report layout.

**Dependencies:** Accepted Phase 4 evidence/source foundations and source terms review.

## Phase 6 — Autonomous Research Planning & Dynamic Orchestration

**Objective:** Convert user intent into bounded, dependency-aware research execution.

**Scope:** Intent engine, research planner, task graph, capability/tool selection, execution monitor, concurrency controls, budgets, cancellation, retries, free-model routing integration, graceful degradation.

**Deliverables:** LangGraph workflow(s), typed plan/task/state contracts, research-run event lifecycle, deterministic-versus-model routing rules, recovery policies, trace views, orchestration evaluations.

**Tests:** Intent/plan fixtures, dependency ordering, parallel execution, cancellation/timeouts, 429/outages/malformed model output, free fallback sequence, budget exhaustion, resumability/idempotency as designed.

**Acceptance criteria:** Plans select only needed capabilities; executions remain bounded and traceable; no paid model can be routed; failures produce transparent partial status; deterministic work bypasses models.

**Authorized Phase 6 Prompt 1–4 completion status:** COMPLETE for Autonomous Research Planning & Dynamic Orchestration foundation (deterministic planner, task DAG, controlled synchronous execution through Phase 2–5 capabilities, budgets/retries/cancellation, evidence aggregation, `POST /research/plans` + `POST /research/execute`). Documented limitations remain: no LangGraph; no LLM planner; no plan persistence/resume; sequential execution only; external-call accounting is executor-invocation based; no investment synthesis; demo-scale fixtures.

**Authorized Phase 7 Prompt 1 status:** OWNER APPROVED.

**Authorized Phase 7 Prompt 2 status:** COMPLETE / OWNER APPROVED — hardening + structured Research Memory + watchlists/monitoring foundation + notification contracts + report-request contract + dashboard list API. RAG/vector memory remain deferred.

**Authorized Phase 7 Prompt 3 status:** OWNER APPROVED — final acceptance audit complete; no blocking gaps; ready for release checkpoint.

**Authorized Phase 7 Prompt 4 status:** COMPLETE — release validation, documentation closure, Git checkpoint, push verified.

**Out of scope:** Full evidence graph/vector memory, final critic loop, multilingual reports, MCP exposure.

**Dependencies:** Accepted specialist capabilities from Phases 2–5 and approved model/orchestration contracts.

## Phase 7 — Evidence Graph, RAG & Research Memory

**Objective:** Persist governed claim/source relationships, enable hybrid retrieval, and support prior-research context.

**Scope:** Evidence graph representation; source/chunk integrity; pgvector embeddings and hybrid retrieval; research/company/session memory; retention and freshness; "what changed?" comparison foundation.

**Owner-authorized Prompt 1 amendment:** Before RAG/embeddings work, Prompt 1 establishes the autonomous workflow persistence/governance foundation (WorkflowId, lifecycle, checkpoint, approval, in-memory store, Phase 6 execution coordination). Workflow checkpoint state is **not** semantic Research Memory. RAG/vector memory remain later Phase 7 prompts.

**Deliverables:** Versioned persistence schema, migration, retrieval pipeline, embedding adapter, filters/authorization boundaries, memory policies, comparison primitives, data lineage tooling. (Prompt 1 delivers workflow foundation only.)

**Tests:** Migration/constraints, claim-evidence relationships, refutation/conflict edges, chunk traceability, hybrid retrieval relevance, isolation, freshness/retention, repeat-run and change-detection fixtures.

**Acceptance criteria:** Every retrieved chunk maps to a source and run; vector results cannot bypass filters; contradictions are preserved; prior context is distinguishable from current evidence; deletion/retention policy is enforceable.

**Out of scope:** Final verification scoring/critic loop, polished conversation, DOCX generation, MCP.

**Dependencies:** Accepted Phase 6 workflow and stable evidence contracts.

**Phase 7 completion status:** COMPLETE (Prompts 1–4).

**Authorized Phase 8 Prompt 1 status:** COMPLETE / OWNER APPROVED — deterministic typed verification foundation, explainable confidence factors, contradiction records, and targeted critic-request contracts.

## Phase 8 — Verification, Confidence & Reflection

**Objective:** Make important claims verifiable and research quality measurable before synthesis.

**Scope:** Source/number/date/freshness validation; contradiction detection; transparent confidence/quality factors; critic/reflection; sufficiency thresholds; bounded targeted re-research; unsupported-conclusion controls.

**Deliverables:** Verification engine, contradiction records, quality rubric, critic workflow, targeted research requests, evaluation datasets and failure reports.

**Tests:** Known true/false/conflicting/stale claims, unit/date mismatches, source hierarchy, confidence monotonicity, missing evidence, critic convergence and exhaustion, adversarial unsupported synthesis.

**Acceptance criteria:** Material claims expose verification and confidence context; scores are explainable; conflicts are not erased; critic requests are bounded/targeted; insufficient evidence cannot become definitive prose.

**Out of scope:** Final multilingual UX/report styling and MCP production exposure.

**Dependencies:** Accepted Phase 7 evidence/retrieval/memory foundation.

**Authorized Phase 8 Prompt 2 status:** COMPLETE / OWNER APPROVED — adversarial verification hardening, supporting-only confidence inputs, strict numeric metadata matching, non-finite value rejection, and 22-case verification coverage.

**Authorized Phase 8 Prompt 3 status:** COMPLETE / OWNER APPROVED — final technical acceptance audit and contract freeze passed with no blocking foundation gaps.

**Authorized Phase 8 Prompt 4 status:** COMPLETE — final validation, documentation closure, staged-content audit, one Phase 8 Git checkpoint, push, and synchronization verification. Phase 9 remains not started pending explicit owner authorization.

## Phase 9 — Conversational Research, Multilingual Output & Word Reports

**Objective:** Deliver verified research through follow-up conversation and professional artifacts.

**Scope:** Conversational context/history, follow-up and comparison requests, English/Telugu rendering, Streamlit portfolio client, charts/tables, versioned report model, professional `.docx` generation and citations.

**Deliverables:** Conversation use cases, language rendering/quality rules, Streamlit UI, accessible visuals, DOCX template/renderer, artifact registry, report and language evaluation fixtures.

**Tests:** Follow-up reference resolution, research-history isolation, Telugu factual invariance, numeric/citation preservation, chart goldens, DOCX content/layout/rendering, filename safety, incomplete-evidence presentation.

**Acceptance criteria:** Users can conduct supported follow-ups; English/Telugu outputs preserve canonical facts; reports contain required supported sections and citations; generated files render reliably; no report queries providers directly.

**Out of scope:** Trade execution, tight JARVIS coupling, unrestricted MCP exposure, unreviewed languages.

**Dependencies:** Accepted Phase 8 verified synthesis contracts.

**Authorized Phase 9 Prompt 1 status:** COMPLETE / OWNER APPROVED — deterministic verified-claim synthesis contracts and gate, stable sections, bounded executive-summary foundation, confidence/conflict/missing-data rendering, citation linkage, multilingual-ready preference contract, report-generation port/contracts, `GenerateResearchSynthesis`, one `POST /research/synthesis` endpoint, and offline Apple/Reliance/GOOG-GOOGL/hostile-content coverage. Scope contract: [PHASE_9_PROMPT_1_SCOPE.md](PHASE_9_PROMPT_1_SCOPE.md).

**Authorized Phase 9 Prompt 2 status:** COMPLETE / OWNER APPROVED — synthesis integrity hardening; explicit material-claim kinds and authority sufficiency; forged confidence/status and semantic-duplicate rejection; claim-aware freshness; preserved conflict/missing/provenance identity; deterministic stable JSON and inert Markdown rendering; optional report output through the existing endpoint; adversarial Apple/Reliance/GOOG-GOOGL, identity, injection, timestamp, URL, confidence, and architecture coverage. Scope contract: [PHASE_9_PROMPT_2_SCOPE.md](PHASE_9_PROMPT_2_SCOPE.md).

**Authorized Phase 9 Prompt 3 status:** COMPLETE / OWNER APPROVED — acceptance audit and semantic contract freeze; verification-bypass, conflict, degradation, cross-phase reuse, language, security, cost, deterministic-report, and Apple/Reliance golden audits; strict unknown-field API rejection; minimal deterministic in-memory DOCX package with safe filename/base64 transport and no new dependency. Acceptance matrix: [PHASE_9_ACCEPTANCE_MATRIX.md](PHASE_9_ACCEPTANCE_MATRIX.md). Final report: [PHASE_9_PROMPT_3_FINAL_REPORT.md](PHASE_9_PROMPT_3_FINAL_REPORT.md).

**Authorized Phase 9 Prompt 4 status:** COMPLETE / OWNER APPROVED — recovery, full/cross-phase regression, quality, architecture, phase, API, security, cost, configuration, documentation, and changed-tree classification gates passed. The owner reviewed the complete pre-release report and authorized the single intentional Phase 9 Git release checkpoint and verified non-force push. Report: [PHASE_9_PROMPT_4_PRE_RELEASE_REPORT.md](PHASE_9_PROMPT_4_PRE_RELEASE_REPORT.md).

Phase 9 is **COMPLETE**. Phase 10 is **NOT STARTED / AWAITING OWNER AUTHORIZATION**.

## Phase 10 — MCP/API Integration, Evaluation & Production Hardening

**Objective:** Validate deployability, expose approved integrations, and produce production-readiness evidence.

**Scope:** Mature REST contracts; selected MCP tools/resources; auth/rate limiting as deployment requires; load/reliability/security testing; observability dashboards; backup/recovery; deployment automation; comprehensive financial/evidence evaluations.

**Deliverables:** Versioned REST and MCP adapters, OpenAPI/contracts, deployment runbooks, threat review, SLOs, dashboards/alerts, recovery tests, evaluation scorecards, release checklist.

**Tests:** Contract/backward compatibility, auth/authorization, abuse/rate limits, load/soak/failure injection, secret scanning, dependency/container scanning, backup/restore, deployment rollback, end-to-end evaluation.

**Acceptance criteria:** Interfaces expose only approved application capabilities; reliability/security/evaluation thresholds pass; operations are documented; service remains independently deployable; production-readiness claims are evidence-backed.

**Out of scope:** Direct trading, guaranteed financial outcomes, paid-model fallback, mandatory paid data, coupling core domain to JARVIS.

**Dependencies:** Accepted Phase 9, target-environment decisions, and owner-approved production criteria.
