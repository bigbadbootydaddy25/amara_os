#!/usr/bin/env python3
"""
OSINT Intelligence Layer – Orchestrator
Usage:
    python3 agents/osint-intelligence/run.py --workspace-root /path/to/ai-brain
    python3 agents/osint-intelligence/run.py --workspace-root . --dry-run
    python3 agents/osint-intelligence/run.py --workspace-root . --subjects "Webb Capital Holdings LLC"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Resolve imports whether run directly or from workspace root
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from source_discovery import (   # noqa: E402
    OSINT_SOURCES,
    write_source_index,
    get_priority1_sources,
    get_free_sources,
)
from entity_research import (    # noqa: E402
    build_entity_research_from_names,
    write_verified_entities,
    write_entity_research_packets,
    is_entity_name,
    detect_entity_type,
)
from record_research import (    # noqa: E402
    build_all_targets_for_subject,
    write_record_source_targets,
    write_agent_routing,
)


# ---------------------------------------------------------------------------
# Seed loader (reads buyers/BUY-*.md from workspace)
# ---------------------------------------------------------------------------

_ENTITY_LINE = re.compile(
    r"(?:entity|company|organization|firm|buyer entity)\s*[:\-]\s*(.+)",
    re.I,
)
_NAME_LINE = re.compile(r"(?:name|buyer name|full name)\s*[:\-]\s*(.+)", re.I)


def load_entity_names_from_seeds(buyers_dir: Path) -> list[str]:
    """Parse buyers/BUY-*.md files and extract entity / buyer names."""
    names: list[str] = []
    for md in sorted(buyers_dir.glob("BUY-*.md")):
        text = md.read_text(errors="replace")
        for line in text.splitlines():
            for pattern in (_ENTITY_LINE, _NAME_LINE):
                m = pattern.match(line.strip())
                if m:
                    val = m.group(1).strip()
                    if val and val not in names:
                        names.append(val)
    return names


def load_entity_names_from_csv_reports(reports_dir: Path) -> list[str]:
    """
    Pull entity names from an existing BUYER_ACTIVITY_PROFILES report JSON
    if it exists in the workspace reports directory.
    """
    names: list[str] = []
    profile_json = reports_dir / "ACTIVITY_SUMMARY.json"
    if not profile_json.exists():
        return names
    try:
        data = json.loads(profile_json.read_text())
        for profile in data.get("profiles", []):
            entity = profile.get("buyer_entity", "")
            name = profile.get("buyer_name", "")
            if entity and entity not in names:
                names.append(entity)
            elif name and name not in names:
                names.append(name)
    except Exception:
        pass
    return names


# ---------------------------------------------------------------------------
# Risk & compliance writer
# ---------------------------------------------------------------------------

def write_risk_and_compliance(reports_dir: Path, subjects: list[str]) -> None:
    lines = [
        "# OSINT Risk and Compliance",
        "",
        f"**Generated:** {date.today().isoformat()}",
        "",
        "## Methodology",
        "",
        "All sources used in this OSINT layer are lawful, public-record sources.",
        "No web scraping, credential bypassing, or unauthorized access was performed.",
        "Every claim in this report is backed by a source URL in the citation field.",
        "",
        "## Data Sources Used",
        "",
        f"- Total sources cataloged: {len(OSINT_SOURCES)}",
        f"- Priority-1 (Dallas/Texas) sources: {len(get_priority1_sources())}",
        f"- Free/open sources: {len(get_free_sources())}",
        "",
        "## Subjects Researched",
        "",
    ]
    for s in subjects:
        lines.append(f"- {s}")
    lines += [
        "",
        "## Compliance Notes",
        "",
        "1. **Public Records Only** — All data obtained from official government portals,",
        "   court records, and public registries.",
        "2. **No PII Beyond Public Record** — We do not use skip-tracing or data brokers",
        "   for personal contact information.",
        "3. **Login-Required Sources** — Flagged but NOT accessed automatically.",
        "   Human review required for login-gated records.",
        "4. **Paid Sources** — Listed for reference only; not automatically queried.",
        "5. **Citation Requirement** — Every entity claim, record target, and finding",
        "   must carry a source URL. Remove any claim that lacks a citation.",
        "6. **Texas Open Records Act (TORA)** — Records obtainable via formal request",
        "   to county/city agencies under Texas Government Code Ch. 552.",
        "",
        "## Limitations",
        "",
        "- SOS and franchise-tax status reflects last manual verification date.",
        "- Deed and lien data may lag county recorder by 24–72 hours.",
        "- Permit and code-violation portals may not reflect real-time status.",
        "- MLS data requires broker membership and is not included in free sources.",
        "",
    ]
    (reports_dir / "OSINT_RISK_AND_COMPLIANCE.md").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OSINT Intelligence Layer — lawful public-record research for real estate"
    )
    parser.add_argument(
        "--workspace-root", default=".", metavar="PATH",
        help="Root of the workspace (default: current directory)",
    )
    parser.add_argument(
        "--reports-dir", metavar="PATH",
        help="Override reports output directory",
    )
    parser.add_argument(
        "--buyers-dir", metavar="PATH",
        help="Override buyers seed directory",
    )
    parser.add_argument(
        "--activity-reports-dir", metavar="PATH",
        help="Directory containing ACTIVITY_SUMMARY.json from buyer-activity-osint",
    )
    parser.add_argument(
        "--subjects", nargs="*", metavar="NAME",
        help="Additional entity/property subjects to research (space-separated)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be written without writing files",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output summary as JSON to stdout",
    )
    parser.add_argument(
        "--county", default="Dallas County",
        help="Default county for record lookups (default: Dallas County)",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace_root).resolve()
    reports_dir = Path(args.reports_dir) if args.reports_dir else _HERE / "reports"
    buyers_dir = Path(args.buyers_dir) if args.buyers_dir else workspace / "buyers"
    activity_reports_dir = (
        Path(args.activity_reports_dir)
        if args.activity_reports_dir
        else workspace / "agents" / "buyer-activity-osint" / "reports"
    )

    # ── Collect subject names ──────────────────────────────────────────────
    subjects: list[str] = list(args.subjects or [])

    if buyers_dir.is_dir():
        seed_names = load_entity_names_from_seeds(buyers_dir)
        for n in seed_names:
            if n not in subjects:
                subjects.append(n)

    if activity_reports_dir.is_dir():
        csv_names = load_entity_names_from_csv_reports(activity_reports_dir)
        for n in csv_names:
            if n not in subjects:
                subjects.append(n)

    entity_subjects = [s for s in subjects if is_entity_name(s)]
    property_subjects = [s for s in subjects if not is_entity_name(s)]

    if not args.json:
        print(f"OSINT Intelligence Layer")
        print(f"  Workspace:        {workspace}")
        print(f"  Reports dir:      {reports_dir}")
        print(f"  Total subjects:   {len(subjects)}")
        print(f"    Entities:       {len(entity_subjects)}")
        print(f"    Properties:     {len(property_subjects)}")
        print(f"  OSINT sources:    {len(OSINT_SOURCES)}")

    if args.dry_run:
        print("\n[dry-run] Would write:")
        for fname in [
            "OSINT_SOURCE_INDEX.json",
            "OSINT_SOURCE_INDEX.md",
            "VERIFIED_ENTITIES.json",
            "ENTITY_RESEARCH_PACKETS.md",
            "RECORD_SOURCE_TARGETS.json",
            "OSINT_TO_AGENT_ROUTING.json",
            "OSINT_RISK_AND_COMPLIANCE.md",
        ]:
            print(f"  {reports_dir / fname}")
        return 0

    # ── Run research ───────────────────────────────────────────────────────
    entity_packets = build_entity_research_from_names(entity_subjects)

    all_targets = []
    for entity in entity_subjects:
        all_targets += build_all_targets_for_subject(entity, "entity", args.county)
    for prop in property_subjects:
        all_targets += build_all_targets_for_subject(prop, "property", args.county)

    # ── Write all reports ──────────────────────────────────────────────────
    write_source_index(reports_dir)
    write_verified_entities(entity_packets, reports_dir)
    write_entity_research_packets(entity_packets, reports_dir)
    write_record_source_targets(all_targets, reports_dir)
    write_agent_routing(all_targets, reports_dir)
    write_risk_and_compliance(reports_dir, subjects)

    # ── Summary ───────────────────────────────────────────────────────────
    summary = {
        "generated": date.today().isoformat(),
        "workspace": str(workspace),
        "subjects_researched": len(subjects),
        "entity_subjects": len(entity_subjects),
        "property_subjects": len(property_subjects),
        "osint_sources_cataloged": len(OSINT_SOURCES),
        "entity_packets": len(entity_packets),
        "record_targets": len(all_targets),
        "reports_written": [
            "OSINT_SOURCE_INDEX.json",
            "OSINT_SOURCE_INDEX.md",
            "VERIFIED_ENTITIES.json",
            "ENTITY_RESEARCH_PACKETS.md",
            "RECORD_SOURCE_TARGETS.json",
            "OSINT_TO_AGENT_ROUTING.json",
            "OSINT_RISK_AND_COMPLIANCE.md",
        ],
        "reports_dir": str(reports_dir),
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"\nReports written to: {reports_dir}")
        print(f"  entity_packets:   {len(entity_packets)}")
        print(f"  record_targets:   {len(all_targets)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
