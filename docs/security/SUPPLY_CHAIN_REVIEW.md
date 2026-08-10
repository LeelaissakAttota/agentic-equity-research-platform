# Phase 10 Supply-Chain Review

## Reviewed inputs

- `pyproject.toml` runtime and development dependency ranges;
- local resolved environment and `pip check`;
- `Dockerfile`, `.dockerignore`, Docker build output, and resolved base-image digest;
- `.github/workflows/ci.yml` permissions, actions, install commands, and test gates;
- package source behavior and Phase 10 dependency delta.

## Findings

- Phase 10 Prompt 1–3A adds **zero** runtime or development dependencies. No OpenAI/OpenRouter,
  LangChain/LangGraph, MCP SDK, database, cache, cloud, monitoring, load-test, vector, or report SDK
  was added.
- Direct dependencies are constrained by compatible major ranges. The local environment reports
  `No broken requirements found` from `pip check`.
- Docker builds from `python:3.12-slim-bookworm`; the validated build resolved digest
  `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`.
  The Dockerfile installs packages only at build time and the runtime image runs as `appuser`.
- CI has read-only repository permission and uses official `actions/checkout@v4` and
  `actions/setup-python@v5`. It installs only the repository's declared package/development extras.
- No lock/constraints file or SBOM is committed. Docker base and Actions use tag/major references,
  not an owner-reviewed immutable digest/commit policy.
- Docker Scout is installed locally, but a CVE scan was not authorized because the tool may upload
  image-derived SBOM/metadata to an external service. No CVE-free claim is made.

## Classification

The **review** is complete, dependency integrity is locally consistent, and the build input is
known. Vulnerability/SBOM evidence remains **partial** until an approved local-only scanner or
explicit authorization for an external scanner is provided. This limitation must stay visible in
the release checklist and final blocker decision.
