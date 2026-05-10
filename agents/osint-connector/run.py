from __future__ import annotations

"""OSINT enrichment connector. Evidence-first: every field carries full provenance."""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_USE = "lawful_osint_only"

_NOT_FOUND = "Not found in provided manual exports or cache."

# ── Provenance helpers ────────────────────────────────────────────────────────

def provenance(
    value: Any,
    source_type: str,
    source_name: str,
    source_path: str,
    collected_at: str,
    confidence: str,
) -> dict:
    return {
        "value": value,
        "source_type": source_type,
        "source_name": source_name,
        "source_path_or_url": source_path,
        "collected_at": collected_at,
        "confidence": confidence,
        "allowed_use": ALLOWED_USE,
    }


def missing(collected_at: str) -> dict:
    return provenance(None, "missing", "", "", collected_at, "none")


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _load_csv(path: Path) -> list[dict]:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Entity enrichment ─────────────────────────────────────────────────────────

def _enrich_entity_from_distress(record: dict, source_path: str, ts: str) -> dict:
    def src(v: Any, conf: str) -> dict:
        return provenance(v, "internal_record", "DISTRESSED_PORTFOLIOS.json", source_path, ts, conf)

    return {
        "entity_id": record["id"],
        "name": src(record.get("owner"), "high"),
        "entity_type": src(record.get("entity_type"), "high"),
        "sos_status": missing(ts),
        "registered_agent": missing(ts),
        "associated_addresses": missing(ts),
        "portfolio_count": src(len(record.get("properties", [])), "high"),
        "estimated_equity": missing(ts),
        "loan_balance": missing(ts),
        "distress_score": src(record.get("distress_score"), "high"),
        "distress_indicators": src(record.get("distress_indicators", {}), "high"),
        "motivation_signals": src(record.get("motivation_signals", []), "high"),
        "source_evidence": src(record.get("source_evidence", []), "high"),
    }


def _enrich_entity_from_buyer(record: dict, source_path: str, ts: str) -> dict:
    def src(v: Any, conf: str) -> dict:
        return provenance(v, "internal_record", "OVERLEVERAGED_BUYERS.json", source_path, ts, conf)

    return {
        "entity_id": record["id"],
        "name": src(record.get("name"), "high"),
        "entity_type": src(record.get("buyer_type"), "high"),
        "sos_status": missing(ts),
        "registered_agent": missing(ts),
        "associated_addresses": missing(ts),
        "portfolio_count": missing(ts),
        "estimated_equity": missing(ts),
        "loan_balance": missing(ts),
        "distress_score": missing(ts),
        "leverage_score": src(record.get("leverage_score"), "high"),
        "dispo_priority": src(record.get("dispo_priority"), "high"),
        "leverage_indicators": src(record.get("leverage_indicators", {}), "high"),
        "acquisition_posture": src(record.get("acquisition_posture", {}), "high"),
        "risk_flags": src(record.get("risk_flags", []), "high"),
        "source_evidence": src(record.get("source_evidence", []), "high"),
    }


def _enrich_entity_from_builder(record: dict, source_path: str, ts: str) -> dict:
    def src(v: Any, conf: str) -> dict:
        return provenance(v, "internal_record", "STALLED_BUILDERS.json", source_path, ts, conf)

    return {
        "entity_id": record["id"],
        "name": src(record.get("name"), "high"),
        "entity_type": src(record.get("builder_type"), "high"),
        "sos_status": missing(ts),
        "registered_agent": missing(ts),
        "associated_addresses": missing(ts),
        "portfolio_count": missing(ts),
        "estimated_equity": missing(ts),
        "loan_balance": missing(ts),
        "distress_score": src(record.get("stall_score"), "high"),
        "role_classification": src(record.get("role_classification"), "high"),
        "buyer_disqualification_reason": src(record.get("buyer_disqualification_reason"), "high"),
        "financial_distress": src(record.get("financial_distress", {}), "high"),
        "stalled_projects": src(record.get("stalled_projects", []), "high"),
        "motivation_signals": src(record.get("motivation_signals", []), "high"),
        "source_evidence": src(record.get("source_evidence", []), "high"),
    }


# ── Property enrichment ───────────────────────────────────────────────────────

def _enrich_property_from_lot(row: dict, source_path: str, ts: str) -> dict:
    def src(v: Any, conf: str) -> dict:
        return provenance(v, "broker_lead", "infill_lots_dallas.csv", source_path, ts, conf)

    address = row.get("Address", "")
    property_id = address.lower().replace(" ", "_").replace(",", "").replace(".", "")

    return {
        "property_id": property_id,
        "address": src(address, "high"),
        "owner_name": missing(ts),
        "assessed_value": missing(ts),
        "last_sale_price": src(row.get("Price"), "medium"),
        "last_sale_date": missing(ts),
        "liens_recorded": missing(ts),
        "permit_activity": missing(ts),
        "zoning_classification": missing(ts),
        "lot_size_acres": src(row.get("Size (Acres)"), "high"),
        "broker_details": src(row.get("Details"), "high"),
        "contact_info": src(row.get("Contact Information"), "medium"),
    }


# ── Queue logic ───────────────────────────────────────────────────────────────

def _collect_missing_fields(record: dict) -> list[str]:
    return [
        key for key, val in record.items()
        if isinstance(val, dict) and val.get("source_type") == "missing"
    ]


def _queue_entry(entity_id: str, entity_type: str, missing_fields: list[str], ts: str) -> dict:
    n = len(missing_fields)
    priority = "high" if n >= 5 else "medium" if n >= 2 else "low"
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "queued_at": ts,
        "missing_fields": missing_fields,
        "priority": priority,
        "allowed_use": ALLOWED_USE,
    }


# ── Compliance audit ──────────────────────────────────────────────────────────

def write_compliance_audit(
    entities: list[dict],
    properties: list[dict],
    queue: list[dict],
    run_ts: datetime,
    report_dir: Path,
) -> Path:
    ts_str = run_ts.strftime("%Y%m%dT%H%M%SZ")
    out = report_dir / ts_str / "OSINT_COMPLIANCE_AUDIT.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    all_records = entities + properties
    provenance_fields = [
        val
        for r in all_records
        for val in r.values()
        if isinstance(val, dict) and "source_type" in val
    ]
    total = len(provenance_fields)
    missing_count = sum(1 for v in provenance_fields if v["source_type"] == "missing")
    filled = total - missing_count
    fill_pct = round(filled / total * 100) if total else 0

    source_type_counts: dict[str, int] = {}
    for v in provenance_fields:
        st = v["source_type"]
        source_type_counts[st] = source_type_counts.get(st, 0) + 1

    lines = [
        "# OSINT Compliance Audit",
        "",
        f"**Run:** `{ts_str}`  ",
        f"**Allowed use:** `{ALLOWED_USE}`  ",
        "**Sources:** public records, broker leads, internal manual exports",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Enriched entities | {len(entities)} |",
        f"| Enriched properties | {len(properties)} |",
        f"| Queued for enrichment | {len(queue)} |",
        f"| Total provenance fields | {total} |",
        f"| Fields with source | {filled} |",
        f"| Fields missing source | {missing_count} |",
        f"| Fill rate | {fill_pct}% |",
        "",
        "---",
        "",
        "## Source Type Breakdown",
        "",
        "| source_type | field_count |",
        "|-------------|-------------|",
    ]
    for st, count in sorted(source_type_counts.items()):
        lines.append(f"| `{st}` | {count} |")

    lines += [
        "",
        "---",
        "",
        "## Compliance Notes",
        "",
        "- All values carry `allowed_use: lawful_osint_only`",
        "- No fabricated values — missing data is marked `source_type: missing`",
        "- Internal records sourced from `data/portfolio-distress/` manual exports",
        "- Broker leads sourced from `data/deal-leads/raw/`",
        "- Public record fields (SOS, assessed value, liens, registered agent) require",
        "  external integration and are queued with `source_type: missing`",
        "",
        "---",
        "",
        "## Enrichment Queue",
        "",
        "| entity_id | type | missing_fields | priority |",
        "|-----------|------|----------------|----------|",
    ]
    for q in queue:
        shown = q["missing_fields"][:3]
        suffix = f" +{len(q['missing_fields']) - 3} more" if len(q["missing_fields"]) > 3 else ""
        lines.append(
            f"| `{q['entity_id']}` | {q['entity_type']} | {', '.join(shown)}{suffix} | {q['priority']} |"
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run(workspace_root: Path) -> None:
    run_ts = datetime.now(timezone.utc)
    ts = run_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    data_dir = workspace_root / "data"
    enriched_dir = data_dir / "osint" / "enriched"

    print("=" * 64)
    print("  AI_BRAIN OSINT CONNECTOR")
    print(f"  workspace: {workspace_root}")
    print("=" * 64)

    # ── Load sources ──────────────────────────────────────────────────────────

    print("\n[ 1 / 4 ] Loading sources ...")

    distress_path = data_dir / "portfolio-distress" / "DISTRESSED_PORTFOLIOS.json"
    buyers_path   = data_dir / "portfolio-distress" / "OVERLEVERAGED_BUYERS.json"
    builders_path = data_dir / "portfolio-distress" / "STALLED_BUILDERS.json"
    lots_path     = data_dir / "deal-leads" / "raw" / "infill_lots_dallas.csv"

    distress_data = (_load_json(distress_path) or {}).get("portfolios", [])
    buyers_data   = (_load_json(buyers_path)   or {}).get("buyers", [])
    builders_data = (_load_json(builders_path) or {}).get("builders", [])
    lots_rows     = _load_csv(lots_path)

    print(f"  distressed portfolios: {len(distress_data)}")
    print(f"  overleveraged buyers:  {len(buyers_data)}")
    print(f"  stalled builders:      {len(builders_data)}")
    print(f"  infill lots:           {len(lots_rows)}")

    # ── Enrich entities ───────────────────────────────────────────────────────

    print("\n[ 2 / 4 ] Enriching entities ...")

    entities: list[dict] = []
    for record in distress_data:
        entities.append(_enrich_entity_from_distress(record, str(distress_path), ts))
    for record in buyers_data:
        entities.append(_enrich_entity_from_buyer(record, str(buyers_path), ts))
    for record in builders_data:
        entities.append(_enrich_entity_from_builder(record, str(builders_path), ts))

    print(f"  {len(entities)} entities enriched")

    # ── Enrich properties ─────────────────────────────────────────────────────

    print("\n[ 3 / 4 ] Enriching properties ...")

    properties: list[dict] = [
        _enrich_property_from_lot(row, str(lots_path), ts)
        for row in lots_rows
    ]

    print(f"  {len(properties)} properties enriched")

    # ── Build queue ───────────────────────────────────────────────────────────

    queue: list[dict] = []
    for rec in entities:
        mf = _collect_missing_fields(rec)
        if mf:
            queue.append(_queue_entry(rec["entity_id"], "entity", mf, ts))
    for rec in properties:
        mf = _collect_missing_fields(rec)
        if mf:
            queue.append(_queue_entry(rec["property_id"], "property", mf, ts))

    # ── Write outputs ─────────────────────────────────────────────────────────

    print("\n[ 4 / 4 ] Writing outputs ...")

    _write_json(enriched_dir / "OSINT_ENRICHED_ENTITIES.json", entities)
    print(f"  {enriched_dir / 'OSINT_ENRICHED_ENTITIES.json'}")

    _write_json(enriched_dir / "OSINT_ENRICHED_PROPERTIES.json", properties)
    print(f"  {enriched_dir / 'OSINT_ENRICHED_PROPERTIES.json'}")

    _write_json(enriched_dir / "OSINT_TO_ENRICHMENT_QUEUE.json", queue)
    print(f"  {enriched_dir / 'OSINT_TO_ENRICHMENT_QUEUE.json'}")

    report_dir = workspace_root / "agents" / "osint-connector" / "reports"
    audit_path = write_compliance_audit(entities, properties, queue, run_ts, report_dir)
    print(f"  {audit_path}")

    all_prov = [
        val
        for r in entities + properties
        for val in r.values()
        if isinstance(val, dict) and "source_type" in val
    ]
    total = len(all_prov)
    missing_n = sum(1 for v in all_prov if v["source_type"] == "missing")
    fill_pct = round((total - missing_n) / total * 100) if total else 0

    print("")
    print("=" * 64)
    print(f"  Entities enriched:   {len(entities)}")
    print(f"  Properties enriched: {len(properties)}")
    print(f"  Queued for OSINT:    {len(queue)}")
    print(f"  Fill rate:           {fill_pct}%")
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI_BRAIN OSINT Connector")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Absolute path to the ai-brain workspace root",
    )
    args = parser.parse_args()
    run(Path(args.workspace_root))


if __name__ == "__main__":
    main()
