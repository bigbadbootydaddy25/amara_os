"""Persistent event log for AEGIS Neuron Network events."""
import json
from dataclasses import asdict
from typing import Dict, List, Optional

from .config import EVENT_LOG_PATH
from .events import Event


def append_event(event: Event) -> None:
    """Write an Event to the JSONL event log, creating parent dirs if needed."""
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event)) + "\n")


def read_events(limit: Optional[int] = None) -> List[Dict]:
    """Return a list of event dicts from the log, newest-first if limit given."""
    if not EVENT_LOG_PATH.exists():
        return []
    events = []
    with EVENT_LOG_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if limit is not None:
        events = events[-limit:]
    return events


def event_counts() -> Dict[str, int]:
    """Return a dict of event_type -> count from the full log."""
    counts: Dict[str, int] = {}
    for ev in read_events():
        et = ev.get("event_type", "UNKNOWN")
        counts[et] = counts.get(et, 0) + 1
    return counts


def clear_events() -> None:
    """Truncate the event log (for testing only)."""
    if EVENT_LOG_PATH.exists():
        EVENT_LOG_PATH.write_text("", encoding="utf-8")
