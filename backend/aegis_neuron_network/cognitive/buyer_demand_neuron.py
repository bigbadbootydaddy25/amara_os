"""Buyer Demand Neuron — compiles buyer demand status from loaded buyer target data."""
from datetime import datetime, timezone
from typing import Dict

from ..config import BUYER_DEMAND_DIR
from ..events import make_event
from ..event_store import append_event


class BuyerDemandNeuron:
    """
    Compiles buyer demand status from buyer target data.
    Preserves NOT_CONFIRMED_BUYER for all targets.
    Never promotes to CONFIRMED_BUYER.
    """

    def run(self, buyer_data: Dict) -> Dict:
        BUYER_DEMAND_DIR.mkdir(parents=True, exist_ok=True)
        output_path = BUYER_DEMAND_DIR / "buyer_demand_status.md"

        files = buyer_data.get("files", {})
        total_count = buyer_data.get("total_buyer_target_count", 0)

        # Build summary per file
        file_summaries = []
        for key, info in files.items():
            if info.get("type") == "markdown":
                file_summaries.append({
                    "key": key,
                    "exists": info.get("exists", False),
                    "count": None,
                    "note": "Markdown summary file",
                })
            else:
                file_summaries.append({
                    "key": key,
                    "exists": info.get("exists", False),
                    "count": info.get("count", 0),
                    "buyer_status": "NOT_CONFIRMED_BUYER",
                })

        lines = [
            "# Buyer Demand Status",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Critical Rules",
            "- All buyer targets carry NOT_CONFIRMED_BUYER status",
            "- Never promote NOT_CONFIRMED_BUYER to CONFIRMED_BUYER without verified source",
            "- Transaction history not verified — NEEDS_TRANSACTION_VERIFICATION",
            "- No direct buyer interest has been confirmed",
            "- Do not send outreach until basic payoff/title checks are complete",
            "",
            f"## Total Buyer Targets: {total_count}",
            "**All Status:** NOT_CONFIRMED_BUYER",
            "",
            "## Buyer Target Files",
        ]

        for fs in file_summaries:
            lines.append(f"\n### {fs['key']}")
            lines.append(f"- File Exists: {fs['exists']}")
            if fs["count"] is not None:
                lines.append(f"- Buyer Count: {fs['count']}")
                lines.append(f"- Buyer Status: NOT_CONFIRMED_BUYER")
            lines.append(f"- Note: {fs.get('note', 'CSV buyer target list')}")

        lines += [
            "",
            "## What Is Needed Before Buyer Outreach",
            "1. Transaction verification — NEEDS_TRANSACTION_VERIFICATION",
            "2. Acquisition contact — official contact channel not yet established",
            "3. Official contact channel — must be sourced from public records or direct response",
            "4. Basic payoff verification — SOURCE_NEEDED for all properties",
            "5. Basic title check — SOURCE_NEEDED for all properties",
            "",
            "## Verification Status",
            "SOURCE_NEEDED — No buyer has confirmed interest or been verified as active acquirer",
            "NEEDS_TRANSACTION_VERIFICATION — Transaction history for all targets is unverified",
        ]

        output_path.write_text("\n".join(lines), encoding="utf-8")

        ev = make_event(
            event_type="BUYER_DEMAND_TASKS_CREATED",
            source="BuyerDemandNeuron",
            payload={
                "total_buyer_target_count": total_count,
                "file_count": len(files),
                "buyer_status": "NOT_CONFIRMED_BUYER",
                "output_file": str(output_path),
            },
            source_file=str(output_path),
            verification_status="SOURCE_NEEDED",
            status="COMPLETED",
            notes="Buyer demand status compiled. All targets NOT_CONFIRMED_BUYER.",
        )
        append_event(ev)

        return {
            "neuron": "BuyerDemandNeuron",
            "status": "COMPLETED",
            "total_buyer_target_count": total_count,
            "buyer_status": "NOT_CONFIRMED_BUYER",
            "needs_transaction_verification": True,
            "output_file": str(output_path),
            "file_summaries": file_summaries,
        }
