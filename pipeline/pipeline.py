"""
Main pipeline orchestrator.

Execution order:
  1. Run all scrapers (in parallel where possible)
  2. Run data cleaner + distress scorer
  3. Run cash buyer matcher
  4. Load into Neo4j (requires .env credentials)
  5. Generate all 7 reports
  6. Log run summary

Usage:
    cd /home/user/amara_os/pipeline
    python pipeline.py               # full run
    python pipeline.py --no-neo4j    # skip Neo4j load (for testing)
    python pipeline.py --scraper hcad # run only HCAD scraper
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Setup logging ─────────────────────────────────────────────────────────
LOG_DIR  = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "run_log.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("Pipeline")


# ── Scraper registry ──────────────────────────────────────────────────────
# Each entry: (short_name, module_path, class_name)
SCRAPER_REGISTRY = [
    ("hcad",        "scrapers.hcad_scraper",         "HCADScraper"),
    ("dcad",        "scrapers.dcad_scraper",          "DCaDScraper"),
    ("tcad",        "scrapers.tcad_scraper",          "TCADScraper"),
    ("bcad",        "scrapers.bcad_scraper",          "BCADScraper"),
    ("collin",      "scrapers.collin_cad_scraper",    "CollinCADScraper"),
    ("kaufman",     "scrapers.kaufman_cad_scraper",   "KaufmanCADScraper"),
    ("nevada",      "scrapers.nevada_scraper",        "NevadaScraper"),
    ("arizona",     "scrapers.arizona_scraper",       "ArizonaScraper"),
    ("oklahoma",    "scrapers.oklahoma_scraper",      "OklahomaScraper"),
    ("florida",     "scrapers.florida_scraper",       "FloridaScraper"),
    ("multistate",  "scrapers.multi_state_scraper",   "MultiStateScraper"),
    ("zillow",      "scrapers.zillow_scraper",        "ZillowScraper"),
    ("redfin",      "scrapers.redfin_scraper",        "RedfinScraper"),
    ("violations",  "scrapers.city_violations_scraper","CityViolationsScraper"),
    ("pacer",       "scrapers.pacer_scraper",         "PACERScraper"),
    ("deeds",       "scrapers.deed_records_scraper",  "DeedRecordsScraper"),
]


def _import_scraper(module_path: str, class_name: str):
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def run_scrapers(selected: list[str] | None = None) -> dict[str, list[dict]]:
    """
    Run all (or selected) scrapers.
    Returns {scraper_name: [records]}.
    """
    results = {}
    registry = SCRAPER_REGISTRY
    if selected:
        registry = [(n, m, c) for n, m, c in SCRAPER_REGISTRY if n in selected]

    for name, module_path, class_name in registry:
        log.info("▶ Running scraper: %s", name)
        t0 = time.time()
        try:
            ScraperClass = _import_scraper(module_path, class_name)
            scraper = ScraperClass()
            records = scraper.run()
            elapsed = time.time() - t0
            log.info("✓ %s — %d records in %.1fs", name, len(records), elapsed)
            results[name] = records
        except Exception as exc:
            log.error("✗ Scraper %s failed: %s", name, exc, exc_info=True)
            results[name] = []

    return results


def run_cleaning() -> "pd.DataFrame":
    log.info("▶ Running data cleaner")
    import importlib
    cleaner_mod = importlib.import_module("data_cleaner")
    df = cleaner_mod.run()
    log.info("✓ Cleaning complete — %d unique properties", len(df))
    return df


def run_matching():
    log.info("▶ Running cash buyer matcher")
    from matchers.cash_buyer_matcher import run_matching as _match
    df = _match()
    log.info("✓ Matching complete — %d buyer-property pairs", len(df))
    return df


def run_neo4j_load():
    log.info("▶ Loading into Neo4j")
    from neo4j_loader.loader import run_loader
    run_loader()
    log.info("✓ Neo4j load complete")


def run_reports():
    log.info("▶ Generating reports")
    from reports.report_generator import run_reports as _reports
    results = _reports()
    log.info("✓ Reports complete")
    return results


def run_obsidian_sync(scraper_results: dict, props_df, matches_df):
    log.info("▶ Syncing Obsidian vault")
    try:
        from obsidian_sync import sync_vault
        new_props   = len(props_df) if props_df is not None else 0
        new_buyers  = sum(1 for r in (props_df.to_dict("records") if props_df is not None else [])
                         if str(r.get("distress_type","")).lower().find("cash_buyer") >= 0)
        new_matches = 0
        if matches_df is not None and hasattr(matches_df, "__len__"):
            new_matches = len(matches_df)
        failed = [k for k, v in scraper_results.items() if not v]
        sync_vault(
            new_props=new_props,
            new_buyers=new_buyers,
            new_matches=new_matches,
            errors=[f"Scraper {k} returned 0 records" for k in failed],
        )
        log.info("✓ Obsidian vault synced")
    except Exception as exc:
        log.error("Obsidian sync failed: %s", exc, exc_info=True)


def print_summary(
    scraper_results: dict,
    props_df,
    matches_df,
    reports: dict,
    run_time: float,
):
    """Print a concise run summary to console."""
    total_raw = sum(len(v) for v in scraper_results.values())
    clean_count = len(props_df) if props_df is not None and hasattr(props_df, "__len__") else 0
    match_count = len(matches_df) if matches_df is not None and hasattr(matches_df, "__len__") else 0

    banner = "\n" + "=" * 60
    print(banner)
    print(f"  PIPELINE RUN COMPLETE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"  Total raw records:        {total_raw:,}")
    print(f"  Unique clean properties:  {clean_count:,}")
    print(f"  Buyer-property matches:   {match_count:,}")
    print(f"  Total run time:           {run_time:.1f}s")
    print()
    print("  Scrapers:")
    for name, recs in sorted(scraper_results.items()):
        status = "✓" if recs else "○"
        print(f"    {status} {name:<15} {len(recs):>6} records")
    print()
    print("  Reports generated:")
    for rname, rdf in reports.items():
        count = len(rdf) if rdf is not None and hasattr(rdf, "__len__") else 0
        print(f"    ✓ {rname:<40} {count:>6} rows")
    print("=" * 60)


def write_run_log(summary: dict):
    """Append a one-line run summary to run_log.txt."""
    line = (
        f"{datetime.now().isoformat()} | "
        f"raw={summary.get('raw',0)} | "
        f"clean={summary.get('clean',0)} | "
        f"matches={summary.get('matches',0)} | "
        f"time={summary.get('time',0):.1f}s\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def main():
    parser = argparse.ArgumentParser(description="Real estate OSINT pipeline")
    parser.add_argument("--no-neo4j",  action="store_true", help="Skip Neo4j load")
    parser.add_argument("--no-reports",action="store_true", help="Skip report generation")
    parser.add_argument("--scraper",   nargs="*",           help="Run only named scraper(s)")
    parser.add_argument("--clean-only",action="store_true", help="Only run cleaner + matcher")
    args = parser.parse_args()

    t_start = time.time()
    log.info("=" * 50)
    log.info("Pipeline starting — %s", datetime.now().isoformat())
    log.info("=" * 50)

    scraper_results = {}
    props_df        = None
    matches_df      = None
    reports         = {}

    if not args.clean_only:
        scraper_results = run_scrapers(selected=args.scraper)

    props_df   = run_cleaning()
    matches_df = run_matching()

    if not args.no_neo4j:
        try:
            run_neo4j_load()
        except SystemExit:
            log.warning("Neo4j load skipped (credentials not set)")

    if not args.no_reports:
        reports = run_reports()

    run_obsidian_sync(scraper_results, props_df, matches_df)

    elapsed = time.time() - t_start
    print_summary(scraper_results, props_df, matches_df, reports, elapsed)
    write_run_log({
        "raw":     sum(len(v) for v in scraper_results.values()),
        "clean":   len(props_df) if props_df is not None else 0,
        "matches": len(matches_df) if matches_df is not None else 0,
        "time":    elapsed,
    })


if __name__ == "__main__":
    main()
