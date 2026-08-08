# Changelog

All notable changes will be documented here. The project intends to adopt Semantic Versioning when releasable software exists.

## [Unreleased]

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