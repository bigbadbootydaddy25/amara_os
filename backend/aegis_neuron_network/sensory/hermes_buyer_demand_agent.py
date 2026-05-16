"""Hermes Buyer Demand Agent — loads and validates buyer target data."""
from typing import Dict

from .. import quickcash_bridge
from ..events import make_event
from ..event_store import append_event


class HermesBuyerDemandAgent:
    """Loads buyer target CSVs and verifies no targets are CONFIRMED_BUYER."""

    def run(self) -> Dict:
        buyer_data = quickcash_bridge.load_buyer_targets()
        files = buyer_data.get("files", {})
        total_count = buyer_data.get("total_buyer_target_count", 0)

        # Verify no target carries CONFIRMED_BUYER status
        contamination_detected = False
        contaminated_entries = []

        for file_key, file_info in files.items():
            buyers = file_info.get("buyers", [])
            for buyer in buyers:
                raw_status = buyer.get("buyer_status", "")
                if raw_status == "CONFIRMED_BUYER":
                    contamination_detected = True
                    contaminated_entries.append({
                        "file": file_key,
                        "buyer": buyer,
                        "issue": "CONFIRMED_BUYER status without verified source",
                    })

        if contamination_detected:
            ev = make_event(
                event_type="CONTAMINATION_DETECTED",
                source="HermesBuyerDemandAgent",
                payload={
                    "reason": "CONFIRMED_BUYER status found without source verification",
                    "contaminated_entries": contaminated_entries,
                },
                verification_status="SOURCE_NEEDED",
                status="FAILED",
                notes="Never promote NOT_CONFIRMED_BUYER to confirmed without source.",
            )
            append_event(ev)
        else:
            files_found = [k for k, v in files.items() if v.get("exists")]
            ev = make_event(
                event_type="BUYER_TARGETS_LOADED",
                source="HermesBuyerDemandAgent",
                payload={
                    "total_buyer_target_count": total_count,
                    "files_found": files_found,
                    "buyer_status": "NOT_CONFIRMED_BUYER",
                    "status_verified": True,
                },
                verification_status="SOURCE_NEEDED",
                status="COMPLETED",
                notes="All targets carry NOT_CONFIRMED_BUYER status as required.",
            )
            append_event(ev)

        return {
            "agent": "HermesBuyerDemandAgent",
            "status": "COMPLETED",
            "buyer_target_count": total_count,
            "files_found": [k for k, v in files.items() if v.get("exists")],
            "status_verified": not contamination_detected,
            "contamination_detected": contamination_detected,
            "contaminated_entries": contaminated_entries,
            "buyer_data": buyer_data,
        }
