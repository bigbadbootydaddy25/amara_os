from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from .config import settings


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
