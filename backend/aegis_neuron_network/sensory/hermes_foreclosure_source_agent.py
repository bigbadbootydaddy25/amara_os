"""Hermes Foreclosure Source Agent — checks AMARA_BRAIN for foreclosure source outputs."""
from datetime import datetime, timezone
from typing import Dict

from ..config import AMARA_BRAIN_AEGIS_ROOT, OPENCLAW_TASKS_DIR, SOURCE_LOGS_DIR
from ..events import make_event
from ..event_store import append_event

# Patterns that indicate a foreclosure source output file
FORECLOSURE_SOURCE_PATTERNS = [
    "foreclosure",
    "tax_sale",
    "hcad",
    "harris_county",
    "strike_board",
    "tax_deed",
]


class HermesForeclosureSourceAgent:
    """
    Checks AMARA_BRAIN for any foreclosure source output files.
    If found but not parsed into lead rows, marks SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED
    and creates a parser task file.
    """

    def run(self) -> Dict:
        found_sources = []
        parsed_sources = []

        # Search through AMARA_BRAIN_AEGIS_ROOT for foreclosure-related files
        if AMARA_BRAIN_AEGIS_ROOT.exists():
            for candidate in AMARA_BRAIN_AEGIS_ROOT.rglob("*"):
                if not candidate.is_file():
                    continue
                fname_lower = candidate.name.lower()
                if any(pattern in fname_lower for pattern in FORECLOSURE_SOURCE_PATTERNS):
                    file_info = {
                        "path": str(candidate),
                        "name": candidate.name,
                        "size_bytes": candidate.stat().st_size,
                    }
                    # Determine if this file has been deeply parsed into lead rows
                    # (heuristic: if it's a CSV with >1 row, it may have lead data)
                    if candidate.suffix.lower() == ".csv":
                        try:
                            lines = candidate.read_text(encoding="utf-8").splitlines()
                            row_count = max(0, len(lines) - 1)  # subtract header
                            file_info["row_count"] = row_count
                            if row_count > 0:
                                parsed_sources.append(file_info)
                            else:
                                file_info["parse_status"] = "SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED"
                                found_sources.append(file_info)
                        except Exception:
                            file_info["parse_status"] = "SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED"
                            found_sources.append(file_info)
                    else:
                        # Markdown/text: not extractable as rows
                        file_info["parse_status"] = "SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED"
                        found_sources.append(file_info)

        # Also check SOURCE_LOGS_DIR specifically
        if SOURCE_LOGS_DIR.exists():
            for candidate in SOURCE_LOGS_DIR.iterdir():
                if candidate.is_file():
                    already_noted = any(
                        s["path"] == str(candidate) for s in found_sources + parsed_sources
                    )
                    if not already_noted:
                        found_sources.append({
                            "path": str(candidate),
                            "name": candidate.name,
                            "size_bytes": candidate.stat().st_size,
                            "parse_status": "SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED",
                        })

        # Write parser task file
        task_file_path = OPENCLAW_TASKS_DIR / "foreclosure_source_parser_tasks.md"
        OPENCLAW_TASKS_DIR.mkdir(parents=True, exist_ok=True)

        task_content = f"""# Foreclosure Source Parser Tasks
Generated: {datetime.now(timezone.utc).isoformat()}
Status: SOURCE_NEEDED

## Summary
- Source files found (not yet parsed into lead rows): {len(found_sources)}
- Source files with extracted lead rows: {len(parsed_sources)}

## Files Found But Not Parsed
"""
        if found_sources:
            for src in found_sources:
                task_content += f"\n### {src['name']}\n"
                task_content += f"- Path: {src['path']}\n"
                task_content += f"- Size: {src.get('size_bytes', 'unknown')} bytes\n"
                task_content += f"- Parse Status: {src.get('parse_status', 'SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED')}\n"
                task_content += "- Required Action: Extract lead rows, verify property addresses, verify tax account numbers\n"
        else:
            task_content += "\nNo foreclosure source files found in AMARA_BRAIN.\n"

        task_content += """
## Files With Extracted Lead Rows
"""
        if parsed_sources:
            for src in parsed_sources:
                task_content += f"\n### {src['name']}\n"
                task_content += f"- Path: {src['path']}\n"
                task_content += f"- Lead Rows: {src.get('row_count', 'unknown')}\n"
                task_content += "- Required Action: Validate each lead row against HCAD and Harris County tax sale records\n"
        else:
            task_content += "\nNo fully parsed foreclosure source files found.\n"

        task_content += """
## Required Next Steps
1. Run OpenClaw to scrape Harris County tax sale list
2. Run OpenClaw to check HCAD for each identified property
3. Verify tax account numbers match property addresses
4. Do NOT create lead rows from unverified addresses
5. Do NOT call any property a tax sale opportunity without source confirmation
6. Screenshots and source URLs required for all data

## Verification Status
SOURCE_NEEDED — No confirmed foreclosure source data in AMARA_BRAIN yet
"""
        task_file_path.write_text(task_content, encoding="utf-8")

        ev = make_event(
            event_type="OPENCLAW_TASKS_CREATED",
            source="HermesForeclosureSourceAgent",
            payload={
                "found_sources_count": len(found_sources),
                "parsed_sources_count": len(parsed_sources),
                "task_file": str(task_file_path),
                "parse_status": (
                    "SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED"
                    if found_sources
                    else "NO_FORECLOSURE_SOURCES_FOUND"
                ),
            },
            source_file=str(task_file_path),
            verification_status="SOURCE_NEEDED",
            status="PENDING",
            notes="Foreclosure sources require OpenClaw verification before lead rows can be extracted.",
        )
        append_event(ev)

        return {
            "agent": "HermesForeclosureSourceAgent",
            "status": "COMPLETED",
            "found_sources": found_sources,
            "parsed_sources": parsed_sources,
            "task_file": str(task_file_path),
            "parse_status": (
                "SOURCE_FOUND_BUT_NO_LEAD_ROWS_EXTRACTED"
                if found_sources
                else "NO_FORECLOSURE_SOURCES_FOUND"
            ),
        }
