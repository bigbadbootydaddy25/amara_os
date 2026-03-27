#!/bin/sh
set -e

echo "[entrypoint] Waiting for Postgres at $PGHOST:$PGPORT…"
until pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -q; do
  sleep 1
done
echo "[entrypoint] Postgres is ready."

echo "[entrypoint] Running migrations…"
psql "$DATABASE_URL" -f /app/migrations/001_create_land_parcels.sql
psql "$DATABASE_URL" -f /app/migrations/002_create_deal_reviews.sql
echo "[entrypoint] Migrations done."

exec "$@"
