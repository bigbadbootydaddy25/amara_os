"""Event dataclass and factory for the AEGIS Neuron Network."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict

ALLOWED_EVENT_TYPES = {
    "QUICKCASH_OUTPUTS_FOUND",
    "SOURCE_INTEGRITY_CHECKED",
    "CONTAMINATION_DETECTED",
    "TAX_SALE_STRIKE_BOARD_LOADED",
    "BUYER_TARGETS_LOADED",
    "DEALS_CLASSIFIED",
    "PAYOFF_TASKS_CREATED",
    "TITLE_TASKS_CREATED",
    "BUYER_DEMAND_TASKS_CREATED",
    "OPENCLAW_TASKS_CREATED",
    "OUTREACH_TASKS_CREATED",
    "AMARA_BRAIN_SYNCED",
    "MONEY_BRIEF_CREATED",
    "NEURON_FAILED",
}


@dataclass
class Event:
    event_id: str
    timestamp: str
    event_type: str
    source: str
    payload: Dict
    source_file: str = ""
    source_url: str = ""
    verification_status: str = "SOURCE_NEEDED"
    status: str = "PENDING"
    notes: str = ""


def make_event(
    event_type: str,
    source: str,
    payload: Dict,
    source_file: str = "",
    source_url: str = "",
    verification_status: str = "SOURCE_NEEDED",
    status: str = "PENDING",
    notes: str = "",
) -> Event:
    """Factory function that generates event_id and timestamp automatically."""
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unknown event_type: {event_type!r}. Must be one of {ALLOWED_EVENT_TYPES}")
    return Event(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type=event_type,
        source=source,
        payload=payload,
        source_file=source_file,
        source_url=source_url,
        verification_status=verification_status,
        status=status,
        notes=notes,
    )
