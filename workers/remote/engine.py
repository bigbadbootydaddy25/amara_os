"""
Multi-market execution engine for AMARA OS deal generation.

Orchestrates:
  1. Market/ZIP selection
  2. Parallel scraping
  3. Normalization + distress filter
  4. PropVision analysis
  5. Tier classification
  6. Output (JSON files + vault stubs)

Continuous mode: re-runs on a configurable interval.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from workers.remote.markets import MARKETS, Market, get_all_zips
from workers.remote.scraper import ScrapeConfig, scrape_zips_parallel
from workers.remote.normalizer import normalize_batch, filter_distressed
from workers.remote.pipeline import (
    BuyBox, analyze_batch, filter_actionable, to_output_record,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.getenv("AMARA_OUTPUT_DIR", "output"))
DEALS_DIR = Path(os.getenv("AMARA_DEALS_DIR", "deals"))
VAULT_ROOT = Path(os.getenv("AMARA_VAULT_ROOT", "."))


@dataclass
class RunConfig:
    regions: list[str] = field(default_factory=list)          # empty = all regions
    markets: list[str] = field(default_factory=list)          # empty = all markets
    concurrency: int = 4                                       # parallel ZIP scrapes
    dom_min: int = 90
    headless: bool = True
    source: str = "redfin"
    max_pages_per_zip: int = 3
    write_vault_stubs: bool = True
    output_dir: Path = OUTPUT_DIR
    continuous: bool = False
    interval_seconds: int = 3600                               # 1 hour default


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    finished_at: str
    markets_processed: int
    zips_scraped: int
    raw_listings: int
    normalized: int
    distressed: int
    deals_analyzed: int
    tier1_count: int
    tier2_count: int
    output_path: str


def _load_buyers_from_vault(vault_root: Path) -> list[BuyBox]:
    """Load buyer buy boxes from the markdown vault."""
    buyers: list[BuyBox] = []
    buyers_dir = vault_root / "buyers"
    if not buyers_dir.exists():
        logger.warning("No buyers/ directory at %s — buyer-first will reject all deals", vault_root)
        return buyers

    for md_file in buyers_dir.glob("BUY-*.md"):
        try:
            text = md_file.read_text()
            buyer_id = md_file.stem.split("_")[0]
            name_line = next((l for l in text.splitlines() if l.startswith("# ")), "")
            name = name_line.lstrip("# ").strip() or md_file.stem

            # Parse ZIP codes
            zip_section = ""
            in_zip = False
            for line in text.splitlines():
                if "zip" in line.lower() and ":" in line:
                    in_zip = True
                    zip_section = line
                    continue
                if in_zip:
                    if line.strip().startswith("-") or line.strip().startswith("*"):
                        zip_section += " " + line
                    else:
                        in_zip = False

            import re
            zips = re.findall(r"\b\d{5}\b", zip_section + text[:800])
            zips = list(dict.fromkeys(zips))  # dedup

            # Parse price range
            price_min, price_max = 50_000, 500_000
            price_m = re.search(r"\$(\d[\d,]*)\s*[-–to]+\s*\$(\d[\d,]*)", text)
            if price_m:
                price_min = int(price_m.group(1).replace(",", ""))
                price_max = int(price_m.group(2).replace(",", ""))

            # Parse strategy
            strategy = "wholesale"
            if "flip" in text.lower():
                strategy = "flip"
            elif "brrrr" in text.lower() or "rental" in text.lower():
                strategy = "brrrr"

            if zips:
                buyers.append(BuyBox(
                    buyer_id=buyer_id,
                    buyer_name=name,
                    zips=zips,
                    price_min=price_min,
                    price_max=price_max,
                    strategy=strategy,
                ))
        except Exception as e:
            logger.warning("Failed to parse buyer file %s: %s", md_file, e)

    logger.info("Loaded %d buyer buy boxes from vault", len(buyers))
    return buyers


def _select_markets(config: RunConfig) -> list[Market]:
    if config.markets:
        return [m for m in MARKETS if m.name in config.markets]
    if config.regions:
        return [m for m in MARKETS if m.region in config.regions]
    return list(MARKETS)


def _write_output(
    deals: list[dict],
    run_id: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    tier1 = [d for d in deals if d["tier"] == "Tier 1"]
    tier2 = [d for d in deals if d["tier"] == "Tier 2"]

    out = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_deals": len(deals),
        "tier1_count": len(tier1),
        "tier2_count": len(tier2),
        "tier1": tier1,
        "tier2": tier2,
    }

    path = output_dir / f"deals_{run_id}.json"
    path.write_text(json.dumps(out, indent=2))

    # Always overwrite latest symlink
    latest = output_dir / "deals_latest.json"
    latest.write_text(json.dumps(out, indent=2))

    return path


def _write_vault_stubs(deals: list[dict], vault_root: Path) -> None:
    deals_dir = vault_root / "deals"
    deals_dir.mkdir(exist_ok=True)

    existing = {f.name for f in deals_dir.glob("DEAL-*.md")}
    # Find next ID
    ids = [int(f.split("-")[1].split("_")[0]) for f in existing if f.startswith("DEAL-")]
    next_id = max(ids, default=0) + 1

    for deal in deals:
        slug = deal["address"].replace(",", "").replace(" ", "_")[:40]
        fname = f"DEAL-{next_id:04d}_{slug}.md"
        if fname in existing:
            next_id += 1
            continue

        content = f"""# {deal['address']}

**Status:** analyzing
**Tier:** {deal['tier']}
**Market:** {deal.get('market', '')}
**ZIP:** {deal['zip_code']}

## Financials

| Field | Value |
|---|---|
| Asking Price | ${deal['price']:,} |
| ARV | ${deal['arv']:,} |
| Rehab | ${deal['rehab']:,} |
| MAO | ${deal['mao']:,} |
| Assignment Fee | ${deal['assignment_fee']:,} |
| ROI | {deal['roi']:.1%} |

## Strategy
{deal['strategy']}

## Matched Buyers
{chr(10).join(f'- {b}' for b in deal['matched_buyers'])}

## Distress Keywords
{chr(10).join(f'- {k}' for k in deal['keywords'])}

## Source
{deal.get('url', 'N/A')}

---
*Auto-generated by AMARA OS engine*
"""
        (deals_dir / fname).write_text(content)
        next_id += 1


async def run_once(config: RunConfig) -> RunSummary:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== AMARA RUN %s START ===", run_id)

    markets = _select_markets(config)
    buyers = _load_buyers_from_vault(VAULT_ROOT)
    logger.info("Markets: %d | Buyers: %d", len(markets), len(buyers))

    all_zips: list[tuple[str, Market]] = []
    for market in markets:
        for z in market.zips:
            all_zips.append((z, market))

    # Scrape all ZIPs
    zip_codes = [z for z, _ in all_zips]
    zip_to_market = {z: m for z, m in all_zips}

    scrape_config = ScrapeConfig(
        dom_min=config.dom_min,
        headless=config.headless,
        source=config.source,
        max_pages=config.max_pages_per_zip,
    )

    logger.info("Scraping %d ZIPs across %d markets (concurrency=%d)...",
                len(zip_codes), len(markets), config.concurrency)

    raw_listings = await scrape_zips_parallel(zip_codes, scrape_config, config.concurrency)
    logger.info("Raw listings collected: %d", len(raw_listings))

    normalized = normalize_batch(raw_listings)
    logger.info("Normalized: %d", len(normalized))

    distressed = filter_distressed(normalized, require_keywords=True, min_dom=config.dom_min)
    logger.info("Distressed (filtered): %d", len(distressed))

    # Analyze per market
    all_results = []
    market_listings: dict[str, list] = {}
    for listing in distressed:
        market = zip_to_market.get(listing.zip_code)
        if market:
            market_listings.setdefault(market.name, []).append((listing, market))

    for market_name, pairs in market_listings.items():
        listings_only = [p[0] for p in pairs]
        market_obj = pairs[0][1]
        results = analyze_batch(listings_only, market_obj, buyers)
        all_results.extend(results)

    actionable = filter_actionable(all_results)
    output_records = [to_output_record(r) for r in actionable]

    tier1 = [r for r in actionable if r.tier == "Tier 1"]
    tier2 = [r for r in actionable if r.tier == "Tier 2"]

    logger.info("Tier 1: %d | Tier 2: %d", len(tier1), len(tier2))

    out_path = _write_output(output_records, run_id, config.output_dir)

    if config.write_vault_stubs and output_records:
        _write_vault_stubs(output_records, VAULT_ROOT)
        logger.info("Wrote %d vault deal stubs", len(output_records))

    finished_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== AMARA RUN %s COMPLETE — output: %s ===", run_id, out_path)

    return RunSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        markets_processed=len(markets),
        zips_scraped=len(zip_codes),
        raw_listings=len(raw_listings),
        normalized=len(normalized),
        distressed=len(distressed),
        deals_analyzed=len(all_results),
        tier1_count=len(tier1),
        tier2_count=len(tier2),
        output_path=str(out_path),
    )


async def run_continuous(config: RunConfig) -> None:
    """Run repeatedly at config.interval_seconds until interrupted."""
    logger.info("Continuous mode: interval=%ds", config.interval_seconds)
    run_count = 0
    while True:
        run_count += 1
        logger.info("--- Continuous run #%d ---", run_count)
        try:
            summary = await run_once(config)
            logger.info(
                "Run #%d complete: Tier1=%d Tier2=%d",
                run_count, summary.tier1_count, summary.tier2_count,
            )
        except Exception as e:
            logger.error("Run #%d failed: %s — continuing in %ds", run_count, e, config.interval_seconds)

        logger.info("Next run in %d seconds...", config.interval_seconds)
        await asyncio.sleep(config.interval_seconds)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="AMARA OS Deal Generation Engine")
    parser.add_argument("--regions", nargs="*", help="Regions to run (default: all)")
    parser.add_argument("--markets", nargs="*", help="Specific market names")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dom-min", type=int, default=90)
    parser.add_argument("--source", default="redfin", choices=["redfin", "propstream_csv", "county"])
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--no-vault", action="store_true", help="Skip writing vault stubs")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between runs (continuous mode)")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    config = RunConfig(
        regions=args.regions or [],
        markets=args.markets or [],
        concurrency=args.concurrency,
        dom_min=args.dom_min,
        headless=not args.no_headless,
        source=args.source,
        max_pages_per_zip=args.max_pages,
        write_vault_stubs=not args.no_vault,
        output_dir=Path(args.output_dir),
        continuous=args.continuous,
        interval_seconds=args.interval,
    )

    if config.continuous:
        asyncio.run(run_continuous(config))
    else:
        summary = asyncio.run(run_once(config))
        print(json.dumps(asdict(summary), indent=2))
