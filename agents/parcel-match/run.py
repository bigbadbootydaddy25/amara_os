#!/usr/bin/env python3
"""
Parcel Match Agent — main entry point.

Matches parcels/opportunities against vetted buyers and builders sourced
from builder-verification outputs or standalone buyer JSON files.

Usage:
    python run.py --parcels parcels.json
    python run.py --parcels parcels.json --buyers BUYER_CONFIDENCE_SCORES.json
    python run.py --parcels parcels.json --builders VERIFIED_BUILDERS.json
    python run.py --parcels parcels.json \
                  --buyers BUYER_CONFIDENCE_SCORES.json \
                  --builders VERIFIED_BUILDERS.json \
                  --output-dir reports/ --verbose

Input formats:
  parcels   — JSON array of parcel objects
  buyers    — BUYER_CONFIDENCE_SCORES.json (from builder-verification)
              OR any JSON with a "profiles" array
  builders  — VERIFIED_BUILDERS.json (from builder-verification)
              OR any JSON with a "builders" array
              Builders and buyers can also be combined in one file.

See tests/fixtures/ for example inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from disposition import enrich_opportunities
from matcher import build_parcel_opportunities
from models import LoadedBuyerProfile, Parcel
from reporter import generate_all_reports


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_parcels(path: Path, verbose: bool = False) -> List[Parcel]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Parcel input must be a JSON array.")
    parcels: List[Parcel] = []
    for item in raw:
        try:
            p = Parcel.from_dict(item, source_file=str(path))
            if not p.parcel_id:
                if verbose:
                    print(f"  [WARN] Skipping parcel with no parcel_id: {item}", file=sys.stderr)
                continue
            parcels.append(p)
        except Exception as exc:
            if verbose:
                print(f"  [WARN] Skipping malformed parcel: {exc}", file=sys.stderr)
    if verbose:
        print(f"  Loaded {len(parcels)} parcel(s) from {path}")
    return parcels


def load_profiles_from_file(path: Path, verbose: bool = False) -> List[LoadedBuyerProfile]:
    """
    Accepts:
      - BUYER_CONFIDENCE_SCORES.json  → { "profiles": [...] }
      - VERIFIED_BUILDERS.json        → { "builders": [...] }
      - POSSIBLE_CASH_BUYERS.json     → { "cash_buyers": [...] }
      - Raw JSON array                → [...]
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    records: List[Dict[str, Any]] = []

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        for key in ("profiles", "builders", "cash_buyers", "buyer_profiles"):
            if key in data and isinstance(data[key], list):
                records.extend(data[key])

    profiles: List[LoadedBuyerProfile] = []
    for item in records:
        try:
            p = LoadedBuyerProfile.from_dict(item)
            if p.owner_name and not p.is_quarantined:
                profiles.append(p)
        except Exception as exc:
            if verbose:
                print(f"  [WARN] Skipping malformed profile: {exc}", file=sys.stderr)

    if verbose:
        print(f"  Loaded {len(profiles)} buyer/builder profile(s) from {path}")
    return profiles


def merge_profiles(
    profiles: List[LoadedBuyerProfile],
) -> List[LoadedBuyerProfile]:
    """Deduplicate profiles by owner_name (keep higher-scored entry)."""
    seen: Dict[str, LoadedBuyerProfile] = {}
    for p in profiles:
        key = p.owner_name.strip().upper()
        if key not in seen:
            seen[key] = p
        else:
            existing = seen[key]
            if max(p.builder_score, p.investor_score) > max(
                existing.builder_score, existing.investor_score
            ):
                seen[key] = p
    return list(seen.values())


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    parcels: List[Parcel],
    profiles: List[LoadedBuyerProfile],
    output_dir: Path,
    verbose: bool = False,
) -> Dict[str, Path]:
    _log = (lambda msg: print(f"  {msg}")) if verbose else (lambda _: None)

    profiles = merge_profiles(profiles)
    builders = [p for p in profiles if p.is_verified_builder]
    investors = [p for p in profiles if p.is_possible_cash_buyer]

    _log(
        f"Profiles: {len(profiles)} total "
        f"({len(builders)} builder(s), {len(investors)} investor(s))"
    )
    _log(f"Parcels: {len(parcels)}")

    _log("Matching parcels to buyers and builders …")
    opportunities = build_parcel_opportunities(parcels, profiles)

    _log("Identifying disposition paths …")
    enrich_opportunities(opportunities)

    matched = sum(1 for o in opportunities if o.best_match_score > 0)
    _log(f"  → {matched}/{len(opportunities)} parcel(s) matched")

    _log(f"Writing reports to {output_dir} …")
    paths = generate_all_reports(opportunities, output_dir)
    for name, p in paths.items():
        _log(f"  ✓ {p.name}")

    return paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Match parcels against vetted buyers and builders."
    )
    p.add_argument(
        "--parcels", "-p",
        required=True,
        help="Path to parcel dataset JSON (array of parcel records).",
    )
    p.add_argument(
        "--buyers", "-b",
        action="append",
        default=[],
        metavar="FILE",
        help=(
            "Path to buyer profile JSON "
            "(BUYER_CONFIDENCE_SCORES.json, VERIFIED_BUILDERS.json, etc.). "
            "May be specified multiple times."
        ),
    )
    p.add_argument(
        "--builders",
        action="append",
        default=[],
        metavar="FILE",
        help="Alias for --buyers (accepts VERIFIED_BUILDERS.json). May be specified multiple times.",
    )
    p.add_argument(
        "--output-dir", "-o",
        default="reports",
        help="Output directory (default: reports/).",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    parcel_path = Path(args.parcels)
    if not parcel_path.exists():
        print(f"ERROR: Parcel file not found: {parcel_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)

    if args.verbose:
        print("\nParcel Match Agent")
        print(f"  parcels    : {parcel_path}")
        print(f"  output dir : {output_dir}")
        print()

    try:
        parcels = load_parcels(parcel_path, verbose=args.verbose)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: Could not parse parcel file: {exc}", file=sys.stderr)
        return 1

    if not parcels:
        print("ERROR: No valid parcels found in input file.", file=sys.stderr)
        return 1

    # Load all profile sources (buyers + builders flags combined)
    all_profiles: List[LoadedBuyerProfile] = []
    for fpath_str in args.buyers + args.builders:
        fpath = Path(fpath_str)
        if not fpath.exists():
            print(f"ERROR: Profile file not found: {fpath}", file=sys.stderr)
            return 1
        try:
            all_profiles += load_profiles_from_file(fpath, verbose=args.verbose)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"ERROR: Could not parse profile file {fpath}: {exc}", file=sys.stderr)
            return 1

    if not all_profiles and args.verbose:
        print("  [INFO] No buyer/builder profiles provided — running parcel-only analysis.")

    paths = run_pipeline(parcels, all_profiles, output_dir, verbose=args.verbose)

    if args.verbose:
        print(f"\nDone. {len(paths)} report(s) written to {output_dir}/\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
