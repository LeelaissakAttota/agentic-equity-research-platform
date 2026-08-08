# Development Notes

## Local Phase 1–7 foundation

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
- `GET /companies/resolve?q=Apple` — deterministic company resolution against the local in-memory reference catalog (`200` for RESOLVED/AMBIGUOUS/NOT_FOUND; `400` invalid query; framework `422` for some parameter validation failures)
- `GET /financials/snapshot?q=Apple&exchange=NASDAQ` — financial fundamentals snapshot (`200` for OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED; `400` invalid query). Response may include derived `metrics`, explainable `omissions`, filing/source provenance, and explicit `conflicts` when present. Default data is **fixture/demo** unless optional SEC live mode is enabled. India live adapters are **not** wired; Reliance coverage is fixture-labelled. Valuation multiples are **deferred** (ADR-030). Phase 4 is complete.
- `GET /news/events/snapshot?q=Apple&exchange=NASDAQ` — news/event snapshot (`200` for OK/UNAVAILABLE/DEGRADED/PARTIAL/RESOLUTION_BLOCKED; `400` invalid query). Fixture-first Phase 5; events carry evidence refs, conflicts, authority tiers, and `data_origin`. No live news provider and no LLM.
- `GET /industry/context/snapshot?q=Apple&exchange=NASDAQ` — industry/competitor snapshot (fixture-first; resolved peers use canonical CompanyIdentity).
- `GET /regulatory/events/snapshot?q=Reliance&exchange=NSE` — regulatory snapshot (fixture-first; secondary coverage stays ALLEGED).
- `POST /research/plans` JSON body `{ "q": "Apple", "exchange": "NASDAQ", "objective": "comprehensive_equity_research" }` — creates a deterministic plan (`200` for ok/resolution_blocked; `400` invalid). Does not execute tasks.
- `POST /research/execute` — same body shape (optional budget fields) create-and-executes a fresh plan synchronously within budget. Plans are not persisted; there is no plan-id lookup. Returns `ResearchExecutionResult` (task outcomes, evidence refs, warnings). No investment conclusion.
- `POST /research/workflows` — Phase 7: create a workflow (Phase 6 plan + lifecycle/approval) in the **in-memory** store.
- `GET /research/workflows` — bounded listing for dashboard foundation.
- `POST /watchlists` / `POST /watchlists/{id}/checks` — watchlist + explicit monitoring check (no schedulers).
- Structured Research Memory is deterministic task/result memory — **not** embeddings/RAG.
- Phase 7 COMPLETE (Prompts 1–4); Phase 8 NOT STARTED / AWAITING OWNER AUTHORIZATION.

Optional resolve parameters: `country`, `exchange`, `ticker`. Explicit constraints are never ignored to force a match.

The reference catalog is a small offline fixture only—not complete market coverage and not live data.

Docker (application only; PostgreSQL/Redis and live providers are not implemented):

```powershell
docker compose build
docker compose up
# If local port 8000 is already allocated:
$env:API_HOST_PORT=18080; docker compose up
```

Store reviewed phase audit records and reproducible troubleshooting notes here. Do not store secrets, machine-specific credentials, copied production data, or unreviewed scratch output.
