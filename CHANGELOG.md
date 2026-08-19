# Changelog

All notable changes are documented here. Release versions follow Semantic Versioning.

## [1.0.0] - Unreleased

### Final release metadata and documentation alignment

- Aligned the authoritative package/runtime/OpenAPI version to `1.0.0`; the future Git tag and GitHub Release name remain `v1.0.0` and have not been created.
- Aligned the local Compose image reference to `agentic-financial-intelligence:1.0.0` without publishing an image.
- Replaced the obsolete planning-shaped synthesis example with a current, schema-valid, fixture-labelled verified-claim request.
- Reconciled current README, phase/status, architecture, development, API, security/supply-chain, and release-checklist documentation while preserving historical phase reports as historical evidence.
- Final Release Blocker 2 is closed locally. Final Release Blocker 1 evidence is retained for exact image `sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f`, but the blocker remains open pending owner review of 26 candidate-affecting Critical/High findings.

### Final release exact-candidate supply-chain evidence

- Added a hashed `release_evidence/v1.0.0/` manifest, exact runtime requirements capture, CycloneDX 1.6 application SBOM, CycloneDX 1.7 container SBOM, pip-audit JSON/human summary, Trivy JSON/table/human summary, all-findings classification, and sanitized secret-hygiene summary.
- `pip-audit 2.10.1` reports no known vulnerabilities across 21 exact active-runtime distributions. Trivy 0.73.0 reports 215 package/advisory records: 6 Critical, 22 High, 79 Medium, 97 Low, and 11 Unknown; no finding was hidden and no dependency or base image was automatically changed.
- Applicability review classifies 2 Critical/High records as not applicable and 26 as requiring owner review. Evidence generation is complete, but residual risk is not owner-accepted; Final Release Blocker 1 therefore remains open.

### Phase 10 Prompt 4 (historical owner-approved release checkpoint)

- Completed final release validation across all Phase 10 Prompt 1–3C capabilities: fail-closed production configuration, trusted-host enforcement, request-body bounds, safe errors/telemetry/logging, versioned REST backward-compatible aliases, static in-process MCP facade, deterministic evaluations, local reliability/load evidence, threat model/control mapping, supply-chain review with local SBOM and vulnerability scans, SLO/runbook/recovery/rollback/release evidence, and deployment smoke test.
- Full regression: 658 passed, 0 failed, 0 skipped. Phase 10 focused: 103 passed. Cross-phase: 304 passed. Architecture/configuration: 39 passed. Evaluations: 21 passed. Ruff: PASS. Formatting: PASS. mypy: PASS (180 source files). OpenAPI: 29 paths. Docker Compose: PASS.
- Historical checkpoint supply-chain evidence: Application SBOM (CycloneDX 1.5, 256 components), Container SBOM (CycloneDX 1.7), pip-audit (0 vulnerabilities in production dependencies), Trivy 0.73.0 local container scan (6 CRITICAL, 20 HIGH, 71 MEDIUM, 97 LOW, 11 UNKNOWN — all OS/build-time packages, zero in production Python runtime). Docker Scout historical scan transmitted metadata to Docker cloud (noted as exception; final acceptance used local Trivy only).
- At that historical checkpoint, production dependencies were recorded as having zero known vulnerabilities; dev/build dependencies with findings were excluded from the production image. This does not replace exact-candidate validation for `v1.0.0`.
- Identity/verification/synthesis regression: Apple/NASDAQ, Reliance/NSE, wrong exchange, GOOG/GOOGL — all green. No-investment-advice, prompt-injection, no-trading boundaries intact.
- Single Phase 10 release commit with message `feat(phase-10): harden production readiness` and verified push to origin/main.
- Phase 10 marked COMPLETE. Phase 11 remains locked and undefined.

### Phase 10 Prompt 3A (historical; blockers resolved via Prompt 3C)

### Phase 10 Prompt 3 (historical state at owner review)

- Audited the authoritative Phase 10 contract and project map: Phases 0–10 are defined; Phase 11 is a boundary label only; Phase 12+ is not defined.
- Published the final acceptance matrix with explicit implemented, partial/documented, deferred-by-design, and blocking classifications.
- Repaired three genuine fail-closed parser defects: Host outer-whitespace/control normalization, extreme numeric Host/Content-Length conversion failure, and correlation outer-whitespace/control normalization.
- Added 16 semantic Prompt 3 cases; final gates pass 610 full, 76 focused Phase 10, 284 cross-phase, and 39 architecture/configuration tests, plus Ruff, formatting, strict mypy, OpenAPI, Compose, diff, dependency, credential-signature, and unsafe-primitive checks.
- Confirmed dependency delta, OpenRouter calls, LLM calls, paid calls, and mandatory external cost remain 0; no staging, commit, or push occurred.
- Recorded blocking versioned REST/MCP, evaluation, reliability/security, operations/SLO, recovery/rollback, and deployment evidence. Phase 10 remains IN PROGRESS; Prompt 4 is not ready or authorized.

### Phase 10 Prompt 2 (owner approved)

- Adversarially hardened the approved Prompt 1 production boundary without changing Phase 1–9 research semantics or adding a dependency/endpoint.
- Rejected duplicate Host and Content-Length headers, malformed/non-numeric host ports, spoof/control/oversized hosts, non-ASCII-digit Content-Length values, duplicate correlation IDs, and excessive body-chunk counts.
- Replaced quadratic body replay with bounded request-local deque replay; verified declared, absent-length, exact-limit, one-byte-over, mid-stream, multibyte, empty, and hostile JSON behavior.
- Normalized route-raised HTTP exception messages, replaced concrete error paths with route templates, suppressed URL-bearing HTTP client/access logs, and added safe boundary-rejection telemetry.
- Bounded watchlist entry/capability collections, rejected unknown watchlist control fields, and bounded workflow-memory query limits while preserving the established workflow-list invalid-request contract.
- Added a 43-test Prompt 2 adversarial suite; full regression now passes 594 tests, with 268 cross-phase and 39 architecture/configuration tests passing.
- Published the preliminary Phase 10 acceptance matrix. Authentication, rate limiting, durable persistence, MCP, comprehensive evaluation, SLOs/load/recovery/deployment evidence, Prompt 3, and Phase 11 remain deferred or incomplete.
- New dependencies, OpenRouter/LLM/paid calls, and mandatory external cost remain 0. No staging, commit, or push.

### Phase 10 Prompt 1 (owner approved)

- Froze the repository-defined Phase 10 scope and implemented only a minimal production-readiness foundation; MCP, authentication, rate limiting, persistence, evaluation scorecards, deployment automation, and Phase 11 remain deferred.
- Added fail-closed production configuration for explicit trusted hosts, non-debug logging, live-provider consistency, bounded request bodies, and the existing paid-model prohibition.
- Added deterministic host and whole-body request safety, including content-length and chunked-body enforcement with normalized correlation-aware errors.
- Preserved distinct health/readiness/version semantics and added a safe configuration readiness diagnostic.
- Added route-template/status/duration request telemetry and removed secret-bearing exception messages and stack traces from structured exception logs.
- Added 17 focused production-hardening, identity, error, host/body, observability, and Phase 9 report-path regression tests; full regression now passes 551 tests.
- Added no dependency, endpoint, LLM/OpenRouter call, paid fallback, external service, arbitrary file write, or Phase 11 capability. Prompt 1 remains unstaged, uncommitted, and unpushed.

### Phase 9 Prompt 4 (owner-approved release checkpoint)

- Recovered and verified `main` at protected Phase 8 ancestor `fcc145a0b4bb33c0c274f758f36d2ef508135a6a`, with no staged files, no local tracking divergence, intentional Prompt 1–3 changes intact, and five protected unrelated owner documents untouched.
- Passed the 534-test full regression and a dedicated 251-test Phase 1–9 cross-phase endpoint/contract gate.
- Passed Ruff, formatting, strict mypy, diff integrity, architecture/phase/settings/repository, OpenAPI/create-app, Docker Compose, secret/path/dependency, paid-model, and runtime-surface gates.
- Closed project-control documentation to Phase 9 COMPLETE at the validated local pre-release boundary; Phase 10 remains NOT STARTED / AWAITING OWNER AUTHORIZATION.
- Classified the complete changed/untracked tree into intentional Phase 9 content and five protected unrelated owner documents; no generated cache, environment, credential, temporary, binary executable, or unsafe report-write surface is present.
- Runtime OpenRouter/LLM/paid/external calls remain 0; mandatory external API cost remains $0; `ALLOW_PAID_MODELS=false` remains fail-closed.
- The owner reviewed the complete pre-release report and authorized one intentional Phase 9 commit and verified non-force push. Phase 10 remains separately gated.

### Phase 9 Prompt 3 (awaiting owner review)

- Completed the Phase 9 acceptance audit and published an implementation/partial/deferred/blocking matrix covering synthesis, provenance, conflicts, confidence, temporal/missing semantics, reporting, language, identity, API, architecture, security, cost, determinism, and readiness.
- Added a semantic external-contract freeze for synthesis claims, verification/evidence linkage, confidence/conflict/omission contexts, section taxonomy, report metadata, language preferences, JSON/Markdown/DOCX, and API response behavior.
- Added verification-bypass, multi-dimensional conflict, stale/current/historical, degraded-research, language-status, Apple/Reliance semantic golden, cross-phase reuse, security, filename, and DOCX package tests.
- Hardened all synthesis API request models with `extra=forbid`; injected verification/policy fields now fail framework validation instead of being silently ignored.
- Added deterministic minimal OOXML DOCX rendering through the existing report port: fixed package order/timestamps, escaped evidence text, cover metadata, stable sections, confidence/conflicts/missing/sources, safe filename, and base64 transport. No file write, network call, PDF, or dependency was added.
- Confirmed LLM, LangGraph, RAG/vector memory, and durable persistence are not required for the accepted Phase 9 closure boundary. Broader conversation, translated narrative, UI/charts, advanced templates, artifact persistence, and Phase 10 capabilities remain explicit deferrals.
- Prompt 4, staging, commit, push, and Phase 10 were not started.

### Phase 9 Prompt 2 (owner approved)

- Hardened synthesis input integrity by recomputing Phase 8 status/confidence, rejecting semantic duplicate evidence, and validating citation company/security/listing identity.
- Added a bounded material-claim taxonomy and authority-sufficiency policy so material revenue, earnings, margin, valuation, market, regulatory, event, industry, and competitor claims cannot become facts without appropriate evidence context.
- Added claim-aware freshness: current market observations use a bounded 24-hour presentation policy, while period-qualified financial facts remain historical rather than being mislabeled current; Phase 8 stale status is never upgraded.
- Added deterministic stable structured JSON and safe Markdown report adapters behind the existing application port. Reports expose unavailable sections, omissions, per-claim confidence, conflicts, missing states, citations, and as-of context without aggregation, translation, network access, or file writes.
- Extended the existing `POST /research/synthesis` request with optional `report_format`/`report_title` and material/citation identity fields. No endpoint was added; DOCX is explicitly rejected.
- Added adversarial coverage for forged verification, duplicate/low-authority evidence, conflicts, stale market versus historical financial data, missing-versus-zero, cross-identity evidence, injection, malformed URL/timestamps, deterministic output, unavailable sections, report API behavior, and Apple/Reliance identity isolation.
- OpenRouter/LLM/paid calls and new dependencies remain 0. Prompt 3, Prompt 4, Phase 10, staging, commit, and push were not started.

### Phase 9 Prompt 1 (owner approved)

- Added framework-independent synthesis contracts for verified claims, structured research documents/sections, citations, confidence, contradictions, missing-data states, deterministic identity, and multilingual-ready output preferences.
- Added an explicit Phase 8 verified-claim gate: strong verified claims may render factually; partial, conflicting, contradicted, stale, unsupported, and policy-excluded claims remain qualified and traceable.
- Added stable section assembly and bounded materiality-based executive summaries with no investment advice, randomness, LLM, or external calls.
- Added report-generation JSON/Markdown/DOCX capability contracts behind `ResearchReportGeneratorPort`; no renderer or report-library dependency was added.
- Added `GenerateResearchSynthesis` and exactly one `POST /research/synthesis` endpoint with canonical company resolution, safe errors, correlation IDs, and structured evidence-linked output.
- Added offline Apple, Reliance, GOOG/GOOGL, Reliance/NASDAQ, hostile-content, URL-safety, architecture, and scope-freeze tests.
- OpenRouter/LLM/paid calls remain 0; mandatory external API cost remains $0. Prompt 1 was not a Git checkpoint.

### Phase 8 Prompt 4 (release checkpoint)

- Owner approved Prompts 1–3 and authorized the Phase 8 release checkpoint.
- Reconfirmed focused Phase 8, full regression, architecture, phase-boundary, configuration/cost, Ruff, mypy, OpenAPI, Compose, diff-integrity, staged-content, and secret-risk gates.
- Closed documentation and the ordered phase/prompt continuation record for a single intentional Phase 8 commit and verified push.
- Phase 8 marked COMPLETE; Phase 9 remains NOT STARTED / AWAITING OWNER AUTHORIZATION.
- Runtime OpenRouter/LLM/paid calls remain 0.

### Phase 8 Prompt 3 (owner approved)

- Completed the Phase 8 technical acceptance audit and added an 18-test contract-freeze suite.
- Hardened claim/evidence identity, duplicate evidence, URL, datetime, future-retrieval, stale-support, numeric metadata, critic bounds, and engine policy invariants.
- Added deterministic critic convergence/exhaustion assessment and versioned confidence policy `phase8-deterministic-v1`.
- Reused canonical `DataOrigin` and `SourceAuthorityTier` vocabularies; removed unsafe workflow-memory-summary conversion into synthetic Tier-1 evidence.
- Added `PHASE_HISTORY.md` as the ordered continuation index and recorded the owner-approved Prompt 4 release sequence.
- Validation passed: focused Phase 8 40/40, full regression 469/469, architecture 10/10, phase boundary 4/4, settings/policy/baseline 15/15, Ruff, mypy, OpenAPI 23 paths, Compose, and diff integrity.
- Phase 8 remains in progress; Prompt 4 and Phase 9 were not started. No staging, commit, or push occurred.

### Phase 8 Prompt 2 (owner approved)

- Recovered the interrupted 22-case verification suite and restored valid deterministic tests for factual, numeric, conflicting, stale, missing-evidence, and critic-request behavior.
- Hardened evidence matching so claim-type mismatches and numeric unit, currency, scale, period, fiscal-year, percentage/ratio, missing-value, NaN, and Infinity cases fail closed.
- Confidence calculation considers supporting evidence only; contradicting or neutral evidence cannot inflate the score.
- Validation passed: verification 22/22, full regression 451/451, architecture 10/10, phase boundary 4/4, Ruff lint/format, mypy (166 source files), OpenAPI (23 paths), Compose config, and diff integrity.
- OpenRouter/LLM/paid calls remain 0; no Phase 9 work, Git staging, commit, or push was performed.

### Phase 8 Prompt 1 (owner approved)

- Added typed verification claims, evidence bundles, confidence factors, contradiction records, results, and critic-request contracts.
- Added a framework-independent deterministic verification engine, application use case, and composition-root wiring.
- Confidence is an explainable evidence-quality score, not a probability; conflicts and insufficient evidence remain explicit.
- No LLM/OpenRouter, RAG/vector, durable persistence, or later-phase runtime dependency was introduced.

### Phase 7 Prompt 4 (release checkpoint)

- Final validation: pytest 429 passed, Ruff, mypy, architecture boundaries, phase boundaries, OpenAPI 23 paths, Docker/Compose config.
- Documentation closure: updated PROJECT_STATUS.md, CHANGELOG.md, PHASES.md, ROADMAP.md, DECISIONS.md, docs/development/README.md.
- Single Phase 7 release commit with message `feat(phase-07): implement autonomous research workflows`.
- Push to origin/main verified; local HEAD = origin/main; working tree clean.
- Phase 7 marked COMPLETE; Phase 8 NOT STARTED / AWAITING OWNER AUTHORIZATION.
- Deferred decisions frozen: durable persistence NO, LangGraph NO, RAG/vector NO, LLM planner NO.
- OpenRouter/LLM/paid calls remain 0.

### Phase 7 Prompt 3 (owner approved)

- Final acceptance audit of Phase 7 across all gates (A–P): workflow identity, lifecycle, checkpoints, pause/resume, cancellation, human approval, research memory, watchlists, monitoring, notifications, report contract, dashboard API, Phase 6 integration, retry/budget, evidence/provenance, company identity, prompt injection, architecture, cost/model policy.
- Phase 1–6 regression validated (health, ready, version, companies/resolve, market/financials/news/industry/regulatory snapshots, research plans/execute, workflow APIs).
- All release gates pass: BLOCKING PHASE 7 GAPS = NO; READY FOR PHASE 7 RELEASE CHECKPOINT = YES.
- No new implementation; adversarial verification and contract freeze only.

### Phase 7 Prompt 2 (owner approved)

- Hardened Prompt 1 workflows: adversarial lifecycle/approval/checkpoint/store tests; resume preserves attempt/external-call/evidence counters.
- Added structured Research Memory (not RAG), watchlists + explicit monitoring checks, in-memory notification contracts, deferred report-request contract.
- Dashboard-facing `GET /research/workflows` with bounds; cancel/memory/report routes; watchlist APIs.
- ADR-044–046: keep in-memory persistence; structured memory ≠ vector RAG; LangGraph still not required.
- OpenRouter/LLM/paid remain 0; Phase 8 not started; Phase 7 not marked complete; no Git commit.

### Phase 7 Prompt 1 (owner approved)

- Autonomous research workflow foundation vertical slice on top of Phase 6 (no RAG/embeddings).
- Added `WorkflowId`, lifecycle transitions, checkpoints, human approval contracts, deterministic approval policy.
- Added `CreateResearchWorkflow` / `ManageResearchWorkflow` coordinating Phase 6 plan + execute.
- Added in-memory `ResearchWorkflowStorePort` adapter (explicitly not durable production persistence).
- Extended `ExecutionControl.request_pause` so soft pause preserves PENDING tasks for safe resume.
- Added workflow API: `POST/GET /research/workflows`, execute/pause/resume/approval.
- ADR-043 records owner-authorized workflow-first Prompt 1 vs frozen PHASES.md RAG title.
- OpenRouter/LLM/paid remain 0; Phase 8 not started; Phase 7 not marked complete; no Git commit (Prompt 4).

### Phase 6 completion checkpoint

- Owner approved Phase 6 Prompts 1–3; Prompt 4 completed final validation, documentation closure, staged-content audit, Git commit, and push.
- Reconfirmed pytest (≥400 passed), Ruff, mypy, OpenAPI, Docker/Compose, secret/paid-model, architecture, and Phase 7 absence gates.
- Established the Phase 6 Git checkpoint on `main` with message `feat(phase-06): implement autonomous research orchestration`.
- Phase 6 Autonomous Research Planning & Dynamic Orchestration scope is complete within authorized foundation; documented limitations remain explicit (no LangGraph, no LLM planner, no plan persistence, sequential execution, invocation-based external-call accounting).
- Phase 7 remains not started and awaits explicit owner authorization.

### Phase 6 Prompt 3 (owner approved)

- Orchestration audit + contract freeze for Prompts 1–2 (DAG, lifecycle, retries, budgets, evidence, identity, API).
- Hardened `FAILED → READY` to require `authorized_retry=True`; identity mismatch for company/security/listing evidence; transparent PARTIAL run status for mixed required outcomes.
- Documented external-call accounting as capability invocations (not packet-accurate network I/O).
- Added Apple/Reliance comprehensive golden tests and Phase 6 contract freeze suite.
- ADR-041: LangGraph, LLM planner, plan persistence, and parallel execution are **not required** to close Phase 6.
- OpenRouter/LLM/paid remain 0; Phase 7 not started; Phase 6 not marked complete until Prompt 4.

### Phase 6 Prompt 2 (owner approved)

- Added controlled synchronous execution engine: `ExecuteResearchPlan` + ready-task scheduling.
- Added `Phase6CapabilityExecutor` bridging capability IDs to existing Phase 2–5 snapshot/resolve use cases.
- Hardened task lifecycle, required/optional failure propagation, PARTIAL semantics, bounded retries, runtime budgets, cancellation, and no-progress guards.
- Added evidence aggregation/dedupe and `ResearchExecutionResult` (no investment conclusion).
- Added `POST /research/execute` create-and-execute API (plans are not persisted).
- LangGraph and LLM planner remain deferred; OpenRouter/LLM/paid calls remain 0; Phase 7 not started.
- Phase 6 Prompt 1 owner-approved; Prompt 2 is not a Git checkpoint.

### Phase 6 Prompt 1 (owner approved)

- Added orchestration foundation: ResearchRequest/Objective/Plan/Task, DAG, budget, OrchestrationState.
- Added CapabilityRegistry + DeterministicPlanner (`phase6-deterministic-v1`); no LLM planning.
- Added `CreateResearchPlan` and `POST /research/plans` (creates plan only; does not execute).
- Deferred LangGraph to a later Phase 6 prompt after contracts stabilize (ADR-039).
- OpenRouter/LLM/paid calls remain 0; Phase 7 not started.
- Phase 6 Prompt 1 is not a Git checkpoint.

### Phase 5 completion checkpoint

- Owner approved Phase 5 Prompts 1–3; Prompt 4 completed final validation, documentation closure, staged-content audit, Git commit, and push.
- Reconfirmed pytest (351 passed), Ruff, mypy, OpenAPI, Docker/Compose, secret/paid-model, architecture, and Phase 6 absence gates.
- Established the Phase 5 Git checkpoint on `main` with message `feat(phase-05): implement qualitative intelligence`.
- Phase 5 News, Events, Industry & Regulatory Intelligence scope is complete within authorized foundation; documented limitations remain explicit.
- Phase 6 remains not started and awaits explicit owner authorization.

### Phase 5 Prompt 3 (owner approved)

- Acceptance audit and qualitative contract freeze for Phase 5 Prompts 1–2.
- Frozen contracts: news/event dedupe/conflicts (ADR-033), industry/competitor identity (ADR-035), regulatory allegation policy (ADR-036), data_origin, API snapshots.
- Acceptance decisions (ADR-038): live qualitative HTTP **not required** to close Phase 5; LLM sentiment **not required**; OpenRouter/LLM/paid remain 0.
- Added `tests/unit/test_phase5_contract_freeze.py` (cross-capability identity, conflicts, caches, API, provenance, Phase 1–4 regression).
- **BLOCKING PHASE 5 GAPS: NO** within authorized foundation scope; Prompt 4 may release-checkpoint after owner approval.
- Phase 5 Prompt 3 is not a Git checkpoint; Phase 5 not marked complete.

### Phase 5 Prompt 2 (owner approved)

- Hardened news/event domain (control chars, URL schemes, time semantics, cross-company rejection, age metadata).
- Conflict-aware event processing: AGREES / SUPERSEDED / CONFLICTING / UNRESOLVED (ADR-033); no last-write-wins.
- Added Industry & Competitor foundation + `GET /industry/context/snapshot` (canonical peer IDs; unresolved peers explicit) — ADR-035.
- Added Regulatory foundation + `GET /regulatory/events/snapshot` (SEC/SEBI/NSE fixtures; secondary = ALLEGED) — ADR-036.
- Deferred live qualitative HTTP providers and LLM sentiment (ADR-034, ADR-037); OpenRouter/LLM/paid calls remain 0.
- Prompt-injection fixture text remains inert research data; cache hardening tests added.
- Phase 5 Prompt 2 is not a Git checkpoint.

### Phase 5 Prompt 1 (owner approved)

- Added News & Event Intelligence foundation: qualitative event domain, evidence refs, information classes, deterministic dedupe (ADR-032).
- Added `NewsEventPort`, fixture adapter (Apple + Reliance), in-process TTL cache.
- Added `GetNewsEventSnapshot` and `GET /news/events/snapshot` with resolution safety and data_origin.
- No OpenRouter/LLM calls; live news providers deferred; industry/competitor depth deferred.
- Phase 5 Prompt 1 is not a Git checkpoint.

### Phase 4 completion checkpoint

- Owner approved Phase 4 Prompts 1–3; Prompt 4 completed final validation, documentation closure, staged-content audit, Git commit, and push.
- Reconfirmed pytest (288 passed), Ruff, mypy, clean install/OpenAPI, Docker/Compose, secret/paid-model, architecture, and Phase 5 absence gates.
- Established the Phase 4 Git checkpoint on `main` with message `feat(phase-04): implement financial and filing intelligence`.
- Phase 4 Financial & Filing Intelligence scope is complete; documented limitations remain explicit.
- Phase 5 remains not started and awaits explicit owner authorization.

### Phase 4 Prompt 3 (owner approved)

- Acceptance audit and financial contract freeze for Phase 4 Prompts 1–2.
- Hardened conflict resolution: unit/currency/exact-period compatibility required before value agreement (ADR-031 clarification).
- Hardened fact invariants (ratio/percent reject currency; package filing_id consistency).
- Added Phase 4 contract-freeze / Prompt 2 verification / provenance regressions.
- Revalidated valuation deferral (ADR-030); documentation truth updates.
- No new Phase 5 capabilities; OpenRouter/LLM calls = 0; Prompt 3 is not a Git checkpoint.
- Acceptance: no blocking Phase 4 gaps within authorized scope; Prompt 4 may release-checkpoint after owner approval.

### Phase 4 Prompt 2 (owner approved)

- Hardened financial domain (NaN/Infinity, scale/unit/currency, duplicates, timezone, filing URL validation, identity consistency).
- Hardened period comparability with explainable incomparability reasons; omitted metrics replace silent skips.
- Added explicit fact-conflict handling (authority-tier resolution; no last-write-wins) — ADR-031.
- Deepened offline SEC companyfacts tests (amendments, instant facts, malformed/empty/oversized/429/5xx/timeout).
- Added India filing foundation (NSE→BSE→SEBI→IR precedence + fixture-labelled parser); live India HTTP deferred.
- Added deterministic filing pipeline foundation; hardened concept mapping (unknown/ambiguous unmapped).
- Extended financial snapshot API with omissions/conflicts provenance; adversarial API/cache/fallback coverage.
- Valuation multiples remain deferred (ADR-030); OpenRouter/LLM calls = 0; Phase 4 Prompt 2 is not a Git checkpoint.

### Phase 4 Prompt 1 (owner approved; local uncommitted foundation preserved)

- Added canonical financial domain: `FinancialFact`, reporting periods, units/scale, income/balance/cash-flow statements, filing metadata, shared `DataOrigin`.
- Added deterministic financial calculation library (growth, margins, liquidity, FCF) with explicit formula versions.
- Added `FinancialDataPort`, fixture-backed in-memory adapter, in-process TTL cache, primary→secondary fallback (ADR-029).
- Added optional SEC EDGAR companyfacts HTTP adapter (`FINANCIAL_DATA_LIVE_ENABLED`, default false).
- Added `GetFinancialSnapshot` requiring uniquely resolved company identity before attaching fundamentals.
- Added `GET /financials/snapshot` with OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED/INVALID contracts.
- Representative Apple (US) and Reliance Industries (India) fixture fundamentals; India live adapters deferred.
- No OpenRouter/LLM calls; valuation multiples bridge deferred; Phase 4 Prompt 1 is not a Git checkpoint.

### Phase 3 completion checkpoint

- Owner approved Phase 3 Prompts 1–3; Prompt 4 completed final validation, documentation closure, staged-content audit, Git commit, and push.
- Reconfirmed pytest (180 passed), Ruff, mypy, clean install, Docker/Compose, secret, paid-model, architecture, and Phase 4 absence gates.
- Established the Phase 3 Git checkpoint on `main` with message `feat(phase-03): implement market intelligence`.
- Phase 3 Market Intelligence scope is complete; documented limitations remain explicit.
- Phase 4 remains not started and awaits explicit owner authorization.

### Phase 3 Prompt 3 (owner approved)

- Acceptance audit: fixture-only insufficient for truthful real-listing Market Intelligence.
- Added optional Yahoo Finance chart HTTP adapter (`MARKET_DATA_LIVE_ENABLED`, default false) behind `MarketDataPort` (ADR-028).
- Added bounded stdlib HTTP client (timeouts, retries, size limits, failure normalization).
- Added explicit `DataOrigin` (`live`/`cached_live`/`fixture`/`unavailable`) on series and API.
- NSE/BSE/US symbol mapping remains infrastructure-only; fixture never labeled as live.
- Valuation multiples deferred pending fundamentals; holiday calendars remain documented limitations.
- Offline fake-transport tests; CI/Docker remain secret-free and start without live mode.

### Phase 3 Prompt 2 (owner approved)

- Hardened OHLCV invariants (finite Decimals, integer share volume, AVAILABLE requires bars, currency consistency).
- Hardened listing identity match checks; Reliance BSE no longer risk of NSE reuse; future `as_of` is DEGRADED/UNKNOWN.
- Hardened fallback (primary exceptions, provenance) and cache (injectable clock, TTL boundary, lock, freshness≠cache age).
- Clarified weekday helper as calendar-day only; simple return documented as ratio.
- Expanded adversarial regression suite; no live providers/LLM introduced.

### Phase 3 Prompt 1 (owner approved)

- Added Market Intelligence domain: OHLCV observations, freshness/availability enums, exchange calendar helpers, and versioned deterministic calculations.
- Added `MarketDataPort`, fixture-backed in-memory adapter, in-process TTL cache, and primary→secondary fallback (ADR-027).
- Added `GetMarketSnapshot` requiring uniquely resolved company identity before attaching market data.
- Added `GET /market/snapshot` with OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED/INVALID contracts and Tier-2 source metadata.
- Added market freshness/cache settings (`MARKET_STALE_AFTER_HOURS`, `MARKET_CACHE_TTL_SECONDS`).
- Added Windows-only `tzdata` runtime dependency so `zoneinfo` exchange calendars resolve IANA zones.
- No live market providers, OpenRouter/LLM calls, Phase 4 filings, agents, Redis, or PostgreSQL were introduced.
- Phase 3 remains IN PROGRESS; Prompt 1 is not a Git checkpoint.

### Added

- Phase 0 project constitution, target architecture, roadmap, detailed phase gates, and initial ADRs.
- Evidence, source authority, free-model, security, testing, Git, coding, deployment, contribution, and agent policies.
- Safe environment example, ignore rules, repository boundaries, architecture reference asset, and minimal Python package-health baseline.

### Security

- Fail-closed no-paid-model policy and external content/network/document safety requirements.
- Secret handling and sensitive/generated file ignore baseline.

### Changed

- Corrected PEP 639/setuptools license metadata compatibility by removing the redundant legacy license classifier while retaining the MIT SPDX expression and license file.
- Clarified fact, model-interpretation, and final-synthesis separation in the evidence model.
- Expanded the testing strategy with explicit security, failure/resilience, regression, and future evaluation scorecard coverage.
- Added model-result cache safety and invalidation requirements.
- Updated project status to reflect Prompt 1 approval and Phase 0 Prompt 2 validation.
- Ignored pytest fallback cache-temporary directories produced by restricted environments.

### Validated

- Created a project-local Python 3.12 virtual environment with only the declared Phase 0 development tools.
- Executed the full current pytest suite, Ruff checks/format validation, and strict mypy audit.
- Audited package metadata, documentation, security, free-model policy, architecture integrity, portability, and Phase 0 boundaries.

### Architecture freeze

- Declared the preserved diagram plus `ARCHITECTURE.md` as the Master Architecture and froze post-approval change control.
- Clarified clean dependency direction, composition rules, canonical terminology and major intelligent/deterministic capability boundaries.
- Defined the Research execution contract, UUIDv4 Research Run identity/traceability and provider-neutral Company Identity.
- Froze evidence provenance, tiered source authority, bounded verification/re-research, token efficiency, multilingual invariants, observability, report classification, prompt-injection, trading and REST/MCP boundaries.
- Added ADR-017 through ADR-021 for deterministic-first execution, Research Run IDs, source authority, bounded reflection and untrusted retrieved content.
- Froze the Phase 0–10 sequence and expanded Phase 1 entry, scope, exclusions, tests and measurable acceptance criteria.
- Improved README portfolio communication while continuing to identify all runtime capabilities as planned.

### Phase 0 completion checkpoint

- Owner approved Phase 0 Prompts 1–3; Prompt 4 completed final validation and documentation closure.
- Reconfirmed pytest, Ruff, mypy, package/TOML, documentation, architecture checksum, secret, ignore, free-model, and Phase 1-absence gates.
- Established the first approved Git checkpoint on `main` and configured the owner-approved GitHub SSH remote.
- Phase 0 is complete; Phase 1 remains not started and awaits explicit owner authorization.

### Phase 1 foundation

- Added typed pydantic-settings configuration with fail-closed `ALLOW_PAID_MODELS=false`.
- Added FastAPI application factory, lifespan foundation, `/health`, `/ready`, and `/version`.
- Added correlation IDs, structured secret-safe logging, security headers, and stable API error contracts.
- Added composition-root wiring, infrastructure-neutral ports, and the UUIDv4 `ResearchRunId` domain primitive.
- Added Dockerfile, app-only Compose foundation, and baseline GitHub Actions CI.
- Added Phase 1 foundation tests; no research intelligence or provider integrations were introduced.

### Phase 1 Prompt 2 validation

- Hardened readiness registry: probe exceptions/name mismatches become controlled `not_ready` checks with stable ordering.
- Hardened nested log redaction and correlation/error fallback sanitization.
- Made Compose host port configurable via `API_HOST_PORT` to avoid local port-8000 conflicts.
- Expanded deep tests for configuration, API/OpenAPI surface, concurrency, logging, architecture, and import side effects.
- Documented Starlette `httpx`/`httpx2` TestClient deprecation as an upstream warning; did not add `httpx2` solely to silence it.

### Phase 1 Prompt 3 stabilization

- Fixed process logging configuration so repeated `create_app()` calls do not clear unrelated/root handlers.
- Expanded sensitive-log fragments (`passwd`, `refresh_token`) and architecture-boundary coverage.
- Recorded ADR-023 deferring Starlette TestClient migration from `httpx` to `httpx2`.
- Revalidated Docker/Compose/clean-install/security/architecture gates for release-candidate readiness ahead of Prompt 4.

### Phase 1 completion checkpoint

- Owner approved Phase 1 Prompts 1–3; Prompt 4 completed final validation, documentation closure, staged-content audit, Git commit, and push.
- Reconfirmed pytest (60 passed), Ruff, mypy, `git diff --check`, clean install, API/OpenAPI smoke, Docker/Compose, secret, paid-model, architecture, and Phase 2 absence gates.
- Established the Phase 1 Git checkpoint on `main` with message `feat(phase-01): establish core application foundation` and synchronized with the owner-approved remote.
- Phase 1 is complete; Phase 2 remains not started and awaits explicit owner authorization.

No production research, provider, agent, model, database, retrieval, report, UI, MCP or trading functionality was added.

### Phase 2 Prompt 1 (unreleased)

- Added provider-neutral company/security/listing identity domain with stable UUIDv4 IDs.
- Added deterministic company resolution (catalog port, in-memory reference dataset, ResolveCompany use case).
- Added `GET /companies/resolve` over local fixtures with RESOLVED/AMBIGUOUS/NOT_FOUND/INVALID outcomes.
- Added source metadata foundation (authority tiers, source types, URL validation, company linkage).
- No live provider network adapters, OpenRouter calls, or Phase 3+ research capabilities were introduced.

### Phase 2 Prompt 2 hardening (unreleased)

- Fixed false-positive RESOLVED when an explicit exchange constraint conflicted with later alias/name matching (e.g. RELIANCE + NASDAQ).
- Enforced explicit ticker-parameter misses without unconstrained name fallthrough.
- Rejected duplicate catalog IDs and duplicate exchange+ticker listings at adapter init.
- Hardened cross-type ID inequality, resolution-result invariants, control-character handling, and source linkage rules.
- Added adversarial collision, fuzzy candidate-only, API ambiguity, and import side-effect tests.

### Phase 2 Prompt 3 stabilization (unreleased)

- Froze identity/resolution/source contracts for Prompt 4 checkpoint readiness.
- Recorded ADR-026: at most one primary listing per security; companies may have multiple primaries across securities.
- Added Alphabet/Reliance/false-positive/serialization/API contract-freeze regressions.
- Documented HTTP semantics for `/companies/resolve` and reference-dataset non-coverage.
- Revalidated Docker/Compose/CI alignment without live providers.

### Phase 2 completion checkpoint

- Owner approved Phase 2 Prompts 1–3; Prompt 4 completed final validation, documentation closure, staged-content audit, Git commit, and push.
- Reconfirmed pytest (126 passed), Ruff, mypy, clean install, Docker/Compose, secret, paid-model, architecture, and Phase 3 absence gates.
- Established the Phase 2 Git checkpoint on `main` with message `feat(phase-02): establish company identity and source foundation`.
- Phase 2 identity/source-foundation scope is complete; live provider acquisition criteria remain deferred by design.
- Phase 3 remains not started and awaits explicit owner authorization.

### Not implemented

- Phase 4–10 runtime research capabilities remain future work.
- Alpha Vantage/Finnhub wiring, Redis/PostgreSQL market stores, full holiday calendars, full corporate-action engines, valuation multiples needing fundamentals, filings, OpenRouter research, agents, RAG, reports, Streamlit, MCP, and trading remain unimplemented.
