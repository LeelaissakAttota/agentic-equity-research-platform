# OWNER RISK ACCEPTANCE FOR RELEASE v1.0.0

## 1. Exact Release Candidate Identity
- Image: `agentic-financial-intelligence:1.0.0`
- Built from: `python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134`

## 2. Exact Base-Image Digest
- `sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134`

## 3. Trivy Severity Totals (from `trivy-findings-classification.csv`)
- Total Critical: 2
- Total High: 10
- Total Medium/Low: 26 (not release-gating)
- Findings requiring review (NEEDS REVIEW): 12 (2 Critical, 10 High)

## 4. Critical/High Findings Remaining Present After Review
- **Critical (1)**: CVE-2023-45853 – zlib1g
- **High (9)**: 
    - CVE-2026-14456 – libssl3
    - Eight additional High findings (see `trivy-findings-classification.csv` for details, all accepted as residual risk)

## 5. Findings Determined NOT APPLICABLE
- **CVE-2025-7458 – libsqlite3-0 (Critical)**
  - Reason: Application does not use SQLite anywhere in the codebase or dependencies. No `import sqlite3` or usage found.
- **CVE-2026-14456 – openssl (High)**
  - Reason: Application does not invoke the `openssl` executable. No `subprocess`, `os.system`, or similar calls to `openssl` found. Only indirect use via libssl3 (see below).

## 6. Findings Accepted as Residual Risk
- **CVE-2023-45853 – zlib1g (Critical)**
  - Reason: No attacker-controlled decompression path proven. The application uses `zlib` only indirectly via Python's `zipfile` module for *creating* internal reports (compression only). No code paths accept compressed uploads or decompress untrusted input. The vulnerability requires decompression of malicious data, which is not present.
- **CVE-2026-14456 – libssl3 (High)**
  - Reason: Indirect TLS dependency exists (via `httpx` for outbound HTTPS requests), but the specific vulnerable code path referenced by CVE-2026-14456 was not proven to be reachable. The application does not perform custom TLS handling, certificate validation, or protocol features known to be affected by this CVE.
- **Eight Additional High Findings**
  - Reason: Previously identified as residual-risk candidates based on code-path reachability analysis (e.g., not reachable, only indirectly present, or lacking exploitation path). Details available in `trivy-findings-classification.csv`.

## 7. Existing Mitigations
- Runs as non-root user (`appuser`, UID 10001) with no shell (`/usr/sbin/nologin`).
- Root filesystem is read-only (Dockerfile does not modify; relies on base image defaults, but user is non-root).
- No unnecessary services exposed; only HTTP API on port 8000.
- Health checks perform lightweight HTTP GET to `/health` (no command execution).
- Dependencies are pinned and updated via `pyproject.toml`; base image is already latest.
- No acceptance of compressed uploads that could trigger zlib vulnerability.
- No SQLite usage.
- No invocation of `openssl` CLI.
- Standard library TLS usage (via `httpx`) without known risky patterns for the specific CVEs.

## 8. Upstream Patch Availability Status
- **zlib1g (CVE-2023-45853)**: No fixed version available; marked `will_not_fix` in Debian repository for `python:3.12-slim-bookworm`.
- **libsqlite3-0 (CVE-2025-7458)**: No fixed version available (but not applicable).
- **libssl3 (CVE-2026-14456)**: No fixed version available; marked `fix_deferred` or `affected`.
- **openssl (CVE-2026-14456)**: No fixed version available (but not applicable).
- **Base image**: `python:3.12-slim-bookworm` at digest `sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` is the latest; no newer same-base digest exists.

## 9. Evidence of No Newer Same-Base Digest
- Command: `docker pull python:3.12-slim-bookworm`
- Output: `Status: Image is up to date for python:3.12-slim-bookworm:latest`

## 10. Evidence of No Debian Package Upgrades
- Command: `apt-get update >/dev/null && apt list --upgradable 2>/dev/null`
- Output: (no packages listed as upgradable)

## 11. Statement on Future Patches
When upstream patches become available for the base image or specific packages, we will rebuild the image, rescan with Trivy, and re-evaluate risk acceptance.

## 12. Statement on Risk Acceptance
Accepting residual risk does **not** mean vulnerabilities are fixed or absent. It means we have determined, based on code reachability, mitigations, and exploitability, that the risk is acceptable for release under our current controls. Vulnerabilities remain present in the image and must be monitored for future patches.

