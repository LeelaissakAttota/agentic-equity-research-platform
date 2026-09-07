# Trivy exact-candidate summary

- Candidate: `agentic-financial-intelligence:1.0.0`
- Immutable local image ID/digest: `sha256:b05d7725d17df2da7b94f8b73afc0aa9d6bcc384a227b48a1d031640104c3b0f`
- Platform: `linux/amd64`; detected OS: Debian `12.15`
- Tool/database: Trivy `0.73.0`, vulnerability DB updated `2026-08-18T12:56:24.164002626Z`
- Scan mode: local Docker source, vulnerability scanner only, offline dependency analysis after the local DB update, all severities, unfixed findings retained
- Result: 215 package/advisory records — 6 Critical, 22 High, 79 Medium, 97 Low, 11 Unknown
- Fix availability: 8 records have a fixed version (2 High, 5 Medium, 1 Low); 207 do not

## Classification

All 215 records are individually retained in `trivy-findings-classification.csv`:

- `NEEDS REVIEW`: 26 (5 Critical, 21 High)
- `NOT APPLICABLE`: 2 (1 Critical, 1 High)
- `ACCEPT`: 187 Medium/Low/Unknown residual records

The accepted records remain visible residual risk; `ACCEPT` means they are non-blocking under this
audit's severity gate, not that they are harmless or absent.

## Critical findings requiring owner review

No fixed Debian package version was reported for these five candidate-affecting records:

| Advisory | Package | Installed | Vendor status | Review reason |
|---|---|---:|---|---|
| CVE-2023-45853 | zlib1g | 1:1.2.13.dfsg-1 | will_not_fix | Present in the runtime image; application does not call the affected minizip file-creation API. |
| CVE-2025-7458 | libsqlite3-0 | 3.40.1-2+deb12u2 | affected | Present in the runtime image; no application SQLite persistence path is configured. |
| CVE-2026-13221 | perl-base | 5.36.0-7+deb12u3 | affected | Present, but the service exposes no Perl or arbitrary-execution path. |
| CVE-2026-42496 | perl-base | 5.36.0-7+deb12u3 | fix_deferred | Archive/symlink path requires Perl Archive::Tar processing, which the service does not expose. |
| CVE-2026-57433 | perl-base | 5.36.0-7+deb12u3 | affected | Present, but the service exposes no Perl or Storable deserialization path. |

`CVE-2026-8376` for `perl-base` is `NOT APPLICABLE`: the advisory is specific to 32-bit builds and
the candidate is amd64.

## High findings requiring owner review

- `GHSA-6v7p-g79w-8964` (`msgpack` 1.1.2; fixed 1.2.1): present only as a package vendored beneath
  `pip`; it is not importable as the application-level `msgpack` module and the service does not
  invoke pip. It remains reviewable because bytes are shipped in the final image.
- `CVE-2025-69720`: `libncursesw6`, `libtinfo6`, `ncurses-base`, and `ncurses-bin`; no fixed Debian
  version reported.
- `CVE-2026-14456`: `libssl3` and `openssl`; the advisory concerns a QUIC server while this service
  uses Uvicorn HTTP and exposes no QUIC listener; no fixed Debian version reported.
- `CVE-2026-41992`: `gzip`; no application archive-execution surface and no fixed Debian version
  reported.
- `CVE-2026-42497`, `CVE-2026-48962`, `CVE-2026-57432`, and `CVE-2026-9538`: `perl-base`; the
  service exposes no Perl/archive/deserialization execution path; no fixed Debian version reported.
- `CVE-2026-53615`: eight `util-linux` family packages; the service has no block-device parsing or
  mount capability and runs non-root with a read-only root filesystem; no fixed Debian version
  reported.
- `CVE-2026-54369`: `libacl1`; the service has no ACL mutation capability and runs non-root with a
  read-only root filesystem; no fixed Debian version reported.

`CVE-2025-47273` for `setuptools` 70.3.0 is `NOT APPLICABLE`: Trivy obtained it from BuildKit
third-party SBOM metadata, while direct final-filesystem and import checks found no setuptools
installation in the candidate. Trivy's stated fixed version is 78.1.1.

No dependency or base-image change was made. The 26 candidate-affecting Critical/High records are
potential release blockers pending owner review; the reachability controls above reduce risk but do
not establish zero risk.
