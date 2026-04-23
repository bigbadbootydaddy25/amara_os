"""
Data cleaning pipeline.

Reads all raw CSV files from /data/raw/, then:
  1. Deduplicates records across sources (keyed on normalized address + ZIP)
  2. Standardizes address formats
  3. Scores each property 1-10 for distress level
  4. Flags properties appearing in 2+ sources as HIGH PRIORITY
  5. Writes cleaned output to /data/clean/

Run standalone:
    cd /home/user/amara_os/pipeline
    python data_cleaner.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict

import pandas as pd

from config import DISTRESS_WEIGHTS, ALL_ZIPS

RAW_DIR   = Path(__file__).parent / "data" / "raw"
CLEAN_DIR = Path(__file__).parent / "data" / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

CANONICAL_FIELDS = [
    "owner_name", "address", "city", "state", "zip_code", "county",
    "parcel_id", "distress_type", "amount_owed", "filing_date",
    "source", "scrape_date", "raw_data",
    # Added by cleaner
    "distress_score", "distress_flags", "is_high_priority",
    "normalized_address", "address_key",
]


class DataCleaner:
    """Merges, deduplicates, scores, and writes clean property records."""

    def __init__(self):
        self.raw_dir  = RAW_DIR
        self.clean_dir = CLEAN_DIR

    # ------------------------------------------------------------------ #
    #  Load all raw files                                                  #
    # ------------------------------------------------------------------ #

    def load_all_raw(self) -> pd.DataFrame:
        dfs = []
        for csv_file in sorted(self.raw_dir.glob("*.csv")):
            try:
                df = pd.read_csv(csv_file, dtype=str)
                df["_source_file"] = csv_file.name
                dfs.append(df)
                print(f"  Loaded {csv_file.name}: {len(df)} rows")
            except Exception as exc:
                print(f"  WARNING: Could not load {csv_file.name}: {exc}")
        if not dfs:
            print("No raw CSV files found in", self.raw_dir)
            return pd.DataFrame(columns=CANONICAL_FIELDS)
        combined = pd.concat(dfs, ignore_index=True)
        print(f"Total raw records: {len(combined)}")
        return combined

    # ------------------------------------------------------------------ #
    #  Address normalization                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def normalize_address(addr: str) -> str:
        if not addr or str(addr).strip() in ("", "nan", "None"):
            return ""
        addr = str(addr).upper().strip()
        addr = re.sub(r"\s+", " ", addr)
        replacements = [
            (r"\bSTREET\b", "ST"), (r"\bAVENUE\b", "AVE"),
            (r"\bBOULEVARD\b", "BLVD"), (r"\bDRIVE\b", "DR"),
            (r"\bROAD\b", "RD"), (r"\bLANE\b", "LN"),
            (r"\bCOURT\b", "CT"), (r"\bPLACE\b", "PL"),
            (r"\bCIRCLE\b", "CIR"), (r"\bNORTH\b", "N"),
            (r"\bSOUTH\b", "S"), (r"\bEAST\b", "E"),
            (r"\bWEST\b", "W"),
        ]
        for pattern, replacement in replacements:
            addr = re.sub(pattern, replacement, addr)
        # Remove unit/apt designations that cause false duplicates
        addr = re.sub(r"\b(APT|UNIT|STE|#)\s*\w+", "", addr).strip()
        return addr

    @staticmethod
    def address_key(address: str, zip_code: str) -> str:
        """Canonical key for deduplication: digits + street name tokens + ZIP."""
        norm = DataCleaner.normalize_address(address)
        tokens = re.findall(r"[A-Z0-9]+", norm)
        return "_".join(tokens[:5]) + "_" + str(zip_code).strip()[:5]

    # ------------------------------------------------------------------ #
    #  Distress scoring                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_distress_score(distress_flags: list[str]) -> int:
        """
        Score 1-10 based on weighted sum of distress flags.
        Max raw weight is ~20 (all flags); we normalize to 10.
        """
        if not distress_flags:
            return 0
        raw = sum(DISTRESS_WEIGHTS.get(flag, 0) for flag in distress_flags)
        max_possible = sum(DISTRESS_WEIGHTS.values())
        score = round((raw / max_possible) * 10)
        return max(1, min(10, score))

    # ------------------------------------------------------------------ #
    #  Main cleaning pipeline                                              #
    # ------------------------------------------------------------------ #

    def clean(self) -> pd.DataFrame:
        raw = self.load_all_raw()
        if raw.empty:
            return raw

        # Ensure required columns exist
        for col in ["address", "zip_code", "distress_type", "owner_name"]:
            if col not in raw.columns:
                raw[col] = ""

        # Only keep records for target ZIPs
        raw["zip_code"] = raw["zip_code"].astype(str).str.strip().str.zfill(5)
        raw = raw[raw["zip_code"].isin(ALL_ZIPS)].copy()
        print(f"After ZIP filter: {len(raw)} records")

        # Normalize address
        raw["normalized_address"] = raw["address"].apply(self.normalize_address)
        raw["address_key"] = raw.apply(
            lambda r: self.address_key(r["address"], r["zip_code"]), axis=1
        )

        # Group by address key to merge flags from multiple sources
        grouped = defaultdict(lambda: {
            "records":        [],
            "distress_flags": set(),
            "sources":        set(),
        })
        for _, row in raw.iterrows():
            key = row["address_key"]
            grouped[key]["records"].append(row.to_dict())
            flag = str(row.get("distress_type", "")).strip()
            if flag:
                grouped[key]["distress_flags"].add(flag)
            src = str(row.get("source", "")).strip()
            if src:
                grouped[key]["sources"].add(src)

        # Build de-duplicated output
        clean_records = []
        for key, data in grouped.items():
            # Use the "best" record as base (most fields filled in)
            base = max(
                data["records"],
                key=lambda r: sum(1 for v in r.values() if v and str(v) not in ("", "nan", "None")),
            )
            flags = sorted(data["distress_flags"])
            score = self.compute_distress_score(flags)
            is_hp = len(data["sources"]) >= 2 or score >= 7  # HIGH PRIORITY

            clean_records.append({
                "owner_name":        base.get("owner_name", ""),
                "address":           base.get("address", ""),
                "normalized_address": base.get("normalized_address", ""),
                "city":              base.get("city", ""),
                "state":             base.get("state", ""),
                "zip_code":          base.get("zip_code", ""),
                "county":            base.get("county", ""),
                "parcel_id":         base.get("parcel_id", ""),
                "distress_type":     base.get("distress_type", ""),
                "distress_flags":    "|".join(flags),
                "distress_score":    score,
                "is_high_priority":  is_hp,
                "amount_owed":       base.get("amount_owed", ""),
                "filing_date":       base.get("filing_date", ""),
                "source":            "|".join(sorted(data["sources"])),
                "scrape_date":       base.get("scrape_date", ""),
                "address_key":       key,
                "raw_data":          base.get("raw_data", "{}"),
            })

        df_clean = pd.DataFrame(clean_records)
        print(f"De-duplicated: {len(df_clean)} unique properties")
        print(f"High priority:  {df_clean['is_high_priority'].sum()} properties")

        # Write outputs
        df_clean.to_csv(self.clean_dir / "properties_clean.csv", index=False)
        df_clean[df_clean["is_high_priority"]].to_csv(
            self.clean_dir / "high_priority_clean.csv", index=False
        )

        # Separate by distress type
        for dtype in df_clean["distress_type"].unique():
            if dtype and str(dtype) not in ("", "nan"):
                subset = df_clean[df_clean["distress_type"] == dtype]
                subset.to_csv(self.clean_dir / f"{dtype}_clean.csv", index=False)

        print(f"Clean data written to {self.clean_dir}/")
        return df_clean


def run():
    cleaner = DataCleaner()
    return cleaner.clean()


if __name__ == "__main__":
    df = run()
    print(f"\nCleaning complete. {len(df)} properties ready for matching.")
