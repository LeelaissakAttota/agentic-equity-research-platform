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

Database schema/ORM/migrations, background execution, auth, graph implementation, storage provider, embeddings/chunking, exact free model IDs, dependency locking, CI platform, and production host are deliberately deferred to investigation in their owning phases. UUIDv4 is frozen for `research_run_id`; its domain type/generator placement is implemented only in Phase 1.
