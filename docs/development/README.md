# Development Notes

## Local v1.0.0 release candidate

```powershell
Copy-Item .env.example .env
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy
python -m uvicorn financial_intelligence.main:app --reload
```

Foundation routes:

- `GET /health` — process liveness (`200`)
- `GET /ready` — foundation readiness (`200` ready, `503` not ready)
- `GET /version` — service metadata
- `GET /v1/health`, `GET /v1/ready`, `GET /v1/version` — backward-compatible current-major aliases; `/v1/companies/resolve` and `/v1/research/synthesis` expose the two approved business aliases. Legacy routes remain supported.
- `GET /companies/resolve?q=Apple` — deterministic company resolution against the local in-memory reference catalog (`200` for RESOLVED/AMBIGUOUS/NOT_FOUND; `400` invalid query; framework `422` for some parameter validation failures)
- `GET /financials/snapshot?q=Apple&exchange=NASDAQ` — financial fundamentals snapshot (`200` for OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED; `400` invalid query). Response may include derived `metrics`, explainable `omissions`, filing/source provenance, and explicit `conflicts` when present. Default data is **fixture/demo** unless optional SEC live mode is enabled. India live adapters are **not** wired; Reliance coverage is fixture-labelled. Valuation multiples are **deferred** (ADR-030). Phase 4 is complete.
- `GET /news/events/snapshot?q=Apple&exchange=NASDAQ` — news/event snapshot (`200` for OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED; `400` invalid query). Fixture-first Phase 5; events carry evidence refs, conflicts, authority tiers, and `data_origin`. No live news provider and no LLM.
- `GET /industry/context/snapshot?q=Apple&exchange=NASDAQ` — industry/competitor snapshot (fixture-first; resolved peers use canonical CompanyIdentity).
- `GET /regulatory/events/snapshot?q=Reliance&exchange=NSE` — regulatory snapshot (fixture-first; secondary coverage stays ALLEGED).
- `POST /research/plans` JSON body `{ "q": "Apple", "exchange": "NASDAQ", "objective": "comprehensive_equity_research" }` — creates a deterministic plan (`200` for ok/resolution_blocked; `400` invalid). Does not execute tasks.
- `POST /research/execute` — same body shape (optional budget fields) create-and-executes a fresh plan synchronously within budget. Plans are not persisted; there is no plan-id lookup. Returns `ResearchExecutionResult` (task outcomes, evidence refs, warnings). No investment conclusion.
- `POST /research/synthesis` — Phase 9 Prompts 1–3: accepts a canonical company query plus bounded typed claims/evidence, runs the existing deterministic Phase 8 verification use case, and returns evidence-linked structured sections and an executive summary. Optional `report_format=structured_json|markdown|docx` returns deterministic content in memory through the report port; DOCX uses base64 transport and a sanitized filename. It does not query providers, call an LLM, translate narrative, render PDF, accept output paths, or write report files.
- `POST /research/workflows` — Phase 7: create a workflow (Phase 6 plan + lifecycle/approval) in the **in-memory** store.
- `GET /research/workflows` — bounded listing for dashboard foundation.
- `POST /watchlists` / `POST /watchlists/{id}/checks` — watchlist + explicit monitoring check (no schedulers).
- Structured Research Memory is deterministic task/result memory — **not** embeddings/RAG.
- Phase 8 Prompts 1–3 add a deterministic verification domain/application foundation: typed claims and evidence, explicit contradictions, versioned explainable confidence factors, targeted critic requests, and bounded critic stop decisions. It is composed internally and does not yet add a public verification endpoint.
- Verification is strict and fail-closed: claim type, numeric value, unit, currency, and reporting period must be compatible; missing or non-finite numeric values cannot support a claim; only supporting evidence contributes to confidence.
- Workflow memory summaries are not claims or evidence and are never assigned source authority implicitly; workflow-wide verification remains deferred until typed claim/evidence production exists.
- Phases 0–10 are COMPLETE. Final Release Blocker 2 is closed locally for the `v1.0.0` candidate. Exact-candidate supply-chain evidence is retained, but Final Release Blocker 1 remains open pending owner review of 26 candidate-affecting Critical/High findings; no Git tag or GitHub Release exists yet. Phase 11 is an undefined locked boundary only, and JARVIS integration is not started.

Production-safety configuration:

- `ALLOWED_HOSTS=localhost,127.0.0.1` is the safe container default. Production rejects wildcard, empty, malformed, or URL-shaped values. Configure the target deployment hostname explicitly before exposure.
- `API_MAX_REQUEST_BODY_BYTES=1048576` bounds declared and chunked bodies. Allowed range: 4096–10485760 bytes.
- `LOG_LEVEL=DEBUG` is rejected in production. `ALLOW_PAID_MODELS=true` remains rejected in every environment.
- `/ready` reports a non-secret `configuration` check. It does not claim PostgreSQL, Redis, providers, auth, rate limiting, or other deferred dependencies are ready.
- Authentication and rate limiting remain deployment-dependent deferrals and are not implemented by the release candidate.

Prompt 2 boundary rules:

- Multiple Host or Content-Length headers are rejected rather than reconciled. Host ports must be decimal `1–65535`; forwarded-host headers are not trusted.
- Content-Length uses strict ASCII digits, but actual ASGI chunks are always counted. More than 1024 chunks is rejected even when byte total is small. The bounded body is request-local and replayed linearly.
- Multiple correlation headers are ambiguous and replaced with a generated UUIDv4.
- Route-raised HTTP details are never reflected; unexpected telemetry uses the static route template and exception type only. `httpx`, `httpcore`, and Uvicorn access INFO logs are suppressed to prevent URL/query leakage.
- Watchlists accept at most 100 entries and the four frozen monitoring capabilities; workflow memory lists accept `limit=1..200`.
- Request-size limiting is not rate limiting. Authentication, rate limits, durable persistence, public-cloud certification, and internet-scale load/SLA evidence remain deferred. Selected MCP, bounded local load/reliability, SLO/runbook, recovery/rollback, and local deployment evidence were added by later Phase 10 prompts.

Historical Prompt 3 contract freeze:

- Host outer whitespace/control and extreme numeric ports fail as `invalid_host`; extreme numeric Content-Length fails safely before integer conversion; whitespace/control correlation IDs generate UUIDv4.
- The final acceptance matrix is [PHASE_10_ACCEPTANCE_MATRIX.md](../../PHASE_10_ACCEPTANCE_MATRIX.md). Its blocking classifications describe the Prompt 3 point in history and were subsequently closed or reclassified by owner-approved Prompt 3A/3C/4 work.
- Do not publicly expose the service as authenticated, rate-limited, durable, distributed, or SLA-certified; those capabilities remain deferred despite Phase 10 completion.

Phase 10 Prompt 3A/3C/4 production-readiness evidence:

- `/v1` is the current REST major prefix for the five approved aliases; legacy endpoints remain supported. Breaking changes require a new major prefix and removals require owner approval plus a released deprecation window.
- Selected MCP is an **in-process facade**, not a network server. Its exact allowlist is `service_status` and `resolve_company`; both are read-only and offline. It provides no dynamic tools, shell/filesystem/network access, secrets, policy mutation, approval, verification bypass, or trading action.
- The deterministic evaluation and bounded local reliability/load suites are reproducible tests, not production SLA or internet-scale performance evidence.
- Operations evidence is in `docs/operations/`; the threat and dependency reviews are in `docs/security/`.
- The Phase 10 candidate and protected Phase 9 rollback images passed production-mode health/readiness/version smoke. Prompt 3C historically added local SBOM/Trivy evidence and Prompt 4 completed the Phase 10 release checkpoint. Fresh evidence for the current `v1.0.0` image is retained under `release_evidence/v1.0.0/`; its unresolved Critical/High security disposition remains Final Release Blocker 1.

Optional resolve parameters: `country`, `exchange`, `ticker`. Explicit constraints are never ignored to force a match.

The reference catalog is a small offline fixture only—not complete market coverage and not live data.

Docker (image `agentic-financial-intelligence:1.0.0`; PostgreSQL/Redis and broad live providers are not implemented):

```powershell
docker compose build
docker compose up
# If local port 8000 is already allocated:
$env:API_HOST_PORT=18080; docker compose up
```

Store reviewed phase audit records and reproducible troubleshooting notes here. Do not store secrets, machine-specific credentials, copied production data, or unreviewed scratch output.
