# Phase 10 Prompt 1 Scope Contract

## Repository-defined phase

**Title:** MCP/API Integration, Evaluation & Production Hardening.

**Objective:** Validate deployability, expose only approved integrations, and produce evidence-backed production-readiness results without weakening Phase 1–9 contracts.

Prompt 1 is a production-hardening foundation slice. It does not complete the broader Phase 10 MCP, evaluation, reliability, recovery, or deployment program.

## Authorized implementation

- Fail-closed production configuration for trusted hosts, non-debug logging, live-provider consistency, the existing paid-model prohibition, and a bounded request-body limit.
- A deterministic request-safety middleware for production host validation and total request-body size.
- Stable, correlation-aware API errors for rejected requests.
- A safe configuration readiness diagnostic while preserving liveness/readiness/version separation.
- Correlation-aware request outcome telemetry with safe operation/status/duration metadata.
- Secret-safe unexpected-exception logging without exception messages or stack traces.
- Focused tests for the new contracts and regression coverage for identity and verified synthesis/report safety.

## Decisions

- **Authentication required now:** DEFERRED. The frozen phase says auth is required as deployment requires; no target environment or identity provider has been approved.
- **Rate limiting required now:** DEFERRED. No deployment threshold or distributed enforcement target has been approved.
- **Durable persistence required for Prompt 1:** NO.
- **New dependencies:** NONE.
- **OpenRouter/LLM/paid calls:** 0.
- **Mandatory external API cost:** $0.

## Explicitly excluded

- MCP adapters/resources/tools.
- Production authentication/authorization implementation.
- Rate-limit enforcement or Redis.
- PostgreSQL, durable workflows, artifact registry, distributed state, backup/restore.
- Load/soak testing, SLO dashboards/alerts, deployment automation, rollback, and target-environment certification.
- New research behavior or reinterpretation of Phase 1–9 capabilities.
- LLM/OpenRouter, paid fallback, LangGraph, RAG/vector memory, PDF, trading, and Phase 11.

## Acceptance boundary

Prompt 1 is complete when unsafe production configuration fails before startup, production host/body limits fail safely with correlation IDs, readiness exposes only safe diagnostics, unexpected errors cannot leak exception content through client responses or structured logs, all focused tests pass, the complete Phase 1–9 suite remains green, documentation marks Phase 10 in progress, and no Git staging/commit/push occurs.
