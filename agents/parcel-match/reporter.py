"""
Report generation for the Parcel Match Agent.

Outputs:
  PARCEL_MATCH_REPORT.md   — human-readable opportunity summaries
  TOP_BUYERS.json          — ranked buyer lists per parcel
  BUILDER_MATCHES.json     — builder matches for infill/vacant parcels
  MATCH_CONFIDENCE.json    — full confidence scores for every match
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from models import DispositionPath, Parcel, ParcelMatch, ParcelOpportunity


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _match_to_dict(m: ParcelMatch) -> Dict[str, Any]:
    return {
        "parcel_id": m.parcel_id,
        "buyer_name": m.buyer_name,
        "match_score": m.match_score,
        "match_type": m.match_type,
        "disposition_path": m.disposition_path,
        "summary": m.summary,
        "signal_evidence": m.signal_evidence(),
    }


def _disposition_to_dict(d: DispositionPath) -> Dict[str, Any]:
    return {
        "path_type": d.path_type,
        "confidence": d.confidence,
        "evidence": d.evidence,
        "recommended_buyers": d.recommended_buyers,
    }


def _parcel_to_dict(p: Parcel) -> Dict[str, Any]:
    return {
        "parcel_id": p.parcel_id,
        "address": p.address,
        "city": p.city,
        "state": p.state,
        "zip_code": p.zip_code,
        "land_use": p.land_use,
        "acres": p.acres,
        "zoning": p.zoning,
        "is_vacant": p.is_vacant,
        "effective_price": p.effective_price,
        "sale_price": p.sale_price,
        "asking_price": p.asking_price,
        "arv": p.arv,
        "distressed": p.distressed,
        "days_on_market": p.days_on_market,
        "permit_count": p.permit_count,
        "owner_name": p.owner_name,
    }


def _opp_to_dict(opp: ParcelOpportunity) -> Dict[str, Any]:
    return {
        "parcel": _parcel_to_dict(opp.parcel),
        "best_match_score": opp.best_match_score,
        "summary": opp.summary,
        "primary_disposition": (
            _disposition_to_dict(opp.primary_disposition)
            if opp.primary_disposition else None
        ),
        "disposition_paths": [_disposition_to_dict(d) for d in opp.disposition_paths],
        "top_buyer_matches": [_match_to_dict(m) for m in opp.top_buyer_matches],
        "top_builder_matches": [_match_to_dict(m) for m in opp.top_builder_matches],
    }


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Individual report writers
# ---------------------------------------------------------------------------

def write_top_buyers(opportunities: List[ParcelOpportunity], output_dir: Path) -> Path:
    path = output_dir / "TOP_BUYERS.json"
    records = []
    for opp in opportunities:
        all_matches = opp.top_buyer_matches + opp.top_builder_matches
        if not all_matches:
            continue
        records.append({
            "parcel_id": opp.parcel.parcel_id,
            "address": opp.parcel.address,
            "zip_code": opp.parcel.zip_code,
            "effective_price": opp.parcel.effective_price,
            "ranked_buyers": [_match_to_dict(m) for m in all_matches],
        })
    # Sort parcels by best match score descending
    records.sort(key=lambda r: max((m["match_score"] for m in r["ranked_buyers"]), default=0), reverse=True)
    _write_json(path, {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "parcel_count": len(records),
        "parcels": records,
    })
    return path


def write_builder_matches(opportunities: List[ParcelOpportunity], output_dir: Path) -> Path:
    path = output_dir / "BUILDER_MATCHES.json"
    infill = [
        opp for opp in opportunities
        if opp.top_builder_matches
    ]
    infill.sort(key=lambda o: o.best_match_score, reverse=True)
    _write_json(path, {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "infill_parcel_count": len(infill),
        "parcels": [
            {
                "parcel_id": opp.parcel.parcel_id,
                "address": opp.parcel.address,
                "zip_code": opp.parcel.zip_code,
                "land_use": opp.parcel.land_use,
                "acres": opp.parcel.acres,
                "effective_price": opp.parcel.effective_price,
                "builder_matches": [_match_to_dict(m) for m in opp.top_builder_matches],
                "disposition_paths": [_disposition_to_dict(d) for d in opp.disposition_paths],
            }
            for opp in infill
        ],
    })
    return path


def write_match_confidence(opportunities: List[ParcelOpportunity], output_dir: Path) -> Path:
    path = output_dir / "MATCH_CONFIDENCE.json"
    _write_json(path, {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_parcels": len(opportunities),
        "opportunities": [_opp_to_dict(opp) for opp in sorted(
            opportunities, key=lambda o: o.best_match_score, reverse=True
        )],
    })
    return path


def write_match_report(opportunities: List[ParcelOpportunity], output_dir: Path) -> Path:
    path = output_dir / "PARCEL_MATCH_REPORT.md"

    total = len(opportunities)
    matched = sum(1 for o in opportunities if o.best_match_score > 0)
    builder_opps = sum(1 for o in opportunities if o.top_builder_matches)
    buyer_opps = sum(1 for o in opportunities if o.top_buyer_matches)

    # Disposition summary
    from collections import Counter
    disp_counts: Counter = Counter()
    for opp in opportunities:
        if opp.primary_disposition:
            disp_counts[opp.primary_disposition.path_type] += 1

    lines: List[str] = [
        "# Parcel Match Report",
        "",
        f"_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total parcels analyzed | {total} |",
        f"| Parcels with buyer matches | {buyer_opps} |",
        f"| Parcels with builder matches | {builder_opps} |",
        f"| Parcels with any match | {matched} |",
        f"| Unmatched parcels | {total - matched} |",
        "",
    ]

    if disp_counts:
        lines += [
            "### Disposition Path Breakdown",
            "",
            "| Path | Parcels |",
            "|------|---------|",
        ]
        for path_type, count in disp_counts.most_common():
            lines.append(f"| {path_type} | {count} |")
        lines.append("")

    lines += ["---", "", "## Parcel Opportunities", ""]

    sorted_opps = sorted(opportunities, key=lambda o: o.best_match_score, reverse=True)
    for opp in sorted_opps:
        lines += _opportunity_section(opp)

    lines += [
        "---",
        "",
        "## Disposition Path Reference",
        "",
        "| Path | Description |",
        "|------|-------------|",
        "| INFILL_BUILD | Vacant/lot parcel with nearby builder activity |",
        "| WHOLESALE_TO_INVESTOR | Below-market or distressed — cash buyer target |",
        "| REHAB_FLIP | Distressed with ARV upside — investor rehab candidate |",
        "| HOLD_FOR_DEVELOPMENT | Large acreage, no immediate buyer — hold for later |",
        "| RETAIL_LISTING | Improved residential — standard MLS listing |",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Report section builders
# ---------------------------------------------------------------------------

def _opportunity_section(opp: ParcelOpportunity) -> List[str]:
    p = opp.parcel
    price_str = f"${p.effective_price:,.0f}" if p.effective_price > 0 else "N/A"
    arv_str = f"${p.arv:,.0f}" if p.arv > 0 else "N/A"

    lines = [
        f"### {p.parcel_id} — {p.address or 'Address Unknown'}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| ZIP | {p.zip_code or 'N/A'} |",
        f"| Land Use | {p.land_use or 'N/A'} |",
        f"| Acres | {p.acres:.2f} |",
        f"| Zoning | {p.zoning or 'N/A'} |",
        f"| Price | {price_str} |",
        f"| ARV | {arv_str} |",
        f"| Vacant | {'Yes' if p.is_vacant else 'No'} |",
        f"| Distressed | {'Yes' if p.distressed else 'No'} |",
        f"| Days on Market | {p.days_on_market} |",
        f"| Best Match Score | {opp.best_match_score}/100 |",
        "",
    ]

    if opp.disposition_paths:
        lines.append("**Disposition Paths:**")
        lines.append("")
        for dp in opp.disposition_paths:
            buyers = f" → {', '.join(dp.recommended_buyers[:2])}" if dp.recommended_buyers else ""
            lines.append(f"- `{dp.path_type}` (confidence {dp.confidence}/100){buyers}")
        lines.append("")

    all_matches = opp.top_buyer_matches + opp.top_builder_matches
    all_matches.sort(key=lambda m: m.match_score, reverse=True)

    if all_matches:
        lines.append("**Ranked Buyers / Builders:**")
        lines.append("")
        for m in all_matches[:5]:
            sig_types = ", ".join({s.signal_type for s in m.signals})
            lines.append(
                f"- [{m.match_score}/100] **{m.buyer_name}** ({m.match_type})"
                f" — signals: {sig_types}"
            )
        lines.append("")

        # Show evidence for the top match
        top = all_matches[0]
        lines.append(f"**Top match evidence ({top.buyer_name}):**")
        lines.append("")
        for sig in top.signals:
            lines.append(f"- `{sig.signal_type}` — {sig.evidence}")
        lines.append("")
    else:
        lines.append("_No buyer or builder matches above threshold._")
        lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_all_reports(
    opportunities: List[ParcelOpportunity],
    output_dir: Path,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "PARCEL_MATCH_REPORT": write_match_report(opportunities, output_dir),
        "TOP_BUYERS": write_top_buyers(opportunities, output_dir),
        "BUILDER_MATCHES": write_builder_matches(opportunities, output_dir),
        "MATCH_CONFIDENCE": write_match_confidence(opportunities, output_dir),
    }
