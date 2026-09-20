-- Phase 1: power layers (HIFLD substations, HIFLD transmission lines, EIA-860 retired generators).
-- Every row carries its own provenance (source, source_url, retrieved_at, dataset_published_at)
-- per the build spec's rule that staleness and origin must travel with the data, not just the value.

CREATE TABLE IF NOT EXISTS substations (
    id SERIAL PRIMARY KEY,
    source_id TEXT,
    name TEXT,
    operator TEXT,
    max_voltage NUMERIC,
    min_voltage NUMERIC,
    status TEXT,
    county TEXT,
    state TEXT,
    geom GEOMETRY(Geometry, 4326),
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    dataset_published_at DATE,
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS substations_geom_idx ON substations USING GIST (geom);
CREATE INDEX IF NOT EXISTS substations_state_county_idx ON substations (state, county);

CREATE TABLE IF NOT EXISTS transmission_lines (
    id SERIAL PRIMARY KEY,
    source_id TEXT,
    voltage NUMERIC,
    owner TEXT,
    status TEXT,
    geom GEOMETRY(Geometry, 4326),
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    dataset_published_at DATE,
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS transmission_lines_geom_idx ON transmission_lines USING GIST (geom);

CREATE TABLE IF NOT EXISTS retired_generators (
    id SERIAL PRIMARY KEY,
    plant_name TEXT,
    plant_code TEXT,
    state TEXT,
    county TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    nameplate_capacity_mw NUMERIC,
    retirement_year INTEGER,
    technology TEXT,
    status TEXT,
    geom GEOMETRY(Point, 4326),
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    dataset_published_at DATE,
    UNIQUE (source, plant_code)
);
CREATE INDEX IF NOT EXISTS retired_generators_geom_idx ON retired_generators USING GIST (geom);
