# F07 — Docker/Lock Dependency Drift: Implementation Report

**Scope: F07 only. F01–F06 untouched. No commit or push performed.**

## 1. Finding Summary

`Dockerfile`'s builder stage ran a bare `pip install .`, which resolves `pyproject.toml`'s ranged dependency constraints (e.g. `pydantic>=2.10,<3`) against whatever is newest on PyPI at build time, instead of installing the project's pinned `requirements-lock.txt` — the exact file `.github/workflows/ci.yml` installs from and validates against. The F07 audit reproduced this against a real build and measured six package-version differences (`pydantic`, `pydantic_core`, `uvicorn`, `click`, `anyio`, `websockets`) plus a structural platform gap (`uvloop`, present on Linux, absent from the Windows-generated lock). The base image (`python:3.12-slim-bookworm`) was also referenced by a floating tag rather than a digest.

## 2. Root Cause

Two independent causes, both in `Dockerfile`:

1. The builder stage's `RUN` block never copied `requirements-lock.txt` into the build context and never referenced it in the install command — `pip install .` re-resolves dependencies from scratch, at build time, from `pyproject.toml`'s ranges.
2. Both `FROM` lines referenced `python:3.12-slim-bookworm` by mutable tag, which this project's own historical evidence (`docs/operations/DEPLOYMENT_EVIDENCE.md`, 2026-08-10) shows has already resolved to a different digest at least once.

## 3. Exact Implementation

**File changed:** [Dockerfile](Dockerfile) only.

Two changes:

**a) Lock-file-constrained install.** `requirements-lock.txt` is now copied into the build context alongside the other build inputs, and the install command supplies it to pip as a **constraints file** rather than switching to a two-step `-r ... --no-deps` install:

```dockerfile
COPY pyproject.toml README.md LICENSE requirements-lock.txt ./
COPY src ./src

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -c requirements-lock.txt .
```

**b) Base image pinned by digest.** Both `FROM` lines now pin the base image by the digest this audit independently confirmed the tag currently resolves to (not invented — verified live via `docker images --digests python:3.12-slim-bookworm` immediately before this change, and cross-checked against the same digest already recorded in this repository's own `release_evidence/v1.0.0/MANIFEST.md`):

```dockerfile
FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134 AS builder
...
FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134 AS runtime
```

## 4. Dependency-Management Decision and Rationale

The audit's own recommendation proposed the same two-step pattern CI uses (`pip install -r requirements-lock.txt && pip install . --no-deps`). During implementation this was reconsidered in favor of a **pip constraints file** (`pip install -c requirements-lock.txt .`), for a concrete reason discovered while satisfying the task's explicit instruction to determine "the safest minimal way for the Linux Docker build to consume the lock without incorrectly installing Windows-only dependencies":

- `requirements-lock.txt` is a flat `pip freeze` of a **Windows** venv with no environment markers. `uvicorn[standard]` pulls in `uvloop` only on non-Windows platforms; since the lock was frozen on Windows, `uvloop` was never captured in it.
- Under the `-r ... --no-deps` pattern (install exactly what the lock lists, then install the project with no further dependency resolution), the Linux Docker image would **stop receiving `uvloop` entirely** — a functional regression (loss of `uvicorn`'s preferred event loop) introduced by the fix itself, which conflicts with the task's requirement to "preserve the existing application behavior."
- Under `pip install -c requirements-lock.txt .`, pip performs its normal dependency resolution against `pyproject.toml` (including `uvicorn[standard]`'s environment-marker-gated extras), but **every package it resolves that also appears in the lock file is forced to that exact pinned version**. Packages the lock cannot represent for this platform (`uvloop`) are left to resolve normally instead of disappearing. Packages that are Windows-only by marker (e.g. `colorama`, listed in the lock because it was frozen on Windows) are simply never required during Linux resolution, so they are correctly never installed — no explicit exclusion list was needed for that side of the platform gap.

This is the smaller and more behavior-preserving change: one line differs from the audit's original recommendation, no second install step, no `--no-deps` flag, and the resulting image was verified (§9) to differ from the lock file only in `uvloop`'s presence — a legitimate, expected platform difference — with zero version drift on every package the lock and CI both cover.

`requirements-lock.txt` itself was **not modified, not regenerated, and not touched** — this remains exactly the file CI installs from, unchanged.

## 5. Files Changed

- [Dockerfile](Dockerfile) — modified (the two changes above).
- [tests/unit/test_docker_lock_dependency_drift.py](tests/unit/test_docker_lock_dependency_drift.py) — new regression test file.
- `F07_DOCKER_LOCK_DEPENDENCY_DRIFT_IMPLEMENTATION_REPORT.md` — this report.

No other file was modified. `requirements-lock.txt`, `pyproject.toml`, `.github/workflows/ci.yml`, `docker-compose.yml` (beyond its pre-existing F06-scope working-tree state, untouched by this session), and all `src/`/other `tests/` files are unchanged by this implementation.

## 6. Before/After Docker Dependency Installation Path

| | Before | After |
|---|---|---|
| Build context inputs | `pyproject.toml`, `README.md`, `LICENSE`, `src/` | Same, **plus `requirements-lock.txt`** |
| Install command | `pip install .` | `pip install -c requirements-lock.txt .` |
| Resolution mode | Unconstrained — pip resolves `pyproject.toml`'s ranges against live PyPI state at build time | Constrained — pip resolves normally, but any resolved package also present in the lock is forced to the lock's exact version |
| Base image reference | `python:3.12-slim-bookworm` (floating tag) | `python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` (digest-pinned) |

## 7. Non-Vacuous Regression Proof

Performed in two independent ways:

**a) In-test proof (part of the committed suite, never mutates the real file).** `tests/unit/test_docker_lock_dependency_drift.py` hardcodes a verbatim copy of the exact pre-fix builder-stage content (`_PRE_FIX_BUILDER_STAGE`) and runs the same checker functions used against the real Dockerfile against it. `DockerfileLockEnforcementNonVacuousTests::test_checks_fail_against_the_reproduced_pre_fix_configuration` asserts all three structural checks (lock copied before install, install constrained by lock, base image pinned by digest) fail against that pre-fix snippet, while `test_checks_pass_against_the_current_fixed_dockerfile` asserts they pass against the real, fixed file.

**b) Live reproduction against the actual repository file (performed once during this implementation, not left in the repository).**
```
$ git stash push -- Dockerfile        # temporarily exposes the pre-fix HEAD Dockerfile
$ python -m pytest tests/unit/test_docker_lock_dependency_drift.py::DockerfileLockEnforcementStructureTests -v
...
FAILED ...::test_base_image_is_pinned_by_digest
FAILED ...::test_builder_install_is_constrained_by_the_lock_file
FAILED ...::test_lock_file_is_copied_into_build_context_before_install
3 failed, 1 passed in 0.26s

$ git stash pop                       # restores the fix
$ python -m pytest tests/unit/test_docker_lock_dependency_drift.py -v
...
7 passed in 5.29s
```
`git stash`/`git stash pop` is a safe, fully reversible way to reproduce the exact pre-fix repository state without ever writing an alternate version to disk by hand; `git status` after the `pop` showed the working tree identical to before the experiment (Dockerfile back to its fixed content, no stash entries left behind).

## 8. Docker Build Verification

Built the image fresh from the fixed repository (`docker build --no-cache -t agentic-financial-intelligence:f07-test .`); build succeeded. Observed during the build log that pip resolved and installed exactly the lock-pinned versions (`pydantic-2.13.4`, `pydantic_core-2.46.4`, `click-8.4.2`, `anyio-4.14.2`, `uvicorn-0.52.3`, `websockets-17.0.1`) alongside `uvloop-0.22.1` (resolved normally, not lock-constrained).

`docker compose config --quiet` succeeded against the fixed `Dockerfile`/`docker-compose.yml` pairing.

**Application smoke test:** ran the built image (`docker run -d --rm -p 127.0.0.1:18000:8000 ...`), confirmed `GET /health` returned `{"status":"ok","service":"agentic-financial-intelligence","version":"1.0.0"}`, confirmed `application_startup` and `Uvicorn running on http://0.0.0.0:8000` in the container logs, then stopped the container (`--rm` self-removed it). `docker ps -a` before/after showed no leftover containers for this project.

**Cleanup:** the ad hoc `agentic-financial-intelligence:f07-test` image built for manual verification was removed (`docker rmi -f`) after use. The regression test's own build (`agentic-financial-intelligence:f07-regression-test`) is removed automatically by the test's `finally` block on every run, pass or fail.

## 9. Installed Dependency Comparison

`docker run --rm --entrypoint /opt/venv/bin/python <image> -m pip freeze --all` against the fixed image:

| Package | `requirements-lock.txt` | Fixed Docker image | Match? |
|---|---|---|---|
| annotated-doc | 0.0.5 | 0.0.5 | Yes |
| annotated-types | 0.8.0 | 0.8.0 | Yes |
| anyio | 4.14.2 | **4.14.2** | **Yes (was 4.15.1 pre-fix)** |
| click | 8.4.2 | **8.4.2** | **Yes (was 8.5.0 pre-fix)** |
| fastapi | 0.141.1 | 0.141.1 | Yes |
| h11 | 0.16.0 | 0.16.0 | Yes |
| httptools | 0.8.0 | 0.8.0 | Yes |
| idna | 3.19 | 3.19 | Yes |
| pydantic | 2.13.4 | **2.13.4** | **Yes (was 2.13.5 pre-fix)** |
| pydantic-settings | 2.15.0 | 2.15.0 | Yes |
| pydantic_core | 2.46.4 | **2.46.4** | **Yes (was 2.46.5 pre-fix)** |
| python-dotenv | 1.2.3 | 1.2.3 | Yes |
| PyYAML | 6.0.3 | 6.0.3 | Yes |
| starlette | 1.6.0 | 1.6.0 | Yes |
| typing-inspection | 0.4.4 | 0.4.4 | Yes |
| typing_extensions | 4.16.0 | 4.16.0 | Yes |
| uvicorn | 0.52.3 | **0.52.3** | **Yes (was 0.53.0 pre-fix)** |
| watchfiles | 1.2.0 | 1.2.0 | Yes |
| websockets | 17.0.1 | **17.0.1** | **Yes (was 17.1 pre-fix)** |
| uvloop | *(absent from lock — Windows-generated)* | 0.22.1 | Expected/acceptable platform-only extra, documented in §4 |

**All six previously-drifted packages now match `requirements-lock.txt` exactly.** `uvloop` remains present (preserving existing runtime behavior) and is the only package in the image without a lock-file counterpart, which is the documented, unavoidable consequence of the lock being generated on Windows rather than a residual defect.

## 10. `pip check` Result

```
$ docker run --rm --entrypoint /opt/venv/bin/python agentic-financial-intelligence:f07-test -m pip check
No broken requirements found.
```

## 11. Targeted Test Result

```
$ python -m pytest tests/unit/test_docker_lock_dependency_drift.py -v
...
DockerfileLockEnforcementStructureTests::test_base_image_is_pinned_by_digest PASSED
DockerfileLockEnforcementStructureTests::test_builder_install_is_constrained_by_the_lock_file PASSED
DockerfileLockEnforcementStructureTests::test_dockerfile_and_lock_file_exist PASSED
DockerfileLockEnforcementStructureTests::test_lock_file_is_copied_into_build_context_before_install PASSED
DockerfileLockEnforcementNonVacuousTests::test_checks_fail_against_the_reproduced_pre_fix_configuration PASSED
DockerfileLockEnforcementNonVacuousTests::test_checks_pass_against_the_current_fixed_dockerfile PASSED
DockerBuildDependencyDriftTests::test_built_image_matches_lock_file_except_platform_only_extras PASSED
7 passed in 5.29s
```
The last test performs a real `docker build` and diffs the installed graph against the lock file (§9's comparison, automated) as part of the suite itself, not just this manual report.

## 12. Full Test Result

```
$ python -m pytest
796 passed in 18.55s
```
Baseline before F07 was 789 passed / 130 subtests; the 7 new F07 tests bring the total to 796 passed, with no failures or regressions elsewhere.

## 13. Ruff Result

```
$ python -m ruff check src tests
All checks passed!

$ python -m ruff format --check src tests
258 files already formatted
```

## 14. Mypy Result

```
$ PYTHONPATH=src python -m mypy
src\financial_intelligence\domain\orchestration\graph.py:149: error: Non-overlapping identity check ... [comparison-overlap]
src\financial_intelligence\domain\orchestration\graph.py:152: error: Non-overlapping identity check ... [comparison-overlap]
Found 2 errors in 1 file (checked 190 source files)
```
These are the same 2 pre-existing errors documented as unrelated in prior phases (F05/F06) and in the F07 audit baseline — identical file, identical lines, identical message. Nothing in this implementation touched `graph.py` or any orchestration code. (Note: `mypy` must be invoked with `PYTHONPATH=src` in this shell for it to resolve the `financial_intelligence` package at all — this is a pre-existing environment-configuration detail unrelated to F07, not introduced by this change; `python -m mypy` alone reports "Can't find package 'financial_intelligence'" regardless of any Dockerfile change.)

## 15. F01–F06 Regression Verification

- `git diff -- Dockerfile` shows exactly the two changes described in §3/§6 — nothing else in the file was touched.
- F06's loopback-only binding remains intact: `docker compose config` (re-run after the fix) still shows `ports: [{host_ip: 127.0.0.1, published: "8000", target: 8000}]` for the `api` service — unchanged from before this implementation.
- `git status --short` before and after this implementation shows the same set of pre-existing F01–F06 modified/untracked files, unchanged by this session, plus exactly three new items: the modified `Dockerfile`, the new test file, and this report.
- `requirements-lock.txt` has zero diff — no lockfile churn, no regeneration, no dependency upgrade beyond what pip's own constrained resolution already produced (which is, by construction, identical to the lock's own pinned versions for every package the lock covers).
- No source file under `src/` was modified.
- No authentication/security behavior was touched (F07 is confined to `Dockerfile`).
- No Docker networking configuration was changed (`docker-compose.yml` has zero diff from before this implementation — the pre-existing F06-scope changes in the working tree are exactly as they were).

## 16. Git Diff/Status

```
$ git status --short
 M Dockerfile
 M docker-compose.yml            <- pre-existing F06-scope change, untouched by this session
 M docs/development/README.md    <- pre-existing, untouched by this session
 M src/... (11 files)             <- pre-existing F01-F06-scope changes, untouched by this session
 M tests/unit/test_*.py (5 files) <- pre-existing F01-F06-scope changes, untouched by this session
?? F07_DOCKER_LOCK_DEPENDENCY_DRIFT_IMPLEMENTATION_REPORT.md   <- new (this report)
?? tests/unit/test_docker_lock_dependency_drift.py             <- new (F07 regression tests)
?? (other pre-existing untracked F0*/audit .md files, unchanged)
```
`git diff -- Dockerfile` shown in full in §3. No other tracked file's diff changed as a result of this implementation. Nothing was staged, committed, or pushed.

## 17. Limitations and Remaining Reproducibility Considerations

- **`requirements-lock.txt` is still Windows-generated.** The constraints-file approach works around this cleanly for the current dependency set (`uvloop` is the only affected package today), but if a future Windows-only package were added to `pyproject.toml`'s dependencies, or a future Linux-only extra were added, the same category of gap could recur for that specific package. A cross-platform (or Linux-targeted) lock regeneration would close this permanently, but is out of scope here per the task's explicit constraint against lockfile regeneration.
- **No hash/checksum enforcement.** `requirements-lock.txt` still contains plain `==` pins with no `--hash=sha256:...` entries, and neither CI nor this Docker fix enable pip's hash-checking mode. This bounds the fix to version-drift prevention, not package-content integrity verification — the same limitation the F07 audit already noted as a secondary, lower-priority observation.
- **Base image digest is a point-in-time pin.** It is correct and reproducible as of this implementation (verified live and cross-checked against `release_evidence/v1.0.0/MANIFEST.md`), but will need deliberate, manual updates whenever the project chooses to move to a newer base image — this is the intended tradeoff of digest pinning (stability over automatic updates), not a defect.
- **Local developer installs (`pip install -e ".[dev]"` per `docs/development/README.md`) still resolve unconstrained from `pyproject.toml` ranges**, same as Docker did before this fix. This was out of scope for F07 (which concerns Docker specifically) and was not changed.

## 18. Conclusion

**F07 is FIXED.**

The Dockerfile now installs the project's dependencies constrained by `requirements-lock.txt`, verified by an actual build showing zero version drift on every package the lock and CI both cover, with the one legitimate, documented, behavior-preserving exception (`uvloop`, a Linux-only extra the Windows-generated lock cannot represent). The base image is pinned by a verified, non-invented digest. The fix was proven non-vacuous both via an in-suite hardcoded pre-fix snippet and via a live `git stash`/`pop` reproduction against the real repository file. Full test suite (796 passed, up from 789 with 7 new F07 tests), Ruff, and Mypy (2 pre-existing unrelated errors only) all confirm no regressions. No F01–F06 file, dependency file, or CI configuration was modified. No commit or push was performed.
