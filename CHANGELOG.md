# Changelog

All notable changes will be documented here. The project intends to adopt Semantic Versioning when releasable software exists.

## [Unreleased]

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

- All Phase 3–10 runtime research capabilities remain future work.
- Live NSE/BSE/SEBI/SEC acquisition, market-data SDKs, OpenRouter research, agents, RAG, reports, Streamlit, MCP, and trading remain unimplemented.