# Phase 10 Release Checklist

Prompt 4 must execute and record this checklist. A checked item requires evidence; documentation or
intent alone is insufficient.

## Recovery and repository

- [ ] `main`, expected protected ancestor/current candidate, and `origin/main` verified.
- [ ] No unexplained tracked edits, staged files, generated files, or protected-owner-file changes.
- [ ] Intentional Phase 10 tree classified and secret/staged-content audit complete.

## Software gates

- [ ] Full pytest, Phase 10 focused, cross-phase, evaluation, reliability/load, architecture,
  phase-boundary, settings, security, repository, and API tests pass with no unexplained critical
  skip/failure.
- [ ] Ruff lint, Ruff format check, strict mypy, and `git diff --check` pass.
- [ ] OpenAPI has the expected legacy routes, selected `/v1` aliases, version metadata, and no
  unauthorized MCP/agent/trading path.
- [ ] Verification, evidence/citation, confidence/conflict, stale/missing, identity, no-advice,
  JSON/Markdown/DOCX, prompt/tool-injection, and report-path protections pass.

## Security and supply chain

- [ ] Threat model/control mapping reviewed; residual risks accepted by the appropriate owner.
- [ ] Dependency manifest/delta, package sources, CI Actions, Docker base/build inputs reviewed.
- [ ] `pip check` or equivalent consistency check passes.
- [ ] Approved dependency/container vulnerability scan and SBOM evidence recorded, or explicit
  owner/security acceptance of the limitation is documented. **Currently unresolved.**
- [ ] No credential/API-key/private-key signature, `.env`, token, unsafe primitive, arbitrary MCP
  tool/path/URL, or paid-model bypass is present.

## Operations and deployment

- [ ] Target SLOs, monitoring ownership, alert routing, log retention/access, and runbook reviewed.
- [ ] Authentication/authorization/rate-limit/public-exposure decision matches the deployment.
- [ ] Durable/in-memory state and recovery consequences are explicitly accepted.
- [ ] Docker image builds; Compose configuration validates; candidate starts as non-root; health,
  readiness, version, versioned route, representative API, and clean shutdown pass.
- [ ] Previous known-good image/release exists; rollback rehearsal and post-rollback smoke are
  recorded for the target environment.

## Release action

- [ ] Owner explicitly authorizes Prompt 4 staging/commit/push.
- [ ] Stage only classified intentional files and inspect the complete staged diff.
- [ ] Create one clear Phase 10 commit; do not amend/force-push.
- [ ] Push, verify local HEAD equals `origin/main`, and record the commit/image identifiers.
