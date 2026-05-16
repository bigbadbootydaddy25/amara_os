"""Title Risk Neuron — creates title checklist tasks for each strike board property."""
from datetime import datetime, timezone
from typing import Dict, List

from ..config import REPORTS_DIR
from ..events import make_event
from ..event_store import append_event

# Standard title checklist items for all properties
STANDARD_TITLE_CHECKLIST = [
    ("deed_mortgage_check", "Deed and mortgage history check (county records)"),
    ("irs_lien", "IRS lien search — IRS liens may survive tax sale"),
    ("hoa_code_lien", "HOA and municipal code enforcement lien search"),
    ("bankruptcy", "Bankruptcy search — automatic stay may apply"),
    ("probate_heirship", "Probate/heirship check — verify no competing ownership claims"),
    ("redemption_classification", "Redemption period classification — confirm whether property is redeemable and for how long"),
    ("title_insurability", "Title insurability assessment — contact title company before any offer"),
]

# Special checks keyed to address fragments
SPECIAL_CHECKS = {
    "800 tidwell": [
        ("environmental_risk", "Environmental risk verification — prior auto use on 800 Tidwell Rd. Phase I ESA may be required before close."),
    ],
    "1307 prairie": [
        ("entity_control", "Bendanmar Limited entity/control verification — confirm ownership authority, registered agent, and standing to convey."),
    ],
    "415 caroline": [
        ("entity_control", "Bendanmar Limited entity/control verification — confirm ownership authority, registered agent, and standing to convey."),
    ],
    "813 w 30": [
        ("owner_verification", "Owner verification — Jason Castaneda listed as USER_PROVIDED_UNVERIFIED. Verify via HCAD deed records before any contact."),
    ],
}


class TitleRiskNeuron:
    """
    Generates a title risk checklist for each strike board property.
    All title statuses are UNVERIFIED until source confirms.
    """

    def run(self, strike_board: List[Dict]) -> int:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / "title_risk_checklist.md"

        lines = [
            "# Title Risk Checklist",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Critical Rules",
            "- Do NOT call title verified unless source confirms it",
            "- All items below are UNVERIFIED until completed with source documentation",
            "- IRS liens may survive tax sale — must be checked for every property",
            "- Environmental risk (800 Tidwell) must be verified before any offer",
            "- Entity/control (Bendanmar Limited) must be verified before any deal",
            "",
            "## Title Checklist by Property",
        ]

        task_count = 0

        for prop in strike_board:
            name = prop.get("name") or prop.get("address") or f"rank_{prop.get('rank', '?')}"
            address = (prop.get("address") or "").lower()

            lines += [
                "",
                f"### {name}",
                f"**Address:** {prop.get('address', 'SOURCE_NEEDED')}",
                "**Title Status:** UNVERIFIED",
                "",
                "**Standard Title Checks:**",
            ]

            for i, (key, desc) in enumerate(STANDARD_TITLE_CHECKLIST, 1):
                lines.append(f"{i}. [ ] {desc}")
                task_count += 1

            # Add special checks if applicable
            special_added = False
            for frag, checks in SPECIAL_CHECKS.items():
                if frag in address:
                    if not special_added:
                        lines += ["", "**Special Risk Checks (This Property):**"]
                        special_added = True
                    for _, desc in checks:
                        lines.append(f"- [ ] {desc}")
                        task_count += 1

            lines += [
                "",
                "**Verification Status:** SOURCE_NEEDED",
                "**Title Insurability:** NOT ASSESSED — contact title company",
            ]

        lines += [
            "",
            "---",
            f"Total Title Verification Tasks: {task_count}",
            "All tasks require source documentation (screenshot or URL) before title can be marked verified.",
        ]

        report_path.write_text("\n".join(lines), encoding="utf-8")

        ev = make_event(
            event_type="TITLE_TASKS_CREATED",
            source="TitleRiskNeuron",
            payload={
                "task_count": task_count,
                "property_count": len(strike_board),
                "report_file": str(report_path),
            },
            source_file=str(report_path),
            verification_status="SOURCE_NEEDED",
            status="COMPLETED",
            notes="Title checklist created. No title status verified yet.",
        )
        append_event(ev)

        return task_count
