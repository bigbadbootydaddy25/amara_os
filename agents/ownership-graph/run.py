#!/usr/bin/env python3
"""
Ownership Graph Agent

Reads CSV exports of deed/ownership records, builds an entity→property
ownership graph, and writes structured reports.

Usage:
    python3 agents/ownership-graph/run.py --workspace-root /path/to/ai-brain
    python3 agents/ownership-graph/run.py --workspace-root . --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# ENCODING-RESILIENT CSV READER
# ═══════════════════════════════════════════════════════════════════════════════

ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


@dataclass
class FileResult:
    """Outcome of attempting to read one CSV file."""
    path: str
    encoding_used: Optional[str] = None
    rows: list[dict] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None


def read_csv_rows(path: Path) -> FileResult:
    """
    Try to read a CSV file using each encoding in ENCODINGS order.

    Returns a FileResult with:
      - rows populated and encoding_used set on success
      - skipped=True and skip_reason set if all encodings fail or another
        error occurs; does NOT raise.
    """
    for enc in ENCODINGS:
        try:
            with open(path, newline="", encoding=enc, errors="strict") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            return FileResult(path=str(path), encoding_used=enc, rows=rows)
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            return FileResult(
                path=str(path),
                skipped=True,
                skip_reason=f"parse error ({type(exc).__name__}): {exc}",
            )

    return FileResult(
        path=str(path),
        skipped=True,
        skip_reason=f"could not decode with any of: {', '.join(ENCODINGS)}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OwnershipEdge:
    """One deed / ownership record: entity → property."""
    source_file: str
    encoding_used: str
    owner_name: Optional[str]
    owner_entity: Optional[str]
    property_address: Optional[str]
    apn: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    sale_date: Optional[str]
    sale_price: Optional[float]
    deed_type: Optional[str]


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER MAP  (subset focused on ownership fields)
# ═══════════════════════════════════════════════════════════════════════════════

_RAW_MAP: dict[str, str] = {
    # owner / grantee
    "owner":                "owner_name",
    "owner name":           "owner_name",
    "owner_name":           "owner_name",
    "grantee":              "owner_name",
    "grantee name":         "owner_name",
    "grantee_name":         "owner_name",
    "buyer name":           "owner_name",
    "buyer_name":           "owner_name",
    # entity
    "entity":               "owner_entity",
    "entity name":          "owner_entity",
    "entity_name":          "owner_entity",
    "owner entity":         "owner_entity",
    "owner_entity":         "owner_entity",
    "buyer company":        "owner_entity",
    "buyer_company":        "owner_entity",
    # property address
    "property address":     "property_address",
    "property_address":     "property_address",
    "address":              "property_address",
    "situs address":        "property_address",
    "situs_address":        "property_address",
    # apn
    "apn":                  "apn",
    "parcel number":        "apn",
    "parcel_number":        "apn",
    "parcel id":            "apn",
    "parcel_id":            "apn",
    "account number":       "apn",
    "account_number":       "apn",
    # location
    "city":                 "city",
    "property city":        "city",
    "property_city":        "city",
    "state":                "state",
    "property state":       "state",
    "property_state":       "state",
    "zip":                  "zip",
    "zip code":             "zip",
    "zip_code":             "zip",
    "property zip":         "zip",
    "property_zip":         "zip",
    # transaction
    "sale date":            "sale_date",
    "sale_date":            "sale_date",
    "recording date":       "sale_date",
    "recording_date":       "sale_date",
    "deed date":            "sale_date",
    "deed_date":            "sale_date",
    "sale price":           "sale_price",
    "sale_price":           "sale_price",
    "consideration amount": "sale_price",
    "consideration_amount": "sale_price",
    "deed type":            "deed_type",
    "deed_type":            "deed_type",
    "instrument type":      "deed_type",
    "instrument_type":      "deed_type",
}

_ENTITY_RE = re.compile(
    r"\b(LLC|Inc|Corp|LP|LLP|Trust|REIT|Properties|Holdings|Investments|"
    r"Homes|Builders|Development|Capital|Ventures|Partners|Group|Realty|"
    r"Fund|Assets|Acquisitions|Enterprises)\b",
    re.IGNORECASE,
)


def _norm_key(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower())


def _build_col_map(headers: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    seen: set[str] = set()
    for h in headers:
        canon = _RAW_MAP.get(_norm_key(h))
        if canon and canon not in seen:
            result[h] = canon
            seen.add(canon)
    return result


def _to_float(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(re.sub(r"[$,\s]", "", raw))
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

def ingest_csv_dir(raw_dir: Path) -> tuple[list[OwnershipEdge], list[FileResult]]:
    """
    Walk raw_dir, read every .csv, return (edges, skipped_files).
    Non-CSV files and files that fail all encodings are recorded in
    skipped_files without raising.
    """
    edges: list[OwnershipEdge] = []
    skipped: list[FileResult] = []

    if not raw_dir.exists():
        return edges, skipped

    for entry in sorted(raw_dir.iterdir()):
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        if entry.suffix.lower() != ".csv":
            skipped.append(FileResult(
                path=str(entry),
                skipped=True,
                skip_reason=f"not a CSV (suffix: {entry.suffix!r})",
            ))
            continue

        result = read_csv_rows(entry)
        if result.skipped:
            skipped.append(result)
            continue

        col_map = _build_col_map(list(result.rows[0].keys()) if result.rows else [])
        if not col_map:
            skipped.append(FileResult(
                path=str(entry),
                skipped=True,
                skip_reason="no recognised ownership headers",
            ))
            continue

        for row in result.rows:
            canon = {c: v for raw_col, c in col_map.items()
                     if (v := row.get(raw_col, "").strip())}
            owner_name   = canon.get("owner_name")
            owner_entity = canon.get("owner_entity")

            # Promote entity-looking names
            if not owner_entity and owner_name and _ENTITY_RE.search(owner_name):
                owner_entity = owner_name
                owner_name = None

            if not owner_name and not owner_entity:
                continue

            edges.append(OwnershipEdge(
                source_file=str(entry),
                encoding_used=result.encoding_used or "",
                owner_name=owner_name,
                owner_entity=owner_entity,
                property_address=canon.get("property_address"),
                apn=canon.get("apn"),
                city=canon.get("city"),
                state=canon.get("state"),
                zip=canon.get("zip"),
                sale_date=canon.get("sale_date"),
                sale_price=_to_float(canon.get("sale_price")),
                deed_type=canon.get("deed_type"),
            ))

    return edges, skipped


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH BUILD
# ═══════════════════════════════════════════════════════════════════════════════

def _owner_key(edge: OwnershipEdge) -> str:
    raw = edge.owner_entity or edge.owner_name or ""
    return re.sub(r"[^a-z0-9]", "", raw.lower())


def build_graph(edges: list[OwnershipEdge]) -> dict[str, dict]:
    """
    Group edges by owner key.
    Returns {owner_key: {display_name, properties: [...], ...}}.
    """
    groups: dict[str, list[OwnershipEdge]] = {}
    for e in edges:
        k = _owner_key(e)
        if k:
            groups.setdefault(k, []).append(e)

    graph: dict[str, dict] = {}
    for key, grp in groups.items():
        entities = [e.owner_entity for e in grp if e.owner_entity]
        names    = [e.owner_name   for e in grp if e.owner_name]
        display  = (max(set(entities), key=entities.count) if entities
                    else max(set(names), key=names.count) if names else key)
        prices   = [e.sale_price for e in grp if e.sale_price is not None]
        encodings_used = sorted({e.encoding_used for e in grp if e.encoding_used})

        graph[key] = {
            "owner_key":       key,
            "display_name":    display,
            "entity_name":     max(set(entities), key=entities.count) if entities else None,
            "individual_name": max(set(names),    key=names.count)    if names    else None,
            "property_count":  len(grp),
            "properties": [
                {
                    "address":    e.property_address,
                    "apn":        e.apn,
                    "city":       e.city,
                    "state":      e.state,
                    "zip":        e.zip,
                    "sale_date":  e.sale_date,
                    "sale_price": e.sale_price,
                    "deed_type":  e.deed_type,
                    "source_file": Path(e.source_file).name,
                }
                for e in grp
            ],
            "price_min":       min(prices) if prices else None,
            "price_max":       max(prices) if prices else None,
            "price_avg":       round(sum(prices) / len(prices), 2) if prices else None,
            "source_files":    sorted({Path(e.source_file).name for e in grp}),
            "encodings_used":  encodings_used,
        }

    return graph


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT WRITERS
# ═══════════════════════════════════════════════════════════════════════════════

def write_reports(
    graph: dict[str, dict],
    skipped: list[FileResult],
    file_results: list[FileResult],
    reports_dir: Path,
    workspace_root: Path,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    _write_ownership_graph_json(graph, skipped, file_results, reports_dir, ts)
    _write_ownership_graph_md(graph, skipped, file_results, reports_dir, ts, workspace_root)


def _write_ownership_graph_json(
    graph: dict[str, dict],
    skipped: list[FileResult],
    file_results: list[FileResult],
    reports_dir: Path,
    ts: str,
) -> None:
    payload = {
        "run_timestamp": ts,
        "owner_count":   len(graph),
        "edge_count":    sum(v["property_count"] for v in graph.values()),
        "owners":        sorted(graph.values(), key=lambda v: v["property_count"], reverse=True),
        "skipped_files": [
            {"file": Path(r.path).name, "reason": r.skip_reason}
            for r in skipped
        ],
        "encoding_used": [
            {"file": Path(r.path).name, "encoding": r.encoding_used}
            for r in file_results
            if not r.skipped
        ],
    }
    (reports_dir / "OWNERSHIP_GRAPH.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def _write_ownership_graph_md(
    graph: dict[str, dict],
    skipped: list[FileResult],
    file_results: list[FileResult],
    reports_dir: Path,
    ts: str,
    workspace_root: Path,
) -> None:
    owners = sorted(graph.values(), key=lambda v: v["property_count"], reverse=True)
    lines = [
        "# OWNERSHIP_GRAPH",
        "",
        f"_Generated: {ts}_",
        f"_Owners: {len(owners)}  |  Total properties: {sum(v['property_count'] for v in owners)}_",
        "",
    ]

    # Skipped files section
    lines += ["## Skipped Files", ""]
    if skipped:
        lines += ["| File | Reason |", "|---|---|"]
        for r in skipped:
            try:
                display = Path(r.path).relative_to(workspace_root)
            except ValueError:
                display = Path(r.path).name
            lines.append(f"| `{display}` | {r.skip_reason} |")
    else:
        lines.append("> No files skipped.")
    lines.append("")

    # Encoding used section
    lines += ["## Encoding Used Per File", ""]
    readable = [r for r in file_results if not r.skipped]
    if readable:
        lines += ["| File | Encoding |", "|---|---|"]
        for r in readable:
            lines.append(f"| `{Path(r.path).name}` | `{r.encoding_used}` |")
    else:
        lines.append("> No files successfully read.")
    lines.append("")

    # Owner graph
    lines += ["## Owner Graph", ""]
    for owner in owners:
        lines += [
            f"### {owner['display_name']}",
            "",
            f"- **Properties**: {owner['property_count']}",
            f"- **Source files**: {', '.join(owner['source_files'])}",
            f"- **Encodings**: {', '.join(owner['encodings_used'])}",
        ]
        if owner["price_avg"] is not None:
            lines.append(
                f"- **Price range**: ${owner['price_min']:,.0f} – ${owner['price_max']:,.0f}"
                f"  (avg ${owner['price_avg']:,.0f})"
            )
        lines.append("")

    (reports_dir / "OWNERSHIP_GRAPH.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ownership Graph — reads CSV ownership records, builds entity→property graph"
    )
    parser.add_argument("--workspace-root", default=".",
                        help="Workspace root (default: current directory)")
    parser.add_argument("--raw-dir", default=None,
                        help="Override CSV input directory")
    parser.add_argument("--reports-dir", default=None,
                        help="Override reports output directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without writing files")
    args = parser.parse_args(argv)

    workspace   = Path(args.workspace_root).expanduser().resolve()
    raw_dir     = (Path(args.raw_dir).resolve() if args.raw_dir
                   else workspace / "data" / "ownership" / "raw")
    reports_dir = (Path(args.reports_dir).resolve() if args.reports_dir
                   else Path(__file__).parent / "reports")

    print(f"\n{'━'*26}\n  ownership-graph\n{'━'*26}\n")
    print(f"  workspace: {workspace}")
    print(f"  raw dir:   {raw_dir}")

    edges, skipped = ingest_csv_dir(raw_dir)

    # Collect per-file results for reporting
    file_results: list[FileResult] = []
    if raw_dir.exists():
        for entry in sorted(raw_dir.iterdir()):
            if entry.suffix.lower() == ".csv" and not entry.name.startswith((".", "_")):
                result = read_csv_rows(entry)
                if not result.skipped:
                    file_results.append(result)

    graph = build_graph(edges)

    print(f"  CSVs read: {len(file_results)}")
    print(f"  Edges:     {len(edges)}")
    print(f"  Owners:    {len(graph)}")
    print(f"  Skipped:   {len(skipped)}")

    if skipped:
        print("\n── Skipped files")
        for r in skipped:
            print(f"  {Path(r.path).name:<40} {r.skip_reason}")

    if not args.dry_run:
        write_reports(graph, skipped, file_results, reports_dir, workspace)
        print(f"\nReports written to: {reports_dir}/")
        print(f"  • OWNERSHIP_GRAPH.json")
        print(f"  • OWNERSHIP_GRAPH.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
