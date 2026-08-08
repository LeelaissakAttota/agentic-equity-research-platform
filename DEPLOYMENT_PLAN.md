# Deployment Plan

## Status

This is a target plan. Phase 0 does not create deployment artifacts or claim deployability. Docker/Compose foundations begin in Phase 1; production hardening is gated by Phase 10.

## Principles

- one independently deployable financial-research service;
- modular monolith before justified service decomposition;
- immutable, reproducible artifacts and environment-driven configuration;
- no baked-in credentials or paid provider requirement;
- health signals distinguish process liveness from dependency readiness;
- migrations, backups, restore, and rollback are explicit operations;
- JARVIS and trading systems remain optional external clients.

## Planned environments

### Local development

Docker Compose is expected to provide application, PostgreSQL with pgvector, and Redis. Local source/artifact storage may use mounted directories. Default tests remain offline and do not require API keys.

### CI/test

Ephemeral services validate migrations, integration contracts, package/container build, and security checks. Live-provider/evaluation jobs are opt-in, budget-bounded, and isolated from the required suite.

### Staging

Production-like configuration with non-production credentials, representative load, migration/rollback rehearsals, observability, restore tests, and end-to-end evaluation.

### Production

Hosting remains undecided. A production option must support managed secrets, TLS, network controls, persistent PostgreSQL/pgvector, Redis policy, durable artifact/source storage, backups, monitoring, and rollback without mandatory paid data/model routes in the application design.

## Target components

- FastAPI application process and, if justified, background worker using the same application/domain contracts;
- PostgreSQL plus pgvector as durable canonical metadata/evidence store;
- Redis as disposable cache/transient coordination;
- governed raw-source and report artifact storage;
- Streamlit as a separately deployable client in Phase 9;
- OpenRouter and external source providers behind outbound policy and adapters.

## Configuration and secrets

Configuration is environment-specific and validated at startup. Secrets enter through a managed secret mechanism, never images or source. `ALLOW_PAID_MODELS=false` remains enforced. Optional provider keys may be absent without preventing unrelated capabilities from starting.

## Delivery flow

Planned flow: checks -> tests/evaluations -> build immutable image -> scan/SBOM -> deploy staging -> migrate -> smoke/load/security validation -> owner-approved production promotion -> post-deploy validation. Rollback and forward-fix procedures must account for database compatibility.

## Data operations

Before production define migration ownership, point-in-time recovery, backup frequency/retention, restore objectives/tests, source/artifact retention, encryption, access control, evidence immutability/correction, and deletion requirements. Redis loss must not lose canonical state.

## Observability and reliability

Health/readiness, structured logs, research-run traces, task/tool/model metrics, token/latency/error tracking, provider/cost-policy failures, database/cache health, queue/backlog if introduced, artifact failures, and alerting are required. SLOs and capacity targets will be evidence-based in Phase 10.

## Scaling posture

Scale the modular monolith vertically and with stateless replicas first. Separate workers or services only for measured isolation/throughput/reliability needs, with stable contracts and an ADR. Apply concurrency and provider-rate budgets before adding replicas.

## Exit criteria for production claim

Accepted Phase 10; threat model and security gates; contract/evaluation thresholds; load/failure evidence; tested migrations, backups, restore and rollback; runbooks/alerts; cost-policy proof; documented provider terms; and explicit owner release approval.
