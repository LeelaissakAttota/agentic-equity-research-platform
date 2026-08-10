# REST API Versioning Policy

## Current contract

- Current API major version: `v1`.
- Versioned prefix: `/v1`.
- Package/service release version remains independent (`0.1.0` at this checkpoint).
- OpenAPI exposes `info.x-api-version=v1` and a top-level `x-api-versioning` policy.

The selected versioned surface is `/v1/health`, `/v1/ready`, `/v1/version`,
`/v1/companies/resolve`, and `/v1/research/synthesis`. These routes reuse the same application
contracts as their unversioned equivalents; they do not fork research logic.

## Legacy compatibility

All existing unversioned Phase 1–9 routes remain supported. Prompt 3A adds aliases and removes or
narrows no route, method, status, response field, identity rule, verification gate, or report format.
New clients should prefer `/v1` where a versioned alias exists. The unversioned surface is not a
promise that every future capability will receive an unversioned alias.

## Change rules

- Backward-compatible additions may remain within `v1` after contract, security, and regression
  review.
- A breaking input/output/status/semantic change requires a new major prefix such as `/v2`, an ADR,
  owner approval, migration guidance, and side-by-side compatibility evidence.
- Removal requires owner approval, documentation, an announced replacement, and at least one
  released deprecation window. Silent removal is prohibited.
- Verification, identity, evidence, contradiction, missing/stale-data, and no-advice semantics are
  truth contracts; a transport version cannot weaken them.

## MCP relationship

MCP is a separate selected delivery adapter. REST path versioning does not authorize new MCP tools,
and MCP tool names do not create REST routes. Both interfaces delegate to existing application
capabilities and remain outside the domain model.
