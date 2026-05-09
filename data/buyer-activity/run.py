#!/usr/bin/env python3
"""
buyer-activity-osint  —  run.py

Reads every CSV in data/buyer-activity/raw/, maps both Propwire-style and
deed/export-style headers to canonical fields, builds buyer activity profiles,
and prints a summary report including ignored files and why they were skipped.

Usage:
    python data/buyer-activity/run.py [--json]

    --json   also write full output to data/buyer-activity/output.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

# Make sibling modules importable regardless of cwd
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from ingest import load_raw_dir, Transaction       # noqa: E402
from seeds import load_seeds, BuyerSeed            # noqa: E402
from profiles import build_profiles, BuyerActivityProfile  # noqa: E402

RAW_DIR   = _HERE / "raw"
WRITE_JSON = "--json" in sys.argv


def main() -> None:
    _banner("buyer-activity-osint")

    # ── 1. Load entity seeds from buyers/*.md ─────────────────────────────────
    seeds = load_seeds()
    seed_label = f"{len(seeds)} seed(s)" if seeds else "none (buyers/ not found)"
    _info(f"entity seeds:            {seed_label}")

    # ── 2. Ingest CSVs ────────────────────────────────────────────────────────
    transactions, ignored = load_raw_dir(RAW_DIR)
    _info(f"raw directory:           {RAW_DIR}")
    _info(f"CSV files scanned:       {_count_csvs(RAW_DIR)}")
    _info(f"transactions ingested:   {len(transactions)}")

    # ── 3. Build profiles ─────────────────────────────────────────────────────
    profiles = build_profiles(transactions, seeds)

    # ── 4. Summary ────────────────────────────────────────────────────────────
    print()
    print(f"eligible_transaction_count: {len(transactions)}")
    print(f"buyer_profiles:             {len(profiles)}")

    # ── 5. Profile listing ────────────────────────────────────────────────────
    if profiles:
        _section("Buyer profiles")
        for p in profiles:
            seed_tag  = f"[{p.seed_id} · {p.seed_status}]" if p.seed_id else "[new]"
            price_str = (
                f"  avg ${p.price_avg:>9,.0f}"
                f"  range ${p.price_min:,.0f}–${p.price_max:,.0f}"
                if p.price_avg else ""
            )
            zip_str = ", ".join(p.zip_codes[:4]) + ("…" if len(p.zip_codes) > 4 else "")
            print(
                f"  {seed_tag:<20} {p.display_name:<40} "
                f"{p.transaction_count:>3} txn(s){price_str}"
            )
            if zip_str:
                print(f"    {'':20} ZIPs: {zip_str}")
            if p.property_types:
                print(f"    {'':20} Types: {', '.join(p.property_types)}")
            if p.financing_types:
                print(f"    {'':20} Financing: {', '.join(p.financing_types)}")

    # ── 6. Ignored files report ───────────────────────────────────────────────
    if ignored:
        _section(f"Ignored files ({len(ignored)})")
        for ign in ignored:
            fname = Path(ign.path).name
            print(f"  {fname:<40} {ign.reason}")
    else:
        print("\nIgnored files: none")

    # ── 7. Optional JSON output ───────────────────────────────────────────────
    if WRITE_JSON:
        output = _build_output(transactions, profiles, ignored)
        out_path = _HERE / "output.json"
        out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        print(f"\nFull output written to {out_path}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _count_csvs(raw_dir: Path) -> int:
    if not raw_dir.exists():
        return 0
    return sum(1 for f in raw_dir.iterdir() if f.suffix.lower() == ".csv")


def _build_output(
    transactions: list[Transaction],
    profiles: list[BuyerActivityProfile],
    ignored,
) -> dict:
    return {
        "eligible_transaction_count": len(transactions),
        "buyer_profiles": [
            {
                "buyer_key":         p.buyer_key,
                "display_name":      p.display_name,
                "entity_name":       p.entity_name,
                "individual_name":   p.individual_name,
                "seed_id":           p.seed_id,
                "seed_status":       p.seed_status,
                "transaction_count": p.transaction_count,
                "zip_codes":         p.zip_codes,
                "property_types":    p.property_types,
                "financing_types":   p.financing_types,
                "price_min":         p.price_min,
                "price_max":         p.price_max,
                "price_avg":         p.price_avg,
                "most_recent_sale":  p.most_recent_sale,
                "earliest_sale":     p.earliest_sale,
                "source_files":      [Path(f).name for f in p.source_files],
            }
            for p in profiles
        ],
        "ignored_files": [
            {"file": Path(ign.path).name, "reason": ign.reason}
            for ign in ignored
        ],
    }


def _banner(title: str) -> None:
    bar = "━" * (len(title) + 4)
    print(f"\n{bar}")
    print(f"  {title}")
    print(f"{bar}\n")


def _section(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 50 - len(title))}")


def _info(msg: str) -> None:
    print(f"  {msg}")


if __name__ == "__main__":
    main()
