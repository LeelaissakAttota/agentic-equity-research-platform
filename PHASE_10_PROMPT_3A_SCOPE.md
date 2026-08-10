# Phase 10 Prompt 3A Scope Contract

## Authorization and objective

The owner authorized Prompt 3A to close or truthfully reclassify the nine blockers frozen by
Phase 10 Prompt 3. Prompts 1–3 remain preserved and local. Prompt 4, staging, commit, push, and any
undefined post-Phase-10 work remain prohibited.

## Minimum implementation boundary

- Add backward-compatible `/v1` aliases for the approved foundation, company-resolution, and
  verified-synthesis REST surfaces while retaining every existing unversioned route.
- Publish a machine-readable OpenAPI version policy and a written compatibility/deprecation policy.
- Add an in-process, dependency-free MCP delivery facade exposing only `service_status` and
  `resolve_company`; do not add a network server or MCP SDK.
- Add deterministic, offline evaluation and bounded reliability/load evidence using existing
  identity, verification, synthesis, report, workflow, and request-safety fixtures/contracts.
- Add a threat model/control mapping, supply-chain/dependency review, target SLOs, operational
  runbook, recovery/rollback procedure, release checklist, and reproducible local deployment
  evidence.

## Explicit exclusions

- No authentication, authorization subsystem, request-rate limiter, Redis, PostgreSQL, durable or
  distributed state, cloud deployment, external monitoring stack, LLM/OpenRouter call, LangGraph,
  RAG/vector store, paid service, arbitrary MCP tool execution, filesystem/network MCP capability,
  trading, Prompt 4, or Phase 11.
- Local evidence is not a production SLA, internet-scale load result, public-deployment security
  certification, or durable recovery claim.

## Acceptance

The slice is acceptable only if versioned and legacy REST contracts coexist, MCP is statically
allowlisted and inert to hostile input, evaluations and bounded reliability/load tests pass, the
security/operations/supply-chain evidence is truthful, all Phase 1–9 contracts remain green, and no
new dependency, external call, paid path, stage, commit, or push occurs.
