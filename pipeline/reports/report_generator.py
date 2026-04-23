"""
Report generator — produces 7 output CSV files after every pipeline run.

Output files (all in /pipeline/reports/):
  1. cash_buyers_by_zip.csv          — cash buyers grouped by ZIP
  2. distressed_properties_by_zip.csv— distressed properties by ZIP with counts
  3. top_matches.csv                  — best buyer-property matches ranked by score
  4. ghost_subdivisions.csv           — ghost plat / dead subdivision records
  5. dead_paper.csv                   — NOD + bankruptcy filings
  6. infill_lots.csv                  — vacant / infill land parcels
  7. high_priority_properties.csv     — properties with 2+ distress flags or score >= 7

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m reports.report_generator
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

CLEAN_DIR   = Path(__file__).parent.parent / "data" / "clean"
REPORTS_DIR = Path(__file__).parent
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_clean() -> pd.DataFrame:
    f = CLEAN_DIR / "properties_clean.csv"
    if not f.exists():
        print("No clean properties file found. Run data_cleaner.py first.")
        return pd.DataFrame()
    return pd.read_csv(f, dtype=str)


def _load_matches() -> pd.DataFrame:
    f = CLEAN_DIR / "matches.csv"
    if not f.exists():
        return pd.DataFrame()
    return pd.read_csv(f, dtype=str)


def generate_cash_buyers_by_zip(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize cash buyer activity per ZIP:
    - buyer name, buyer type, purchase count, last purchase date
    - sorted by purchase count desc
    """
    buyers = df[df["distress_type"].str.lower().str.contains("cash_buyer", na=False)].copy()
    if buyers.empty:
        return pd.DataFrame(columns=["zip_code", "buyer_name", "buyer_type", "purchase_count", "last_purchase"])

    result = (
        buyers.groupby(["zip_code", "owner_name"])
        .agg(
            purchase_count=("address", "count"),
            last_purchase=("filing_date", "max"),
        )
        .reset_index()
        .rename(columns={"owner_name": "buyer_name"})
        .sort_values(["zip_code", "purchase_count"], ascending=[True, False])
    )
    out = REPORTS_DIR / "cash_buyers_by_zip.csv"
    result.to_csv(out, index=False)
    print(f"  cash_buyers_by_zip.csv  — {len(result)} rows")
    return result


def generate_distressed_by_zip(df: pd.DataFrame) -> pd.DataFrame:
    """
    Count distressed properties per ZIP, broken down by distress type.
    """
    if df.empty:
        return pd.DataFrame()

    pivot = (
        df[df["distress_type"].notna() & (df["distress_type"] != "cash_buyer")]
        .groupby(["zip_code", "city", "state", "distress_type"])
        .size()
        .reset_index(name="count")
        .sort_values(["zip_code", "distress_type"])
    )
    zip_totals = (
        pivot.groupby(["zip_code", "city", "state"])["count"]
        .sum()
        .reset_index(name="total_distressed")
        .sort_values("total_distressed", ascending=False)
    )
    out1 = REPORTS_DIR / "distressed_properties_by_zip.csv"
    pivot.to_csv(out1, index=False)
    print(f"  distressed_properties_by_zip.csv — {len(pivot)} rows")
    return zip_totals


def generate_top_matches(matches_df: pd.DataFrame) -> pd.DataFrame:
    """
    Top buyer-property matches ranked by match_score, filtered to rank == 1
    (best match per property), then sorted by distress_score desc.
    """
    if matches_df.empty:
        return pd.DataFrame()
    top = matches_df[matches_df["match_rank"].astype(str) == "1"].copy()
    top["match_score"]    = pd.to_numeric(top["match_score"], errors="coerce").fillna(0)
    top["distress_score"] = pd.to_numeric(top["distress_score"], errors="coerce").fillna(0)
    top.sort_values(["distress_score", "match_score"], ascending=False, inplace=True)
    out = REPORTS_DIR / "top_matches.csv"
    top.to_csv(out, index=False)
    print(f"  top_matches.csv          — {len(top)} rows")
    return top


def generate_ghost_subdivisions(df: pd.DataFrame) -> pd.DataFrame:
    ghost = df[df["distress_type"].str.lower().str.strip() == "ghost_plat"].copy()
    out = REPORTS_DIR / "ghost_subdivisions.csv"
    ghost.to_csv(out, index=False)
    print(f"  ghost_subdivisions.csv   — {len(ghost)} rows")
    return ghost


def generate_dead_paper(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["distress_type"].str.lower().str.strip().isin(["nod", "bankruptcy"])
    dead = df[mask].copy()
    dead.sort_values(["zip_code", "filing_date"], ascending=[True, False], inplace=True)
    out = REPORTS_DIR / "dead_paper.csv"
    dead.to_csv(out, index=False)
    print(f"  dead_paper.csv           — {len(dead)} rows")
    return dead


def generate_infill_lots(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["distress_type"].str.lower().str.strip().isin(["vacant_land", "infill"])
    infill = df[mask].copy()
    infill.sort_values(["zip_code", "distress_score"], ascending=[True, False], inplace=True)
    out = REPORTS_DIR / "infill_lots.csv"
    infill.to_csv(out, index=False)
    print(f"  infill_lots.csv          — {len(infill)} rows")
    return infill


def generate_high_priority(df: pd.DataFrame) -> pd.DataFrame:
    if "is_high_priority" not in df.columns:
        return pd.DataFrame()
    hp = df[df["is_high_priority"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()
    hp["distress_score"] = pd.to_numeric(hp.get("distress_score"), errors="coerce").fillna(0)
    hp.sort_values("distress_score", ascending=False, inplace=True)
    out = REPORTS_DIR / "high_priority_properties.csv"
    hp.to_csv(out, index=False)
    print(f"  high_priority_properties.csv — {len(hp)} rows")
    return hp


def run_reports() -> dict:
    """Generate all 7 reports. Returns dict of {name: DataFrame}."""
    print(f"\n{'='*50}")
    print(f"Generating reports — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    df      = _load_clean()
    matches = _load_matches()

    results = {}
    for name, fn, *args in [
        ("cash_buyers_by_zip",         generate_cash_buyers_by_zip,   df),
        ("distressed_properties_by_zip", generate_distressed_by_zip,  df),
        ("top_matches",                generate_top_matches,           matches),
        ("ghost_subdivisions",         generate_ghost_subdivisions,    df),
        ("dead_paper",                 generate_dead_paper,            df),
        ("infill_lots",                generate_infill_lots,           df),
        ("high_priority_properties",   generate_high_priority,         df),
    ]:
        try:
            results[name] = fn(*args)
        except Exception as exc:
            print(f"  ERROR generating {name}: {exc}")
            results[name] = pd.DataFrame()

    print(f"\nAll reports written to {REPORTS_DIR}/")
    return results


if __name__ == "__main__":
    run_reports()
