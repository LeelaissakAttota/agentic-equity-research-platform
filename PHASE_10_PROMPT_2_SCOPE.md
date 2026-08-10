# Phase 10 Prompt 2 Scope Contract

## Authorized objective

Adversarially harden the approved Phase 10 Prompt 1 production boundary without redesigning Phase 10 or changing Phase 1–9 research semantics.

## Included

- Production configuration normalization and malformed-value tests.
- Trusted-host ambiguity, spoofing, malformed-port, duplicate-header, and missing-header protection.
- Declared, absent-length, chunked, exact-boundary, multibyte, and excessive-chunk request enforcement.
- Duplicate/invalid correlation-header protection.
- Safe HTTP and unexpected-error contracts that never reflect exception details or concrete sensitive paths.
- Telemetry and logging privacy tests for bodies, queries, credentials, headers, paths, report content, and hostile data.
- Phase 9 verification/report, identity, concurrency, deployment, dependency, security, and complete cross-phase regression audits.
- A preliminary Phase 10 acceptance matrix that distinguishes implemented, partial, deferred, and blocking work.

## Excluded

- Authentication/authorization implementation.
- Request-rate limiting or Redis.
- Durable PostgreSQL/Redis workflow or artifact persistence.
- MCP, cloud deployment, load/soak program, dashboards/SLOs, backup/restore, and rollback automation.
- New research/domain behavior, providers, report formats, LLM/OpenRouter, paid fallback, RAG/vector memory, trading, Prompt 3, or Phase 11.

## Decisions under review

- Authentication for Phase 10 closure: deployment-dependent and deferred pending an approved trust model.
- Rate limiting for Phase 10 closure: deployment-dependent and deferred pending thresholds/enforcement design.
- Durable persistence for Phase 10 closure: deferred pending the approved production operating model; not required for Prompt 2 hardening.
- New dependencies: none expected.

## Completion boundary

Prompt 2 completes when confirmed boundary defects are fixed, adversarial tests pass, the full Phase 1–9 regression remains green, security/cost/dependency/deployment audits pass, documentation remains truthful about incomplete Phase 10 capabilities, and no Git staging/commit/push occurs.
