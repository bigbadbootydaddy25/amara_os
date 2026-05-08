"""
Report generation: writes the four output artefacts to an output directory.

Outputs:
  VERIFIED_BUILDERS.json        — profiles scoring >= builder threshold
  POSSIBLE_CASH_BUYERS.json     — profiles scoring >= investor threshold
  BUYER_ACTIVITY_REPORT.md      — human-readable markdown summary
  BUYER_CONFIDENCE_SCORES.json  — all profiles with both scores + quarantine flag
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from models import BuyerProfile, QuarantinedRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_to_dict(profile: BuyerProfile) -> Dict[str, Any]:
    return {
        "owner_name": profile.owner_name,
        "parcel_count": profile.parcel_count,
        "parcel_ids": profile.parcel_ids,
        "zip_codes": profile.zip_codes,
        "acquisition_dates": profile.acquisition_dates,
        "total_spend": round(profile.total_spend, 2),
        "builder_score": profile.builder_score,
        "investor_score": profile.investor_score,
        "is_verified_builder": profile.is_verified_builder,
        "is_possible_cash_buyer": profile.is_possible_cash_buyer,
        "is_quarantined": profile.is_quarantined,
        "quarantine_reason": profile.quarantine_reason,
        "summary": profile.summary,
        "signal_evidence": profile.signal_evidence(),
    }


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Summary text generator
# ---------------------------------------------------------------------------

def generate_profile_summary(profile: BuyerProfile) -> str:
    parts: List[str] = []

    if profile.is_verified_builder:
        parts.append(f"VERIFIED BUILDER (score {profile.builder_score}/100).")
    if profile.is_possible_cash_buyer:
        parts.append(f"POSSIBLE CASH BUYER (investor score {profile.investor_score}/100).")

    parts.append(
        f"Holds {profile.parcel_count} parcel(s) across "
        f"{len(profile.zip_codes)} ZIP code(s)."
    )

    if profile.total_spend > 0:
        parts.append(f"Total recorded spend: ${profile.total_spend:,.0f}.")

    signal_types = list({s.signal_type for s in profile.signals})
    if signal_types:
        parts.append(f"Active signals: {', '.join(signal_types)}.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main report writers
# ---------------------------------------------------------------------------

def write_verified_builders(
    profiles: List[BuyerProfile],
    output_dir: Path,
) -> Path:
    path = output_dir / "VERIFIED_BUILDERS.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(profiles),
        "builders": [_profile_to_dict(p) for p in sorted(
            profiles, key=lambda p: p.builder_score, reverse=True
        )],
    }
    _write_json(path, payload)
    return path


def write_possible_cash_buyers(
    profiles: List[BuyerProfile],
    output_dir: Path,
) -> Path:
    path = output_dir / "POSSIBLE_CASH_BUYERS.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(profiles),
        "cash_buyers": [_profile_to_dict(p) for p in sorted(
            profiles, key=lambda p: p.investor_score, reverse=True
        )],
    }
    _write_json(path, payload)
    return path


def write_confidence_scores(
    all_profiles: Dict[str, BuyerProfile],
    quarantined: List[QuarantinedRecord],
    output_dir: Path,
) -> Path:
    path = output_dir / "BUYER_CONFIDENCE_SCORES.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_profiles": len(all_profiles),
        "quarantined_records": len(quarantined),
        "profiles": [_profile_to_dict(p) for p in sorted(
            all_profiles.values(),
            key=lambda p: max(p.builder_score, p.investor_score),
            reverse=True,
        )],
        "quarantine": [
            {
                "parcel_id": q.parcel_id,
                "owner_name": q.owner_name,
                "reason": q.reason,
            }
            for q in quarantined
        ],
    }
    _write_json(path, payload)
    return path


def write_activity_report(
    builders: List[BuyerProfile],
    cash_buyers: List[BuyerProfile],
    all_profiles: Dict[str, BuyerProfile],
    quarantined: List[QuarantinedRecord],
    output_dir: Path,
) -> Path:
    path = output_dir / "BUYER_ACTIVITY_REPORT.md"

    total = len(all_profiles)
    q_count = len(quarantined)
    clean = total - sum(1 for p in all_profiles.values() if p.is_quarantined)

    lines: List[str] = [
        "# Buyer Activity Report",
        "",
        f"_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total owner profiles | {total} |",
        f"| Scoreable profiles | {clean} |",
        f"| Quarantined (weak evidence) | {sum(1 for p in all_profiles.values() if p.is_quarantined)} |",
        f"| Invalid / pre-validation quarantine | {q_count} |",
        f"| **Verified builders** | **{len(builders)}** |",
        f"| **Possible cash buyers** | **{len(cash_buyers)}** |",
        "",
        "---",
        "",
        "## Verified Builders",
        "",
    ]

    if builders:
        for p in sorted(builders, key=lambda x: x.builder_score, reverse=True):
            lines += _profile_section(p, score_label="Builder Score", score=p.builder_score)
    else:
        lines.append("_No verified builders detected._")
        lines.append("")

    lines += [
        "---",
        "",
        "## Possible Cash Buyers",
        "",
    ]

    if cash_buyers:
        for p in sorted(cash_buyers, key=lambda x: x.investor_score, reverse=True):
            lines += _profile_section(p, score_label="Investor Score", score=p.investor_score)
    else:
        lines.append("_No possible cash buyers detected._")
        lines.append("")

    lines += [
        "---",
        "",
        "## Quarantine Log",
        "",
    ]

    weak_profiles = [p for p in all_profiles.values() if p.is_quarantined]
    if weak_profiles or quarantined:
        lines.append("| Owner | Parcel(s) | Reason |")
        lines.append("|-------|-----------|--------|")
        for p in weak_profiles:
            pids = ", ".join(p.parcel_ids[:3])
            if len(p.parcel_ids) > 3:
                pids += f" (+{len(p.parcel_ids)-3} more)"
            lines.append(f"| {p.owner_name} | {pids} | {p.quarantine_reason} |")
        for q in quarantined:
            lines.append(f"| {q.owner_name} | {q.parcel_id} | {q.reason} |")
        lines.append("")
    else:
        lines.append("_No records quarantined._")
        lines.append("")

    lines += [
        "---",
        "",
        "## Signal Reference",
        "",
        "| Signal Type | Description |",
        "|-------------|-------------|",
        "| LLC_COMPANY | Owner name contains corporate entity suffix |",
        "| BUILDER_KEYWORD | Owner name contains builder/developer keyword |",
        "| INVESTOR_KEYWORD | Owner name contains investment keyword |",
        "| VACANT_LAND | Parcel flagged as vacant or unimproved |",
        "| PERMIT_ACTIVITY | Active permits on file for this parcel |",
        "| MAILING_MISMATCH | Mailing address differs from property address |",
        "| ROUND_SALE_PRICE | Sale price is a round number (cash proxy) |",
        "| REPEAT_ACQUISITIONS | Owner holds 3+ parcels across the dataset |",
        "| MULTIPLE_NEARBY_PARCELS | 2+ parcels in same ZIP code |",
        "| RECENT_PURCHASE_CLUSTERING | 2+ purchases within 90 days |",
        "| VACANT_LAND_CONCENTRATION | Owner holds 2+ vacant parcels |",
        "| INFILL_ACTIVITY | Permits on vacant parcels (infill dev indicator) |",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _profile_section(
    profile: BuyerProfile,
    score_label: str,
    score: int,
) -> List[str]:
    lines = [
        f"### {profile.owner_name}",
        "",
        f"- **{score_label}:** {score}/100",
        f"- **Parcels:** {profile.parcel_count}",
        f"- **ZIP codes:** {', '.join(profile.zip_codes) or 'N/A'}",
        f"- **Total spend:** ${profile.total_spend:,.0f}",
        f"- **Acquisition dates:** {', '.join(profile.acquisition_dates) or 'N/A'}",
        "",
        "**Evidence:**",
        "",
    ]
    for sig in profile.signals:
        lines.append(f"- `{sig.signal_type}` — {sig.evidence}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_all_reports(
    all_profiles: Dict[str, BuyerProfile],
    builders: List[BuyerProfile],
    cash_buyers: List[BuyerProfile],
    quarantined: List[QuarantinedRecord],
    output_dir: Path,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Attach summaries
    for profile in all_profiles.values():
        profile.summary = generate_profile_summary(profile)

    paths = {
        "VERIFIED_BUILDERS": write_verified_builders(builders, output_dir),
        "POSSIBLE_CASH_BUYERS": write_possible_cash_buyers(cash_buyers, output_dir),
        "BUYER_CONFIDENCE_SCORES": write_confidence_scores(all_profiles, quarantined, output_dir),
        "BUYER_ACTIVITY_REPORT": write_activity_report(
            builders, cash_buyers, all_profiles, quarantined, output_dir
        ),
    }
    return paths
