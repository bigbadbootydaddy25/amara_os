import json

from psycopg import Connection

from sources.base import NormalizedRecord


def _geom_json(geometry: dict | None) -> str | None:
    return json.dumps(geometry) if geometry else None


def load_substations(conn: Connection, records: list[NormalizedRecord]) -> int:
    with conn.cursor() as cur:
        for r in records:
            d = r.data
            cur.execute(
                """
                INSERT INTO substations
                    (source_id, name, operator, max_voltage, min_voltage, status, county, state,
                     geom, source, source_url, retrieved_at, dataset_published_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s, %s, %s)
                ON CONFLICT (source, source_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    operator = EXCLUDED.operator,
                    max_voltage = EXCLUDED.max_voltage,
                    min_voltage = EXCLUDED.min_voltage,
                    status = EXCLUDED.status,
                    county = EXCLUDED.county,
                    state = EXCLUDED.state,
                    geom = EXCLUDED.geom,
                    source_url = EXCLUDED.source_url,
                    retrieved_at = EXCLUDED.retrieved_at,
                    dataset_published_at = EXCLUDED.dataset_published_at
                """,
                (
                    d.get("source_id"), d.get("name"), d.get("operator"),
                    d.get("max_voltage"), d.get("min_voltage"), d.get("status"),
                    d.get("county"), d.get("state"), _geom_json(d.get("geometry")),
                    r.source, r.source_url, r.retrieved_at, r.dataset_published_at,
                ),
            )
    conn.commit()
    return len(records)


def load_transmission_lines(conn: Connection, records: list[NormalizedRecord]) -> int:
    with conn.cursor() as cur:
        for r in records:
            d = r.data
            cur.execute(
                """
                INSERT INTO transmission_lines
                    (source_id, voltage, owner, status, geom, source, source_url, retrieved_at, dataset_published_at)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s, %s, %s)
                ON CONFLICT (source, source_id) DO UPDATE SET
                    voltage = EXCLUDED.voltage,
                    owner = EXCLUDED.owner,
                    status = EXCLUDED.status,
                    geom = EXCLUDED.geom,
                    source_url = EXCLUDED.source_url,
                    retrieved_at = EXCLUDED.retrieved_at,
                    dataset_published_at = EXCLUDED.dataset_published_at
                """,
                (
                    d.get("source_id"), d.get("voltage"), d.get("owner"), d.get("status"),
                    _geom_json(d.get("geometry")),
                    r.source, r.source_url, r.retrieved_at, r.dataset_published_at,
                ),
            )
    conn.commit()
    return len(records)


def load_retired_generators(conn: Connection, records: list[NormalizedRecord]) -> int:
    with conn.cursor() as cur:
        for r in records:
            d = r.data
            lat, lon = d.get("latitude"), d.get("longitude")
            cur.execute(
                """
                INSERT INTO retired_generators
                    (plant_name, plant_code, state, county, latitude, longitude,
                     nameplate_capacity_mw, retirement_year, technology, status,
                     geom, source, source_url, retrieved_at, dataset_published_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s IS NOT NULL AND %s IS NOT NULL
                             THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                        %s, %s, %s, %s)
                ON CONFLICT (source, plant_code) DO UPDATE SET
                    plant_name = EXCLUDED.plant_name,
                    state = EXCLUDED.state,
                    county = EXCLUDED.county,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    nameplate_capacity_mw = EXCLUDED.nameplate_capacity_mw,
                    retirement_year = EXCLUDED.retirement_year,
                    technology = EXCLUDED.technology,
                    status = EXCLUDED.status,
                    geom = EXCLUDED.geom,
                    source_url = EXCLUDED.source_url,
                    retrieved_at = EXCLUDED.retrieved_at,
                    dataset_published_at = EXCLUDED.dataset_published_at
                """,
                (
                    d.get("plant_name"), d.get("plant_code"), d.get("state"), d.get("county"),
                    lat, lon, d.get("nameplate_capacity_mw"), d.get("retirement_year"),
                    d.get("technology"), d.get("status"),
                    lon, lat, lon, lat,
                    r.source, r.source_url, r.retrieved_at, r.dataset_published_at,
                ),
            )
    conn.commit()
    return len(records)
