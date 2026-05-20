"""
Phase 4 validation gate — every lead passes through here before any alert fires.

Rules:
  1. operator_number must be present (non-empty).
  2. operator_number must not be on the blacklist.
  3. operator_number must appear in the RRC P-5 active operator list
     (when the list file is available).
  4. If the P-5 list file is absent and require_p5_verification=True,
     quarantine the lead as UNVERIFIED rather than letting it through.

No LLM involvement. All checks are against local files sourced from RRC.
"""

from __future__ import annotations

import csv
import datetime
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

QUARANTINE_COLUMNS = [
    "timestamp",
    "operator_name",
    "operator_number",
    "permit_no",
    "reason",
    "missing_fields",
    "raw_data",
]

# Module-level cache so we only read the P-5 file once per process.
_p5_cache: Optional[set[str]] = None
_p5_cache_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_active_p5_operators(p5_file: Path) -> set[str]:
    """
    Load the set of active RRC P-5 operator numbers from *p5_file*.

    File format (JSON):
      Either a plain list of strings:  ["12345", "67890", ...]
      Or a dict with key "operator_numbers": {"operator_numbers": [...]}

    Returns an empty set if the file does not exist — caller decides
    whether to treat that as a hard block or soft warning.
    """
    global _p5_cache, _p5_cache_path

    if _p5_cache is not None and _p5_cache_path == p5_file:
        return _p5_cache

    if not p5_file.exists():
        logger.warning(
            "P-5 active operator list not found at %s.\n"
            "  → Obtain from the RRC Organization Report download and save as JSON.\n"
            "  → In live mode, leads will be quarantined as UNVERIFIED_P5.",
            p5_file,
        )
        _p5_cache = set()
        _p5_cache_path = p5_file
        return _p5_cache

    with open(p5_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        numbers = data
    elif isinstance(data, dict):
        numbers = data.get("operator_numbers", data.get("p5_numbers", []))
    else:
        logger.error("Unrecognised P-5 file format in %s — expected list or dict", p5_file)
        numbers = []

    _p5_cache = {str(n).strip() for n in numbers if n}
    _p5_cache_path = p5_file
    logger.info("Loaded %d active P-5 numbers from %s", len(_p5_cache), p5_file)
    return _p5_cache


def load_blacklist(blacklist_file: Path) -> set[str]:
    """Return the set of blacklisted operator numbers."""
    if not blacklist_file.exists():
        return set()
    with open(blacklist_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    numbers = data.get("blacklisted_operator_numbers", [])
    result = {str(n).strip() for n in numbers if n}
    if result:
        logger.info("Blacklist loaded: %d operator(s) blocked", len(result))
    return result


# ---------------------------------------------------------------------------
# Quarantine writer
# ---------------------------------------------------------------------------

def log_quarantine(
    quarantine_csv: Path,
    operator_name: str,
    operator_number: str,
    permit_no: str,
    reason: str,
    missing_fields: list[str],
    raw_data: dict,
) -> None:
    quarantine_csv.parent.mkdir(parents=True, exist_ok=True)

    write_header = not quarantine_csv.exists()
    with open(quarantine_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=QUARANTINE_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "operator_name": operator_name,
                "operator_number": operator_number,
                "permit_no": permit_no,
                "reason": reason,
                "missing_fields": "|".join(missing_fields),
                "raw_data": json.dumps(raw_data, default=str),
            }
        )
    logger.info(
        "QUARANTINE: %s (P5: %s) permit=%s — %s",
        operator_name,
        operator_number,
        permit_no,
        reason,
    )


# ---------------------------------------------------------------------------
# Phase 4 validation gate
# ---------------------------------------------------------------------------

def validate_lead(
    *,
    operator_number: str,
    operator_name: str,
    permit_no: str,
    raw_data: dict,
    p5_file: Path,
    blacklist_file: Path,
    quarantine_csv: Path,
    require_p5_verification: bool = True,
) -> bool:
    """
    Returns True only if the lead passes all checks.
    Writes to quarantine and returns False on any failure.
    No network calls, no LLM — purely local file lookups.
    """

    def _quarantine(reason: str, missing: Optional[list[str]] = None) -> bool:
        log_quarantine(
            quarantine_csv=quarantine_csv,
            operator_name=operator_name,
            operator_number=operator_number,
            permit_no=permit_no,
            reason=reason,
            missing_fields=missing or [],
            raw_data=raw_data,
        )
        return False

    # Gate 1 — operator_number must be present
    if not operator_number or not operator_number.strip():
        return _quarantine("No RRC P-5 number — operator identity unverifiable")

    op_num = operator_number.strip()

    # Gate 2 — blacklist check
    blacklist = load_blacklist(blacklist_file)
    if op_num in blacklist:
        return _quarantine(f"Operator {op_num} is on the blacklist")

    # Gate 3 — P-5 active operator list
    active = load_active_p5_operators(p5_file)
    if active:
        if op_num not in active:
            return _quarantine(f"P-5 {op_num} not found in RRC active operator list")
    elif require_p5_verification:
        return _quarantine(
            "P-5 active operator list unavailable — cannot verify. "
            "Download the RRC Organization Report and save to data/active_p5_operators.json"
        )
    else:
        logger.warning(
            "UNVERIFIED_P5 (dry-run only): %s (%s) — P-5 list not loaded",
            operator_name,
            op_num,
        )

    return True
