# F07 — Docker/Lock Dependency Drift: Audit Report

**Status: AUDIT ONLY. No source, test, Docker, dependency, or configuration file was modified during this audit.**

## 1. Executive Summary

The project maintains a pinned dependency lock file, `requirements-lock.txt`, which CI installs from exclusively (`pip install -r requirements-lock.txt` followed by `pip install -e . --no-deps`). `Dockerfile`, however, does not reference this lock file at all: its builder stage runs `pip install .` directly, letting pip resolve `pyproject.toml`'s ranged version constraints (e.g. `pydantic>=2.10,<3`) against whatever is newest on PyPI at build time.

This was independently reproduced in this audit, not merely inferred from static inspection: a Docker image was built from the current, unmodified `Dockerfile`/`pyproject.toml` (`agentic-financial-intelligence:1.0.0`, built 2026-09-17, HEAD `d983bce`) and its installed package set was compared directly against `requirements-lock.txt`. **Six packages differ** (`pydantic`, `pydantic_core`, `uvicorn`, `click`, `anyio`, `websockets`), and a seventh divergence exists structurally: `uvloop` is installed in the Linux-based Docker image but is entirely absent from the lock file, because the lock file was generated on a Windows development machine where `uvicorn[standard]`'s Linux-only `uvloop` marker never activates.

The Dockerfile's base image (`python:3.12-slim-bookworm`) is also referenced by a mutable tag, not a digest. Repository evidence (`docs/operations/DEPLOYMENT_EVIDENCE.md`, dated 2026-08-10) shows the same tag previously resolved to a different digest than it resolves to today, confirming the tag has already moved at least once in this project's own history.

**This is a confirmed reproducibility and supply-chain-integrity defect.** The image that Docker would build today from current repository content is not the dependency graph that CI tests, that `requirements-lock.txt` documents as pinned, or that any retained SBOM/vulnerability evidence in `release_evidence/` was generated against. It is not a documentation nitpick — it is a live, measured divergence between what is tested and what would ship.

**Verdict: CONFIRMED.**

## 2. Baseline and Repository State

- Branch: `main`
- HEAD commit: `d983bcea152488c1005168c22f2766fc9dd24056` ("feat(phase-11.2): implement API key authentication foundation"), committed 2026-09-08
- Working tree at audit start: matches the stated F01–F06 baseline (`docker-compose.yml` and several `src`/`tests` files modified from an in-progress, previously-reviewed change set; various untracked `F0*`/audit markdown files). `Dockerfile`, `pyproject.toml`, `requirements-lock.txt`, and `.github/workflows/ci.yml` all have **no uncommitted changes** — this audit inspected exactly what is at HEAD for every file relevant to F07.
- No files were modified by this audit except the creation of this report.
- Docker: available (`Docker version 29.8.0`). Image `agentic-financial-intelligence:1.0.0` was already present locally (built ~4 hours prior to this audit, per `docker inspect`/`docker history`, from the current unmodified `Dockerfile`); it was reused for inspection — no image was rebuilt or mutated for this audit.
- Test/lint baseline was not re-run in this audit (per task scope: audit-only, no file changes); the task's stated baseline (789 passed / 130 subtests, Ruff clean, 2 pre-existing unrelated mypy errors in `domain/orchestration/graph.py`) is taken as given and is orthogonal to F07, which concerns the Docker build path, not the test suite.

## 3. Authoritative Dependency Source

Established from direct repository inspection:

- [pyproject.toml](pyproject.toml) declares **ranged** runtime dependencies:
  ```
  fastapi>=0.115,<1
  pydantic>=2.10,<3
  pydantic-settings>=2.7,<3
  uvicorn[standard]>=0.34,<1
  tzdata>=2025.1; platform_system == 'Windows'
  ```
  plus a `dev` extra (`httpx`, `mypy`, `pytest`, `pytest-asyncio`, `ruff`). Ranges alone do not pin exact versions and are not sufficient to reproduce a specific installed environment.
- [requirements-lock.txt](requirements-lock.txt) is a `pip freeze` snapshot with 35 exact `==` pins. Its own header states: *"Pinned dependency lock for agentic-financial-intelligence v1.0.0. Generated from the verified development venv (Python 3.12.10) via `pip freeze`. Install with: `pip install -r requirements-lock.txt` then `pip install -e . --no-deps`. Do not edit manually."*
- [.github/workflows/ci.yml](.github/workflows/ci.yml) installs **exclusively from this lock file**:
  ```yaml
  - name: Install pinned dependencies
    run: |
      python -m pip install --upgrade pip
      python -m pip install -r requirements-lock.txt
  - name: Install project (no dependency re-resolution)
    run: python -m pip install -e . --no-deps
  - name: Verify dependency integrity
    run: python -m pip check
  ```
  The `--no-deps` flag on the editable install is explicit and deliberate: it prevents pip from re-resolving anything beyond what the lock file already pinned. CI then runs ruff, mypy, and pytest against this exact pinned environment.
- [docs/development/README.md](docs/development/README.md) instructs local developers to run `python -m pip install -e ".[dev]"` — i.e., local dev setup also does **not** install from the lock file; it resolves from `pyproject.toml` ranges directly, same as Docker (see §5).

**Conclusion:** `requirements-lock.txt`, as installed by CI with `--no-deps`, is the project's authoritative, CI-validated dependency source. `pyproject.toml` is the declaration of acceptable version bounds, not a reproducible pin.

## 4. Docker Dependency Installation Path

`Dockerfile` (builder stage):
```dockerfile
FROM python:3.12-slim-bookworm AS builder
...
WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .
```

Verified via `docker history --no-trunc agentic-financial-intelligence:1.0.0`: the only files copied into the build context are `pyproject.toml`, `README.md`, `LICENSE`, and `src/`. `requirements-lock.txt` is **never copied** and **never referenced** by any instruction.

- `pip install .` triggers pip's own resolver against `pyproject.toml`'s ranges at whatever moment the image is built. There is no `-r requirements-lock.txt` and no `--no-deps` — the opposite of CI's pattern.
- The runtime stage only does `COPY --from=builder /opt/venv /opt/venv`; it performs no re-install, so whatever the builder stage resolved is exactly what ships.
- Both `FROM` lines (builder and runtime) reference `python:3.12-slim-bookworm` — a mutable tag, not a digest.

## 5. Local/CI/Docker Dependency Comparison

| Installation path | Source of truth | Resolution mode |
|---|---|---|
| Local dev (`docs/development/README.md`: `pip install -e ".[dev]"`) | `pyproject.toml` ranges | Unconstrained — resolves against live PyPI state at install time |
| CI (`.github/workflows/ci.yml`) | `requirements-lock.txt` | Fully pinned, `--no-deps` on the editable install — no re-resolution possible |
| Docker build (`Dockerfile`) | `pyproject.toml` ranges | Unconstrained — resolves against live PyPI state at build time, identical mode to local dev, **not** CI's pinned mode |

CI is the only installation path in this repository that is fully pinned. Both local development and Docker independently re-resolve from ranges, and can each land on different exact versions depending solely on *when* the resolution happens — with no relationship to each other or to what CI tested.

## 6. Exact Drift Mechanism(s) — Reproduced

**Mechanism 1 — Python package version drift (measured directly).**

Command run against the current image, built from the unmodified `Dockerfile` at HEAD `d983bce`:
```
$ MSYS_NO_PATHCONV=1 docker run --rm --entrypoint /opt/venv/bin/python \
    agentic-financial-intelligence:1.0.0 -m pip freeze --all
```
Result vs. `requirements-lock.txt`:

| Package | `requirements-lock.txt` (CI-tested) | Docker image (actually built) | Drift? |
|---|---|---|---|
| anyio | 4.14.2 | 4.15.1 | **Yes** |
| click | 8.4.2 | 8.5.0 | **Yes** |
| pydantic | 2.13.4 | 2.13.5 | **Yes** |
| pydantic_core | 2.46.4 | 2.46.5 | **Yes** |
| uvicorn | 0.52.3 | 0.53.0 | **Yes** |
| websockets | 17.0.1 | 17.1 | **Yes** |
| fastapi | 0.141.1 | 0.141.1 | No |
| starlette | 1.6.0 | 1.6.0 | No |
| annotated-doc, annotated-types, h11, httptools, idna, pydantic-settings, python-dotenv, PyYAML, typing-inspection, typing_extensions, watchfiles | matched | matched | No |
| uvloop | *(absent — no Linux marker satisfied on the Windows venv that generated the lock file)* | 0.22.1 (installed) | **Yes — structural gap, not just a version mismatch** |

**Six of the seventeen runtime packages present in both differ**, plus one package (`uvloop`) that Docker installs and the lock file cannot represent at all on the platform it was generated on. `pip check` inside the image reports "No broken requirements found" — the drifted graph is internally consistent, which means nothing would visibly alert a developer that it differs from what CI validated.

**Mechanism 2 — Mutable base image tag.**

`FROM python:3.12-slim-bookworm` is not pinned to a digest. Current resolution:
```
$ docker images --digests python:3.12-slim-bookworm
python   3.12-slim-bookworm   sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134
```
This matches the digest recorded in `release_evidence/v1.0.0/MANIFEST.md` (image built 2026-08-18) but **differs** from the digest recorded earlier in `docs/operations/DEPLOYMENT_EVIDENCE.md` (2026-08-10): `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`. This is direct, repository-internal evidence that the same floating tag has already resolved to at least two different digests within this project's own history — it is not a hypothetical risk.

**Contributing factor — no hash enforcement.** `requirements-lock.txt` contains plain `package==version` pins with no `--hash=sha256:...` entries, and neither `requirements-lock.txt` nor `ci.yml` invoke pip's hash-checking mode (`grep -n hash` over both files returns nothing). So even the CI-side pin only fixes version numbers, not package content; this is a secondary observation, not the primary F07 defect, since it affects CI's own reproducibility guarantee too, not just Docker's divergence from CI.

## 7. Evidence and Commands/Results

**Static inspection — no lock-file reference in Dockerfile:**
```
$ grep -n "COPY\|RUN\|FROM" Dockerfile
3:FROM python:3.12-slim-bookworm AS builder
12:COPY pyproject.toml README.md LICENSE ./
13:COPY src ./src
15:RUN python -m venv /opt/venv \
16:    && /opt/venv/bin/pip install --upgrade pip \
17:    && /opt/venv/bin/pip install .
19:FROM python:3.12-slim-bookworm AS runtime
34:COPY --from=builder /opt/venv /opt/venv
```
No `COPY requirements-lock.txt` anywhere in the file; confirmed independently via `docker history --no-trunc` on the built image, which lists only `pyproject.toml`, `README.md`, `LICENSE`, and `src` as copied build inputs.

**CI installation path** (`.github/workflows/ci.yml`, read directly): pinned install + `--no-deps` + `pip check` gate, as quoted in §3/§4.

**Image freeze vs. lock file** — full commands and output:
```
$ docker images agentic-financial-intelligence   # confirms :1.0.0 present, built ~4h prior
$ docker inspect agentic-financial-intelligence:1.0.0 --format '{{.Created}}'
2026-09-17T08:48:47Z
$ MSYS_NO_PATHCONV=1 docker run --rm --entrypoint /opt/venv/bin/python \
    agentic-financial-intelligence:1.0.0 -m pip freeze --all
agentic-financial-intelligence @ file:///build
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
click==8.5.0
fastapi==0.141.1
h11==0.16.0
httptools==0.8.0
idna==3.19
pip==26.2.1
pydantic==2.13.5
pydantic-settings==2.15.0
pydantic_core==2.46.5
python-dotenv==1.2.3
PyYAML==6.0.3
starlette==1.6.0
typing-inspection==0.4.4
typing_extensions==4.16.0
uvicorn==0.53.0
uvloop==0.22.1
watchfiles==1.2.0
websockets==17.1
```
Diffed by hand against `requirements-lock.txt` (§6 table).

**Integrity check inside the image:**
```
$ MSYS_NO_PATHCONV=1 docker run --rm --entrypoint /opt/venv/bin/python \
    agentic-financial-intelligence:1.0.0 -m pip check
No broken requirements found.
```
Confirms the drift is silent — pip's own consistency check passes on the drifted graph.

**Base image digest:**
```
$ docker images --digests python:3.12-slim-bookworm
python   3.12-slim-bookworm   sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134
```
vs. `docs/operations/DEPLOYMENT_EVIDENCE.md` line 10 (2026-08-10): `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2` — different digest, same tag, earlier point in this project's history.

**docker compose config** (confirms compose resolves to the same image/build context, no separate dependency path introduced by Compose):
```
$ docker compose config
services:
  api:
    build: { context: ., dockerfile: Dockerfile }
    image: agentic-financial-intelligence:1.0.0
    ...
```
Compose does not add or alter the dependency-installation mechanism; it builds from the same `Dockerfile` already audited above.

**Hash enforcement check:**
```
$ grep -n "hash" requirements-lock.txt .github/workflows/ci.yml
(no output)
```

**Cleanup:** All inspection commands used `docker run --rm` (self-removing containers) against an image that already existed before this audit began; no image was built or rebuilt, and `docker ps -a` before and after shows no new containers attributable to this project (only pre-existing, unrelated containers from other local projects).

## 8. Security/Reproducibility Impact

**Confirmed:**
- The Docker image buildable from current repository content is **not reproducible** from `requirements-lock.txt`. A second build at a different time would plausibly resolve yet another set of versions, independent of both this audit's snapshot and the lock file.
- Any retained security evidence tied to a specific historical image build (SBOM/Trivy scans referenced in `release_evidence/v1.0.0/MANIFEST.md`) is valid only for that specific build's exact dependency graph and cannot certify a fresh rebuild from the same Git commit, because dependency versions and the base image digest are not fixed inputs to the build.
- CI's quality gates (ruff, mypy, pytest, `pip check`) run against the pinned lock-file environment only. A green CI run provides no assurance about the exact package versions a Docker build performed afterward — or before — would actually contain.

**Not confirmed / bounded:**
- No evidence was found that any of the six drifted versions are individually vulnerable or behaviorally broken today — the defect is the absence of a controlled, reproducible mapping between the tested environment and the shipped image, not a currently-known-bad version.
- No evidence of supply-chain compromise (e.g., a malicious package substitution); this is a process/reproducibility gap, not an indication of tampering.

## 9. Severity Assessment

**Severity: Medium** (process/reproducibility integrity defect; not an active exploit or known vulnerability).

Justification:
- The drift is confirmed and measured (6 of 17 comparable packages, plus a structural platform gap for `uvloop`), not speculative.
- No production deployment currently exists (`docs/development/README.md` states hosting/release status remains open), so no live production traffic is served by a drifted image today — but the exact same `Dockerfile` is what would be used the moment that changes, and the gap already undermines the retained supply-chain evidence in `release_evidence/`.
- Mitigating factor: the application is fixture-first with no database and no default live external calls, bounding the blast radius of a drifted dependency to the API process itself rather than a broader persistence or data-integrity concern.
- Aggravating factor: `pip check` passes on the drifted image, so nothing in the existing pipeline would surface this without a manual, cross-referenced audit like this one.

## 10. Minimal Remediation Options (not implemented)

1. **Install from the lock file in the Dockerfile builder stage** — add `COPY requirements-lock.txt ./` and change the install step to `pip install -r requirements-lock.txt && pip install . --no-deps`, mirroring CI's exact pattern. Closes Mechanism 1.
2. **Pin the base image by digest** (`FROM python:3.12-slim-bookworm@sha256:...`), updated deliberately rather than floating. Closes Mechanism 2.
3. **Regenerate `requirements-lock.txt` from a Linux-targeted resolution** (or an explicit multi-platform lock) so platform-conditional packages like `uvloop` are actually captured for the environment Docker runs. This is a necessary companion to option 1 — without it, wiring Docker to the current Windows-generated lock file would still leave `uvicorn[standard]`'s Linux-only extra unresolved by the lock file.
4. **(Optional, broader) Add a CI step that builds the Docker image and diffs its installed packages against `requirements-lock.txt`**, to catch future drift automatically rather than relying on periodic manual audits.

Options 1–3 together are the minimal correct fix; option 4 is a regression-prevention enhancement, not required to close the immediate defect.

## 11. Recommended Remediation Approach

Implement options 1–3 together as a single, minimal F07 fix (subject to owner approval, not implemented in this audit):
- Wire `Dockerfile` to install from `requirements-lock.txt` using the same `-r ... && --no-deps` pattern CI already uses, so Docker and CI install the identical pinned graph.
- Pin the base image tag to the digest this audit confirmed the tag currently resolves to (`sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134`), removing the float.
- Regenerate `requirements-lock.txt` from a Linux-targeted resolution (or document a separate Linux-specific lock) so it fully specifies what `uvicorn[standard]` needs on the platform Docker actually runs.

This does not propose broader dependency modernization, a lock-tool migration (e.g. to `uv`/`poetry`), or any version upgrades — only making Docker consume the lock file the project already maintains and pin the base image already recorded in its own release evidence.

## 12. Regression-Test Strategy (for a future implementation phase, not built here)

- A configuration-level test (parsing `Dockerfile`, in the style of `tests/unit/test_docker_compose_config.py`) asserting:
  - a `COPY requirements-lock.txt` (or equivalent) instruction exists before the install step;
  - the install command includes `-r requirements-lock.txt` and `--no-deps` for the editable install;
  - both `FROM` lines pin the base image by digest (`@sha256:...`).
- A Docker-gated test (skip-if-unavailable) that builds the image and runs `pip freeze --all` inside it, asserting every package present in both the image and `requirements-lock.txt` matches exactly — this is the direct, non-vacuous regression test for the defect measured in §6/§7, and would have caught today's drift immediately.
- These tests should fail against the current (pre-fix) `Dockerfile` and pass once the fix lands.

## 13. Final Audit Verdict

**CONFIRMED.**

The Dockerfile installs application dependencies independently of `requirements-lock.txt`, the project's own CI-enforced, documented-as-authoritative pinned dependency source. This audit independently built no new image but instead directly inspected the existing image built from current, unmodified `Dockerfile`/`pyproject.toml` content, and measured six package-version divergences (`anyio`, `click`, `pydantic`, `pydantic_core`, `uvicorn`, `websockets`) plus a structural platform gap (`uvloop` present in the Linux image, entirely absent from the Windows-generated lock file). The base image is additionally referenced by a mutable tag, confirmed via the project's own historical deployment-evidence documents to have already drifted at least once. This is a real reproducibility/supply-chain-integrity defect, not a documentation or tooling-preference difference.

## 14. No Files Modified

No source, test, Docker/Compose, dependency, or configuration file was modified during this audit. The only file created was this report, `F07_DOCKER_LOCK_DEPENDENCY_DRIFT_REMEDIATION_PLAN.md`. All Docker inspection used `docker run --rm` (self-removing) against a pre-existing image; no image was built or rebuilt for this audit, and no container was left running for this project (verified via `docker ps -a` before and after — only pre-existing, unrelated containers from other local projects are present).

## 15. Git Status/Diff Summary

`Dockerfile`, `pyproject.toml`, `requirements-lock.txt`, and `.github/workflows/ci.yml` show **no diff from HEAD** (`git diff -- Dockerfile` etc. all empty) — everything in this audit was evaluated against the exact, already-committed content at HEAD `d983bce`. `git status --short` before and after this audit is identical apart from this new report file. Nothing was staged, committed, or pushed.
