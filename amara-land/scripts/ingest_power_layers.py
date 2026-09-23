"""Phase 1: fetch HIFLD substations/transmission lines and EIA-860 retired generators,
run migrations if needed, and load everything into Postgres/PostGIS.

Usage: python -m scripts.ingest_power_layers   (run from the amara-land/ directory)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import ensure_postgis, get_connection, run_migrations  # noqa: E402
from app.ingest import load_retired_generators, load_substations, load_transmission_lines  # noqa: E402
from sources import eia860, hifld_substations, hifld_transmission_lines  # noqa: E402


def main() -> int:
    with get_connection() as conn:
        ensure_postgis(conn)
        applied = run_migrations(conn)
        if applied:
            print(f"applied migrations: {', '.join(applied)}")

        sub_records = hifld_substations.fetch()
        n = load_substations(conn, sub_records)
        print(f"substations: fetched {len(sub_records)}, loaded {n}")

        line_records = hifld_transmission_lines.fetch()
        n = load_transmission_lines(conn, line_records)
        print(f"transmission_lines: fetched {len(line_records)}, loaded {n}")

        gen_records = eia860.fetch()
        n = load_retired_generators(conn, gen_records)
        print(f"retired_generators: fetched {len(gen_records)}, loaded {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
