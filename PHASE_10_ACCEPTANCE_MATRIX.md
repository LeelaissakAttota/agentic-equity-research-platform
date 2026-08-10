# Phase 10 Acceptance Matrix

This is the authoritative Phase 10 Prompt 3 classification. It is grounded in
`PHASES.md`, `ROADMAP.md`, the Prompt 1–2 scopes/reports, source code, tests, and the
current Git diff. Phase 10 remains in progress; this matrix does not claim public-production
readiness.

## Frozen phase definition

- **Title:** MCP/API Integration, Evaluation & Production Hardening
- **Objective:** Validate deployability, expose approved integrations, and produce
  production-readiness evidence.
- **Required scope/deliverables:** mature and versioned REST contracts; selected MCP
  tools/resources; deployment-dependent auth/rate-limit decisions; reliability/security
  testing; observability/SLO evidence; backup/recovery/rollback evidence; deployment
  automation/runbooks; comprehensive financial/evidence evaluation and a release checklist.
- **Acceptance:** approved interfaces only, passed reliability/security/evaluation thresholds,
  documented operations, independent deployability, and evidence-backed readiness claims.
- **Boundary:** no direct trading, guaranteed outcomes, paid-model fallback, mandatory paid
  data, or JARVIS coupling.

## Capability classification

| Requirement | Classification | Evidence and limitation |
|---|---|---|
| Production configuration | IMPLEMENTED | Typed environment/configuration contract; production validation is fail-closed. |
| Fail-closed production settings | IMPLEMENTED | Production rejects debug logging, wildcard/empty/malformed hosts, inconsistent enabled providers, and paid models. Local-only host defaults prevent accidental public admission. |
| Trusted-host validation | IMPLEMENTED | Exact allowlist with case normalization and valid optional ports. Forwarded host headers are not trusted. |
| Ambiguous Host rejection | IMPLEMENTED | Missing, duplicate, malformed, control/outer-whitespace, oversized, spoof-like, and extreme-port values fail safely. |
| Content-Length validation | IMPLEMENTED | Duplicate and non-ASCII/negative/signed/whitespace/malformed/extreme numeric values fail safely without unbounded integer conversion. |
| Request-body byte limits | IMPLEMENTED | Declared and actual received bytes are bounded at below/exact/above thresholds, including multibyte and absent-length requests. |
| Chunk-count limits | IMPLEMENTED | At most 1024 request-body messages; rejection occurs before downstream execution. |
| Query/parameter bounds | IMPLEMENTED | Existing bounded schemas plus watchlist collection and workflow-memory limits; global body bound is the aggregate backstop. |
| Correlation IDs | IMPLEMENTED | Safe caller IDs are retained; missing, duplicate, oversized, Unicode, control, whitespace-ambiguous, or malformed IDs become UUIDv4 values. |
| Safe API errors | IMPLEMENTED | Stable correlation-aware envelopes and safe status categories. |
| Exception sanitization | IMPLEMENTED | HTTP detail, unexpected exception messages, repr, and traceback are not returned. Structured errors retain type only. |
| Path leakage prevention | IMPLEMENTED | Error telemetry uses route templates rather than concrete URLs or filesystem paths. |
| Telemetry privacy | IMPLEMENTED | Correlation, route template/constant operation, method, status category/code, duration, and safe error category only. |
| Access/client logging privacy | IMPLEMENTED | URL-bearing Uvicorn access, HTTPX, and HTTPCore INFO logging is suppressed; tested application events omit bodies, queries, headers, cookies, reports, and exception text. |
| Readiness semantics | IMPLEMENTED | `/ready` covers registered application/configuration checks only and does not invent deferred dependencies. |
| Health semantics | IMPLEMENTED | `/health` is process liveness. |
| Version semantics | IMPLEMENTED | `/version` exposes service/version/environment only. |
| Report delivery safety | IMPLEMENTED | Deterministic in-memory JSON/Markdown/DOCX; safe filename/base64 transport; no output path, file write, fetch, shell, LibreOffice, or PDF. |
| Verification preservation | IMPLEMENTED | Phase 8 verification, confidence, contradictions, stale/missing/insufficient semantics, and fail-closed bypass behavior remain green. |
| Synthesis preservation | IMPLEMENTED | Phase 9 verified-claim gate, sections, summary, citations, JSON/Markdown/DOCX, language truthfulness, and no-advice rules remain green. |
| Identity preservation | IMPLEMENTED | Apple/NASDAQ, Reliance NSE/BSE isolation, wrong-exchange rejection, and GOOG/GOOGL distinct securities remain green. |
| Prompt-injection resistance | IMPLEMENTED | Hostile data cannot alter configuration, identity, verification, conflicts, workflow approval, reports, secrets, commands, or advice policy. |
| Docker/Compose foundation | IMPLEMENTED | Python 3.12, non-root runtime, read-only Compose root, `/tmp` tmpfs, no-new-privileges, blank secrets, local health, and offline startup. It is not a production deployment manifest. |
| Architecture | IMPLEMENTED | Domain → Application/Ports → Infrastructure → API/Composition remains intact; HTTP hardening stays outside research truth logic. |
| Dependencies | IMPLEMENTED | Prompt 1–3 dependency delta is zero. |
| Paid-model/cost policy | IMPLEMENTED | `ALLOW_PAID_MODELS=false` remains fail-closed; OpenRouter/LLM/paid calls are zero; required external cost is $0. |
| Security | PARTIAL / DOCUMENTED | Boundary, secret, logging, injection, unsafe-primitive, and regression gates pass. Required threat review, dependency/container scanning, abuse testing, and target certification are absent. |
| Authentication | DEFERRED BY DESIGN | The phase requires it only as the approved deployment requires. No target IdP, trust boundary, token format, role model, or secret lifecycle is approved. Public exposure is prohibited without a decision/control. |
| Authorization | DEFERRED BY DESIGN | Human workflow approval is not API authorization. A target capability/role policy remains unapproved. |
| Request-rate limiting | DEFERRED BY DESIGN | Body/chunk limits are not rate limits. Keying, thresholds, proxy trust, endpoint classes, and local/distributed enforcement require a target deployment decision. |
| Durable persistence | DEFERRED BY DESIGN | Phase 7 workflow/memory/watchlist state remains process-local. Closure requires explicit owner acceptance of that operating model or durable adapters plus recovery evidence. |
| Distributed state | DEFERRED BY DESIGN | No distributed worker, rate-limit state, or idempotency claim; not required without an approved distributed topology. |
| Observability | PARTIAL / DOCUMENTED | Safe structured logs, correlation, readiness, and request outcome telemetry exist. SLOs, dashboards, alerts, retention, and target monitoring integration are absent. |
| Deployment configuration | PARTIAL / DOCUMENTED | A safe local container foundation exists. TLS, proxy policy, managed secrets, target hosts, artifact provenance, vulnerability evidence, rollout, and rollback are not certified. |
| Production deployment assumptions | PARTIAL / DOCUMENTED | `DEPLOYMENT_PLAN.md` is explicitly a target plan. No public/cloud/distributed production claim is supported. |
| Versioned REST adapter/maturity | BLOCKING | Current OpenAPI is stable and tested, but the phase deliverable explicitly calls for versioned REST adapters/contracts; no approved versioning/deprecation contract exists. |
| Selected MCP exposure | BLOCKING | Selected MCP tools/resources are explicit Phase 10 scope/deliverables and have not been scoped or implemented. |
| Comprehensive financial/evidence evaluation | BLOCKING | Regression fixtures exist, but approved datasets, thresholds, scorecards, and end-to-end evaluation evidence do not. |
| Load/soak/failure reliability evidence | BLOCKING | Request resources are bounded, but approved load/soak/failure-injection thresholds and results do not exist. |
| Threat/supply-chain review | BLOCKING | Local source/secret checks pass; formal threat review, dependency/container scan evidence, and SBOM/release policy are absent. |
| SLOs/dashboards/alerts/runbooks | BLOCKING | Required operational deliverables and thresholds are not yet defined or evidenced. |
| Backup/recovery/rollback | BLOCKING | No approved persistence topology, recovery objectives/tests, deployment rollback rehearsal, or release runbook exists. |
| Deployment automation/release checklist | BLOCKING | No target deployment or evidence-backed release automation/checklist has been accepted. |

## Final acceptance decisions

| Decision | Result | Basis |
|---|---|---|
| Blocking Phase 10 gaps | YES | Explicit phase-level integration, evaluation, reliability, security, operations, and recovery deliverables remain absent. |
| Can Phase 10 close after Prompt 4 now | NO | Prompt 4 cannot truthfully be a release checkpoint until blockers are resolved or the owner explicitly changes the frozen phase contract. |
| Authentication required for closure | DEFERRED | Deployment-dependent in `PHASES.md`; target trust model is not approved. |
| Authorization required for closure | DEFERRED | Deployment-dependent and distinct from workflow approval. |
| Rate limiting required for closure | DEFERRED | Target enforcement policy is not approved. |
| Durable persistence required for closure | DEFERRED | Depends on the accepted operating model; current state is explicitly process-local. |
| Redis required | NO | No approved closure requirement currently selects Redis. |
| PostgreSQL required | NO | No approved closure requirement currently selects PostgreSQL. |
| LangGraph required | NO | Deterministic existing orchestration remains accepted. |
| LLM required | NO | Production hardening and deterministic evaluation do not require an LLM. |
| External observability platform required | NO | Operational evidence is required; a particular external platform is not. |
| Cloud deployment required | DEFERRED | Hosting remains undecided; deployability evidence is required, not a specific cloud. |

## Project phase map

| Phase | Repository-defined title/state |
|---|---|
| 0 | Project Constitution & Repository Bootstrap — complete |
| 1 | Core Application Foundation — complete |
| 2 | Company Resolution & Source Foundation — complete |
| 3 | Market Intelligence — complete |
| 4 | Financial & Filing Intelligence — complete |
| 5 | News, Events, Industry & Regulatory Intelligence — complete |
| 6 | Autonomous Research Planning & Dynamic Orchestration — complete |
| 7 | Evidence Graph, RAG & Research Memory — complete at its accepted deferred-RAG boundary |
| 8 | Verification, Confidence & Reflection — complete |
| 9 | Conversational Research, Multilingual Output & Word Reports — complete at its accepted deterministic reporting boundary |
| 10 | MCP/API Integration, Evaluation & Production Hardening — in progress |
| 11 | Boundary label only; title and objective are not defined; implementation is absent |
| 12+ | Not defined |

The highest explicitly defined phase is **Phase 10**. Phase 10 is the final phase in the frozen
Phase 0–10 roadmap. References to Phase 11 mean only “do not start later work”; they are not a
phase definition or authorization.
