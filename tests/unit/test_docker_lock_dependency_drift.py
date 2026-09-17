"""F07 regression: the Docker build must consume the locked dependency set
rather than independently resolving `pyproject.toml`'s ranges (see
F07_DOCKER_LOCK_DEPENDENCY_DRIFT_REMEDIATION_PLAN.md /
F07_DOCKER_LOCK_DEPENDENCY_DRIFT_IMPLEMENTATION_REPORT.md).

Before the fix, `Dockerfile` ran a bare `pip install .`, letting pip resolve
`pyproject.toml`'s ranges against whatever was newest on PyPI at build time.
This was reproduced against a real build: six packages (`pydantic`,
`pydantic_core`, `uvicorn`, `click`, `anyio`, `websockets`) differed from
`requirements-lock.txt`, the file CI installs from exclusively. The fix
installs the project with `requirements-lock.txt` supplied as a pip
*constraints* file (`pip install -c requirements-lock.txt .`), which forces
every package pip resolves that also appears in the lock to that exact
pinned version, while packages the lock cannot represent for this platform
(the lock was generated on Windows; `uvloop` is pulled in by
`uvicorn[standard]` only on non-Windows) still resolve normally instead of
silently vanishing. The base image is also now pinned by digest.

These tests validate the parsed Dockerfile structure directly (not a single
fragile string match), demonstrate non-vacuously that the check actually
distinguishes the pre-fix pattern from the fix, and -- when Docker is
available -- build the real image and diff its installed packages against
the lock file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from unittest import TestCase

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"
LOCK_FILE_PATH = REPO_ROOT / "requirements-lock.txt"

# Packages that may legitimately appear in the built Linux image without a
# corresponding entry in requirements-lock.txt: the lock file is a flat
# `pip freeze` of a Windows development venv, so platform-conditional
# packages that only activate on Linux (uvloop, pulled in by
# `uvicorn[standard]`'s environment marker) cannot be represented in it.
_PLATFORM_ONLY_EXTRAS = frozenset({"uvloop"})

# Packages that legitimately appear in the image but are not part of the
# application's own dependency graph (the venv's package manager, and the
# project's own self-installed wheel).
_NON_DEPENDENCY_PACKAGES = frozenset({"pip", "agentic-financial-intelligence"})

_FROM_LINE_PATTERN = re.compile(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", re.MULTILINE)
_COPY_LOCK_PATTERN = re.compile(r"^COPY\s+.*requirements-lock\.txt.*$", re.MULTILINE)
# A RUN instruction plus any backslash-continued lines that follow it. The
# first alternative consumes zero or more "...\<newline>" continuation
# lines; the trailing `.*` consumes the final, non-continued line.
_RUN_BLOCK_PATTERN = re.compile(r"^RUN\s(?:.*\\\n)*.*", re.MULTILINE)

# The exact pre-fix builder-stage content, kept here verbatim (not read from
# git history) so the non-vacuousness check below is self-contained and
# never touches the real Dockerfile on disk.
_PRE_FIX_BUILDER_STAGE = """\
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m venv /opt/venv \\
    && /opt/venv/bin/pip install --upgrade pip \\
    && /opt/venv/bin/pip install .
"""


def _dockerfile_text() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _base_image_refs(text: str) -> list[str]:
    return [match.group(1) for match in _FROM_LINE_PATTERN.finditer(text)]


def _pip_install_run_block(text: str) -> re.Match[str] | None:
    """Find the RUN block (with continuations) that runs `pip install`.

    Deliberately does not require "pip install" on the RUN line itself: in
    this Dockerfile the instruction starts with `RUN python -m venv ...` and
    the `pip install` calls appear on backslash-continued lines.
    """

    for match in _RUN_BLOCK_PATTERN.finditer(text):
        if "pip install" in match.group(0):
            return match
    return None


def _copies_lock_file_before_install(text: str) -> bool:
    copy_match = _COPY_LOCK_PATTERN.search(text)
    install_match = _pip_install_run_block(text)
    if not copy_match or not install_match:
        return False
    return copy_match.start() < install_match.start()


def _install_enforces_lock(text: str) -> bool:
    """True only if the builder's pip install is constrained by the lock.

    Deliberately narrow: a bare `pip install .` (the pre-fix defect) must
    fail this check even though it contains the substring "pip install".
    """

    install_match = _pip_install_run_block(text)
    if not install_match:
        return False
    install_block = install_match.group(0)
    # Accept either a constraints-file install (`-c requirements-lock.txt`)
    # or a two-step pinned-install + --no-deps pattern; reject anything that
    # installs the project without either mechanism.
    has_constraint = bool(re.search(r"-c\s+requirements-lock\.txt", install_block))
    has_pinned_no_deps = bool(
        re.search(r"-r\s+requirements-lock\.txt", install_block)
        and re.search(r"--no-deps", install_block)
    )
    return has_constraint or has_pinned_no_deps


def _base_images_pinned_by_digest(text: str) -> bool:
    refs = _base_image_refs(text)
    return bool(refs) and all("@sha256:" in ref for ref in refs)


def _parse_freeze_output(freeze_text: str) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in freeze_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, _, version = line.partition("==")
        packages[name.strip().lower().replace("_", "-")] = version.strip()
    return packages


def _parse_lock_file() -> dict[str, str]:
    return _parse_freeze_output(LOCK_FILE_PATH.read_text(encoding="utf-8"))


class DockerfileLockEnforcementStructureTests(TestCase):
    """Structural checks against the real, current Dockerfile."""

    def test_dockerfile_and_lock_file_exist(self) -> None:
        self.assertTrue(DOCKERFILE_PATH.is_file())
        self.assertTrue(LOCK_FILE_PATH.is_file())

    def test_lock_file_is_copied_into_build_context_before_install(self) -> None:
        text = _dockerfile_text()
        self.assertTrue(
            _copies_lock_file_before_install(text),
            "expected a COPY of requirements-lock.txt before the pip install step",
        )

    def test_builder_install_is_constrained_by_the_lock_file(self) -> None:
        text = _dockerfile_text()
        self.assertTrue(
            _install_enforces_lock(text),
            "expected the builder's pip install to reference requirements-lock.txt "
            "as a constraint (or a pinned --no-deps install), not an unconstrained "
            "`pip install .`",
        )

    def test_base_image_is_pinned_by_digest(self) -> None:
        text = _dockerfile_text()
        self.assertTrue(
            _base_images_pinned_by_digest(text),
            "expected every FROM line to pin the base image by @sha256:... digest, "
            "not a floating tag",
        )


class DockerfileLockEnforcementNonVacuousTests(TestCase):
    """Prove the structural checks actually distinguish fixed from vulnerable.

    This never mutates the real Dockerfile on disk. It re-runs the exact
    same checker functions used above against a verbatim, hardcoded copy of
    the pre-fix builder-stage content, and against the real (fixed) file, to
    demonstrate the assertions are non-vacuous.
    """

    def test_checks_pass_against_the_current_fixed_dockerfile(self) -> None:
        text = _dockerfile_text()
        self.assertTrue(_copies_lock_file_before_install(text))
        self.assertTrue(_install_enforces_lock(text))
        self.assertTrue(_base_images_pinned_by_digest(text))

    def test_checks_fail_against_the_reproduced_pre_fix_configuration(self) -> None:
        vulnerable_text = _PRE_FIX_BUILDER_STAGE
        self.assertFalse(
            _copies_lock_file_before_install(vulnerable_text),
            "pre-fix Dockerfile never copied requirements-lock.txt; the check "
            "should have detected that absence",
        )
        self.assertFalse(
            _install_enforces_lock(vulnerable_text),
            "pre-fix Dockerfile ran a bare `pip install .`; the check should "
            "have rejected it as unconstrained",
        )
        self.assertFalse(
            _base_images_pinned_by_digest(vulnerable_text),
            "pre-fix Dockerfile used a floating base-image tag; the check "
            "should have rejected the missing digest",
        )


class DockerBuildDependencyDriftTests(TestCase):
    """Live build verification: skipped when Docker is unavailable."""

    _IMAGE_TAG = "agentic-financial-intelligence:f07-regression-test"

    def test_built_image_matches_lock_file_except_platform_only_extras(self) -> None:
        if shutil.which("docker") is None:
            self.skipTest("docker CLI not available in this environment")

        try:
            build_result = subprocess.run(
                ["docker", "build", "-t", self._IMAGE_TAG, "."],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.skipTest(f"docker build unavailable/unresponsive: {exc}")

        if build_result.returncode != 0:
            if "Cannot connect" in (build_result.stderr or ""):
                self.skipTest("Docker engine not running in this environment")
            self.fail(f"docker build failed:\n{build_result.stderr}")

        try:
            freeze_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--entrypoint",
                    "/opt/venv/bin/python",
                    self._IMAGE_TAG,
                    "-m",
                    "pip",
                    "freeze",
                    "--all",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                freeze_result.returncode,
                0,
                f"pip freeze inside the image failed: {freeze_result.stderr}",
            )

            check_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--entrypoint",
                    "/opt/venv/bin/python",
                    self._IMAGE_TAG,
                    "-m",
                    "pip",
                    "check",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                check_result.returncode,
                0,
                f"pip check failed inside the built image: {check_result.stdout}"
                f"{check_result.stderr}",
            )

            image_packages = _parse_freeze_output(freeze_result.stdout)
            lock_packages = _parse_lock_file()

            mismatches = []
            for name, image_version in image_packages.items():
                if name in _NON_DEPENDENCY_PACKAGES or name in _PLATFORM_ONLY_EXTRAS:
                    continue
                lock_version = lock_packages.get(name)
                if lock_version is None:
                    # Present in the image, absent from the lock, and not an
                    # acknowledged platform-only extra: this is exactly the
                    # kind of undocumented drift F07 exists to catch.
                    mismatches.append(f"{name}: in image ({image_version}) but not in lock")
                elif lock_version != image_version:
                    mismatches.append(f"{name}: lock={lock_version} image={image_version}")

            self.assertFalse(
                mismatches,
                "Docker-built image's dependency versions drifted from "
                "requirements-lock.txt:\n" + "\n".join(mismatches),
            )

            # uvloop is expected to be present (real runtime behavior must be
            # preserved) even though it cannot appear in the Windows-locked file.
            self.assertIn(
                "uvloop",
                image_packages,
                "expected uvloop to still be installed via uvicorn[standard]'s "
                "normal (unconstrained) resolution on Linux",
            )
        finally:
            subprocess.run(
                ["docker", "rmi", "-f", self._IMAGE_TAG],
                capture_output=True,
                text=True,
                timeout=60,
            )
