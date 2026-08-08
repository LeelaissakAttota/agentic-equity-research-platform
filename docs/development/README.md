# Development Notes

## Local Phase 1–2 foundation

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
