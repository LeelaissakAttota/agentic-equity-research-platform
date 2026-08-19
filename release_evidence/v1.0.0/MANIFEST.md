# v1.0.0 release supply-chain evidence manifest

## Release and candidate identity

| Field | Value |
|---|---|
| Release version | `1.0.0` |
| Intended Git release identifier | `v1.0.0` |
| Git HEAD during audit | `27359b5da100f721953cd27096035c24c490f33a` (`docs: add resume/demo packaging for equity research platform`) |
| Branch / upstream | `main` / `origin/main` at the same HEAD |
| Image name | `agentic-financial-intelligence:1.0.0` |
| Immutable local image ID | `sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f` |
| Local repository digest | `agentic-financial-intelligence@sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f` |
| Candidate linux/amd64 manifest | `sha256:9ac5d440d21e3ab2ff09f1c0bd59dd2594fd92059d86fedd1e5e16379873f722` |
| Published registry digest | None; the image was not pushed or published |
| Image created | `2026-08-18T15:12:14.751008325Z` |
| Platform | `linux/amd64` |
| Image size | 62,864,749 bytes |
| Base tag/digest used by build | `python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` |
| Base linux/amd64 manifest | `sha256:356b0d18f9385f4bdcc673af60e1e64c9d1504952e4ec36ee32044c722a6bc4e` |
| Underlying Debian base annotation | `debian:bookworm-slim@sha256:362e64223cc0da95422b3b13c045186fc0a81250e765d31c025fbddf257f6143` |
| BuildKit history | Build `a4o2vwwxkfdc9rkzva4f8x5cb`; VCS revision `27359b5da100f721953cd27096035c24c490f33a`; material digest confirms base index `sha256:a116...8134` |
| Evidence window | `2026-08-18T15:32:21Z` through `2026-08-18T15:36:13Z` |

The local repository digest is a Docker-local OCI index digest and equals the image ID. It is not a
registry digest and was not obtained by publishing the image.

## Toolchain

| Tool | Version | Installation / identity |
|---|---:|---|
| Docker Client / Engine | `29.6.2` / `29.6.2` | Docker Desktop `4.84.0 (234817)`, local `desktop-linux` context |
| Docker Compose | `v5.3.1` | Existing Docker Desktop plugin |
| Docker Buildx | `v0.35.0-desktop.2` | Existing Docker Desktop plugin |
| pip-audit | `2.10.1` | Installed into isolated `%LOCALAPPDATA%\CodexAuditTools\financial-intelligence-v1.0.0\python` virtual environment; no project declaration changed |
| cyclonedx-bom | `7.3.1` | Installed into the same isolated audit virtual environment; no project declaration changed |
| Trivy | `0.73.0` | Official portable Windows release ZIP extracted under `%LOCALAPPDATA%\CodexAuditTools\financial-intelligence-v1.0.0\trivy-0.73.0`; no project declaration changed |
| Trivy vulnerability DB | schema `2`, updated `2026-08-18T12:56:24.164002626Z` | Downloaded locally from `mirror.gcr.io/aquasec/trivy-db:2`; subsequent scans used offline dependency analysis |

No Docker Scout scan was run. The image and repository contents were not uploaded. `pip-audit`
queried the PyPI vulnerability service using only the retained package names and versions; Trivy
downloaded its public vulnerability database and then read the image from the local Docker daemon.

## Commands

Paths to isolated tools are represented as `<audit-tools>` below. Commands did not contain secrets.

```text
docker image inspect agentic-financial-intelligence:1.0.0
docker buildx imagetools inspect python:3.12-slim-bookworm
docker run --rm --entrypoint /opt/venv/bin/python sha256:b05d...c3b0f -m pip freeze --all
docker run --rm --entrypoint /opt/venv/bin/python sha256:b05d...c3b0f -m pip check

<audit-tools>/pip-audit --requirement application-requirements.txt --no-deps --disable-pip --strict --vulnerability-service pypi --progress-spinner off --format json --output pip-audit.json
<audit-tools>/cyclonedx-py requirements application-requirements.txt --pyproject ../../pyproject.toml --mc-type application --spec-version 1.6 --output-reproducible --output-format JSON --output-file application-sbom.cdx.json --validate

<audit-tools>/trivy image --download-db-only --cache-dir <audit-cache> --skip-version-check
<audit-tools>/trivy image --image-src docker --offline-scan --skip-db-update --skip-java-db-update --skip-version-check --cache-dir <audit-cache> --scanners vuln --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --list-all-pkgs --format json --output trivy-vulnerabilities.json sha256:b05d...c3b0f
<audit-tools>/trivy image --image-src docker --offline-scan --skip-db-update --skip-java-db-update --skip-version-check --cache-dir <audit-cache> --scanners vuln --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --format table --output trivy-vulnerabilities.txt sha256:b05d...c3b0f
<audit-tools>/trivy image --image-src docker --offline-scan --skip-db-update --skip-java-db-update --skip-version-check --cache-dir <audit-cache> --scanners vuln --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --format cyclonedx --output container-sbom.cdx.json sha256:b05d...c3b0f

git ls-files
git grep -Il -E <private-key-signature-patterns> -- .
git grep -Il -E <high-confidence-token-signature-patterns> -- .
.venv/Scripts/python -m pytest -q tests/unit/test_repository_baseline.py tests/unit/test_logging_safety.py tests/unit/test_settings.py tests/unit/test_settings_deep.py
```

The actual scans used the full immutable image ID shown in the identity table. Abbreviated IDs above
are for readability only.

## Results and decisions

### Application dependencies

`pip-audit` evaluated all 21 exact third-party/tooling distributions from the active `/opt/venv`
release environment and reported no known vulnerabilities (exit 0). No findings were suppressed and
no package was upgraded. This does not cover vendored packages as independent distributions; Trivy
covers those bytes at the container level.

### SBOMs

- Application SBOM: CycloneDX 1.6 JSON, application root
  `agentic-financial-intelligence` version `1.0.0`, 21 components and 22 dependency records.
- Container SBOM: CycloneDX 1.7 JSON, exact image ID as root, 148 components and 149 dependency
  records.

### Container vulnerabilities

Trivy retained 215 package/advisory records: **6 Critical, 22 High, 79 Medium, 97 Low, and 11
Unknown**. Eight records report a fixed version; unfixed records were not hidden. Individual
classification is retained in `trivy-findings-classification.csv`:

- 26 `NEEDS REVIEW` (5 Critical and 21 High that affect shipped bytes);
- 2 `NOT APPLICABLE` (one 32-bit-only Perl advisory on amd64; one setuptools record sourced from
  BuildKit third-party SBOM metadata although setuptools is absent from the final filesystem);
- 187 `ACCEPT` Medium/Low/Unknown residual records under the audit severity gate.

The `NEEDS REVIEW` records are potential release blockers. Most have no vendor fix and no identified
service attack path because the container is non-root/read-only and exposes no shell, package-manager,
Perl, archive, mount, ACL, block-device, QUIC, or SQLite persistence capability. The fixable High
`msgpack` record is present only as a dependency vendored beneath pip; pip is not invoked by the
service. These reachability limits reduce risk but do not replace owner review. No dependency,
Dockerfile, or base-image remediation was performed.

### Secret hygiene

The sanitized tracked-file checks found no private-key signature, no high-confidence live-token
signature, and no tracked environment/key artifact except the intentionally tracked `.env.example`.
Sixteen repository secret/configuration tests passed. No secret value was printed or retained.

## Artifact hashes

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `application-requirements.txt` | 376 | `1ea9f7c18807fafab507ac1a9eb6b3fc60b7b2c4ae2d8b274e2f09deae77e789` |
| `application-sbom.cdx.json` | 14,394 | `513004ac078f07561e656b85f3f9492b27832d0fc490ac9b9122c13ccdc6ace1` |
| `container-sbom.cdx.json` | 614,482 | `8dba4169fcff60ce17aed47da49a386e51f6637833531a87557c3f985b8ba69c` |
| `pip-audit-summary.md` | 870 | `e63a8584a699f211f43865c628546390d38222224ecfcc3dd87e3d096934432b` |
| `pip-audit.json` | 1,228 | `ef5aa127edc2363658314a858fba76f88a3f58b89223f4600a2b5323cb1d7e22` |
| `secret-hygiene-summary.md` | 783 | `5bebb2581db85da603abaa54841f549502d7c295621c553dee8e7b955cb395fe` |
| `trivy-findings-classification.csv` | 68,948 | `135fcf9c532a8a15f2b9f9a81f1d5139faa12bbf77099f9c209f2560ff246129` |
| `trivy-summary.md` | 3,955 | `70462bc0a3419d3dec9b6a71d2c2e30c35296a73fafc1d2c383fe564fa1ac2d7` |
| `trivy-vulnerabilities.json` | 1,083,318 | `90f0cc7144b0c24abf38ca4340ca98acb61d64e2e4865d63504eb24f45b7c42b` |
| `trivy-vulnerabilities.txt` | 222,138 | `3c541493506f8c7cdd2abed77f854cfbef1d6f7fe2668b1bdb9b89e9d7b110de` |

## Limitations and remaining gate

- The Git HEAD is unchanged and synchronized, but Blocker 2 changes and this evidence remain local
  and unstaged. The image is tied to the exact local ID, not yet to a published registry digest.
- The Docker base is referenced by a floating tag in `Dockerfile`; the digest above is the identity
  resolved for this candidate, not a permanent source pin.
- The application SBOM was reconstructed from the immutable candidate's exact `pip freeze` and
  validated, but CycloneDX reported that the root-component dependency graph is incomplete.
- Trivy warned that BuildKit third-party SBOM metadata can produce inaccurate package detection;
  direct filesystem/import probes were used for the two affected High/Critical applicability
  decisions described above.
- Reachability review is static and configuration-based; no exploit testing was performed.
- The repository has no dependency lock/constraints file.

**Blocker 1 status: STILL OPEN pending owner review of 26 candidate-affecting Critical/High records.**
The evidence-generation requirement is complete and reproducible; the security disposition gate is
not closed. Owner review must either explicitly accept the documented residual risk or authorize
targeted remediation and regeneration of this exact-candidate evidence.
