# Supply-Chain Review

## Current v1.0.0 release-candidate status

The Phase 10 Prompt 3C checkpoint historically satisfied its supply-chain gate with local
pip-audit, CycloneDX application/container SBOM, and Trivy evidence. Those results are preserved in
the Phase 10 status/changelog/audit record and are not a CVE-free claim.

Fresh exact-candidate evidence is now retained under `release_evidence/v1.0.0/` for local image
`sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f`, built from
`python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134`.
The evidence includes pip-audit JSON/human summary, CycloneDX application and container SBOMs,
Trivy JSON/table/human summary, an individual classification for every finding, artifact hashes,
commands, tool/database versions, and sanitized secret-hygiene results.

`pip-audit 2.10.1` reports no known vulnerabilities in the 21 exact active-runtime distributions.
Trivy 0.73.0 reports 6 Critical, 22 High, 79 Medium, 97 Low, and 11 Unknown package/advisory records.
Applicability review marks 2 Critical/High records not applicable and leaves 26 candidate-affecting
Critical/High records for owner review. Most have no vendor fix and no identified service attack
path; one fixable High record is vendored beneath pip. No package/base change was made, no finding
was hidden, and no CVE-free claim is made.

Final Release Blocker 1 therefore remains **open on security disposition, not missing evidence**.
Before a tag or GitHub Release is published, the owner must explicitly accept the documented
residual risk or authorize targeted remediation and regeneration of exact-candidate evidence.

## Historical Prompt 3A review

### Reviewed inputs

- `pyproject.toml` runtime and development dependency ranges;
- local resolved environment and `pip check`;
- `Dockerfile`, `.dockerignore`, Docker build output, and resolved base-image digest;
- `.github/workflows/ci.yml` permissions, actions, install commands, and test gates;
- package source behavior and Phase 10 dependency delta.

### Findings

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

### Classification at Prompt 3A

At Prompt 3A, the **review** was complete and dependency integrity was locally consistent, but
vulnerability/SBOM evidence remained partial. Prompt 3C later closed that historical Phase 10 gate
with approved local tooling. The current release-candidate status is governed by the section above.
