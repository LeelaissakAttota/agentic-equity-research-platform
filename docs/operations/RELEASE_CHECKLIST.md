# v1.0.0 Release Checklist

A checked item requires evidence. Historical Phase 10 checkpoint completion does not substitute
for validation of a newly built release candidate.

## Recovery and repository

- [x] Phase 10 Prompt 4 release checkpoint was committed and pushed on `main`.
- [x] Final Release Blocker 2 aligned runtime/package/OpenAPI version `1.0.0`, Compose image naming,
  current documentation, and the synthesis example without changing product logic.
- [ ] Before publication, verify the intended release commit and `origin/main` are synchronized,
  with no unexplained tracked edits, staged files, generated files, or protected-owner-file changes.

## Software gates

- [x] After all release-only changes, rerun full pytest, Phase 10 focused, evaluation,
  architecture/configuration/API, security, and repository gates with no unexplained failure.
- [x] Rerun Ruff lint, Ruff format check, strict mypy, and `git diff --check`.
- [x] Verify `/health`, `/ready`, `/version=1.0.0`, OpenAPI `info.version=1.0.0`, the five selected
  `/v1` aliases, and the current fixture-labelled synthesis example against the built candidate.
- [x] Preserve verification/evidence/confidence/conflict/stale/missing/no-advice and
  JSON/Markdown/DOCX protections.

## Security and supply chain

- [x] Threat model/control mapping and deployment-dependent residual risks are documented.
- [x] Dependency manifest, package sources, CI Actions, and Docker build inputs were reviewed.
- [x] `pip check` passed during final release validation.
- [x] Generate and retain local application/container SBOM and vulnerability evidence for exact
  candidate image `sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f`,
  including commands, versions, timestamps, hashes, findings, and limitations under
  `release_evidence/v1.0.0/`.
- [ ] **Final Release Blocker 1:** owner reviews the 26 candidate-affecting Critical/High records
  and explicitly accepts the documented residual risk or authorizes targeted remediation and fresh
  exact-candidate evidence. Do not claim CVE-free status.
- [x] Reconfirm no committed credential/private-key signature, unsafe primitive, arbitrary MCP
  capability, or paid-model bypass is present.

## Operations and deployment

- [x] Target-vs-measured SLO, local reliability evidence, runbook, deployment evidence, and
  historical rollback rehearsal are documented.
- [ ] Confirm the target deployment decision for authentication, authorization, rate limiting,
  TLS/proxy/network controls, monitoring ownership, and in-memory state consequences.
- [x] Build `agentic-financial-intelligence:1.0.0`; validate Compose; start as non-root with a
  read-only root filesystem; run health/readiness/version/versioned-route/representative smokes;
  and stop any temporary audit container cleanly.

## Release action

- [ ] Owner reviews the final diff and exact-candidate supply-chain evidence.
- [ ] Owner explicitly authorizes staging, commit, and non-force push of release-only changes.
- [ ] Only after all preceding gates pass, create and verify Git tag/release name `v1.0.0` and the
  GitHub Release. Do not begin JARVIS integration as part of this release.
