"""Payoff Task Neuron — creates payoff verification tasks for each strike board property."""
from datetime import datetime, timezone
from typing import Dict, List

from ..config import REPORTS_DIR
from ..events import make_event
from ..event_store import append_event


class PayoffTaskNeuron:
    """
    Generates payoff verification tasks for each property.
    Never calls minimum bid 'final payoff'.
    All payoff amounts are UNVERIFIED until source confirms.
    """

    def run(self, strike_board: List[Dict]) -> int:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / "payoff_verification_needed.md"

        lines = [
            "# Payoff Verification Needed",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Critical Rules",
            "- Do NOT call minimum bid 'final payoff' — they are different amounts",
            "- Payoff status is UNVERIFIED until Harris County Tax Office confirms",
            "- Do NOT call payoff verified unless source confirms it",
            "- Verify good-through date for any payoff amount",
            "- Check for additional taxes accrued after judgment",
            "",
            "## Payoff Verification Tasks by Property",
        ]

        task_count = 0

        for prop in strike_board:
            name = prop.get("name") or prop.get("address") or f"rank_{prop.get('rank', '?')}"
            address = prop.get("address", "SOURCE_NEEDED")
            min_bid = prop.get("minimum_bid", "SOURCE_NEEDED")

            lines += [
                "",
                f"### {name}",
                f"**Address:** {address}",
                f"**Visible Minimum Bid:** {min_bid}",
                "**Payoff Status:** UNVERIFIED",
                "",
                "**Required Verification Tasks:**",
            ]

            tasks = [
                "Verify Harris County tax account number (HCAD lookup required)",
                "Verify tax sale date and listing status (Harris County Tax Office)",
                "Request official payoff good-through date from taxing authority",
                "Check for additional taxes accrued after judgment date",
                "Verify no IRS liens that survive tax sale",
                "Confirm minimum bid does NOT equal total payoff — request itemized breakdown",
                "Obtain source URL or screenshot for all amounts",
            ]

            for i, task in enumerate(tasks, 1):
                lines.append(f"{i}. {task}")
                task_count += 1

            lines += [
                "",
                "**Verification Status:** SOURCE_NEEDED",
                "**Do Not Proceed Until:** All payoff tasks above are completed with source confirmation",
            ]

        lines += [
            "",
            "---",
            f"Total Payoff Verification Tasks: {task_count}",
            "All tasks require SOURCE confirmation before any offer or outreach.",
        ]

        report_path.write_text("\n".join(lines), encoding="utf-8")

        ev = make_event(
            event_type="PAYOFF_TASKS_CREATED",
            source="PayoffTaskNeuron",
            payload={
                "task_count": task_count,
                "property_count": len(strike_board),
                "report_file": str(report_path),
            },
            source_file=str(report_path),
            verification_status="SOURCE_NEEDED",
            status="COMPLETED",
            notes="Payoff verification tasks created. No amounts verified yet.",
        )
        append_event(ev)

        return task_count
