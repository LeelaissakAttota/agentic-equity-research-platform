# Phase 10 Blocking Gaps Matrix

This matrix starts from the owner-approved Prompt 3 acceptance freeze. “Closed” requires the kind
of evidence named in each row; documentation alone cannot close a runtime or test requirement.

| Prompt 3 blocker | Closure requirement | Initial classification | Prompt 3A minimum evidence | Final classification |
|---|---|---|---|---|
| Versioned REST policy | Backward-compatible version identity, route strategy, OpenAPI representation, compatibility/breaking/deprecation rules | IMPLEMENTATION REQUIRED | `/v1` approved aliases, unchanged legacy routes, policy document, compatibility tests | **CLOSED** — five approved `/v1` aliases, legacy compatibility, OpenAPI metadata, and 27 interface/security tests |
| Selected MCP exposure | Explicitly allowlisted adapter over approved use cases with negative/security tests | IMPLEMENTATION REQUIRED | In-process facade for service status and company resolution; no server/SDK/dynamic tools | **CLOSED** — minimal in-process exposure; exactly two read-only/offline capabilities; unknown, hostile, URL/path, shell, secret, trading, and policy inputs reject |
| Comprehensive evaluations | Deterministic financial/evidence end-to-end cases with machine pass/fail criteria | EVIDENCE REQUIRED | Offline Apple/Reliance/GOOG/GOOGL, evidence states, workflow, verification, synthesis/report, and boundary suite | **CLOSED** — 21 deterministic production-readiness and reliability/load evaluations pass |
| Reliability evidence | Finite repeated operations, deterministic consistency, exception/failure/isolation counts | EVIDENCE REQUIRED | Reproducible local repeated and concurrent test budget | **CLOSED (local evidence only)** — 114 bounded operations, zero unexpected failures, deterministic outputs, unique correlations/workflow IDs |
| Load/resource evidence | Finite representative concurrent/repeated requests; no 5xx/leakage/collision/bypass symptoms | EVIDENCE REQUIRED | Local-development-only bounded load tests and documented scale | **CLOSED (local evidence only)** — 32 concurrent resolutions plus bounded repeated endpoint, synthesis, and workflow operations; no production-scale claim |
| Formal threat review | Architecture-specific assets/boundaries/actors/threats/control mapping/residual risks | DOCUMENTATION REQUIRED | Threat model mapped to actual tests and explicit residual risks | **CLOSED** — structured threat/control/evidence/residual-risk mapping in `docs/security/THREAT_MODEL.md` |
| Supply-chain review | Manifest/build/CI/source audit plus dependency policy and residual visibility limits | EVIDENCE REQUIRED | Offline manifest/CI/container review, `pip check`, dependency policy | **CLOSED** — local Trivy 0.73.0 container scan, CycloneDX SBOM (application + container), pip-audit (0 production vulns), dependency policy documented; Docker Scout historical scan noted as exception |
| SLOs/runbooks | Unevaluated targets separated from measured evidence; actionable current-architecture procedures | DOCUMENTATION REQUIRED | SLO, runbook, observability limits, incident and failure procedures | **CLOSED** — target-versus-measured SLO contract and current-architecture runbook exist; external dashboards/alerts are not claimed |
| Recovery/rollback | Known-good selection, bad config/deploy recovery, rollback validation, state-loss caveats | DOCUMENTATION REQUIRED | Current-architecture recovery/rollback procedure and checklist | **CLOSED** — protected Phase 9 checkpoint image built separately, became healthy/ready in production mode, reported version `0.1.0`, and stopped cleanly; in-memory loss is explicit |
| Deployment-release evidence | Reproducible build/config/start/smoke/stop evidence and release checklist | EVIDENCE REQUIRED | Docker/Compose evidence where locally available; limitation if unavailable | **CLOSED (local evidence only)** — candidate image built, ran healthy as non-root, passed health/ready/version/`v1`/Apple smoke, and shut down cleanly; no cloud claim |

## Frozen deployment-dependent deferrals

Authentication, authorization, request-rate limiting, durable persistence, distributed state, and
cloud deployment remain deferred by the Prompt 3 acceptance decision. They are not silently
represented by request-size limits, workflow approval, in-memory storage, or local container tests.

## Prompt 3A release decision (superseded by Prompt 3C)

Eight blocker groups were closed at the frozen local/private-deployment acceptance boundary. The
supply-chain group remained blocking because a dependency/container vulnerability scan and SBOM are
not available as approved evidence. The owner authorized Prompt 3C (local Trivy + CycloneDX SBOM) to
close this group.

## Prompt 3C resolution

Local Trivy 0.73.0 container scan completed with CycloneDX SBOM generation. Application SBOM
(CycloneDX 1.5, 256 components), Container SBOM (CycloneDX 1.7), pip-audit (0 vulnerabilities in
production dependencies), Trivy scan (6 CRITICAL, 20 HIGH, 71 MEDIUM, 97 LOW, 11 UNKNOWN — all
OS/build-time packages, zero in production Python runtime). Docker Scout historical scan transmitted
metadata to Docker cloud (noted as exception; final acceptance uses local Trivy only). Supply-chain
requirement **SATISFIED**.

All nine blocker groups are now closed. Phase 10 Prompt 4 authorized.
