"""
Neo4j graph loader.

Reads cleaned data from /data/clean/ and loads it into Neo4j as a
property graph using the schema defined in schema.cypher.

Node types:
  Property, CashBuyer, ZIP, County, DistressFlag

Relationships:
  (Property)-[:LOCATED_IN]->(ZIP)
  (ZIP)-[:IN_COUNTY]->(County)
  (CashBuyer)-[:BOUGHT_IN]->(ZIP)
  (CashBuyer)-[:MATCHES]->(Property)
  (Property)-[:HAS_FLAG]->(DistressFlag)
  (CashBuyer)-[:REPEAT_BUYER_IN]->(ZIP)
  (Property)-[:ADJACENT_TO]->(Property)

IMPORTANT: This module requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
to be set in /pipeline/.env — it will refuse to run otherwise.

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m neo4j_loader.loader
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Load .env from the pipeline directory
load_dotenv(Path(__file__).parent.parent / ".env")

CLEAN_DIR = Path(__file__).parent.parent / "data" / "clean"
SCHEMA_FILE = Path(__file__).parent / "schema.cypher"

# Batch size for UNWIND queries — keeps memory usage bounded
BATCH_SIZE = 500


def _check_credentials() -> tuple[str, str, str]:
    """
    Verify Neo4j credentials are set. Exit with a clear error if not.
    Returns (uri, user, password).
    """
    uri  = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USER", "")
    pwd  = os.environ.get("NEO4J_PASSWORD", "")
    if not uri or not user or not pwd:
        print(
            "\n[Neo4j Loader] ERROR: Neo4j credentials not set.\n"
            "Please create /pipeline/.env with:\n"
            "  NEO4J_URI=bolt://localhost:7687\n"
            "  NEO4J_USER=neo4j\n"
            "  NEO4J_PASSWORD=your_password\n"
        )
        sys.exit(1)
    return uri, user, pwd


def _get_driver(uri: str, user: str, password: str):
    """Create and return a Neo4j driver instance."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print(f"[Neo4j] Connected to {uri}")
        return driver
    except Exception as exc:
        print(f"[Neo4j] Connection failed: {exc}")
        sys.exit(1)


def _run_schema(driver) -> None:
    """Execute the schema.cypher setup statements."""
    if not SCHEMA_FILE.exists():
        print("[Neo4j] schema.cypher not found, skipping schema setup")
        return
    statements = [
        s.strip() for s in SCHEMA_FILE.read_text().split(";")
        if s.strip() and not s.strip().startswith("//")
    ]
    with driver.session() as session:
        for stmt in statements:
            try:
                session.run(stmt)
            except Exception as exc:
                print(f"[Neo4j] Schema statement warning: {exc}")
    print("[Neo4j] Schema setup complete")


def _batch(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def load_zips_and_counties(driver, df: pd.DataFrame) -> None:
    """Create ZIP and County nodes, and the (ZIP)-[:IN_COUNTY]->(County) relationship."""
    from config import ZIP_COUNTY_MAP
    zip_data = []
    for zip_code in df["zip_code"].unique():
        info = ZIP_COUNTY_MAP.get(str(zip_code), {})
        zip_data.append({
            "zip_code": str(zip_code),
            "city":     info.get("city", ""),
            "state":    info.get("state", ""),
            "county":   info.get("county", ""),
        })

    cypher = """
    UNWIND $rows AS row
    MERGE (z:ZIP {zip_code: row.zip_code})
      SET z.city = row.city, z.state = row.state
    MERGE (c:County {name: row.county, state: row.state})
    MERGE (z)-[:IN_COUNTY]->(c)
    """
    with driver.session() as session:
        for chunk in _batch(zip_data, BATCH_SIZE):
            session.run(cypher, rows=chunk)
    print(f"[Neo4j] Loaded {len(zip_data)} ZIP nodes")


def load_properties(driver, df: pd.DataFrame) -> None:
    """Create Property nodes and link to ZIP."""
    rows = []
    for _, r in df.iterrows():
        flags = [f.strip() for f in str(r.get("distress_flags", "")).split("|") if f.strip()]
        rows.append({
            "address":       str(r.get("address", "")),
            "zip_code":      str(r.get("zip_code", "")),
            "city":          str(r.get("city", "")),
            "state":         str(r.get("state", "")),
            "county":        str(r.get("county", "")),
            "owner_name":    str(r.get("owner_name", "")),
            "parcel_id":     str(r.get("parcel_id", "")),
            "distress_type": str(r.get("distress_type", "")),
            "distress_score": int(r.get("distress_score") or 0),
            "is_high_priority": str(r.get("is_high_priority", "False")).lower() == "true",
            "source":        str(r.get("source", "")),
            "scrape_date":   str(r.get("scrape_date", "")),
            "distress_flags": flags,
        })

    cypher_prop = """
    UNWIND $rows AS row
    MERGE (p:Property {address: row.address, zip_code: row.zip_code})
      SET p.city           = row.city,
          p.state          = row.state,
          p.county         = row.county,
          p.owner_name     = row.owner_name,
          p.parcel_id      = row.parcel_id,
          p.type           = row.distress_type,
          p.distress_score = row.distress_score,
          p.is_high_priority = row.is_high_priority,
          p.source         = row.source,
          p.scrape_date    = row.scrape_date
    WITH p, row
    MATCH (z:ZIP {zip_code: row.zip_code})
    MERGE (p)-[:LOCATED_IN]->(z)
    """
    cypher_flags = """
    UNWIND $rows AS row
    MATCH (p:Property {address: row.address, zip_code: row.zip_code})
    UNWIND row.distress_flags AS flag
    MATCH (d:DistressFlag {type: flag})
    MERGE (p)-[:HAS_FLAG]->(d)
    """

    with driver.session() as session:
        for chunk in _batch(rows, BATCH_SIZE):
            session.run(cypher_prop, rows=chunk)
        for chunk in _batch(rows, BATCH_SIZE):
            session.run(cypher_flags, rows=chunk)
    print(f"[Neo4j] Loaded {len(rows)} Property nodes")


def load_cash_buyers(driver, df: pd.DataFrame) -> None:
    """Create CashBuyer nodes and (CashBuyer)-[:BOUGHT_IN]->(ZIP) relationships."""
    buyer_df = df[df["distress_type"].str.lower().str.contains("cash_buyer", na=False)].copy()
    if buyer_df.empty:
        print("[Neo4j] No cash buyer records found")
        return

    # Aggregate: count purchases per buyer
    buyer_groups = buyer_df.groupby("owner_name").agg(
        purchase_count=("zip_code", "count"),
        last_purchase_date=("filing_date", "max"),
        zips=("zip_code", lambda x: list(x.unique())),
    ).reset_index()

    rows = []
    for _, r in buyer_groups.iterrows():
        rows.append({
            "name":               str(r["owner_name"]),
            "purchase_count":     int(r["purchase_count"]),
            "last_purchase_date": str(r["last_purchase_date"]),
            "zips":               r["zips"],
            "buyer_type":         "entity_buyer",  # refined by matcher
        })

    cypher_buyer = """
    UNWIND $rows AS row
    MERGE (b:CashBuyer {name: row.name})
      SET b.purchase_count     = row.purchase_count,
          b.last_purchase_date = row.last_purchase_date,
          b.buyer_type         = row.buyer_type
    WITH b, row
    UNWIND row.zips AS zip_code
    MATCH (z:ZIP {zip_code: zip_code})
    MERGE (b)-[:BOUGHT_IN]->(z)
    """
    with driver.session() as session:
        for chunk in _batch(rows, BATCH_SIZE):
            session.run(cypher_buyer, rows=chunk)
    print(f"[Neo4j] Loaded {len(rows)} CashBuyer nodes")


def load_matches(driver) -> None:
    """
    Create (CashBuyer)-[:MATCHES]->(Property) relationships from matches.csv.
    """
    matches_file = CLEAN_DIR / "matches.csv"
    if not matches_file.exists():
        print("[Neo4j] No matches.csv found, skipping match relationships")
        return

    df = pd.read_csv(matches_file, dtype=str)
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "buyer_name":      str(r.get("buyer_name", "")),
            "prop_address":    str(r.get("property_address", "")),
            "prop_zip":        str(r.get("property_zip", "")),
            "match_score":     float(r.get("match_score") or 0),
            "match_rank":      int(r.get("match_rank") or 0),
        })

    cypher = """
    UNWIND $rows AS row
    MATCH (b:CashBuyer {name: row.buyer_name})
    MATCH (p:Property {address: row.prop_address, zip_code: row.prop_zip})
    MERGE (b)-[m:MATCHES]->(p)
      SET m.score = row.match_score,
          m.rank  = row.match_rank
    """
    with driver.session() as session:
        for chunk in _batch(rows, BATCH_SIZE):
            try:
                session.run(cypher, rows=chunk)
            except Exception as exc:
                print(f"[Neo4j] Match load warning: {exc}")
    print(f"[Neo4j] Loaded {len(rows)} MATCHES relationships")


def load_repeat_buyer_relationships(driver) -> None:
    """
    Flag (CashBuyer)-[:REPEAT_BUYER_IN]->(ZIP) for buyers with 3+ purchases in a ZIP.
    """
    cypher = """
    MATCH (b:CashBuyer)-[:BOUGHT_IN]->(z:ZIP)
    WITH b, z, COUNT(*) AS purchases
    WHERE purchases >= 3
    MERGE (b)-[:REPEAT_BUYER_IN]->(z)
    """
    with driver.session() as session:
        session.run(cypher)
    print("[Neo4j] REPEAT_BUYER_IN relationships created")


def run_loader() -> None:
    uri, user, password = _check_credentials()
    driver = _get_driver(uri, user, password)

    try:
        _run_schema(driver)

        props_file = CLEAN_DIR / "properties_clean.csv"
        if not props_file.exists():
            print("[Neo4j] No clean properties file found. Run data_cleaner.py first.")
            return

        df = pd.read_csv(props_file, dtype=str)
        df["zip_code"] = df["zip_code"].astype(str).str.strip()
        df["distress_score"] = pd.to_numeric(df.get("distress_score"), errors="coerce").fillna(0)

        load_zips_and_counties(driver, df)
        load_properties(driver, df)
        load_cash_buyers(driver, df)
        load_matches(driver)
        load_repeat_buyer_relationships(driver)

        print("\n[Neo4j] Graph load complete.")

    finally:
        driver.close()


if __name__ == "__main__":
    run_loader()
