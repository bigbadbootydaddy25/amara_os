"""Hermes QuickCash Agent — sensory layer that ingests QuickCash outputs."""
from typing import Dict

from .. import quickcash_bridge
from ..events import make_event
from ..event_store import append_event


class HermesQuickCashAgent:
    """Checks QuickCash output availability and loads the strike board."""

    def run(self) -> Dict:
        # 1. Ensure outputs exist (or document why they don't)
        bridge_result = quickcash_bridge.ensure_quickcash_outputs_exist()

        found_files = bridge_result.get("found_files", {})
        missing_files = bridge_result.get("missing_files", {})

        ev = make_event(
            event_type="QUICKCASH_OUTPUTS_FOUND",
            source="HermesQuickCashAgent",
            payload={
                "status": bridge_result.get("status"),
                "found_count": len(found_files),
                "missing_count": len(missing_files),
                "found_files": list(found_files.keys()),
                "missing_files": list(missing_files.keys()),
                "error": bridge_result.get("error"),
                "task": bridge_result.get("task"),
            },
            verification_status="SOURCE_NEEDED" if missing_files else "VERIFIED_SOURCE",
            status="COMPLETED" if not missing_files else "PARTIAL",
        )
        append_event(ev)

        # 2. Load strike board
        strike_result = quickcash_bridge.load_strike_board()
        property_count = strike_result.get("count", 0)

        ev2 = make_event(
            event_type="TAX_SALE_STRIKE_BOARD_LOADED",
            source="HermesQuickCashAgent",
            payload={
                "property_count": property_count,
                "source": strike_result.get("source"),
                "source_file": strike_result.get("source_file"),
                "note": strike_result.get("note"),
            },
            source_file=strike_result.get("source_file", ""),
            verification_status=strike_result.get("source", "SOURCE_NEEDED"),
            status="COMPLETED",
        )
        append_event(ev2)

        return {
            "agent": "HermesQuickCashAgent",
            "status": "COMPLETED",
            "bridge_result": bridge_result,
            "strike_board": strike_result,
            "property_count": property_count,
        }
