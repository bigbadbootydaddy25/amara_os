#!/usr/bin/env python3
"""
AMARA OS — Buyer-First Real Estate Intelligence System
Main CLI entry point.

Usage:
    python amara.py mao sfr --buyer-price 200000 --repairs 30000
    python amara.py mao land --retail-value 1000000 --acquisition 400000
    python amara.py analyze sfr --deal-id DEAL-0001 [options]
    python amara.py buyer new
    python amara.py vault list buyers
    python amara.py vault search buyers "Dallas"
    python amara.py propstream import-buyers export.csv
    python amara.py propstream import-distressed export.csv --buyer-zips 77009,77018
    python amara.py learn transcript.txt --title "Subject-To Investing 101"
"""

import sys
import argparse
from pathlib import Path

from system.config import (
    SFR_MIN_ASSIGNMENT_FEE,
    SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
    WORKFLOW_STEPS,
)
from system.mao_calculator import (
    calculate_sfr_mao,
    calculate_land_spread,
    calculate_ldp,
    what_buyer_price_is_needed,
)
from system.deal_analyzer import analyze_sfr_deal, analyze_land_deal, quick_screen
from system.vault import (
    ensure_vault_dirs,
    list_vault,
    search_vault,
    create_buyer_file,
)
from system.zip_corridor import create_corridor, list_hot_corridors
from system.auto_matcher import (
    run_pipeline, run_batch, print_batch_summary, _load_vault_buyers,
)
from system.lead_intake import ingest_from_csv, ingest_manual, PropertyType, LeadSource
from system.offer_queue import get_queue, get_rejections, print_queue_summary
from system.comp_intelligence import (
    underwrite_sfr,
    underwrite_land,
    fast_repair_estimate,
    LandSignals,
    RepairCondition,
)
from system.propstream_operator import (
    load_cash_buyer_export,
    load_distressed_property_export,
    create_buyer_from_propstream,
    screen_distressed_properties,
    create_deal_stub_from_propstream,
    log_propstream_session,
)
from system.video_to_playbook import process_transcript


def cmd_mao(args) -> None:
    """Calculate MAO or spread."""
    if args.asset_type == "sfr":
        fee = getattr(args, "assignment_fee", SFR_TARGET_ASSIGNMENT_FEE) or SFR_TARGET_ASSIGNMENT_FEE
        result = calculate_sfr_mao(args.buyer_price, args.repairs, fee)
        print(result.summary())

        # Also show minimum fee version if different
        if fee != SFR_MIN_ASSIGNMENT_FEE:
            print(f"\n--- At minimum fee (${SFR_MIN_ASSIGNMENT_FEE:,.0f}) ---")
            min_result = calculate_sfr_mao(args.buyer_price, args.repairs, SFR_MIN_ASSIGNMENT_FEE)
            print(f"MAO: ${min_result.mao:,.0f}")

        if hasattr(args, "seller_asking") and args.seller_asking:
            gap = args.seller_asking - result.mao
            if gap > 0:
                print(f"\n⚠  Seller asking ${args.seller_asking:,.0f} is ${gap:,.0f} over MAO.")
                needed = what_buyer_price_is_needed(args.seller_asking, args.repairs, fee)
                print(f"   Need buyer at ${needed:,.0f} to hit target fee at that seller price.")
            else:
                print(f"\n✓  Seller asking ${args.seller_asking:,.0f} is ${abs(gap):,.0f} under MAO.")
                actual_fee = args.buyer_price - args.repairs - args.seller_asking
                print(f"   Actual fee at seller price: ${actual_fee:,.0f}")

    elif args.asset_type == "land":
        result = calculate_land_spread(args.retail_value, args.acquisition, getattr(args, "assignment_fee", 0) or 0)
        print(result.summary())


def cmd_analyze(args) -> None:
    """Run full deal analysis."""
    if args.asset_type == "sfr":
        analysis = analyze_sfr_deal(
            deal_id=args.deal_id,
            address=getattr(args, "address", "Unknown"),
            arv=args.arv,
            buyer_price=args.buyer_price,
            repairs=args.repairs,
            seller_asking=args.seller_asking,
            target_fee=getattr(args, "fee", SFR_TARGET_ASSIGNMENT_FEE) or SFR_TARGET_ASSIGNMENT_FEE,
        )
        print(analysis.summary())

    elif args.asset_type == "land":
        analysis = analyze_land_deal(
            deal_id=args.deal_id,
            address=getattr(args, "address", "Unknown"),
            retail_value=args.retail_value,
            acquisition_cost=args.acquisition,
            assignment_fee=getattr(args, "fee", 0) or 0,
        )
        print(analysis.summary())


def cmd_screen(args) -> None:
    """Quick go/no-go screen."""
    result = quick_screen(
        asset_type=args.asset_type.upper() if args.asset_type.lower() == "sfr" else args.asset_type.capitalize(),
        buyer_price=args.buyer_price,
        repairs=getattr(args, "repairs", 0) or 0,
        seller_asking=args.seller_asking,
    )
    print("\nQUICK SCREEN RESULT:")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"  {k}: ${v:,.0f}" if "price" in k or "fee" in k or "mao" in k or "spread" in k else f"  {k}: {v}")
        else:
            print(f"  {k}: {v}")


def cmd_buyer(args) -> None:
    """Buyer management commands."""
    if args.action == "new":
        name = input("Buyer name: ").strip()
        company = input("Company (or blank): ").strip()
        phone = input("Phone: ").strip()
        email = input("Email: ").strip()
        source = input("Source: ").strip()
        buyer_id, path = create_buyer_file(name, company, phone, email, source)
        print(f"\n✓ Buyer created: {buyer_id}")
        print(f"  File: {path}")
        print(f"  Edit buy box: {path}")

    elif args.action == "list":
        files = list_vault("buyers")
        if not files:
            print("No buyers in vault.")
            return
        print(f"\nActive Buyers ({len(files)}):")
        for f in files:
            if f.name == "TEMPLATE.md":
                continue
            print(f"  {f.stem}")


def cmd_vault(args) -> None:
    """Vault browse and search commands."""
    if args.action == "list":
        folder = args.folder
        files = list_vault(folder)
        if not files:
            print(f"No files in {folder}/")
            return
        print(f"\n{folder}/ ({len(files)} files):")
        for f in files:
            print(f"  {f.name}")

    elif args.action == "search":
        folder = args.folder
        keyword = args.keyword
        results = search_vault(folder, keyword)
        if not results:
            print(f"No matches for '{keyword}' in {folder}/")
            return
        print(f"\nSearch '{keyword}' in {folder}/:")
        for path, lines in results:
            print(f"\n  {path.name}:")
            for line in lines[:5]:
                print(f"    {line}")


def cmd_corridors(args) -> None:
    """ZIP corridor commands."""
    if args.action == "hot":
        hot = list_hot_corridors()
        if not hot:
            print("No hot corridors on record.")
            return
        print(f"\nHot ZIP Corridors ({len(hot)}):")
        for f in hot:
            print(f"  {f.stem}")

    elif args.action == "new":
        name = input("Corridor name: ").strip()
        zips = input("ZIP codes (comma-separated): ").strip().split(",")
        city = input("City: ").strip()
        state = input("State: ").strip()
        corridor_id, path = create_corridor(name, [z.strip() for z in zips], city, state)
        print(f"\n✓ Corridor created: {corridor_id}")
        print(f"  File: {path}")


def cmd_workflow(_args) -> None:
    """Print the system workflow."""
    print("\nAMARA OS — System Workflow")
    print("─" * 40)
    for step in WORKFLOW_STEPS:
        print(f"  {step}")
    print()


def cmd_match(args) -> None:
    """Auto Matcher — run the full 10-stage pipeline."""
    buyers = _load_vault_buyers()
    print(f"\nBuyers loaded from vault: {len(buyers)}")

    if args.action == "csv":
        leads = ingest_from_csv(args.file, source=args.source)
        print(f"Leads loaded: {len(leads)}")
        results = run_batch(leads, buyers)
        print_batch_summary(results)

    elif args.action == "manual":
        lead = ingest_manual(
            address       = args.address,
            zip_code      = args.zip,
            city          = getattr(args, "city", "") or "",
            state         = getattr(args, "state", "") or "",
            list_price    = args.price,
            property_type = getattr(args, "property_type", PropertyType.SFR) or PropertyType.SFR,
            beds          = getattr(args, "beds", 0) or 0,
            baths         = getattr(args, "baths", 0) or 0,
            sqft          = getattr(args, "sqft", 0) or 0,
            lot_size      = getattr(args, "lot_size", 0) or 0,
            year_built    = getattr(args, "year_built", 0) or 0,
            dom           = getattr(args, "dom", 0) or 0,
            description   = getattr(args, "description", "") or "",
            source        = LeadSource.MANUAL,
        )
        result = run_pipeline(lead, buyers)
        print(f"\n{result.summary()}")
        if result.notes:
            print("\nPipeline stages:")
            for note in result.notes:
                print(f"  {note}")

    elif args.action == "queue":
        print_queue_summary()

    elif args.action == "rejections":
        rejs = get_rejections()
        if not rejs:
            print("No rejections on record.")
            return
        print(f"\nRejection Log ({len(rejs)}):")
        for r in rejs[-20:]:
            print(f"  [{r.stage.upper()}] {r.address} ({r.zip_code}) — {r.reason}")


def cmd_underwrite(args) -> None:
    """Comp Intelligence + Fast Underwriting — under 60 seconds."""
    if args.asset_type == "sfr":
        result = underwrite_sfr(
            deal_id=getattr(args, "deal_id", "DEAL-???"),
            address=getattr(args, "address", "Unknown"),
            zip_code=getattr(args, "zip_code", ""),
            buyer_id=getattr(args, "buyer_id", ""),
            buyer_price=args.buyer_price,
            seller_asking=args.seller_asking,
            sqft=getattr(args, "sqft", 0) or 0,
            repairs=getattr(args, "repairs", 0) or 0,
            condition=getattr(args, "condition", "medium") or "medium",
            market=getattr(args, "market", "default") or "default",
        )
        print(result.summary())

    elif args.asset_type == "land":
        signals = LandSignals(
            nearby_builders=getattr(args, "builders", False),
            active_subdivisions=getattr(args, "subdivisions", False),
            new_construction_prices_available=getattr(args, "new_construction", False),
            expansion_direction_confirmed=getattr(args, "expansion", False),
        )
        result = underwrite_land(
            deal_id=getattr(args, "deal_id", "LAND-???"),
            address=getattr(args, "address", "Unknown"),
            acres=args.acres,
            median_home_price=args.median_home_price,
            asking_price=args.asking_price,
            signals=signals,
            density=getattr(args, "density", 3.5) or 3.5,
            lot_multiplier=getattr(args, "lot_multiplier", 0.23) or 0.23,
            dev_cost_per_lot=getattr(args, "dev_cost", 60_000) or 60_000,
        )
        print(result.summary())


def cmd_ldp(args) -> None:
    """Land Development Play underwriting."""
    result = calculate_ldp(
        acres=args.acres,
        median_home_price=args.median_home_price,
        asking_price=args.asking_price,
        density=args.density,
        lot_value_multiplier=args.lot_multiplier,
        dev_cost_per_lot=args.dev_cost,
        builder_profit_pct=0.15,
    )
    print(result.summary())


def cmd_propstream(args) -> None:
    """PropStream import commands."""
    if args.action == "import-buyers":
        csv_path = args.file
        print(f"\nLoading PropStream cash buyer export: {csv_path}")
        buyers = load_cash_buyer_export(csv_path)
        print(f"  Records loaded: {len(buyers)}")

        created = []
        skipped = 0
        for buyer in buyers:
            result = create_buyer_from_propstream(buyer)
            if result:
                buyer_id, path = result
                created.append((buyer_id, buyer.entity_name, path))
            else:
                skipped += 1

        print(f"\n  Buyers created: {len(created)}")
        print(f"  Skipped (did not qualify): {skipped}")
        for buyer_id, name, path in created:
            print(f"    {buyer_id} — {name}")

        log_propstream_session(
            market=getattr(args, "market", "Unknown"),
            search_type="Cash Buyer Export",
            records_reviewed=len(buyers),
            buyers_created=len(created),
            deals_created=0,
            observations=[f"{skipped} records skipped (fewer than 2 transactions)"],
        )
        print(f"\n  Session logged to observations/")

    elif args.action == "import-distressed":
        csv_path = args.file
        buyer_zips = [z.strip() for z in args.buyer_zips.split(",")] if args.buyer_zips else []
        buyer_id = getattr(args, "buyer_id", "") or ""
        buyer_name = getattr(args, "buyer_name", "") or "Unknown Buyer"

        print(f"\nLoading PropStream distressed property export: {csv_path}")
        properties = load_distressed_property_export(csv_path)
        print(f"  Records loaded: {len(properties)}")

        if buyer_zips:
            screened = screen_distressed_properties(properties, buyer_zips)
            print(f"  Passed buyer-first screen: {len(screened)}")
        else:
            screened = [p for p in properties if p.has_equity()]
            print(f"  Passed equity screen: {len(screened)} (no buyer ZIPs provided — limited screen only)")

        if not buyer_id:
            print("\n  ⚠  No --buyer-id provided. Deal stubs require a confirmed buyer match.")
            print("     Run: python amara.py buyer list — then re-run with --buyer-id BUY-XXXX")
            return

        created_deals = []
        for prop in screened[:20]:  # Cap at 20 stubs per session
            deal_id, path = create_deal_stub_from_propstream(prop, buyer_id, buyer_name)
            created_deals.append((deal_id, prop.address, path))

        print(f"\n  Deal stubs created: {len(created_deals)}")
        for deal_id, address, path in created_deals:
            print(f"    {deal_id} — {address}")

        log_propstream_session(
            market=getattr(args, "market", "Unknown"),
            search_type="Distressed Property Export",
            records_reviewed=len(properties),
            buyers_created=0,
            deals_created=len(created_deals),
            observations=[
                f"{len(properties) - len(screened)} records filtered out (no equity or outside buyer ZIPs)",
                f"Buyer matched: {buyer_id} — {buyer_name}",
            ],
        )
        print(f"\n  Session logged to observations/")


def cmd_learn(args) -> None:
    """Video-to-Playbook learning skill."""
    transcript_path = args.file
    path = Path(transcript_path)

    if not path.exists():
        # Treat input as raw transcript text if not a file path
        transcript = transcript_path
    else:
        transcript = path.read_text(encoding="utf-8")

    title = getattr(args, "title", "") or ""
    topic = getattr(args, "topic", "") or ""

    print(f"\nProcessing transcript...")
    if title:
        print(f"  Title: {title}")
    print(f"  Words: {len(transcript.split())}")

    result = process_transcript(transcript, video_title=title, topic_override=topic)

    if result["success"]:
        print(f"\n  Playbook written: {result['playbook_path']}")
        print(f"  Observation logged: {result['observation_path']}")
        print(f"  Confidence: {result['confidence']}")
    else:
        print(f"\n  Could not extract playbook.")
        print(f"  Reason: {result['reason']}")
        print(f"  Provide a longer, more structured transcript.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amara",
        description="AMARA OS — Buyer-First Real Estate Intelligence System",
    )
    sub = parser.add_subparsers(dest="command")

    # ── mao ──────────────────────────────────────────────────────────────────
    mao_p = sub.add_parser("mao", help="Calculate MAO or land spread")
    mao_p.add_argument("asset_type", choices=["sfr", "land"], help="sfr or land")
    mao_p.add_argument("--buyer-price", type=float, dest="buyer_price")
    mao_p.add_argument("--retail-value", type=float, dest="retail_value")
    mao_p.add_argument("--repairs", type=float, default=0)
    mao_p.add_argument("--acquisition", type=float, default=0)
    mao_p.add_argument("--assignment-fee", type=float, default=0, dest="assignment_fee")
    mao_p.add_argument("--seller-asking", type=float, default=0, dest="seller_asking")
    mao_p.set_defaults(func=cmd_mao)

    # ── analyze ───────────────────────────────────────────────────────────────
    ana_p = sub.add_parser("analyze", help="Full deal analysis")
    ana_p.add_argument("asset_type", choices=["sfr", "land"])
    ana_p.add_argument("--deal-id", required=True, dest="deal_id")
    ana_p.add_argument("--address", default="Unknown")
    ana_p.add_argument("--arv", type=float, default=0)
    ana_p.add_argument("--buyer-price", type=float, default=0, dest="buyer_price")
    ana_p.add_argument("--retail-value", type=float, default=0, dest="retail_value")
    ana_p.add_argument("--repairs", type=float, default=0)
    ana_p.add_argument("--seller-asking", type=float, default=0, dest="seller_asking")
    ana_p.add_argument("--acquisition", type=float, default=0)
    ana_p.add_argument("--fee", type=float, default=SFR_TARGET_ASSIGNMENT_FEE)
    ana_p.set_defaults(func=cmd_analyze)

    # ── screen ────────────────────────────────────────────────────────────────
    scr_p = sub.add_parser("screen", help="Quick go/no-go screen")
    scr_p.add_argument("asset_type", choices=["sfr", "land"])
    scr_p.add_argument("--buyer-price", type=float, default=0, dest="buyer_price")
    scr_p.add_argument("--repairs", type=float, default=0)
    scr_p.add_argument("--seller-asking", type=float, required=True, dest="seller_asking")
    scr_p.set_defaults(func=cmd_screen)

    # ── buyer ─────────────────────────────────────────────────────────────────
    buy_p = sub.add_parser("buyer", help="Buyer management")
    buy_p.add_argument("action", choices=["new", "list"])
    buy_p.set_defaults(func=cmd_buyer)

    # ── vault ─────────────────────────────────────────────────────────────────
    vlt_p = sub.add_parser("vault", help="Browse and search the vault")
    vlt_p.add_argument("action", choices=["list", "search"])
    vlt_p.add_argument("folder", help="Vault folder (buyers, deals, land, etc.)")
    vlt_p.add_argument("keyword", nargs="?", help="Search keyword")
    vlt_p.set_defaults(func=cmd_vault)

    # ── corridors ─────────────────────────────────────────────────────────────
    cor_p = sub.add_parser("corridors", help="ZIP corridor management")
    cor_p.add_argument("action", choices=["hot", "new"])
    cor_p.set_defaults(func=cmd_corridors)

    # ── workflow ──────────────────────────────────────────────────────────────
    wf_p = sub.add_parser("workflow", help="Print system workflow steps")
    wf_p.set_defaults(func=cmd_workflow)

    # ── match ─────────────────────────────────────────────────────────────────
    mat_p = sub.add_parser("match", help="Auto Matcher — full 10-stage pipeline")
    mat_p.add_argument("action", choices=["csv", "manual", "queue", "rejections"])
    mat_p.add_argument("file", nargs="?", default="", help="CSV file path (csv action only)")
    mat_p.add_argument("--source", default="csv", help="Lead source label")
    mat_p.add_argument("--address", default="")
    mat_p.add_argument("--zip", default="")
    mat_p.add_argument("--city", default="")
    mat_p.add_argument("--state", default="")
    mat_p.add_argument("--price", type=float, default=0)
    mat_p.add_argument("--beds", type=float, default=0)
    mat_p.add_argument("--baths", type=float, default=0)
    mat_p.add_argument("--sqft", type=int, default=0)
    mat_p.add_argument("--lot-size", type=float, default=0, dest="lot_size")
    mat_p.add_argument("--year-built", type=int, default=0, dest="year_built")
    mat_p.add_argument("--dom", type=int, default=0)
    mat_p.add_argument("--description", default="")
    mat_p.add_argument("--property-type", default="SFR", dest="property_type")
    mat_p.set_defaults(func=cmd_match)

    # ── underwrite ────────────────────────────────────────────────────────────
    uw_p = sub.add_parser("underwrite", help="Comp Intelligence + Fast Underwriting (<60s)")
    uw_p.add_argument("asset_type", choices=["sfr", "land"])
    uw_p.add_argument("--deal-id", default="DEAL-???", dest="deal_id")
    uw_p.add_argument("--address", default="Unknown")
    uw_p.add_argument("--zip", default="", dest="zip_code")
    uw_p.add_argument("--buyer-id", default="", dest="buyer_id")
    uw_p.add_argument("--market", default="default")
    # SFR args
    uw_p.add_argument("--buyer-price", type=float, default=0, dest="buyer_price")
    uw_p.add_argument("--seller-asking", type=float, default=0, dest="seller_asking")
    uw_p.add_argument("--repairs", type=float, default=0)
    uw_p.add_argument("--sqft", type=float, default=0)
    uw_p.add_argument("--condition", choices=["light", "medium", "heavy"], default="medium")
    # Land args
    uw_p.add_argument("--acres", type=float, default=0)
    uw_p.add_argument("--median-home-price", type=float, default=0, dest="median_home_price")
    uw_p.add_argument("--asking-price", type=float, default=0, dest="asking_price")
    uw_p.add_argument("--density", type=float, default=3.5)
    uw_p.add_argument("--lot-multiplier", type=float, default=0.23, dest="lot_multiplier")
    uw_p.add_argument("--dev-cost", type=float, default=60_000, dest="dev_cost")
    # Land signal flags
    uw_p.add_argument("--builders", action="store_true", help="Nearby builders confirmed")
    uw_p.add_argument("--subdivisions", action="store_true", help="Active subdivisions confirmed")
    uw_p.add_argument("--new-construction", action="store_true", dest="new_construction",
                      help="New construction prices available")
    uw_p.add_argument("--expansion", action="store_true", help="Expansion direction confirmed")
    uw_p.set_defaults(func=cmd_underwrite)

    # ── ldp ───────────────────────────────────────────────────────────────────
    ldp_p = sub.add_parser("ldp", help="Land Development Play underwriting")
    ldp_p.add_argument("--acres", type=float, required=True)
    ldp_p.add_argument("--median-home-price", type=float, required=True, dest="median_home_price")
    ldp_p.add_argument("--asking-price", type=float, required=True, dest="asking_price")
    ldp_p.add_argument("--density", type=float, default=3.5, help="Lots per acre (default 3.5)")
    ldp_p.add_argument("--lot-multiplier", type=float, default=0.23, dest="lot_multiplier",
                       help="Lot value as % of median home price (default 0.23)")
    ldp_p.add_argument("--dev-cost", type=float, default=60_000, dest="dev_cost",
                       help="Development cost per lot (default $60,000)")
    ldp_p.set_defaults(func=cmd_ldp)

    # ── propstream ────────────────────────────────────────────────────────────
    ps_p = sub.add_parser("propstream", help="PropStream import and session logging")
    ps_p.add_argument("action", choices=["import-buyers", "import-distressed"])
    ps_p.add_argument("file", help="Path to PropStream CSV export")
    ps_p.add_argument("--market", default="Unknown", help="Market name for session log")
    ps_p.add_argument("--buyer-zips", default="", dest="buyer_zips",
                      help="Comma-separated buyer ZIPs to screen against (import-distressed only)")
    ps_p.add_argument("--buyer-id", default="", dest="buyer_id",
                      help="Confirmed buyer ID to match deals to (import-distressed only)")
    ps_p.add_argument("--buyer-name", default="", dest="buyer_name",
                      help="Confirmed buyer name (import-distressed only)")
    ps_p.set_defaults(func=cmd_propstream)

    # ── learn ─────────────────────────────────────────────────────────────────
    lrn_p = sub.add_parser("learn", help="Process a video transcript into a playbook")
    lrn_p.add_argument("file", help="Path to transcript .txt file (or raw text)")
    lrn_p.add_argument("--title", default="", help="Video title")
    lrn_p.add_argument("--topic", default="", help="Topic override for playbook filename")
    lrn_p.set_defaults(func=cmd_learn)

    return parser


def main() -> None:
    ensure_vault_dirs()
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        print("\nAMARA OS — Buyer-First Real Estate Intelligence System")
        print("=" * 55)
        print("Core Rule: No buyer = no deal.\n")
        print("Commands: match | underwrite | mao | screen | ldp | buyer | vault | corridors | propstream | learn | workflow")
        print("\nRun: python amara.py <command> --help")
        print()
        return

    # Fix land MAO command arg routing
    if args.command == "mao" and args.asset_type == "land":
        if not hasattr(args, "retail_value") or not args.retail_value:
            args.retail_value = args.buyer_price or 0

    args.func(args)


if __name__ == "__main__":
    main()
