"""
Cash buyer matching engine.

Reads:
  - /data/clean/properties_clean.csv  — distressed properties
  - /data/clean/cash_buyer_clean.csv  — cash buyers (from deed records)

Matching logic:
  infill_lot / vacant_land / ghost_plat → builders + land bankers
  distressed SFR (code_violation/probate/absentee_owner) → flippers + landlords
  preforeclosure / nod / bankruptcy → note buyers + distressed asset buyers
  dom90 → all buyer types in ZIP or adjacent ZIPs

Output:
  /data/clean/matches.csv  — each property with ranked list of 3-5 buyers

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m matchers.cash_buyer_matcher
"""

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

CLEAN_DIR = Path(__file__).parent.parent / "data" / "clean"

# Distress type → which buyer types to match
MATCH_RULES: dict[str, list[str]] = {
    "vacant_land":      ["builder", "land_banker", "flipper_investor"],
    "ghost_plat":       ["builder", "land_banker", "flipper_investor"],
    "infill":           ["builder", "land_banker"],
    "preforeclosure":   ["note_buyer", "flipper_investor", "entity_buyer"],
    "nod":              ["note_buyer", "flipper_investor"],
    "bankruptcy":       ["note_buyer", "flipper_investor"],
    "tax_delinquent":   ["flipper_investor", "builder", "landlord"],
    "code_violation":   ["flipper_investor", "landlord"],
    "probate":          ["flipper_investor", "landlord", "builder"],
    "absentee_owner":   ["flipper_investor", "landlord"],
    "dom90":            ["builder", "flipper_investor", "landlord", "land_banker", "note_buyer"],
    "cash_buyer":       [],  # These ARE the buyers, not properties to match
}


def _load_buyers(clean_dir: Path) -> pd.DataFrame:
    """Load the de-duplicated buyer DataFrame from deed records."""
    buyer_file = clean_dir / "cash_buyer_clean.csv"
    if not buyer_file.exists():
        # Build from properties marked as cash_buyer distress type
        props_file = clean_dir / "properties_clean.csv"
        if not props_file.exists():
            return pd.DataFrame()
        df = pd.read_csv(props_file, dtype=str)
        buyers = df[df["distress_type"].str.lower().str.contains("cash_buyer", na=False)].copy()
        return buyers
    return pd.read_csv(buyer_file, dtype=str)


def _adjacent_zips(zip_code: str) -> list[str]:
    """
    Return adjacent ZIP codes for a given ZIP.
    In production this would use a ZIP-adjacency table or Haversine lookup.
    This implementation uses a pre-built adjacency list from the USPS data.
    For now returns ZIPs in the same city market as a proxy.
    """
    from config import TARGET_ZIPS, ZIP_COUNTY_MAP
    info = ZIP_COUNTY_MAP.get(zip_code, {})
    county = info.get("county", "")
    state  = info.get("state", "")
    # All ZIPs in the same county = "adjacent" for matching purposes
    same_county = [
        z for z, v in ZIP_COUNTY_MAP.items()
        if v.get("county") == county and v.get("state") == state
    ]
    return same_county


def _score_buyer_match(buyer_row: pd.Series, prop_row: pd.Series, zip_match: str) -> float:
    """
    Score a buyer-property match on 0.0 – 1.0.
    Higher score = better match.
    """
    score = 0.0

    # Same ZIP = best match
    if zip_match == "same":
        score += 0.5
    elif zip_match == "adjacent":
        score += 0.2

    # Buyer type alignment
    raw = {}
    try:
        raw = json.loads(buyer_row.get("raw_data", "{}"))
    except (ValueError, TypeError):
        pass
    buyer_type = raw.get("buyer_type", "")
    prop_dtype = str(prop_row.get("distress_type", "")).lower()
    preferred_types = MATCH_RULES.get(prop_dtype, [])
    if buyer_type in preferred_types:
        score += 0.3

    # Repeat buyer bonus
    if raw.get("repeat_buyer") or raw.get("purchase_zip_count", 0) >= 3:
        score += 0.1

    # High distress property bonus
    try:
        dscore = int(prop_row.get("distress_score", 0))
        score += dscore / 100.0
    except (ValueError, TypeError):
        pass

    return round(min(score, 1.0), 3)


def run_matching() -> pd.DataFrame:
    """
    Main matching function.
    Returns a DataFrame of (property, buyer, score) triples.
    """
    props_file = CLEAN_DIR / "properties_clean.csv"
    if not props_file.exists():
        print("No clean properties file found. Run data_cleaner.py first.")
        return pd.DataFrame()

    props = pd.read_csv(props_file, dtype=str)
    buyers = _load_buyers(CLEAN_DIR)

    if buyers.empty:
        print("No cash buyer records found. Run deed_records_scraper first.")
        return pd.DataFrame()

    print(f"Matching {len(props)} properties against {len(buyers)} cash buyers...")

    # Index buyers by ZIP for fast lookup
    buyers_by_zip: dict[str, list[dict]] = defaultdict(list)
    for _, brow in buyers.iterrows():
        bzip = str(brow.get("zip_code", "")).strip()
        if bzip:
            buyers_by_zip[bzip].append(brow.to_dict())

    matches = []
    for _, prop in props.iterrows():
        prop_zip   = str(prop.get("zip_code", "")).strip()
        prop_dtype = str(prop.get("distress_type", "")).lower()

        if prop_dtype == "cash_buyer":
            continue  # buyers, not properties

        preferred_types = MATCH_RULES.get(prop_dtype, MATCH_RULES["dom90"])

        # Gather candidate buyers: same ZIP first, then adjacent
        candidate_buyers: list[tuple[dict, str]] = []
        for b in buyers_by_zip.get(prop_zip, []):
            candidate_buyers.append((b, "same"))
        for adj_zip in _adjacent_zips(prop_zip):
            for b in buyers_by_zip.get(adj_zip, []):
                candidate_buyers.append((b, "adjacent"))

        if not candidate_buyers:
            continue

        # Score and rank
        scored: list[tuple[float, dict, str]] = []
        for buyer, match_type in candidate_buyers:
            raw = {}
            try:
                raw = json.loads(buyer.get("raw_data", "{}"))
            except (ValueError, TypeError):
                pass
            buyer_type = raw.get("buyer_type", "")
            # Filter by buyer type alignment
            if preferred_types and buyer_type and buyer_type not in preferred_types:
                continue
            brow_series = pd.Series(buyer)
            score = _score_buyer_match(brow_series, prop, match_type)
            scored.append((score, buyer, match_type))

        # Take top 5
        scored.sort(key=lambda x: x[0], reverse=True)
        top5 = scored[:5]

        for rank, (score, buyer, match_type) in enumerate(top5, start=1):
            raw_b = {}
            try:
                raw_b = json.loads(buyer.get("raw_data", "{}"))
            except (ValueError, TypeError):
                pass
            matches.append({
                "property_address":    prop.get("address", ""),
                "property_zip":        prop_zip,
                "property_distress":   prop_dtype,
                "distress_score":      prop.get("distress_score", ""),
                "is_high_priority":    prop.get("is_high_priority", ""),
                "buyer_name":          buyer.get("owner_name", ""),
                "buyer_entity":        buyer.get("owner_name", ""),
                "buyer_zip":           buyer.get("zip_code", ""),
                "buyer_type":          raw_b.get("buyer_type", ""),
                "is_repeat_buyer":     raw_b.get("repeat_buyer", False),
                "purchase_count":      raw_b.get("purchase_zip_count", ""),
                "match_type":          match_type,
                "match_score":         score,
                "match_rank":          rank,
            })

    df_matches = pd.DataFrame(matches)
    if not df_matches.empty:
        df_matches.sort_values(["match_score"], ascending=False, inplace=True)
    df_matches.to_csv(CLEAN_DIR / "matches.csv", index=False)
    print(f"Matching complete: {len(df_matches)} buyer-property pairs")
    return df_matches


if __name__ == "__main__":
    run_matching()
