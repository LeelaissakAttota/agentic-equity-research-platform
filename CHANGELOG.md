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

No production application, provider, agent, model, database, retrieval, report, UI, MCP or trading functionality was added.

### Not implemented

- All Phase 1–10 runtime capabilities remain future work.
