from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import Connection

from .config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"


@contextmanager
def get_connection() -> Iterator[Connection]:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    conn = psycopg.connect(settings.database_url)
    try:
        yield conn
    finally:
        conn.close()


def ensure_postgis(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    conn.commit()


def run_migrations(conn: Connection) -> list[str]:
    """Applies db/migrations/*.sql files not yet recorded in schema_migrations, in filename order."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute("SELECT filename FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}
    conn.commit()

    newly_applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        with conn.cursor() as cur:
            cur.execute(path.read_text())
            cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
        conn.commit()
        newly_applied.append(path.name)
    return newly_applied
