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
"""

import sys
import argparse

from system.config import (
    SFR_MIN_ASSIGNMENT_FEE,
    SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
    WORKFLOW_STEPS,
)
from system.mao_calculator import (
    calculate_sfr_mao,
    calculate_land_spread,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amara",
        description="AMARA OS — Buyer-First Real Estate Intelligence System",
    )
    sub = parser.add_subparsers(dest="command")

    # ── mao ──────────────────────────────────────────────────────────────────
    mao_p = sub.add_parser("mao", help="Calculate MAO or land spread")
    mao_p.add_argument("asset_type", choices=["sfr", "land"], help="sfr or land")
    mao_p.add_argument("--buyer-price", "--retail-value", type=float, dest="buyer_price")
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

    return parser


def main() -> None:
    ensure_vault_dirs()
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        print("\nAMARA OS — Buyer-First Real Estate Intelligence System")
        print("=" * 55)
        print("Core Rule: No buyer = no deal.\n")
        print("Commands: mao | analyze | screen | buyer | vault | corridors | workflow")
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
