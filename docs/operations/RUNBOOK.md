# Operations, Recovery, and Rollback Runbook

This runbook applies to the current single-process/container architecture. Substitute only
environment-approved image identifiers, hostnames, ports, and secret injection. Never paste real
credentials into commands, logs, tickets, or reports.

## Startup and validation

1. Confirm the intended Git release/image identifier and review the release checklist.
2. Supply `APP_ENV=production`, non-debug `LOG_LEVEL`, explicit `ALLOWED_HOSTS`, bounded body limit,
   and `ALLOW_PAID_MODELS=false`. Leave optional provider/model credentials blank unless separately
   approved.
3. Validate Compose/configuration, build the immutable candidate, and start it through the approved
   deployment mechanism.
4. Check `/health` (process liveness), `/ready` (registered runtime/config readiness), `/version`
   (expected service version/environment), and `/v1/health`.
5. Run a canonical `/v1/companies/resolve?q=Apple&exchange=NASDAQ` smoke and an offline verified
   synthesis/report smoke where permitted.

## Failure procedures

### Configuration or startup failure

- Read the safe error category/type, not raw secrets. Compare only approved variable names and
  non-secret values with `.env.example` and deployment configuration.
- Correct invalid host/log/body/provider/paid policy; do not bypass validators.
- If startup remains failed, stop the candidate and trigger rollback.

### Health/readiness failure

- Health failure means the process/container is not serving: inspect container state and safe logs.
- Ready failure means a registered check failed: record its non-secret check name/detail and repair
  the dependency/configuration. Do not remove the check to declare readiness.
- Confirm `/version` before assuming which release is running.

### Request rejection

- Use correlation ID, static route/operation, status, and safe error code.
- `invalid_host`, `invalid_request`, `request_too_large`, and `request_too_complex` are boundary
  failures. Never log/copy raw authorization, cookie, body, query secret, or malicious content.
- Repeated boundary failures may indicate abuse; request-rate protection is deployment-deferred.

### Unexpected 5xx

- Record time, correlation ID, route template, version, safe exception type, and reproduction class.
- Do not expose stack traces, exception messages, bodies, reports, evidence bundles, or paths to the
  client. Reproduce offline with a sanitized fixture and add a regression test.
- Roll back if errors are sustained or affect verification, identity, report integrity, or readiness.

### Docker startup/build failure

- Verify Docker availability, build context, base-image resolution, disk capacity, and package index
  reachability. Do not disable TLS or use an untrusted index.
- A failed image build is not deployable evidence. Preserve the last known-good image.

### Report-generation failure

- Preserve the research run/correlation ID and structured error category. Confirm verified evidence,
  safe title/filename, bounded content, and requested format.
- Do not add arbitrary output paths, invoke office/PDF tools, fetch URLs, or rewrite missing data.

### Workflow failure

- Inspect workflow ID, lifecycle status, checkpoint version, task outcomes, and bounded budget.
- Never auto-approve, fabricate task success, or rerun without preserving visible failure state.
- Remember that workflow/memory/watchlist/notification state is process-local and lost on restart.

### Verification failure

- Inspect claim/evidence identity, type, value/unit/currency/period, timestamps, authority, and
  contradiction status. Do not lower gates or treat an LLM/model output as evidence.

### Security incident first response

1. Contain public access or stop the affected candidate without deleting evidence.
2. Revoke/rotate potentially exposed credentials using the approved secret system.
3. Preserve permitted safe logs, version/image identity, correlation IDs, and timeline.
4. Assess Host/header, secrets, paths/reports, prompt/tool injection, identity, verification,
   dependency/build, and paid-policy impact.
5. Roll back to a verified release and obtain owner/security direction before re-exposure.

## Recovery and rollback contract

### Trigger

Rollback on startup/readiness failure, sustained unexpected 5xx, contract/evaluation regression,
security exposure, verification/identity corruption, or owner-declared bad release.

### Procedure

1. Identify the last owner-approved Git checkpoint and immutable image digest/tag from release
   records; verify it passed its release checklist. Do not use destructive Git reset on working
   changes.
2. Stop routing new requests to the candidate and stop it cleanly where possible.
3. Redeploy the previous known-good image/artifact through the same approved mechanism. Do not build
   “latest” during an incident.
4. Verify `/health`, `/ready`, `/version`, `/v1/health`, company resolution, and a representative
   verified synthesis/report result.
5. Confirm logs show the expected version and no repeated failure category; record the rollback and
   remaining impact.

### State caveat

Restart/rollback loses in-memory workflows, research memory, watchlists, notifications, caches, and
unpersisted report artifacts. There is no database backup/restore contract because no durable store
is implemented. Never claim recovery of that state. Durable adapters would require migrations,
backup/restore tests, RPO/RTO, and a new runbook revision.
