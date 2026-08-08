# Testing Strategy

## Goals

Tests protect factual integrity, deterministic calculations, provider replaceability, security/cost policy, and phase gates. Tests must prove failures are visible and bounded—not merely prove a happy path.

## Test layers

### Unit

Fast, offline tests for domain rules, normalized models, calculations, validation, state transitions, freshness, contradiction logic, and security utilities. These form the majority of the suite.

### Integration

Tests for owned infrastructure boundaries such as PostgreSQL/pgvector, Redis, document parsing, migrations, and application wiring. Use isolated disposable resources and deterministic fixtures.

### Contract

Adapter/API contracts covering request/response normalization, error taxonomy, provenance, provider fixture compatibility, OpenAPI behavior, and later MCP schemas. Live calls are opt-in, quota-aware, and never required for the default suite.

### Evaluation

Curated cases for company resolution, extraction, retrieval relevance, research plans, evidence grounding, contradictions, verification, synthesis, multilingual factual invariance, and report quality. Track versioned datasets and thresholds rather than subjective demos.

### Security

Boundary-focused tests for secret redaction, URL and file safety, path traversal, parser limits, prompt injection, authorization when introduced, dependency policy, and fail-closed model cost controls.

### Failure and resilience

Deterministic fault cases for timeouts, 429 responses, malformed data, unavailable providers/models, bounded retries, cancellation, partial results, cache loss, and later database/queue recovery. Tests must prove terminal failures remain visible.

### Regression

Every confirmed correctness, evidence, security, or operational defect gains the smallest durable regression test at the appropriate layer. Regression fixtures retain the defect context without copying secrets or impermissible data.

## Required properties

- Default tests run without network, secrets, paid services, or model spend.
- Time, randomness, provider output, and IDs are controllable in tests.
- Financial calculations use golden inputs/expected outputs and document formulas/tolerances.
- Important negative cases cover missing, stale, malformed, contradictory, rate-limited, and malicious input.
- Async work tests cancellation, timeouts, retries, and cleanup.
- Tests assert provenance and research-run correlation, not just final prose.
- Security tests cover redaction, URL/file limits, path safety, prompt injection, and fail-closed cost policy.

## Markers and execution intent

Planned pytest markers include `unit`, `integration`, `contract`, `evaluation`, `live`, and `slow`. The exact marker configuration will be introduced with the owning tests. `live` tests must require explicit enablement and should use dedicated non-production credentials and strict budgets.

## Phase 0 checks

- package imports from the `src` layout;
- public version is a non-empty string;
- required files/directories exist;
- `pyproject.toml` parses;
- `.env.example` has placeholders only and `.env` is ignored;
- documentation references and Git state are auditable.

The Phase 0 health test is compatible with pytest and Python's standard-library
`unittest` discovery so a fresh, offline workspace can validate the baseline
before development dependencies are installed.

## Quality gates

Later CI should run formatting/linting, type checks, unit tests, selected integration/contract tests, coverage reporting, secret scanning, dependency/container scanning, build validation, and documentation checks. Thresholds should be chosen from baseline evidence; coverage percentage alone does not prove research correctness.

## Future evaluation scorecard

Versioned evaluation releases should report, where applicable:

- company-resolution accuracy, including ambiguity and exchange/country correctness;
- financial-number accuracy, unit/currency/period correctness, and deterministic calculation accuracy;
- citation correctness and evidence-reference resolvability;
- source-authority policy compliance and provenance completeness;
- freshness/date validation accuracy;
- unsupported-claim rate and evidence-grounding rate;
- evidence-coverage rate across required research dimensions;
- contradiction detection and conflict-preservation quality;
- report completeness and multilingual factual invariance;
- free-model route/failure/degradation rates, retry behavior and paid-route policy violations (target: zero);
- context/token efficiency and model-call avoidance for deterministic tasks;
- Research Run success, partial-result and terminal-failure rates;
- end-to-end, provider, tool, and model latency distributions.

Datasets, scoring definitions, thresholds, and sampling rules must be versioned so results remain comparable.

## Defect policy

Every production/research-integrity defect should gain a regression test. Flaky tests are defects: quarantine only with an owner, reason, tracking item, and removal date. Do not weaken assertions to hide nondeterminism.

## Test data

Prefer small, licensed/permitted, redacted fixtures with source and capture metadata. Never commit secrets, personal data, or large copyrighted documents without explicit permission. Generated fixtures must be labeled synthetic and must not masquerade as financial facts.

## Acceptance evidence

At each phase boundary, record commands/checks, environment, result summary, known skips, warnings, and unresolved failures in `PROJECT_STATUS.md` or the phase audit. A phase cannot pass with unacknowledged critical test failures.
