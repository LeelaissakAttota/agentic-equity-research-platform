# Development Notes

## Local Phase 1 foundation

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

Docker (application only; PostgreSQL/Redis are not implemented):

```powershell
docker compose build
docker compose up
# If local port 8000 is already allocated:
$env:API_HOST_PORT=18080; docker compose up
```

Store reviewed phase audit records and reproducible troubleshooting notes here. Do not store secrets, machine-specific credentials, copied production data, or unreviewed scratch output.
