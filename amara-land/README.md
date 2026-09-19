# amara-land

Powered-land screening backend. Runs locally only — no cloud deploy.

Phase 0 (current): FastAPI skeleton, a Supabase/PostGIS connection, `.env`
handling, and the `sources/` package scaffold. Later phases (see the build
spec) add ingestion, scoring, an MCP server, and the CesiumJS globe.

## Setup

```bash
cd amara-land
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
# edit .env with your Supabase DATABASE_URL
```

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Check (Phase 0)

```bash
curl -s http://127.0.0.1:8000/health
# -> {"status": "ok"}

curl -s http://127.0.0.1:8000/health/db
# -> {"status": "ok", "postgis_point": "POINT(-96.8 33.2)"}

# or, without running the server:
python -m scripts.check_postgis
```

## Layout

- `app/` — FastAPI app, config, DB connection.
- `sources/` — one module per data source, each exposing a single
  `fetch()` returning a list of `NormalizedRecord` (see `sources/base.py`).
  Phase 1 fills these in.

## Rules (apply to every phase, see the build spec)

- Never fabricate public-record data; a missing value stays missing.
- No tool advances, contacts, spends, deletes, or deploys.
- Keys live in `.env`, owner-readable only, never committed.
- The server binds to localhost.
