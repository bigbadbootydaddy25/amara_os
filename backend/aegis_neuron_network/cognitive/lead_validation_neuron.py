"""Lead Validation Neuron — applies validation rules to each strike board property."""
from typing import Dict, List

from ..events import make_event
from ..event_store import append_event


class LeadValidationNeuron:
    """
    Applies rule-based validation to each strike board property.
    All buyer targets are forced to NOT_CONFIRMED_BUYER.
    Never promotes any status to VERIFIED without a confirmed source.
    """

    STATUS_RULES = {
        "CANCELLED": "AUDIT_ONLY",
        "SOLD_WITH_ACCOUNT": "MANUAL_VERIFICATION_REQUIRED",
    }

    def run(self, strike_board: List[Dict]) -> List[Dict]:
        validated = []

        for prop in strike_board:
            entry = dict(prop)
            raw_status = entry.get("status", "")

            if raw_status == "CANCELLED":
                entry["validation_status"] = "AUDIT_ONLY"
                entry["validation_note"] = "Property cancelled — review only, no active pursuit"
            elif raw_status == "SOLD_WITH_ACCOUNT":
                entry["validation_status"] = "MANUAL_VERIFICATION_REQUIRED"
                entry["validation_note"] = "Sold with account — must manually verify current status"
            else:
                entry["validation_status"] = "ACTIVE_UNVERIFIED"
                entry["validation_note"] = (
                    "Payoff, title, and owner contact NOT confirmed. "
                    "SOURCE_NEEDED before any action."
                )

            # Buyer targets attached to this property
            if "buyer_targets" in entry:
                for buyer in entry["buyer_targets"]:
                    buyer["buyer_status"] = "NOT_CONFIRMED_BUYER"

            # Preserve original source status string
            entry["source_status"] = raw_status if raw_status else "SOURCE_NEEDED"

            validated.append(entry)

        return validated
