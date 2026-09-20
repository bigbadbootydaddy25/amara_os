"""Phase 1 check: substation count and max voltage per target county.

Usage: python -m scripts.check_phase1   (run from the amara-land/ directory, after ingestion)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db import get_connection  # noqa: E402


def main() -> int:
    counties = [c.strip() for c in settings.target_counties.split(",") if c.strip()]
    with get_connection() as conn, conn.cursor() as cur:
        for county in counties:
            cur.execute(
                """
                SELECT COUNT(*), MAX(max_voltage)
                FROM substations
                WHERE state = %s AND county ILIKE %s
                """,
                (settings.target_state, county),
            )
            count, max_voltage = cur.fetchone()
            print(f"{county}, {settings.target_state}: {count} substations, max voltage {max_voltage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
