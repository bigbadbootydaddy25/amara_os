from __future__ import annotations

"""Entity lookup for lawful OSINT. Evidence-first connector."""

from typing import Any
import os
import json

_NOT_FOUND = "Not found in provided manual exports or cache."

_MISSING_FIELDS = [
    "entity_status",
    "sos_registration_evidence",
    "associated_addresses",
    "linked_properties",
    "purchase_history",
    "portfolio_count",
    "estimated_equity",
    "loan_balance",
    "last_purchase",
    "active_counties_zips",
    "cash_vs_financed_pattern",
]


def _missing(field: str, reason: str) -> dict:
    return {"value": None, "missing": True, "reason": reason, "evidence": [], "field": field}


def lookup_entity(entity: dict[str, Any], *, cache_dir: str) -> dict[str, Any]:
    os.makedirs(cache_dir, exist_ok=True)

    entity_key = entity.get("entity_id") or entity.get("name") or entity.get("source") or "unknown"
    cache_path = os.path.join(cache_dir, f"entity_{entity_key}.json")

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    result: dict[str, Any] = {
        "input": entity,
        **{field: _missing(field, _NOT_FOUND) for field in _MISSING_FIELDS},
        "source_urls_files": [],
    }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result
