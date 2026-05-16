"""
AMARA-AI Texas Foreclosure Trustee Intelligence Builder CLI
Reads verified source files from AMARA_BRAIN/texas_foreclosure_intel/
and generates county-specific reports and full pipeline status.

Usage:
    python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --county "Harris County, TX"
    python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --county "Dallas County, TX"
    python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --county "Tarrant County, TX"
    python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --all
    python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --report
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTEL_ROOT   = PROJECT_ROOT / "AMARA_BRAIN" / "texas_foreclosure_intel"
SOURCES_DIR  = INTEL_ROOT / "sources"
REPORTS_DIR  = INTEL_ROOT / "reports"
LOGS_DIR     = INTEL_ROOT / "logs"
EXPORTS_DIR  = INTEL_ROOT / "exports"

SOURCES_CSV      = SOURCES_DIR / "texas_trustee_sources.csv"
AUTOMATION_CSV   = SOURCES_DIR / "automation_scorecard.csv"
VERIFICATION_LOG = LOGS_DIR    / "verification_log.md"

COUNTY_FILES = {
    "Harris County, TX":  SOURCES_DIR / "harris_county_foreclosure_sources.md",
    "Dallas County, TX":  SOURCES_DIR / "dallas_county_foreclosure_sources.md",
    "Tarrant County, TX": SOURCES_DIR / "tarrant_county_foreclosure_sources.md",
}

REPORT_FILES = {
    "best_wholesale":         REPORTS_DIR / "best_wholesale_sources.md",
    "best_preforeclosure":    REPORTS_DIR / "best_preforeclosure_outreach_sources.md",
    "best_hedge_fund":        REPORTS_DIR / "best_hedge_fund_intel_sources.md",
    "best_automation":        REPORTS_DIR / "best_automation_ready_sources.md",
    "highest_activity":       REPORTS_DIR / "highest_activity_counties_and_zips.md",
}

VALID_COUNTIES = list(COUNTY_FILES.keys())

# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_sources_csv(county_filter: str | None = None) -> list[dict]:
    if not SOURCES_CSV.exists():
        print(f"[ERROR] Sources CSV not found: {SOURCES_CSV}", file=sys.stderr)
        return []
    with SOURCES_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if county_filter:
        rows = [r for r in rows if r.get("county", "").strip() == county_filter]
    return rows


def _load_automation_csv(county_filter: str | None = None) -> list[dict]:
    if not AUTOMATION_CSV.exists():
        return []
    with AUTOMATION_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if county_filter:
        rows = [r for r in rows if r.get("county", "").strip() == county_filter]
    return rows


def _sep(char: str = "─", width: int = 72) -> str:
    return char * width


def _banner(title: str) -> None:
    print()
    print(_sep("═"))
    print(f"  {title}")
    print(_sep("═"))


def _section(title: str) -> None:
    print()
    print(_sep())
    print(f"  {title}")
    print(_sep())


def _verified_unverified(rows: list[dict]) -> tuple[list, list]:
    verified   = [r for r in rows if r.get("verification_status", "").upper() == "VERIFIED"]
    unverified = [r for r in rows if r.get("verification_status", "").upper() != "VERIFIED"]
    return verified, unverified


def _write_export(filename: str, data: object) -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = EXPORTS_DIR / filename
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return out

# ── County command ─────────────────────────────────────────────────────────────

def cmd_county(county: str) -> None:
    if county not in VALID_COUNTIES:
        print(f"[ERROR] Unknown county: {county!r}", file=sys.stderr)
        print(f"        Valid options: {', '.join(VALID_COUNTIES)}", file=sys.stderr)
        sys.exit(1)

    _banner(f"AMARA-AI  │  Texas Foreclosure Intel  │  {county}")
    print(f"  Run date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    rows = _load_sources_csv(county)
    auto = _load_automation_csv(county)

    if not rows:
        print(f"\n[WARN] No source rows found for {county} in {SOURCES_CSV}")
    else:
        verified, unverified = _verified_unverified(rows)

        _section("Source Summary")
        print(f"  Total sources   : {len(rows)}")
        print(f"  Verified        : {len(verified)}")
        print(f"  Unverified      : {len(unverified)}")

        by_type: dict[str, list] = {}
        for r in rows:
            t = r.get("source_type", "Unknown")
            by_type.setdefault(t, []).append(r)

        _section("Sources by Type")
        for stype, srcs in sorted(by_type.items()):
            print(f"  {stype:<40}  {len(srcs):>2} source(s)")

        _section("Top Automation Candidates  (score ≥ 7)")
        high = sorted(
            [r for r in rows if int(r.get("automation_score", 0) or 0) >= 7],
            key=lambda r: int(r.get("automation_score", 0) or 0),
            reverse=True,
        )
        if high:
            for r in high:
                print(f"  [{r['automation_score']:>2}]  {r['trustee_company_name']:<45}  {r.get('website','')}")
        else:
            print("  None meeting threshold.")

        _section("Top Lead Quality Candidates  (score ≥ 7)")
        lq = sorted(
            [r for r in rows if int(r.get("lead_quality_score", 0) or 0) >= 7],
            key=lambda r: int(r.get("lead_quality_score", 0) or 0),
            reverse=True,
        )
        if lq:
            for r in lq:
                print(f"  [{r['lead_quality_score']:>2}]  {r['trustee_company_name']:<45}  {r.get('website','')}")
        else:
            print("  None meeting threshold.")

        _section("Unverified Sources (require manual confirmation)")
        if unverified:
            for r in unverified:
                print(f"  UNVERIFIED  {r['trustee_company_name']:<45}  {r.get('website','')}")
        else:
            print("  All sources verified.")

    # County deep-dive file
    county_md = COUNTY_FILES[county]
    _section("County Deep-Dive Report")
    if county_md.exists():
        print(f"  File   : {county_md}")
        print(f"  Size   : {county_md.stat().st_size:,} bytes")
        print(f"  Lines  : {len(county_md.read_text().splitlines()):,}")
    else:
        print(f"  [MISSING]  {county_md}")

    # Export
    export_name = county.lower().replace(", ", "_").replace(" ", "_") + "_sources.json"
    out = _write_export(export_name, rows)
    print()
    print(f"  Export  : {out}")
    print()

# ── All counties ───────────────────────────────────────────────────────────────

def cmd_all() -> None:
    _banner("AMARA-AI  │  Texas Foreclosure Intel  │  ALL COUNTIES")
    print(f"  Run date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_rows = _load_sources_csv()
    all_auto = _load_automation_csv()

    _section("Overall Summary")
    print(f"  Total source records : {len(all_rows)}")
    verified, unverified = _verified_unverified(all_rows)
    print(f"  Verified             : {len(verified)}")
    print(f"  Unverified           : {len(unverified)}")

    for county in VALID_COUNTIES:
        rows = [r for r in all_rows if r.get("county", "").strip() == county]
        v, u = _verified_unverified(rows)
        print(f"  {county:<22}  total={len(rows):>3}  verified={len(v):>3}  unverified={len(u):>3}")

    _section("Top 10 Automation-Ready Sources (all counties)")
    top_auto = sorted(
        all_rows,
        key=lambda r: int(r.get("automation_score", 0) or 0),
        reverse=True,
    )[:10]
    for r in top_auto:
        print(f"  [{r['automation_score']:>2}]  {r['county']:<22}  {r['trustee_company_name']:<40}  {r.get('website','')}")

    _section("Top 10 Lead Quality Sources (all counties)")
    top_lq = sorted(
        all_rows,
        key=lambda r: int(r.get("lead_quality_score", 0) or 0),
        reverse=True,
    )[:10]
    for r in top_lq:
        print(f"  [{r['lead_quality_score']:>2}]  {r['county']:<22}  {r['trustee_company_name']:<40}  {r.get('website','')}")

    _section("Files")
    for county, path in COUNTY_FILES.items():
        status = "OK" if path.exists() else "MISSING"
        print(f"  [{status:<7}]  {path}")
    for label, path in REPORT_FILES.items():
        status = "OK" if path.exists() else "MISSING"
        print(f"  [{status:<7}]  {path}")

    out = _write_export("all_counties_sources.json", all_rows)
    print(f"\n  Export  : {out}")
    print()

# ── Report command ─────────────────────────────────────────────────────────────

def cmd_report() -> None:
    _banner("AMARA-AI  │  Texas Foreclosure Intel  │  PIPELINE REPORT")
    print(f"  Run date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Folder tree
    _section("Folder Tree")
    for root, dirs, files in os.walk(INTEL_ROOT):
        dirs.sort()
        depth = Path(root).relative_to(PROJECT_ROOT).parts
        indent = "  " + "    " * (len(depth) - 1)
        print(f"{indent}{Path(root).name}/")
        for f in sorted(files):
            print(f"{indent}    {f}")

    # Files created
    all_files = sorted(INTEL_ROOT.rglob("*"))
    file_list = [p for p in all_files if p.is_file()]
    _section(f"Files Created  ({len(file_list)} total)")
    for p in file_list:
        size = p.stat().st_size
        print(f"  {size:>8,} bytes  {p.relative_to(PROJECT_ROOT)}")

    # Source counts
    all_rows = _load_sources_csv()
    verified, unverified = _verified_unverified(all_rows)
    _section("Source Verification")
    print(f"  Verified sources   : {len(verified)}")
    print(f"  Unverified sources : {len(unverified)}")
    if unverified:
        print()
        print("  Unverified (require manual confirmation):")
        for r in unverified:
            print(f"    - {r['county']:<22}  {r['trustee_company_name']}  {r.get('source_link','')}")

    # Automation blockers
    _section("Automation Blockers")
    blockers = [r for r in all_rows if r.get("automation_score") and int(r["automation_score"]) <= 3]
    if blockers:
        for r in blockers:
            print(f"  [{r['automation_score']}]  {r['trustee_company_name']:<45}  (no online presence / manual only)")
    else:
        print("  None identified at score ≤ 3 other than courthouse-steps entries.")

    # Scraping limitations
    _section("Scraping / Automation Limitations")
    limitations = [
        "Foreclosure.com and RealtyTrac require subscriptions — scraping behind login walls is fragile.",
        "PropertyRadar and ATTOM offer APIs; prefer API over scraping for institutional-grade sources.",
        "Harris County District Clerk: JS-heavy portal; Playwright recommended over raw HTTP.",
        "Courthouse steps (all counties): no online data; physical attendance or local agent required.",
        "GovEase Harris County participation unverified — confirm before building automation.",
        "CAPTCHA and login bypass is out of scope and must not be attempted.",
    ]
    for lim in limitations:
        print(f"  • {lim}")

    # Reports status
    _section("Output Reports")
    for label, path in REPORT_FILES.items():
        status = "CREATED" if path.exists() else "MISSING"
        print(f"  [{status:<7}]  {path.name}")

    # Recommended next steps
    _section("Recommended Next Steps")
    steps = [
        "1.  Automate BDF Group (bdfgroup.com) — PDF scrape of monthly posting list.",
        "2.  Automate Mackie Wolf (mwzmlaw.com) — PDF scrape, similar structure to BDF.",
        "3.  Automate LOGS.org — HTTP GET + PDF parse, multi-county coverage.",
        "4.  Subscribe to PropertyRadar API for real-time trustee-sale feeds.",
        "5.  Subscribe to ATTOM Data for institutional/hedge-fund-grade feeds.",
        "6.  Confirm Dallas County Clerk PDF download workflow (dallascounty.org).",
        "7.  Confirm Tarrant County Clerk filing access.",
        "8.  Manually verify GovEase Harris County participation.",
        "9.  Manually verify BiggerPockets data freshness.",
        "10. Set up monthly scheduler to pull first-Tuesday auction lists by county.",
    ]
    for step in steps:
        print(f"  {step}")

    # AEGIS Neuron Network integration note
    _section("AEGIS Neuron Network Integration")
    aegis_cli = PROJECT_ROOT / "backend" / "aegis_neuron_network" / "cli.py"
    aegis_api = PROJECT_ROOT / "backend" / "aegis_neuron_network" / "api.py"
    print(f"  CLI  : {'OK' if aegis_cli.exists() else 'MISSING'}  {aegis_cli.relative_to(PROJECT_ROOT)}")
    print(f"  API  : {'OK' if aegis_api.exists() else 'MISSING'}  {aegis_api.relative_to(PROJECT_ROOT)}")
    if aegis_cli.exists():
        print()
        print("  Run AEGIS pipeline:")
        print("    python -m backend.aegis_neuron_network.cli run-all")
        print("    python -m backend.aegis_neuron_network.cli status")

    print()
    print(_sep("═"))
    print("  AMARA-AI Texas Foreclosure Trustee Intelligence Builder — COMPLETE")
    print(_sep("═"))
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AMARA-AI Texas Foreclosure Trustee Intelligence Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --county "Harris County, TX"
  python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --county "Dallas County, TX"
  python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --county "Tarrant County, TX"
  python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --all
  python3 tools/texas_foreclosure_intel/texas_trustee_builder.py --report
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--county",
        metavar="COUNTY",
        help=f'County name. One of: {", ".join(VALID_COUNTIES)}',
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Run for all three target counties.",
    )
    group.add_argument(
        "--report",
        action="store_true",
        help="Generate full pipeline validation report.",
    )

    args = parser.parse_args()

    if args.county:
        cmd_county(args.county)
    elif args.all:
        cmd_all()
    elif args.report:
        cmd_report()


if __name__ == "__main__":
    main()
