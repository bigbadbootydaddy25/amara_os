"""OpenClaw Task Writer — writes structured OpenClaw verification tasks for each property."""
from datetime import datetime, timezone
from typing import Dict, List

from ..config import OPENCLAW_TASKS_DIR
from ..events import make_event
from ..event_store import append_event

STANDARD_TASKS = [
    "Verify HCAD record — confirm property address, tax account number, owner of record (screenshot required)",
    "Verify Harris County tax sale status — confirm property is listed, listing date, and sale date (source URL required)",
    "Verify owner of record — cross-reference HCAD deed records with any user-provided owner name",
    "Verify tax payoff contact — obtain Harris County Tax Office contact for official payoff request",
    "Verify sale date — confirm auction/sale date from official Harris County Tax Office calendar",
    "Verify deed, mortgage, and lien history — pull Harris County records for all recorded encumbrances",
]

SPECIAL_TASKS = {
    "800 tidwell": [
        "Environmental risk verification — prior auto use at 800 Tidwell Rd. Check for underground storage tanks, "
        "hazmat records, or prior environmental violations via TCEQ and EPA public databases. "
        "Screenshot required. Do NOT estimate — source only.",
    ],
    "1307 prairie": [
        "Bendanmar Limited entity/control verification — confirm registered agent, current good standing "
        "(Texas Secretary of State), authorized signatory, and whether entity has capacity to convey. "
        "Screenshot of SOS record required.",
    ],
    "415 caroline": [
        "Bendanmar Limited entity/control verification — same as 1307 Prairie St. Confirm this property "
        "is part of the same entity and same authorized signatory can convey both.",
    ],
}

BUYER_VERIFICATION_TASKS = [
    "Verify buyer target official sites — confirm each buyer target's official website, contact page, "
    "and acquisition criteria (no third-party sources — official site only)",
    "Verify recent purchases by buyer targets — search Harris County deed records for recent acquisitions "
    "by each buyer target (screenshots required, source URL required)",
    "Do NOT bypass CAPTCHA or automated login protections",
    "Do NOT scrape private buyer databases — public records only",
]


class OpenClawTaskWriter:
    """
    Writes structured OpenClaw verification tasks for all strike board properties.
    """

    def run(self, strike_board: List[Dict]) -> str:
        OPENCLAW_TASKS_DIR.mkdir(parents=True, exist_ok=True)
        task_file_path = OPENCLAW_TASKS_DIR / "houston_tax_sale_tasks.md"

        lines = [
            "# Houston Tax Sale — OpenClaw Verification Tasks",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Rules for All OpenClaw Tasks",
            "- Screenshots required for every data point",
            "- Source URLs required for every data point",
            "- Do NOT bypass CAPTCHA or login protections",
            "- Do NOT use AVM as final ARV",
            "- Do NOT call payoff verified unless official source confirms",
            "- Do NOT call title verified unless official source confirms",
            "- Do NOT create fake data if source is unavailable — write SOURCE_NEEDED instead",
            "",
            "## Verification Tasks by Property",
        ]

        for prop in strike_board:
            name = prop.get("name") or prop.get("address") or f"rank_{prop.get('rank', '?')}"
            address = (prop.get("address") or "").lower()

            lines += [
                "",
                f"### {name}",
                f"**Address:** {prop.get('address', 'SOURCE_NEEDED')}",
                f"**Entity:** {prop.get('entity', 'SOURCE_NEEDED')}",
                f"**Source Status:** {prop.get('status', 'SOURCE_NEEDED')}",
                "",
                "**Standard Verification Tasks:**",
            ]

            for i, task in enumerate(STANDARD_TASKS, 1):
                lines.append(f"{i}. {task}")

            # Add special tasks if applicable
            special_added = False
            for frag, tasks in SPECIAL_TASKS.items():
                if frag in address:
                    if not special_added:
                        lines += ["", "**Special Verification Tasks (This Property):**"]
                        special_added = True
                    for task in tasks:
                        lines.append(f"- {task}")

        lines += [
            "",
            "---",
            "## Buyer Target Verification Tasks",
            "(Apply to all buyer targets across all properties)",
            "",
        ]

        for i, task in enumerate(BUYER_VERIFICATION_TASKS, 1):
            lines.append(f"{i}. {task}")

        lines += [
            "",
            "---",
            "All tasks output: SOURCE_NEEDED until completed with screenshot/URL documentation.",
            "Do not proceed to outreach or offers until these tasks are complete.",
        ]

        task_file_path.write_text("\n".join(lines), encoding="utf-8")

        ev = make_event(
            event_type="OPENCLAW_TASKS_CREATED",
            source="OpenClawTaskWriter",
            payload={
                "property_count": len(strike_board),
                "task_file": str(task_file_path),
                "standard_tasks_per_property": len(STANDARD_TASKS),
                "buyer_verification_tasks": len(BUYER_VERIFICATION_TASKS),
            },
            source_file=str(task_file_path),
            verification_status="SOURCE_NEEDED",
            status="COMPLETED",
            notes="OpenClaw task list created. No verification completed yet.",
        )
        append_event(ev)

        return str(task_file_path)
