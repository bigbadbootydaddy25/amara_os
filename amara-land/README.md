# amara-land

Powered-land screening backend. Runs locally only — no cloud deploy.

Phase 0: FastAPI skeleton, a Supabase/PostGIS connection, `.env` handling,
and the `sources/` package scaffold.

Phase 1 (current): ingestion for HIFLD Electric Substations, HIFLD Electric
Power Transmission Lines, and EIA-860 retired/canceled generators, loaded
into Postgres/PostGIS with per-record provenance. Later phases (see the
build spec) add distress layers, parcels, scoring, an MCP server, and the
CesiumJS globe.

**Before running Phase 1 ingestion, verify the source URLs in `app/config.py`.**
They were written from the commonly published HIFLD/EIA endpoint conventions,
but could not be confirmed live from the environment they were authored in
(outbound access to `arcgis.com` and `eia.gov` was blocked there). Check:

- `hifld_substations_url` / `hifld_transmission_lines_url` — look the layer
  up on https://hifld-geoplatform.hub.arcgis.com, open its page, and copy the
  exact FeatureServer layer URL (ends in `/FeatureServer/<n>`) if these don't
  resolve or return the wrong fields.
- `eia860_zip_url_template` / `eia860_year` — confirm against
  https://www.eia.gov/electricity/data/eia860/ that the year's zip is at that
  path and that it still contains a `3_1_Generator_*` file with a "Retired
  and Canceled" tab.

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

## Ingest + check (Phase 1)

```bash
python -m scripts.ingest_power_layers
python -m scripts.check_phase1
# -> Collin, TX: <count> substations, max voltage <value>
# -> Grayson, TX: ...
# (one line per target county)
```

`ingest_power_layers` applies `db/migrations/*.sql` automatically, then
fetches and upserts all three Phase 1 sources. Re-running it is safe — rows
are keyed by `(source, source_id)` (or `(source, plant_code)` for retired
generators) so it updates existing rows instead of duplicating them.

## Layout

- `app/` — FastAPI app, config, DB connection, migration runner, and
  `ingest.py` (loads `NormalizedRecord`s into Postgres/PostGIS).
- `sources/` — one module per data source, each exposing a single
  `fetch()` returning a list of `NormalizedRecord` (see `sources/base.py`):
  `hifld_substations`, `hifld_transmission_lines`, `eia860`.
- `db/migrations/` — plain numbered `.sql` files, applied in order and
  tracked in a `schema_migrations` table.

## Rules (apply to every phase, see the build spec)

- Never fabricate public-record data; a missing value stays missing.
- No tool advances, contacts, spends, deletes, or deploys.
- Keys live in `.env`, owner-readable only, never committed.
- The server binds to localhost.
