# Security Guidelines

## Security posture

Financial research data and external content are untrusted. Security controls must fail safely without fabricating research, leaking secrets, or silently reducing evidence quality. This is an engineering baseline, not a substitute for a later threat model and production security review.

## Secrets and configuration

- Never hardcode keys, credentials, tokens, database passwords, or private URLs.
- Never commit `.env`; `.env.example` contains blank placeholders only.
- Load secrets from environment or an approved secret manager in later deployments.
- Never log secrets or echo them in startup output, traces, reports, or exceptions.
- Redact common authorization/query/header/DSN fields centrally and test redaction.
- Keep database and Redis credentials out of source and generated client artifacts.

## Network and URL safety

- Require explicit connection/read/write/pool timeouts and total deadlines.
- Use bounded retries only for classified transient failures.
- Validate schemes and destinations; prevent SSRF to loopback, link-local, metadata, private, and disallowed networks unless explicitly approved for a deployment.
- Resolve and revalidate redirect destinations; cap redirects.
- Bound response bytes, decompression ratio, content type, and download duration.
- Use TLS verification; exceptions require an ADR and environment-scoped control.
- Identify clients and respect source terms/rate limits.

## Document and content processing

- Validate type using content and signatures, not extension alone.
- Limit file, page, image, archive, table, and extracted-text sizes.
- Treat parsers as risk boundaries; isolate or sandbox high-risk parsing where practical.
- Reject path traversal, unsafe archives, active content, and unexpected executable formats.
- Use safe temporary paths and remove artifacts according to retention policy.
- Store integrity hashes and parsing status; do not treat partial parses as complete.

## Prompt injection and model safety

- System/developer/application instructions are trusted control input; retrieved filings, reports, web pages, news, transcripts and embedded document text are **untrusted research content**. Keep the two channels structurally separated and label source boundaries.
- Instructions found in retrieved content are quoted data. They cannot tell the system to ignore control rules, reveal secrets, change model/cost policy, execute code, call arbitrary tools, access unrelated files, modify repository state, place trades, or bypass evidence verification.
- Permit models to call only allowlisted, typed, least-privilege tools through application policy.
- Validate model output schemas, citations, URLs, and tool arguments before action.
- Never allow model-produced code or commands to execute automatically.
- Apply task, token, tool, retry, recursion, time, and concurrency budgets.
- A retrieved instruction that conflicts with control policy is recorded as untrusted content and ignored; it is not forwarded as a tool authorization.

## Input, API, and file safety

- Validate all boundary inputs with typed schemas and explicit length/range/enum constraints.
- Authenticate and authorize before sensitive access when those capabilities are introduced.
- Rate-limit and size-limit public interfaces; use idempotency for expensive mutations.
- Avoid exposing stack traces, internal paths, raw provider bodies, or keys in errors.
- Sanitize report filenames, enforce approved output roots, and prevent overwrite by default.
- Use parameterized database queries and least-privilege service accounts.
- Avoid arbitrary deserialization and arbitrary code execution.

## Logging and audit

Record correlation/research-run identifiers, safe event names, state changes, validation outcomes, provider error categories, and access events. Avoid full document/model payloads, credentials, personal data, and confidential source content. Protect log integrity, retention, and access in deployment.

## Dependencies and supply chain

- Minimize and constrain dependencies; prefer maintained libraries and lock/reproducible environments.
- Review licenses and provenance; scan dependencies, containers, and secrets in CI before production.
- Pin deployment artifacts by digest where appropriate and generate an SBOM in hardening phases.
- Never install packages dynamically from model/user-provided content.

## Data protection

Classify source, user/session, report, and operational data. Define retention, deletion, backup, access, and encryption policies before production. Collect the minimum user data required. Keep tenants/users isolated when multi-user support arrives.

## Incident behavior

Security-relevant failures must be explicit and traceable. Revoke/rotate exposed credentials, preserve permitted evidence, contain the path, assess impact, and document remediation. Never “fix” a leak by deleting history without owner/security direction.

## Security gates by phase

Every phase reviews new trust boundaries. Production hardening requires a threat model, secret and dependency scans, auth/authorization review, abuse tests, backup/restore validation, container review, and incident/runbook evidence.
