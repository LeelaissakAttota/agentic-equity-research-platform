# Local Container Deployment Evidence

Classification: **LOCAL DEVELOPMENT EVIDENCE ONLY**. Date: 2026-08-10 (Asia/Calcutta).

## Validated sequence

1. Docker Engine server `29.6.2` and Compose `v5.3.1` were available.
2. `docker build --tag agentic-financial-intelligence:phase10-prompt3a .` completed successfully.
3. The build resolved `python:3.12-slim-bookworm` to
   `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2` and produced local image
   `sha256:2a598a0397aebb1b0d25e2569c5e6b3fc77dc07123b089d89f02004c80344230`.
4. A temporary localhost-only production-mode container started as `appuser` with paid models
   disabled and an explicit local host allowlist.
5. Docker reported the container `running healthy`.
6. `/health=ok`, `/ready=ready`, `/version=0.1.0` with environment `production`,
   `/v1/health=ok`, and `/v1/companies/resolve` returned canonical Apple/NASDAQ `RESOLVED`.
7. The container stopped cleanly and `--rm` removed it. No cloud deployment occurred.
8. `docker compose config --quiet` is part of the final quality gate.

## Rollback rehearsal

The protected Phase 9 checkpoint `572ddeb7c6a5c96350af2520f0f5a0eb7ad391e1` was exported without
checkout/reset and built as the separate local image
`agentic-financial-intelligence:phase9-known-good`. A localhost-only production-mode container
started with paid models disabled and an explicit host allowlist, became Docker `healthy`, returned
`/health=ok`, `/ready=ready`, and `/version=0.1.0` with environment `production`, then stopped and
removed cleanly. Temporary archive files were removed. The working tree and Git references were not
changed.

## Limitations

- The image build resolved dependencies from public package/container registries; no committed lock
  or SBOM exists.
- No target TLS, proxy, public hostname, auth/rate policy, durable state, cloud rollout, load balancer,
  external monitoring, backup restore, or target-environment rollback was exercised. The rollback
  rehearsal proves the local protected image/start/status/stop procedure only.
- Docker Scout CVE scanning was not authorized because it may upload image-derived metadata. This
  unresolved supply-chain evidence remains in the release checklist.
