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

## ADR-028 — Optional Yahoo chart live adapter with explicit data origin

**Decision:** Phase 3 Prompt 3 adds an optional, key-free Yahoo Finance chart HTTP adapter behind `MarketDataPort`, enabled only when `MARKET_DATA_LIVE_ENABLED=true`. Default remains offline fixture mode. Observations carry explicit `DataOrigin` (`live` / `cached_live` / `fixture` / `unavailable`). Composition is cache → (optional live primary) → fixture secondary. Provider symbol mapping (e.g. `RELIANCE.NS` / `.BO`) stays in infrastructure and never becomes canonical identity. Valuation multiples requiring fundamentals remain deferred to Phase 4. Exchange holiday calendars and full corporate-action engines remain documented limitations. Optional live providers do not affect `/ready`.

**Rationale:** Frozen Phase 3 acceptance requires replaceable adapters and safe provider degradation. Fixture-only data cannot truthfully claim usable market intelligence for arbitrary real India/US listings. Yahoo chart HTTP is $0/no-key, allowlisted, and tested via fake transports so CI stays offline.

**Consequences:** Live mode is opt-in; fixture data must never be labeled live; Alpha Vantage/Finnhub remain unused optional keys; multi-provider conflict comparison beyond fallback provenance remains limited; Yahoo TOS/reliability risk is accepted as optional Tier-2 structured data, not Tier-1 exchange authority.
