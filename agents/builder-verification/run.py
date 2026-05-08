#!/usr/bin/env python3
"""
Builder Verification Agent — main entry point.

Usage:
    python run.py --input records.json
    python run.py --input records.json --output-dir reports/
    python run.py --input records.json --output-dir reports/ --verbose

Input format: JSON array of owner/buyer record objects.
See tests/fixtures/sample_records.json for an example.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure the agent directory is on the path when invoked directly
sys.path.insert(0, str(Path(__file__).parent))

from analyzers import (
    classify_builders,
    classify_cash_buyers,
    enrich_profiles,
    group_records_by_owner,
    quarantine_weak_profiles,
)
from confidence_scorer import score_all_profiles
from models import OwnerRecord
from reporter import generate_all_reports


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert raw owner/buyer records into ranked builder and cash-buyer profiles.",
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input JSON file (array of owner/buyer records).",
    )
    p.add_argument(
        "--output-dir", "-o",
        default="reports",
        help="Directory for output reports (default: reports/).",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print progress to stdout.",
    )
    return p


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_records(input_path: Path, verbose: bool = False) -> List[OwnerRecord]:
    raw_data: List[Dict[str, Any]] = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError("Input JSON must be an array of record objects.")

    records: List[OwnerRecord] = []
    for item in raw_data:
        try:
            records.append(OwnerRecord.from_dict(item, source_file=str(input_path)))
        except Exception as exc:
            if verbose:
                print(f"  [WARN] Skipping malformed record: {exc} — {item}", file=sys.stderr)

    if verbose:
        print(f"  Loaded {len(records)} record(s) from {input_path}")
    return records


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    records: List[OwnerRecord],
    output_dir: Path,
    verbose: bool = False,
) -> Dict[str, Path]:
    _log = (lambda msg: print(f"  {msg}")) if verbose else (lambda _: None)

    _log(f"Grouping {len(records)} record(s) by owner …")
    profiles, quarantined = group_records_by_owner(records)
    _log(f"  → {len(profiles)} unique owner profile(s), {len(quarantined)} pre-validation quarantine(s)")

    _log("Running profile-level signal enrichment …")
    enrich_profiles(profiles)

    _log("Computing confidence scores …")
    score_all_profiles(profiles)

    _log("Quarantining weak profiles …")
    quarantine_weak_profiles(profiles)

    _log("Classifying builders …")
    builders = classify_builders(profiles)
    for p in builders:
        p.is_verified_builder = True
    _log(f"  → {len(builders)} verified builder(s)")

    _log("Classifying cash buyers / investors …")
    cash_buyers = classify_cash_buyers(profiles)
    for p in cash_buyers:
        p.is_possible_cash_buyer = True
    _log(f"  → {len(cash_buyers)} possible cash buyer(s)")

    _log(f"Writing reports to {output_dir} …")
    paths = generate_all_reports(profiles, builders, cash_buyers, quarantined, output_dir)

    for name, path in paths.items():
        _log(f"  ✓ {path.name}")

    return paths


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)

    if args.verbose:
        print(f"\nBuilder Verification Agent")
        print(f"  input  : {input_path}")
        print(f"  output : {output_dir}")
        print()

    try:
        records = load_records(input_path, verbose=args.verbose)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: Could not parse input: {exc}", file=sys.stderr)
        return 1

    if not records:
        print("ERROR: No valid records found in input file.", file=sys.stderr)
        return 1

    paths = run_pipeline(records, output_dir, verbose=args.verbose)

    if args.verbose:
        print(f"\nDone. {len(paths)} report(s) written to {output_dir}/\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
