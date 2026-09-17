# Product audit — 15 September 2026

## Verdict

The current implementation is a tested, deterministic research backend with limited fixture coverage and optional live adapters. It is not ready to be relied on for autonomous, production financial research. Passing regression tests do not cover the verification and workflow failures reproduced below.

**12 findings: 5 P1 (high priority), 7 P2 (medium priority).** Fix the P1 findings before trusting verified output or concurrent workflow controls. Deployment and release-evidence gaps also need closure before a production rollout.

This audit makes no new claim about current CVE exposure and does not change or revoke historical owner risk acceptance.

## Scope and method

- Audited local HEAD `d983bcea152488c1005168c22f2766fc9dd24056`, branch `main`.
- Read governance, phase/status/history, architecture-related contracts, runtime composition, API/authentication, orchestration/workflows, verification/synthesis, calculations, provider transport/SEC ingestion, stores/report generation, CI, Docker, and retained release evidence. Review was risk-based across product surfaces, not a claim of exhaustive line-by-line verification of every module.
- Ran the entire automated suite and repository quality checks. Exercised additional offline API and adapter probes using synthetic input, dependency injection, and an event-controlled concurrent workflow.
- No live market, SEC, OpenRouter, or paid-model calls. No external service deployment, image rebuild, vulnerability database refresh, or remote Git fetch was performed.
- Read-only product audit: application code, tests, configuration, prior reports, architecture assets, and phase documents were not edited. Only this report was added.

## Confirmed findings

### F01 — P1: Numeric verification accepts non-numbers and rejects equivalent numbers

**Locations:** `src/financial_intelligence/domain/verification/evidence.py:203–223`; `src/financial_intelligence/api/routes/synthesis.py:67–68,96`.

The API accepts numeric values as strings. Finiteness checks apply only to actual `Decimal` instances, then equality is determined by string comparison. Numeric strings bypass number validation.

**Reproduction:** Load `examples/sample_research_request.json`, replace both `claims[0].expected_value` and `claims[0].evidence[0].extracted_value`, and POST to `/research/synthesis` in the test environment. Each of `"NaN"`, `"Infinity"`, and `"not-a-number"` returned HTTP 200 with `verification_status=verified` and the invalid string in `structured_value`. Conversely, leaving the expected value as `"100"` and changing the evidence value to `"100.0"` returned `contradicted`.

**Impact:** Invalid financial values can receive the verified label; equivalent representations create false contradictions. The displayed claim text is also not reconciled with these supplied structured values.

**Correction:** Normalize numeric claims and evidence to bounded, finite decimals at the trust boundary; compare numeric values with explicit units, currency, and periods. Reject malformed numeric inputs and ensure presentation derives from validated facts. Add API tests covering these exact cases.

### F02 — P1: Keyword overlap verifies a negated factual claim

**Locations:** `src/financial_intelligence/domain/verification/evidence.py:69–122,199–201`.

Factual evidence is classified by word overlap. If no expected value is supplied, overlapping text is accepted without determining whether it supports or negates the claim.

**Reproduction:** Adapt the sample synthesis request to a factual claim `Apple acquired ExampleCorp`, material kind `other`, and evidence snippet `Apple did not acquire ExampleCorp`; remove the expected/extracted value fields. The API returned HTTP 200, disposition `factual`, verification status `verified`, confidence `1.0`, label `high_confidence`, and no contradiction IDs.

**Impact:** The central verification gate can turn explicitly contradictory evidence into an asserted fact and report it with maximum confidence.

**Correction:** Do not promote keyword similarity to verified factual support. Use typed facts/relations for deterministic support or an explicitly bounded evidence assessment; unsupported semantic judgments must remain uncertain. Negation-only patches would not solve broader entity, event, and meaning mismatches.

### F03 — P1: Acknowledged workflow cancellation is overwritten by running execution

**Locations:** `src/financial_intelligence/application/manage_research_workflow.py:186–204,269–308,349–429`; `src/financial_intelligence/infrastructure/workflow/in_memory_store.py:28–53`.

Execution creates a local control object and retains its initial workflow snapshot. The cancel endpoint updates the stored workflow but does not signal that control object. Result application later saves a terminal state based on the older snapshot, without enforcing the stored cancellation.

**Reproduction:** Create an Apple `company_overview` workflow. Hold the market capability using a thread event while executing it in another request. POST `/research/workflows/{id}/cancel`: HTTP 200 and status `cancelled`. Release the capability: execution returns HTTP 200 and a subsequent GET reports `partial`.

**Impact:** Cancellation does not reliably stop subsequent work or preserve the acknowledged terminal state. Individual store locks do not make the entire lifecycle transition atomic.

**Correction:** Coordinate active execution control with persisted cancellation, check control between tasks, and apply results through an atomic version/state check. Test cancellation and pause during execution and simultaneous execute requests. The cancellation overwrite is reproduced; the other races need dedicated validation.

### F04 — P1: Capability exception messages leak into research responses

**Location:** `src/financial_intelligence/infrastructure/orchestration/capability_executor.py:63–70`.

The broad exception handler includes the exception's complete string in `TaskExecutionResult.message`. This is serialized into normal research responses, bypassing generic HTTP exception sanitization.

**Reproduction:** Inject a market snapshot failure `RuntimeError('AUDIT_SYNTHETIC_SECRET_MARKER')`, then POST `/research/execute` with `{"q":"Apple","objective":"company_overview"}`. The HTTP 200 response contains the marker. Only synthetic text was used; no real secret was read or disclosed.

**Impact:** A provider or adapter exception containing a credential, internal URL, path, or sensitive payload can be exposed to callers and retained in workflow result data.

**Correction:** Return a stable public error code and generic message. Keep diagnostic metadata limited to safe fields and correlation identifiers. Test serialized nested results, not only top-level 500 handlers.

### F05 — P1: SEC ingestion fabricates filing dates and misidentifies the accession

**Location:** `src/financial_intelligence/infrastructure/financial/sec_company_facts.py:263–278`.

The adapter sets both `filed_at` and `published_at` to the reporting period end, and uses the payload's CIK as `accession_or_reference`. The source rows' actual filing metadata is discarded.

**Reproduction:** Extend the existing SEC fixture with `filed=2024-11-01`, `accn=0000320193-24-000123`, and `form=10-K`. The emitted filing has `filed_at=2024-09-28`, `published_at=2024-09-28`, and accession/reference `0000320193`.

**Impact:** Live financial outputs assert false filing/publication dates and cannot identify the actual filing. This compromises provenance and time-sensitive interpretation.

**Correction:** Preserve filing-specific row metadata; keep issuer CIK separate from accession. When facts span filings, retain the appropriate references instead of inventing one common filing. Unknown publication dates must remain explicitly unknown.

### F06 — P2: Local Compose publishes the unauthenticated development service on all interfaces

**Locations:** `docker-compose.yml:14–16`; `src/financial_intelligence/security/auth.py:86–89`.

Compose maps `${API_HOST_PORT:-8000}:8000` without a host bind address and explicitly selects `APP_ENV=development`. Authentication is bypassed in development regardless of `AUTH_ENABLED`; production host enforcement is also disabled.

**Evidence:** `docker compose config --quiet` passes. The committed configuration permits network access through the host's exposed port, subject to Docker and host firewall/network policy. No remote attack or actual external reachability test was attempted.

**Impact:** A configuration described as local can expose workflow creation, approval, cancellation, and research operations without a credential on reachable host interfaces.

**Correction:** Bind the local preset explicitly to loopback. Provide a separate deployment configuration with production settings and secret injection when authorized. This finding does not require implementing the deferred rate-limiting phase.

### F07 — P2: Docker does not build the dependency baseline tested in CI

**Locations:** `Dockerfile:3,12–19`; `.github/workflows/ci.yml`; `requirements-lock.txt`; `release_evidence/v1.0.0/MANIFEST.md:11–25`.

CI installs the lock file, but Docker does not copy or install it: the builder upgrades pip and runs `pip install .` against broad dependency ranges. Both stages also reference a mutable base tag.

**Impact:** A rebuilt image can contain different dependencies from the tested environment. Retained scans identify an August image built at Git revision `27359b5...`, not this September HEAD with authentication changes. Those scans cannot certify a new build.

**Correction:** Establish a locked production dependency/build baseline, pin the intended base digest, and test/scan the actual release image. Associate the resulting evidence with its immutable image and source identities. Preserve historical evidence as historical.

### F08 — P2: Non-ASCII bearer input returns 500 instead of 401

**Location:** `src/financial_intelligence/infrastructure/auth/in_memory_api_key_store.py:59`.

`secrets.compare_digest` on strings rejects non-ASCII characters with `TypeError`. The credential boundary does not validate this before comparison.

**Reproduction:** With a configured synthetic production key, GET `/companies/resolve?q=Apple` using raw header bytes `Authorization: Bearer \xff`. Observed HTTP 500. Missing credentials return 401 and the valid synthetic key returns 200.

**Impact:** Malformed authentication input causes an internal-server error and breaks the uniform authentication failure contract. This does not demonstrate authentication bypass.

**Correction:** Define and validate a bounded credential encoding/grammar; reject malformed input generically before comparison or use a carefully defined byte comparison. Validate configured keys under the same contract.

### F09 — P2: Readiness reports success when no production key can authenticate

**Locations:** `src/financial_intelligence/config/settings.py:73–74,213–225`; `src/financial_intelligence/composition/__init__.py:174–181,361–363`.

Production settings reject disabled authentication but accept an empty key set. Readiness unconditionally reports configuration as ready and never checks the resulting key store.

**Reproduction:** Build a production app with `_env_file=None` and no `API_KEYS`. `/ready` returns HTTP 200 while every protected operation returns 401. There is no runtime key-provisioning endpoint to recover without reconfiguration/restart.

**Impact:** Deployment readiness can succeed for an unusable research service.

**Correction:** Reject an empty effective key set at production/staging startup or report not-ready until the required authentication configuration exists. Account for CSV strings containing only separators/whitespace.

### F10 — P2: Staging validates a host allowlist but does not enforce it

**Locations:** `src/financial_intelligence/api/app.py:72`; `src/financial_intelligence/config/settings.py:213–219`.

Settings apply production-style host validation to staging, but middleware enforcement is enabled only for production.

**Reproduction:** A staging TestClient with default allowed hosts, base URL `http://attacker.invalid`, and a valid synthetic key receives HTTP 200 for company resolution.

**Impact:** Staging does not exercise or provide the host boundary implied by its configuration; deployment validation can miss host-policy defects.

**Correction:** Align environment policy between configuration and middleware and cover staging with the same allowed/disallowed-host tests.

### F11 — P2: OpenAPI omits the required authentication contract

**Locations:** `src/financial_intelligence/security/auth.py:61–98`; `src/financial_intelligence/api/app.py:78–96`.

Authentication parses a raw request header inside an ordinary dependency. It is not represented through an OpenAPI security dependency or equivalent schema declaration.

**Reproduction:** Inspect production `/openapi.json`: no `components.securitySchemes`, and `/companies/resolve` GET has no security requirement despite returning 401 without a key.

**Impact:** Generated clients and integrations cannot discover the new bearer-key requirement. Schema-based checks do not validate the actual protected/public route contract.

**Correction:** Describe bearer authentication in OpenAPI, apply it to protected legacy and versioned routes, document 401 responses, and preserve explicitly public operational endpoints.

### F12 — P2: Authoritative phase and release documents contradict one another

**Locations:** `PROJECT_STATUS.md:6–10`; `PHASE_HISTORY.md:7–13,31`; `PHASES.md:291`; `README.md:5`; `release_evidence/v1.0.0/OWNER_RISK_ACCEPTANCE.md`.

The status declares Phase 11.2 complete, then says Phase 11 is locked and undefined and release security review remains open. History and phase map also call Phase 11 undefined. README says the release was published and residual risk accepted. The risk-acceptance document itself reports 26 review findings, then 24, while another section describes 1 Critical and 9 High remaining without a clear complete disposition mapping.

**Impact:** A maintainer cannot reliably infer the next authorized scope or current release gate. Existing passing phase tests check selected source markers, not coherence of these documents. Commit history confirms Phase 11.1/11.2 changes exist, but this audit cannot reconstruct owner authorization from absent conversation history.

**Correction:** Reconcile the continuation point and release disposition against preserved owner decisions and exact-candidate evidence. Keep historical phase statements clearly historical and provide a complete per-finding disposition. Do not silently infer new phase approval.

## Product capability assessment

| Surface | Current capability and limitation |
|---|---|
| Company identity | Typed issuer/security/listing separation; small local reference universe. Apple, Reliance, and GOOG resolution smoke checks passed. Not broad exchange coverage. |
| Market intelligence | Deterministic calculations, fixture-first data, opt-in Yahoo adapter and fallback. Current Apple fixture snapshot correctly returned a degraded status. Live freshness/availability not tested. |
| Financial/filing intelligence | Typed facts, units, periods, ratios, conflicts and an optional SEC adapter. SEC provenance is affected by F05; broader filings and live cash-flow coverage remain limited. |
| News, industry, regulatory | Structured fixture-backed snapshots. Smoke checks passed. This is not a live news, competitor, or regulatory monitoring service. |
| Planning and execution | Deterministic dependency-aware planning and bounded attempts. No live LLM reasoning. `max_external_calls` explicitly counts capability invocations, not actual HTTP requests. |
| Workflow governance | In-memory workflow, approval, pause/resume/cancel, watchlist and memory contracts. F03 invalidates reliable in-flight cancellation. |
| Verification/synthesis | Typed evidence and qualified output exist, but F01/F02 prevent treating the verified label as a dependable factual guarantee. Client-supplied source names, authority tiers and snippets are not independently authenticated acquisitions. |
| Reports | JSON, Markdown and base64 DOCX generation passed offline smoke checks. DOCX ZIP/XML structure parsed successfully; visual layout in Word was not inspected. Workflow report requests remain deferred rather than automatically generating these synthesis reports. |
| Access control | Shared configured bearer-key set in production/staging. No user identities, tenant isolation, ownership permissions or scoped approval roles. Treat authorized keys as one shared trust domain. |
| Storage/operations | Process-local stores; restart loses data and workers do not share state. No total retention/quota policy was found for accumulated workflows, watchlists, memory, notifications and report requests. Per-request limits do not bound lifetime growth. |
| UI and autonomous research | No implemented user-facing research UI, conversation loop, evaluated translation, dedicated Risk Intelligence, autonomous targeted re-research, or production MCP server. These documented deferrals are not counted as bugs. |

Absence of durable storage, rate limiting, UI, broader providers, or future reasoning capabilities does not authorize implementing them. They limit deployment suitability and should be addressed only under an explicit phase decision.

## Validation record

| Check | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | **705 passed**, 18.18 seconds |
| Ruff lint | Passed |
| Ruff formatting | Passed, 251 files |
| Strict mypy | Passed, 190 source files |
| `pip check` | No broken requirements |
| `docker compose config --quiet` | Passed |
| `git diff --check` | Passed |
| Health/readiness/version and company/snapshot smoke | All HTTP 200; market degradation remained visible |
| JSON/Markdown/DOCX report smoke | All HTTP 200; DOCX ZIP and XML parsed |
| Additional adversarial probes | Reproduced F01–F05 and F08–F11; F06/F07/F12 established by configuration/document review |

Tests named `live` use injected offline transports here; passing them does not establish live-provider reliability. No new load/soak measurement, real deployment test, fresh supply-chain scan, visual report review, or penetration-test certification is claimed.

## Recommended order

1. Repair numeric and factual verification, secret-safe capability errors, workflow cancellation consistency, and SEC provenance; add failing regression cases before fixing them.
2. Close the local/deployment configuration and authentication-contract findings.
3. Reconcile phase/release documentation, build the intended immutable candidate, and rerun quality/security evidence against that candidate.
4. Obtain explicit scope approval before tackling deferred production capabilities. This audit is not authorization to start Phase 11.3 or any later phase.

## Git and phase boundary

At audit start, tracked files were clean. Existing untracked `IDEA.md` and `test_results.txt` were preserved. Local `HEAD...origin/main` was `0 0`; this compares the existing remote-tracking ref, not a freshly queried remote. Local tag `v1.0.0` exists. No staging, commit, push, tag change, remote change or Git identity change occurred. Only this audit report was added; no phase implementation was undertaken.
