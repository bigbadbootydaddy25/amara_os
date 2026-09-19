"""Phase 0 check: confirms DATABASE_URL works and an ST_MakePoint query runs.

Usage: python -m scripts.check_postgis   (run from the amara-land/ directory)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import ensure_postgis, get_connection  # noqa: E402


def main() -> int:
    with get_connection() as conn:
        ensure_postgis(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT ST_AsText(ST_MakePoint(%s, %s))", (-96.8, 33.2))
            point = cur.fetchone()[0]
    print(f"PostGIS OK: {point}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
