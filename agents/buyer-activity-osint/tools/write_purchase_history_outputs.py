#!/usr/bin/env python3
"""
Standalone purchase-history and heat-ranking writer.

Reads ACTIVITY_SUMMARY.json produced by run.py and writes six output files:
  BUYER_PURCHASE_HISTORY.md
  RECENT_BUYERS.json
  MULTI_PURCHASE_BUYERS.json
  HOT_BUYERS.json
  ACTIVE_BUYERS.json
  BUYER_HEAT_RANKINGS.md

Scoring fields (activity_recency_score, weighted_buyer_score,
acquisition_heat_score, buyer_state) are computed here when they are absent
from the input file, so this tool works with both new and older run.py output.

Usage:
    python3 agents/buyer-activity-osint/tools/write_purchase_history_outputs.py \\
        --workspace-root /path/to/ai-brain

    python3 agents/buyer-activity-osint/tools/write_purchase_history_outputs.py \\
        --reports-dir agents/buyer-activity-osint/reports
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import scoring helpers from the parent agent.
_AGENT_DIR = Path(__file__).parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from run import (  # noqa: E402
    _activity_recency_score,
    _weighted_buyer_score,
    _acquisition_heat_score,
    _buyer_state,
    _SFR_RE,
    _CASH_RE,
    _HARD_MONEY_RE,
    _LAND_RE,
    _DISTRESS_RE,
)


# ─── ensure every profile dict carries scoring fields ────────────────────────

def _ensure_scores(p: dict) -> dict:
    """
    Return p (possibly a shallow copy) with all four scoring fields present.
    If acquisition_heat_score is already in p the dict is returned as-is.
    """
    if "acquisition_heat_score" in p:
        return p

    p = dict(p)  # don't mutate the original

    days_since = p.get("days_since_last_purchase")
    cnt_30  = p.get("recent_purchase_count_30d",  0)
    cnt_90  = p.get("recent_purchase_count_90d",  0)
    cnt_180 = p.get("recent_purchase_count_180d", 0)
    cnt_365 = p.get("recent_purchase_count_365d", 0)
    total   = p.get("total_purchase_count", p.get("transaction_count", 0))
    multi   = p.get("multi_purchase_buyer",  False)
    repeat  = p.get("repeat_market_buyer",   False)
    velocity = p.get("purchase_velocity_score", 0.0)

    zip_codes  = p.get("purchase_zip_codes",    p.get("zip_codes",    []))
    ptypes_lst = p.get("purchase_property_types", p.get("property_types", []))
    ftypes_lst = p.get("financing_types", [])

    all_ptypes = " ".join(ptypes_lst)
    all_ftypes = " ".join(ftypes_lst)

    has_sfr        = bool(_SFR_RE.search(all_ptypes))
    has_cash       = bool(_CASH_RE.search(all_ftypes))
    has_hard_money = bool(_HARD_MONEY_RE.search(all_ftypes))
    has_land       = bool(_LAND_RE.search(all_ptypes))
    has_distress   = bool(_DISTRESS_RE.search(all_ptypes + " " + all_ftypes))

    recency = _activity_recency_score(days_since)
    weighted = _weighted_buyer_score(
        cnt_30, cnt_90, cnt_180, total,
        multi, repeat, len(zip_codes),
        has_sfr, has_cash, has_hard_money, has_land, has_distress,
    )
    heat  = _acquisition_heat_score(recency, weighted, velocity, days_since)
    state = _buyer_state(cnt_30, cnt_90, cnt_365, total)

    p["activity_recency_score"] = recency
    p["weighted_buyer_score"]   = weighted
    p["acquisition_heat_score"] = heat
    p["buyer_state"]            = state
    return p


# ─── writers ─────────────────────────────────────────────────────────────────

def write_recent_buyers(profiles: list[dict], reports_dir: Path, ts: str) -> None:
    recent = [p for p in profiles if p.get("recent_purchase_count_90d", 0) >= 1]
    recent.sort(key=lambda p: p["acquisition_heat_score"], reverse=True)
    (reports_dir / "RECENT_BUYERS.json").write_text(
        json.dumps({
            "run_timestamp": ts,
            "total_recent_buyers": len(recent),
            "window_days": 90,
            "buyers": recent,
        }, indent=2, default=str),
        encoding="utf-8",
    )


def write_multi_purchase_buyers(profiles: list[dict], reports_dir: Path, ts: str) -> None:
    multi = [p for p in profiles if p.get("multi_purchase_buyer", False)]
    multi.sort(key=lambda p: p["acquisition_heat_score"], reverse=True)
    (reports_dir / "MULTI_PURCHASE_BUYERS.json").write_text(
        json.dumps({
            "run_timestamp": ts,
            "total_multi_purchase_buyers": len(multi),
            "buyers": multi,
        }, indent=2, default=str),
        encoding="utf-8",
    )


def write_hot_buyers(profiles: list[dict], reports_dir: Path, ts: str) -> None:
    hot = sorted(
        [p for p in profiles if p.get("buyer_state") == "HOT"],
        key=lambda p: p["acquisition_heat_score"],
        reverse=True,
    )
    (reports_dir / "HOT_BUYERS.json").write_text(
        json.dumps({
            "run_timestamp": ts,
            "total_hot_buyers": len(hot),
            "definition": "Buyers with at least one purchase recorded in the last 30 days",
            "buyers": hot,
        }, indent=2, default=str),
        encoding="utf-8",
    )


def write_active_buyers(profiles: list[dict], reports_dir: Path, ts: str) -> None:
    active = sorted(
        [p for p in profiles if p.get("buyer_state") in ("HOT", "ACTIVE")],
        key=lambda p: p["acquisition_heat_score"],
        reverse=True,
    )
    (reports_dir / "ACTIVE_BUYERS.json").write_text(
        json.dumps({
            "run_timestamp": ts,
            "total_active_buyers": len(active),
            "definition": "Buyers with at least one purchase in the last 90 days (HOT or ACTIVE state)",
            "buyers": active,
        }, indent=2, default=str),
        encoding="utf-8",
    )


_STATE_BADGE = {
    "HOT":     "🔥 HOT",
    "ACTIVE":  "✅ ACTIVE",
    "WARM":    "🟡 WARM",
    "COLD":    "🔵 COLD",
    "DORMANT": "⬜ DORMANT",
}


def write_buyer_heat_rankings(profiles: list[dict], reports_dir: Path, ts: str) -> None:
    ranked = sorted(profiles, key=lambda p: p["acquisition_heat_score"], reverse=True)
    state_counts: dict[str, int] = {}
    for p in ranked:
        s = p.get("buyer_state", "DORMANT")
        state_counts[s] = state_counts.get(s, 0) + 1

    lines = [
        "# BUYER_HEAT_RANKINGS",
        "",
        f"_Generated: {ts}_",
        f"_Total buyers ranked: {len(ranked)}_",
        "",
        "## State Summary",
        "",
    ]
    for state in ("HOT", "ACTIVE", "WARM", "COLD", "DORMANT"):
        lines.append(f"- **{_STATE_BADGE[state]}**: {state_counts.get(state, 0)}")

    lines += [
        "",
        "## Scoring Model",
        "",
        "| Component | Weight | Notes |",
        "|---|---|---|",
        "| activity_recency_score | 40% | 100=last 30d, decays to 0 after ~2yr |",
        "| weighted_buyer_score | 40% | Recency + distress + market signals |",
        "| purchase_velocity_score | 20% | Purchases/month over active window |",
        "| Inactivity decay | ×0–50% | Applied when last purchase >365d ago |",
        "",
        "## Buyer State Definitions",
        "",
        "| State | Criteria |",
        "|---|---|",
        "| 🔥 HOT | Purchase in last 30 days |",
        "| ✅ ACTIVE | Purchase in last 90 days |",
        "| 🟡 WARM | Purchase in last 365 days |",
        "| 🔵 COLD | Multi-purchase buyer, last >365 days |",
        "| ⬜ DORMANT | Single purchase or no date |",
        "",
        "## Rankings",
        "",
        "| Rank | State | Buyer | Heat | Recency | Weighted | Velocity | Last Purchase | Count |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(ranked, 1):
        badge = _STATE_BADGE.get(p.get("buyer_state", "DORMANT"), p.get("buyer_state", ""))
        lines.append(
            f"| {i} | {badge} | {p.get('display_name', '')} "
            f"| {p['acquisition_heat_score']} "
            f"| {p.get('activity_recency_score', '')} "
            f"| {p.get('weighted_buyer_score', '')} "
            f"| {p.get('purchase_velocity_score', '')} "
            f"| {p.get('last_purchase_date') or 'unknown'} "
            f"| {p.get('total_purchase_count', p.get('transaction_count', 0))} |"
        )

    lines += ["", "## Buyer Detail", ""]
    for p in ranked:
        badge    = _STATE_BADGE.get(p.get("buyer_state", "DORMANT"), "")
        seed_id  = p.get("seed_id")
        seed_st  = p.get("seed_status")
        seed_tag = f"[{seed_id}·{seed_st}]" if seed_id else "[new]"
        total    = p.get("total_purchase_count", p.get("transaction_count", 0))
        c30, c90, c180, c365 = (
            p.get("recent_purchase_count_30d",  0),
            p.get("recent_purchase_count_90d",  0),
            p.get("recent_purchase_count_180d", 0),
            p.get("recent_purchase_count_365d", 0),
        )
        days_since = p.get("days_since_last_purchase")
        markets = ", ".join(p.get("purchase_markets", []))
        zips    = ", ".join(p.get("purchase_zip_codes", p.get("zip_codes", [])))
        price_avg = p.get("price_avg")

        lines += [
            f"### {badge}  {p.get('display_name', '')}  {seed_tag}",
            "",
            "| Score | Value |",
            "|---|---|",
            f"| acquisition_heat_score | **{p['acquisition_heat_score']}** |",
            f"| activity_recency_score | {p.get('activity_recency_score', '')} |",
            f"| weighted_buyer_score | {p.get('weighted_buyer_score', '')} |",
            f"| purchase_velocity_score | {p.get('purchase_velocity_score', '')} |",
            f"| Total purchases | {total} |",
            f"| Purchases 30d / 90d / 180d / 365d | {c30} / {c90} / {c180} / {c365} |",
            f"| Last purchase | {p.get('last_purchase_date') or 'unknown'} |",
            f"| Days since last purchase | {days_since if days_since is not None else 'unknown'} |",
            f"| Multi-purchase | {p.get('multi_purchase_buyer', False)} |",
            f"| Repeat market | {p.get('repeat_market_buyer', False)} |",
        ]
        if markets:
            lines.append(f"| Markets | {markets} |")
        if zips:
            lines.append(f"| ZIP codes | {zips} |")
        if price_avg is not None:
            lines.append(f"| Avg price | ${price_avg:,.0f} |")

        evidence = p.get("recent_purchase_evidence", [])
        if evidence:
            lines += ["", "**Recent evidence:**", "",
                      "| Date | Address | Price | Financing | Source |",
                      "|---|---|---|---|---|"]
            for ev in evidence:
                sp = ev.get("sale_price")
                price_str = f"${sp:,.0f}" if sp is not None else "n/a"
                lines.append(
                    f"| {ev.get('date','')} "
                    f"| {ev.get('address') or 'n/a'} "
                    f"| {price_str} "
                    f"| {ev.get('financing_type') or 'n/a'} "
                    f"| {ev.get('source_file','')} |"
                )
        lines.append("")

    (reports_dir / "BUYER_HEAT_RANKINGS.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_buyer_purchase_history(profiles: list[dict], reports_dir: Path, ts: str) -> None:
    ranked = sorted(profiles, key=lambda p: p["acquisition_heat_score"], reverse=True)
    lines = [
        "# BUYER_PURCHASE_HISTORY",
        "",
        f"_Generated: {ts}_",
        f"_Profiles: {len(ranked)}_",
        "",
        "Ranked by acquisition_heat_score (most active buyers first).",
        "",
    ]
    for p in ranked:
        badge    = _STATE_BADGE.get(p.get("buyer_state", "DORMANT"), "")
        seed_id  = p.get("seed_id")
        seed_st  = p.get("seed_status")
        seed_tag = f"[{seed_id}·{seed_st}]" if seed_id else "[new]"
        total    = p.get("total_purchase_count", p.get("transaction_count", 0))
        c30, c90, c180, c365 = (
            p.get("recent_purchase_count_30d",  0),
            p.get("recent_purchase_count_90d",  0),
            p.get("recent_purchase_count_180d", 0),
            p.get("recent_purchase_count_365d", 0),
        )
        days_since = p.get("days_since_last_purchase")
        price_min  = p.get("price_min")
        price_max  = p.get("price_max")
        price_avg  = p.get("price_avg")
        markets    = ", ".join(p.get("purchase_markets", []))
        zips       = ", ".join(p.get("purchase_zip_codes", p.get("zip_codes", [])))
        ptypes     = ", ".join(p.get("purchase_property_types", p.get("property_types", [])))

        lines += [
            f"## {badge}  {p.get('display_name', '')}  {seed_tag}",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| acquisition_heat_score | **{p['acquisition_heat_score']}** |",
            f"| buyer_state | {p.get('buyer_state', 'DORMANT')} |",
            f"| Total purchases | {total} |",
            f"| First purchase | {p.get('first_purchase_date') or 'unknown'} |",
            f"| Last purchase | {p.get('last_purchase_date') or 'unknown'} |",
            f"| Days since last purchase | {days_since if days_since is not None else 'unknown'} |",
            f"| Purchases (30d / 90d / 180d / 365d) | {c30} / {c90} / {c180} / {c365} |",
            f"| Purchase velocity score | {p.get('purchase_velocity_score', '')} |",
            f"| Multi-purchase buyer | {p.get('multi_purchase_buyer', False)} |",
            f"| Repeat market buyer | {p.get('repeat_market_buyer', False)} |",
            f"| Purchase timing confidence | {p.get('purchase_timing_confidence', 'unknown')} |",
        ]
        if markets:
            lines.append(f"| Markets | {markets} |")
        if zips:
            lines.append(f"| ZIP codes | {zips} |")
        if ptypes:
            lines.append(f"| Property types | {ptypes} |")
        if price_avg is not None:
            lines.append(f"| Price range | ${price_min:,.0f} – ${price_max:,.0f} (avg ${price_avg:,.0f}) |")
        lines.append("")

        evidence = p.get("recent_purchase_evidence", [])
        if evidence:
            lines += ["**Recent purchase evidence:**", "",
                      "| Date | Address | Price | Financing | Source |",
                      "|---|---|---|---|---|"]
            for ev in evidence:
                sp = ev.get("sale_price")
                price_str = f"${sp:,.0f}" if sp is not None else "n/a"
                lines.append(
                    f"| {ev.get('date','')} "
                    f"| {ev.get('address') or 'n/a'} "
                    f"| {price_str} "
                    f"| {ev.get('financing_type') or 'n/a'} "
                    f"| {ev.get('source_file','')} |"
                )
            lines.append("")
        lines.append("")

    (reports_dir / "BUYER_PURCHASE_HISTORY.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


# ─── main ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write purchase-history and heat-ranking output files from ACTIVITY_SUMMARY.json"
    )
    parser.add_argument(
        "--workspace-root", default=".",
        help="Workspace root (default: current directory)",
    )
    parser.add_argument(
        "--reports-dir", default=None,
        help="Directory containing ACTIVITY_SUMMARY.json and where outputs are written "
             "(default: agents/buyer-activity-osint/reports relative to workspace-root)",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace_root).expanduser().resolve()
    if args.reports_dir:
        reports_dir = Path(args.reports_dir).expanduser().resolve()
    else:
        reports_dir = workspace / "agents" / "buyer-activity-osint" / "reports"

    summary_path = reports_dir / "ACTIVITY_SUMMARY.json"
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found. Run run.py first.", file=sys.stderr)
        return 1

    data     = json.loads(summary_path.read_text(encoding="utf-8"))
    raw_profiles: list[dict] = data.get("buyer_profiles", [])
    profiles = [_ensure_scores(p) for p in raw_profiles]
    ts = datetime.now(timezone.utc).isoformat()

    reports_dir.mkdir(parents=True, exist_ok=True)

    write_buyer_purchase_history(profiles, reports_dir, ts)
    write_recent_buyers(profiles, reports_dir, ts)
    write_multi_purchase_buyers(profiles, reports_dir, ts)
    write_hot_buyers(profiles, reports_dir, ts)
    write_active_buyers(profiles, reports_dir, ts)
    write_buyer_heat_rankings(profiles, reports_dir, ts)

    state_counts: dict[str, int] = {}
    for p in profiles:
        s = p.get("buyer_state", "DORMANT")
        state_counts[s] = state_counts.get(s, 0) + 1

    print(f"Wrote 6 output files to: {reports_dir}")
    print(f"  Profiles processed: {len(profiles)}")
    for state in ("HOT", "ACTIVE", "WARM", "COLD", "DORMANT"):
        n = state_counts.get(state, 0)
        if n:
            print(f"  {_STATE_BADGE[state]}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
