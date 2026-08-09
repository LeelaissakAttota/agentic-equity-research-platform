# Architectural Decision Record Index

Phase 0 decisions are summarized here in lightweight ADR form. Status is **Accepted for planning** unless noted; implementation validation occurs in the owning phase. New significant decisions append an ADR and do not silently rewrite prior rationale.

## ADR-001 — Python 3.12

**Decision:** Target Python 3.12 for application and tooling.

**Rationale:** Modern typing/async capabilities, broad library support, and a stable production baseline.

**Consequences:** CI and containers must test 3.12; newer-version-only features are disallowed without a later ADR.

## ADR-002 — FastAPI API layer

**Decision:** Use FastAPI for the future REST interface.

**Rationale:** Typed async contracts and OpenAPI fit the planned Python service.

**Consequences:** FastAPI remains an outer adapter; the domain cannot depend on it.

## ADR-003 — LangGraph orchestration

**Decision:** Use LangGraph for future stateful agent/workflow orchestration.

**Rationale:** It supports explicit graphs, state, and controlled loops.

**Consequences:** Workflow state must be typed and observable; ordinary deterministic use cases need not use LangGraph.

## ADR-004 — PostgreSQL plus pgvector

**Decision:** Use PostgreSQL as canonical transactional storage and pgvector for governed embedding search.

**Rationale:** One durable platform can support relational integrity and initial vector retrieval.

**Consequences:** Vector rows must link to canonical sources/evidence; adopting a separate graph/vector database requires evidence and an ADR.

## ADR-005 — Redis caching

**Decision:** Use Redis for bounded cache and transient coordination.

**Rationale:** It supports low-latency caching and later coordination needs.

**Consequences:** Redis cannot be the sole durable source/evidence store; behavior must survive cache loss.

## ADR-006 — OpenRouter as LLM gateway

**Decision:** Route future model calls through OpenRouter behind an application port.

**Rationale:** A gateway permits configuration-driven free-model selection and fallbacks.

**Consequences:** Provider types cannot leak into domain code; gateway outages must degrade safely.

## ADR-007 — Free models only

**Decision:** Development uses models currently validated/configured as free.

**Rationale:** The project has a zero external API/LLM cost target.

**Consequences:** Model IDs stay in configuration and require current cost validation.

## ADR-008 — No automatic paid fallback

**Decision:** `ALLOW_PAID_MODELS=false` fails closed and no failure can escalate to paid capacity.

**Rationale:** Cost predictability is a hard invariant.

**Consequences:** Exhausted free routes yield explicit partial/failure states.

## ADR-009 — Evidence-first research

**Decision:** Sources, claims, evidence, time, verification, and contradictions are first-class domain concepts.

**Rationale:** An LLM is not a source of truth and financial conclusions require auditability.

**Consequences:** Material findings need resolvable evidence; unsupported conclusions are rejected or qualified.

## ADR-010 — Independent service architecture

**Decision:** Build an independently deployable modular service.

**Rationale:** Portfolio value and operational clarity require operation without JARVIS/trading dependencies.

**Consequences:** External ecosystems integrate through versioned interfaces.

## ADR-011 — REST first, MCP later

**Decision:** Establish REST before exposing selected capabilities through MCP.

**Rationale:** REST provides a familiar initial service contract; MCP can adapt mature use cases later.

**Consequences:** Neither interface defines core domain architecture.

## ADR-012 — Research does not execute trades

**Decision:** The platform supplies intelligence only and never places, authorizes, or routes trades.

**Rationale:** Research and execution carry distinct risk, compliance, and safety boundaries.

**Consequences:** Trading integration remains a separate consumer with its own controls.

## ADR-013 — English and Telugu initial presentation

**Decision:** Prioritize English and Telugu while separating evidence from presentation.

**Rationale:** Meets initial user needs without duplicating research pipelines.

**Consequences:** Renderers must preserve canonical numbers, names, dates, currencies, and citations; Hindi/others remain extensible.

## ADR-014 — Microsoft Word primary report artifact

**Decision:** Use `.docx` as the first professional generated report format through a versioned report model.

**Rationale:** It supports editable, portable professional reports.

**Consequences:** `python-docx` is planned; report rendering cannot acquire evidence directly.

## ADR-015 — Modular monolith initially

**Decision:** Begin as a cleanly bounded modular monolith, containerized with supporting PostgreSQL/pgvector and Redis services.

**Rationale:** This preserves separation without premature distributed-system cost.

**Consequences:** Module ports permit later extraction only when measured needs justify it.

## ADR-016 — MIT license for repository bootstrap

**Decision:** Apply the MIT License using “Project Contributors” as the copyright holder.

**Rationale:** A permissive portfolio-friendly default provides an explicit license.

**Consequences:** The owner may replace this before external distribution; third-party data/content retains its own terms.

## ADR-017 — Deterministic-first execution and token efficiency

**Decision:** Use deterministic software for calculation, validation, parsing, storage, retrieval and formatting; use models only for bounded reasoning needs after relevant evidence is retrieved.

**Rationale:** Deterministic work is more reproducible, testable and cost-efficient, especially under free-model rate/context limits.

**Consequences:** Whole documents are not sent to models by default; model calls require explicit context/token budgets and measurable justification.

## ADR-018 — UUIDv4 canonical Research Run ID

**Decision:** Use UUIDv4 as the canonical globally unique `research_run_id`, with explicit timestamps for ordering and optional derived human-readable labels.

**Rationale:** UUIDv4 is opaque, implementation-friendly in Python 3.12/PostgreSQL, globally unique and independent of local sequences.

**Consequences:** All important research objects and telemetry link directly or transitively to this identifier; generator/domain implementation belongs to Phase 1.

## ADR-019 — Tiered source authority and conflict preservation

**Decision:** Govern sources through the Tier 1 authoritative, Tier 2 structured financial data, Tier 3 reputable news/business and Tier 4 general-web hierarchy, evaluated by claim type.

**Rationale:** Financial research quality depends on authority, freshness and explicit disagreement rather than whichever provider responds first.

**Consequences:** Lower tiers cannot silently override authoritative evidence; missing authoritative support reduces confidence and conflicts remain first-class.

## ADR-020 — Bounded verification and reflection loops

**Decision:** Verification/Critic may request targeted re-research only within explicit iteration, task, deadline, attempt and token/context budgets.

**Rationale:** Reflection improves coverage but an unbounded loop creates cost, latency and reliability failures.

**Consequences:** Exhausted or non-improving research terminates transparently as partial/insufficient instead of fabricating completion.

## ADR-021 — Retrieved content is untrusted data

**Decision:** Keep trusted control instructions structurally separate from retrieved research content and prohibit retrieved instructions from authorizing policy, secret, tool, file, code, repository or trading actions.

**Rationale:** Filings, web pages, news and documents may contain prompt injection or malicious payloads.

**Consequences:** Tools are typed, allowlisted, least-privilege and budgeted; violations are ignored/recorded as untrusted content and never forwarded as authorization.

## Deferred decisions

Database schema/ORM/migrations, background execution, auth, graph implementation, storage provider, embeddings/chunking, exact free model IDs, full dependency locking, and production host remain deferred to investigation in their owning phases. Phase 1 selected GitHub Actions for baseline CI and Uvicorn as the ASGI server for local/container execution. Migration from TestClient `httpx` to `httpx2` is deferred (see ADR-023).

## ADR-022 — Phase 1 FastAPI foundation stack

**Decision:** Implement Phase 1 with FastAPI, Pydantic v2, pydantic-settings, and Uvicorn; keep domain code free of framework imports; wire concrete components only in the composition root.

**Rationale:** Matches ADR-002 and the frozen Phase 1 scope while preserving clean architecture and the smallest dependency surface needed for a runnable foundation.

**Consequences:** Health/readiness/version endpoints, configuration, correlation, logging, Docker/CI, and Research Run ID primitives may land in Phase 1; research providers and orchestration remain forbidden until later phases.

## ADR-023 — Defer Starlette TestClient httpx2 migration

**Decision:** Keep the Phase 1 TestClient development dependency on `httpx`, retain a narrowly scoped pytest filter for Starlette's `httpx`→`httpx2` deprecation warning, and defer installing/migrating to `httpx2` until an explicit dependency-upgrade decision.

**Rationale:** Starlette 1.4+ prefers `httpx2` for `TestClient` and deprecates plain `httpx`, but the current suite remains functionally correct with `httpx`. Prompt 3 forbids installing `httpx2` merely to silence the warning, and the warning does not indicate a failing compatibility break today.

**Consequences:** CI/local pytest remain quiet via a message-scoped filter only; runtime application dependencies are unchanged; a future ADR may adopt `httpx2` as the supported TestClient client.

## ADR-024 — Stable UUIDv4 company/security/listing identity

**Decision:** Use opaque UUIDv4 values as canonical `CompanyId`, `SecurityId`, and `ListingId`. Legal names, tickers, aliases, and provider symbols are mutable attributes and never redefine the entity.

**Rationale:** Matches the frozen Company Identity contract: ticker alone is not globally unique; renames and provider syntax must not break cross-run linkage; UUIDv4 is already the Research Run identity pattern (ADR-018).

**Consequences:** Resolution returns structured ambiguity instead of guessing; provider identifiers remain scoped side data; Phase 2 Prompt 1 may ship an in-memory catalog without PostgreSQL persistence.

## ADR-025 — Explicit resolution constraints and ticker-first precedence

**Decision:** Explicit `country` / `exchange` / `ticker` query constraints must never be ignored. A token that looks like a ticker is matched as a ticker before alias/name matching. Fuzzy matches may only produce AMBIGUOUS candidates.

**Rationale:** Prompt 2 adversarial validation found false-positive RESOLVED outcomes when alias/name fallthrough bypassed an explicit exchange miss. False-positive company identity is worse than NOT_FOUND/AMBIGUOUS.

**Consequences:** Contradictory constraints return NOT_FOUND; ticker-vs-alias collisions resolve to the listing owner when the token is ticker-like; catalog adapters must not silently overwrite duplicate canonical IDs.

## ADR-026 — At most one primary listing per security

**Decision:** Within a single `SecurityIdentity`, at most one `ListingIdentity` may set `is_primary=True`. Zero primary listings are allowed. Companies may have multiple primary listings across different securities (for example Alphabet Class A and Class C).

**Rationale:** Architecture distinguishes issuer, security/share class, and listing, and explicitly contemplates ADRs versus primary listings and dual listings. Enforcing exactly one primary listing per company would break multi-class issuers. Allowing multiple primaries on the same security would make “primary” meaningless for dual-listed equities (e.g. NSE+BSE).

**Consequences:** Domain validation rejects multiple primaries on one security; fixture dual listings mark one primary; full exchange/home-market policy for live masters remains future work.

## ADR-027 — Fixture-first Phase 3 market adapters with deterministic calculations

**Decision:** Phase 3 Prompt 1 ships Market Intelligence through application-owned `MarketDataPort`, an in-memory/fixture OHLCV adapter with optional in-process TTL cache and primary→secondary fallback, and a versioned deterministic calculation library. Live Yahoo/Alpha Vantage/Finnhub clients, Redis, and PostgreSQL market stores are deferred until separately authorized. Market snapshots require uniquely `RESOLVED` company identity before attaching observations.

**Rationale:** Frozen Phase 3 requires traceable market datasets and reproducible calculations, not premature live-provider cost or agent orchestration. Fixture adapters preserve offline tests, fail-closed paid-model policy, and false-positive company safety from Phase 2.

**Consequences:** `GET /market/snapshot` returns structured OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED outcomes with Tier-2 `SourceMetadata`; stale/missing data is visible; calculations never run in an LLM; live quote acquisition remains future work.

## ADR-029 — Fixture-first Phase 4 financial adapters with deterministic fundamentals

**Decision:** Phase 4 Prompt 1 ships Financial & Filing Intelligence through application-owned `FinancialDataPort`, in-memory/fixture financial packages for Apple and Reliance Industries, optional in-process TTL cache, primary→secondary fallback, and a versioned deterministic financial calculation library. Optional SEC EDGAR companyfacts HTTP adapter is enabled only when `FINANCIAL_DATA_LIVE_ENABLED=true`. Default remains offline fixture mode. Financial snapshots require uniquely `RESOLVED` company identity before attaching fundamentals. India live NSE/BSE/SEBI adapters remain deferred; fixture/reference contracts only.

**Rationale:** Frozen Phase 4 requires traceable financial facts, filing metadata, and reproducible ratio/growth calculations without LLM extraction or premature India scraping. Fixture adapters preserve offline CI, fail-closed paid-model policy, and Phase 2 identity safety.

**Consequences:** `GET /financials/snapshot` returns structured OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED outcomes with Tier-1/Tier-2 source metadata; missing facts remain absent; calculations never run in an LLM; valuation multiples needing market+fundamentals bridge remain deferred to later prompts; SEC live mode is opt-in and demo-scale CIK mapping only.

## ADR-030 — Defer valuation multiples until market+fundamentals as-of bridge

**Decision:** Phase 4 Prompt 2 does **not** implement P/E, P/B, EV/EBITDA, or similar valuation multiples. EPS remains a reportable `FinancialFact` when present. A valuation bridge requires trustworthy, period-aligned market price and per-share fundamentals with explicit as-of semantics and preserved dual provenance.

**Rationale:** Prompt 2 evaluated whether Phase 4 fundamentals alone are sufficient. They are not: market snapshots and financial packages are separate acquisition paths with independent freshness/as-of clocks. Computing P/E from an unrelated price timestamp and fiscal EPS would fabricate false precision. Resume-driven metrics are explicitly disallowed by the Prompt 2 contract.

**Consequences:** Valuation multiples stay deferred to a later authorized prompt that designs an explicit market+fundamentals bridge; missing valuation inputs must degrade as omitted/unavailable rather than invented ratios.

## ADR-031 — Explicit financial fact conflict resolution (no last-write-wins)

**Decision:** When multiple sources provide values for the same company/concept/period, the platform records all candidates. Deterministic resolution is allowed only when candidates share compatible measurement basis (exact reporting period, unit, and currency) and either (a) normalized values agree, or (b) a unique higher authority tier (lower tier number) agrees internally. Otherwise the conflict remains `UNRESOLVED` and no fact is selected. Retrieval timestamp ordering never silently decides disagreements. Numeric coincidence across mismatched unit/currency/period is never treated as agreement.

**Rationale:** ADR-019 requires conflicts to remain first-class. Silent last-write-wins would corrupt auditability of Tier-1 filings versus lower-tier structured feeds. Agreeing numbers with incompatible units or currencies would fabricate false certainty.

**Consequences:** Packages may expose a `conflicts` collection; unresolved conflicts omit the contested concept from statements; API consumers see explicit conflict payloads when present.

## ADR-032 — Fixture-first Phase 5 news/event intelligence (deterministic Prompt 1)

**Decision:** Phase 5 Prompt 1 ships News & Event Intelligence through application-owned `NewsEventPort`, in-memory/fixture event packages for Apple and Reliance Industries, deterministic deduplication by company/type/date/title with higher-authority preference (no last-write-wins), in-process TTL cache, and `GET /news/events/snapshot` gated on uniquely `RESOLVED` company identity. No live news HTTP provider and no OpenRouter/LLM usage in Prompt 1. Tier-4 general web cannot be labeled FACT; directional sentiment cannot be labeled FACT. Industry/competitor depth and live qualitative providers remain later Phase 5 prompts.

**Rationale:** Frozen Phase 5 requires source-grounded qualitative events with provenance before semantic LLM analysis. Fixture-first preserves offline CI, fail-closed paid-model policy, and Phase 2 identity safety while establishing event taxonomy and evidence refs.

**Consequences:** Default news/event snapshots are fixture/demo origin; incomplete coverage is disclosed; Prompt 1 does not claim full news/industry/regulatory corpus coverage; live providers and LLM-assisted sentiment remain deferred.

## ADR-033 — Conflict-aware qualitative event deduplication

**Decision:** Phase 5 Prompt 2 freezes deterministic event conflict semantics. Exact-key duplicates that agree on material fields collapse with higher authority / earlier retrieval (`AGREES`). Unique higher-authority agreeing tiers may `SUPERSEDE` lower tiers. Same-tier material disagreement remains `UNRESOLVED` with all candidates visible. Same company/type/title with disagreeing event dates is `CONFLICTING` and never silently merged. Retrieval order never last-write-wins.

**Rationale:** Frozen Phase 5 acceptance requires conflicting coverage to remain visible; authority alone must not erase contradictions.

**Consequences:** `CompanyEventPackage.conflicts` is first-class; API exposes conflict payloads; consumers must not assume a single winner for UNRESOLVED/CONFLICTING groups.

## ADR-034 — Defer live qualitative HTTP providers in Phase 5 Prompt 2

**Decision:** Prompt 2 does not add live news, industry, or regulatory HTTP adapters. Fixture/reference adapters remain the default offline path. Optional live acquisition may be reconsidered in later Phase 5 prompts only if a safe structured official source fits scope without scraping sprawl.

**Rationale:** Prompt 2 priority is hardening and foundations; fragile scraping or broad web acquisition would expand risk without improving acceptance evidence.

**Consequences:** CI stays network-independent; data_origin remains fixture for qualitative snapshots; production-like live coverage is explicitly not claimed.

## ADR-035 — Industry/competitor identity policy

**Decision:** Competitor peers must resolve to canonical `CompanyIdentity` when known (`PeerResolutionState.RESOLVED`). Unresolved or ambiguous peers remain explicit without attaching a guessed `CompanyId`. A company cannot compete with itself. Relationships require evidence refs; keyword coincidence alone does not create competitors. Industry taxonomy is reference/provider labeled; `UNMAPPED` forbids invented canonical codes.

**Rationale:** Phase 2 identity is canonical; silent peer guessing would corrupt India/US resolution protections.

**Consequences:** Fixture peers use existing catalog companies (e.g. Microsoft, TCS); unknown peers stay unlabeled by ID.

## ADR-036 — Regulatory authority and allegation policy

**Decision:** Official regulatory FACT records require Tier-1-style authoritative evidence and non-ALLEGED status. Tier-3/4 secondary coverage may describe regulatory activity only as `ALLEGED` or `UNKNOWN` with non-FACT information class. Secondary sources are never silently upgraded to official regulatory evidence.

**Rationale:** DATA_SOURCES.md / ADR-019 require regulator precedence and conflict visibility for qualitative claims.

**Consequences:** Fixture packages include both Tier-1 illustrative notices and secondary allegations; consumers can distinguish confirmed vs alleged items.

## ADR-037 — Defer LLM evidence-based sentiment in Phase 5 Prompt 2

**Decision:** Prompt 2 keeps OpenRouter/LLM calls at zero. Fixture `sentiment_label` values remain OPINION/FINDING metadata only. Evidence-based model INTERPRETATION sentiment may be introduced later only if required for Phase 5 acceptance and only under fail-closed free-model routing with structured validated outputs.

**Rationale:** Deterministic-first policy; opinion labeling already satisfies “opinion is labeled”; semantic sentiment is not required to freeze Prompt 2 foundations.

**Consequences:** No model IDs hardcoded; paid fallback remains prohibited; Prompt 3+ may revisit minimal sentiment foundation.

## ADR-038 — Phase 5 Prompt 3 acceptance freeze (live/LLM not required to close)

**Decision:** Against frozen PHASES.md Phase 5 acceptance criteria—(1) material qualitative claims cite evidence, (2) opinion is labeled, (3) events are time-aware, (4) general web never silently overrides authoritative records, (5) incomplete coverage is disclosed—Prompt 3 determines:

- Live qualitative HTTP providers are **NOT required** to truthfully close Phase 5. Provider-neutral ports + fixture/reference adapters with explicit `data_origin=fixture`, resolution gating, and disclosed incomplete coverage satisfy the authorized foundation release (consistent with Phase 2 fixture-first closure and ADR-034).
- LLM/OpenRouter evidence-based sentiment is **NOT required** to truthfully close Phase 5. Fixture `sentiment_label` values remain OPINION/FINDING/MODEL_INTERPRETATION metadata; “opinion is labeled” is satisfied without model calls (ADR-037 affirmed).
- Dedicated Risk Intelligence agent, large evaluation corpus beyond fixture adversarial sets, live SEC/SEBI feeds, and NLP entity extraction from raw articles remain **deferred by design**, not blocking gaps for this phase’s authorized foundation scope.

**Rationale:** Acceptance criteria emphasize provenance, labeling, conflict visibility, and disclosure—not live network acquisition or agentic LLM loops. Adding live scraping or paid-risk model calls would expand scope without closing a frozen acceptance gap.

**Consequences:** Phase 5 may release-checkpoint after Prompt 4 with documented limitations; OpenRouter/LLM/paid calls remain 0 for Phase 5; optional live qualitative adapters stay future work requiring separate authorization.

## ADR-039 — Framework-independent Phase 6 planning first; workflow engine deferred

**Decision:** Phase 6 Prompt 1 ships framework-independent orchestration domain/application contracts (ResearchRequest/Plan/Task DAG, DeterministicPlanner, CapabilityRegistry, CreateResearchPlan, `POST /research/plans`) without installing a workflow-engine dependency. PHASES.md lists workflow engine deliverables for Phase 6 overall; integration is deferred to a later Phase 6 prompt after contracts stabilize. Prompt 1 makes zero LLM/OpenRouter calls; planning is fully deterministic.

**Rationale:** Architecture requires domain independence from orchestration frameworks. Stable typed plans/tasks/budgets must exist before binding an execution engine. Deterministic-first planning satisfies Prompt 1 without paid-model or uncontrolled agent risk.

**Consequences:** Plan creation and plan execution remain separable; automatic multi-task execution and workflow-engine wiring are later Phase 6 prompts; no new runtime dependency is added in Prompt 1.

## ADR-040 — Controlled synchronous execution before any workflow engine

**Decision:** Phase 6 Prompt 2 implements `ExecuteResearchPlan` as a framework-independent, synchronous, one-ready-task-at-a-time execution engine with explicit budgets, bounded retries, cancellation tokens, failure/partial propagation, and a thin `Phase6CapabilityExecutor` adapter to existing Phase 2–5 use cases. `POST /research/execute` is create-and-execute only (plans are not persisted). LangGraph remains deferred (ADR-039 affirmed). No LLM planner/executor. No unbounded autonomous loops or uncontrolled concurrency.

**Rationale:** Runtime safety contracts (lifecycle, budgets, retries, evidence) must be proven independently before binding an orchestration framework. Correctness and reproducibility outweigh premature parallelism.

**Consequences:** Prompt 3 may reconsider LangGraph only after these contracts are owner-approved; distributed idempotency and plan persistence remain explicit non-goals for Prompt 2.

## ADR-041 — Phase 6 acceptance freeze: LangGraph/LLM/persistence/parallelism not required

**Decision:** Against PHASES.md Phase 6 acceptance criteria—(1) plans select only needed capabilities, (2) executions remain bounded and traceable, (3) no paid model can be routed, (4) failures produce transparent partial status, (5) deterministic work bypasses models—Prompt 3 determines:

| Item | Closure requirement |
| --- | --- |
| LangGraph / workflow engine | **NOT required** — framework-independent engine satisfies DAG execution, state, retries, budgets, cancellation foundation |
| LLM / intent planner | **NOT required** — `DeterministicPlanner` selects capabilities without model calls; OpenRouter/LLM/paid remain 0 |
| Plan persistence / resume | **NOT required** — create-and-execute with truthful non-persistence docs meets foundation acceptance |
| Parallel / concurrent workers | **NOT required** — sequential deterministic scheduling is an accepted correctness-first design |
| PARTIAL semantics | **Frozen** — capability PARTIAL → task SUCCEEDED (deps may proceed); run status PARTIAL; completeness not claimed |
| External-call budget | **Frozen** — counts capability `execute_task` invocations, not verified network I/O |
| API idempotency | **Frozen** — within one `OrchestrationState` only; no distributed/API idempotency claim |

**Rationale:** Acceptance emphasizes bounded, traceable, fail-closed deterministic orchestration—not a specific framework brand, model planner, or durable job store. Adding LangGraph/LLM/Postgres/Redis solely for Phase 6 would expand risk without closing a frozen acceptance gap.

**Consequences:** Phase 6 may release-checkpoint after Prompt 4 with documented limitations; deferred items are future optimizations requiring separate authorization; Phase 7 remains not started.

## ADR-042 — Phase 6 Prompt 4 release checkpoint (foundation complete)

**Decision:** Phase 6 Prompt 4 closes the authorized foundation after green release gates. The single Git checkpoint message is `feat(phase-06): implement autonomous research orchestration`. ADR-041 closure decisions remain frozen: LangGraph, LLM planner, plan persistence, and parallel execution are not required for Phase 6 completeness. Phase 7 is not started.

**Rationale:** Prompt 3 established no blocking acceptance gaps; Prompt 4 is validation + documentation + Git checkpoint only.

**Consequences:** Phase 6 is COMPLETE within documented limitations; further orchestration enhancements require new authorization; Phase 7 awaits owner authorization.

## ADR-043 — Phase 7 Prompt 1: workflow foundation before RAG

**Decision:** Owner-authorized Phase 7 Prompt 1 implements an Autonomous Research Workflows foundation vertical slice (WorkflowId, lifecycle, checkpoint, human approval, in-memory `ResearchWorkflowStorePort`, Create/Manage use cases, workflow API) that extends Phase 6 without replacing it. Frozen `PHASES.md` / `ROADMAP.md` title Phase 7 as Evidence Graph, RAG & Research Memory; RAG/embeddings/vector memory/`pgvector` are **deferred** to later Phase 7 prompts. Workflow checkpoints are control/audit state only—not semantic Research Memory. LangGraph is not added; soft pause uses `ExecutionControl.request_pause` to preserve PENDING tasks. No durable PostgreSQL/Redis workflow store in Prompt 1. Phase 8 is not started.

**Rationale:** Prompt 1 requires persistent, resumable, human-governed workflows on proven Phase 6 contracts before introducing retrieval/embedding complexity. Framework-independent architecture remains sufficient.

**Consequences:** Phase 7 is IN PROGRESS after Prompt 1; PHASES.md RAG acceptance criteria remain for later prompts; in-memory store is explicitly non-durable; Git checkpoint deferred to Phase 7 Prompt 4.

## ADR-044 — Keep in-memory workflow persistence through Phase 7 Prompt 2

**Decision:** Durable PostgreSQL/Redis workflow persistence is **not required** to truthfully progress Phase 7 Prompt 2. The `ResearchWorkflowStorePort` / memory / watchlist / notification ports remain the frozen abstractions. Prompt 2 keeps in-memory adapters and documents durability as an explicit limitation.

**Rationale:** Frozen Phase 7 acceptance emphasizes governed memory/retrieval later; Prompt 2 focuses on hardening and structured contracts. Adding a database service now would expand operational complexity without closing a Prompt 2 acceptance gap.

**Consequences:** Process restart loses local workflow/memory/watchlist state; durable adapters may be evaluated in later prompts if owner-authorized.

## ADR-045 — Research Memory is structured deterministic memory, not RAG

**Decision:** Phase 7 Prompt 2 Research Memory means immutable structured records of workflow task outcomes (workflow/run/company/capability/task/status/evidence refs/data_origin). It does **not** mean vector DB, embeddings, semantic retrieval, chunking, LLM memory, or knowledge graphs.

**Rationale:** Owner Prompt 2 explicitly forbids RAG pull-forward; structured memory satisfies cross-workflow continuity without authority upgrades.

**Consequences:** Memory adapters stay in-memory for Prompt 2; RAG remains deferred within Phase 7.

## ADR-046 — LangGraph still not required after Phase 7 Prompt 2

**Decision:** Re-evaluation confirms framework-independent workflow state, soft pause/resume, approval, monitoring checks, and structured memory are sufficient. LangGraph is **not** installed.

**Rationale:** No Prompt 2 acceptance criterion requires a workflow-engine dependency; deterministic contracts already support the authorized slice.

**Consequences:** Continue framework-independent architecture; revisit only with explicit owner authorization.

## ADR-028 — Optional Yahoo chart live adapter with explicit data origin

**Decision:** Phase 3 Prompt 3 adds an optional, key-free Yahoo Finance chart HTTP adapter behind `MarketDataPort`, enabled only when `MARKET_DATA_LIVE_ENABLED=true`. Default remains offline fixture mode. Observations carry explicit `DataOrigin` (`live` / `cached_live` / `fixture` / `unavailable`). Composition is cache → (optional live primary) → fixture secondary. Provider symbol mapping (e.g. `RELIANCE.NS` / `.BO`) stays in infrastructure and never becomes canonical identity. Valuation multiples requiring fundamentals remain deferred to Phase 4. Exchange holiday calendars and full corporate-action engines remain documented limitations. Optional live providers do not affect `/ready`.

**Rationale:** Frozen Phase 3 acceptance requires replaceable adapters and safe provider degradation. Fixture-only data cannot truthfully claim usable market intelligence for arbitrary real India/US listings. Yahoo chart HTTP is $0/no-key, allowlisted, and tested via fake transports so CI stays offline.

**Consequences:** Live mode is opt-in; fixture data must never be labeled live; Alpha Vantage/Finnhub remain unused optional keys; multi-provider conflict comparison beyond fallback provenance remains limited; Yahoo TOS/reliability risk is accepted as optional Tier-2 structured data, not Tier-1 exchange authority.

## ADR-047 — Deterministic, framework-independent verification foundation

**Decision:** Phase 8 verification is implemented as typed domain contracts and deterministic application logic. Claims, evidence bundles, contradiction records, confidence factors, verification results, and targeted critic requests remain independent of FastAPI, provider SDKs, OpenRouter, LangGraph, storage engines, and presentation layers. Confidence is an explainable evidence-quality score, not a probability or factual authority.

**Rationale:** Verification rules for source authority, numeric metadata, freshness, contradiction visibility, and sufficiency can be executed reproducibly without an LLM. Keeping the domain framework-independent preserves auditability and prevents model prose from becoming evidence.

**Consequences:** Runtime LLM/OpenRouter calls remain zero for Phase 8 Prompts 1–2. Critic requests are structured recommendations for bounded later orchestration, not an autonomous or unbounded loop. Persistence, synthesis, and presentation remain separate concerns.

## ADR-048 — Numeric verification fails closed on incompatible or non-finite values

**Decision:** Numeric evidence supports a claim only when claim type and normalized value match and required unit, currency, and reporting-period metadata are compatible. Missing expected values, mismatched scale/unit/currency/period, percentage-versus-ratio differences, and non-finite `Decimal` values (`NaN` or Infinity) cannot produce supporting evidence. Confidence is calculated from supporting evidence only; neutral or contradicting evidence cannot increase it.

**Rationale:** Financial verification must not accept text overlap or string-equal invalid numerics as proof. Prompt 2 adversarial testing confirmed that non-finite values required an explicit fail-closed guard.

**Consequences:** Invalid or incompatible numeric evidence remains contradicting or non-supporting with explicit low confidence and critic guidance. No tolerance, currency conversion, or unit conversion is inferred silently; any future normalization policy requires a separate approved decision and tests.

## ADR-049 — Phase 8 Prompt 3 verification acceptance freeze

**Decision:** Phase 8 foundation closure requires a deterministic single-claim verification contract with canonical source/provenance vocabularies, strict identity and evidence validation, versioned explainable confidence, preserved contradictions, and a bounded critic stop decision. `CriticAssessment` may return `sufficient_evidence`, `research_required`, or `attempts_exhausted`; it does not execute re-research. Free-form workflow memory summaries are not typed claims or evidence and must not be assigned synthetic authority. The prior summary-to-Tier-1 workflow verification path is removed.

**Rationale:** Prompt 3 adversarial tests found that missing metadata, future timestamps, fresh neutral evidence, duplicated identity, unsafe URLs, unversioned scoring, and synthetic workflow evidence could overstate verification quality. A deterministic contract freeze closes those gaps without introducing models, provider calls, or later-phase presentation features.

**Consequences:** Phase 8 Prompt 3 has no blocking foundation gap and may proceed to the owner-gated Prompt 4 release checkpoint. Workflow/run-wide verification remains deferred until upstream capabilities emit typed claims and resolvable evidence. No public verification endpoint, autonomous re-research executor, LLM critic, RAG/vector store, durable verification persistence, synthesis, report generation, or Phase 9 feature is required for this foundation closure.
