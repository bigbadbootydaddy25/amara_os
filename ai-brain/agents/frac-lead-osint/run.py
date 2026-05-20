"""
Frac Lead OSINT Agent — RRC W-1 Permit Monitor
Enforces the Real Data Only Rule on every run. No synthetic data. No fallbacks.
"""

from __future__ import annotations

import csv
import os
import sys
import logging
import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

AGENT_DIR = Path(__file__).parent.resolve()
QUARANTINE_CSV = AGENT_DIR / "quarantine.csv"
RUN_ERRORS_LOG = AGENT_DIR / "run_errors.log"
DRY_RUN_LOG = AGENT_DIR / "dry_run.log"

# Set RRC_CSV_PATH via environment variable or CLI argument
RRC_CSV_PATH = Path(os.environ.get("RRC_CSV_PATH", "")) if os.environ.get("RRC_CSV_PATH") else None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _log_run_error(message: str) -> None:
    RUN_ERRORS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_ERRORS_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().isoformat()}Z  ERROR  {message}\n")
    logger.error(message)


# ---------------------------------------------------------------------------
# Section 6: Agent self-check — runs at top of every execution
# ---------------------------------------------------------------------------

def enforce_real_data_rule() -> None:
    """
    Hard gate: abort with exit code 1 if any condition is violated.
    Must run before any CSV processing.
    """
    if RRC_CSV_PATH is None or str(RRC_CSV_PATH).strip() == "":
        msg = "ABORT: RRC_CSV_PATH not set. No alerts will fire."
        _log_run_error(msg)
        sys.exit(1)

    # Assertion 1: file exists and is non-empty
    if not RRC_CSV_PATH.exists() or RRC_CSV_PATH.stat().st_size == 0:
        msg = f"ABORT: RRC source file missing or empty: {RRC_CSV_PATH}. No alerts will fire."
        _log_run_error(msg)
        sys.exit(1)

    # Assertion 2: file contains required column OPER_NO
    try:
        with open(RRC_CSV_PATH, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
    except Exception as exc:
        msg = f"ABORT: Could not read RRC source file ({exc}). No alerts will fire."
        _log_run_error(msg)
        sys.exit(1)

    if "OPER_NO" not in header:
        msg = (
            f"ABORT: Source file schema invalid — 'OPER_NO' column not found. "
            f"Columns present: {header}. Wrong file loaded. No alerts will fire."
        )
        _log_run_error(msg)
        sys.exit(1)

    # Assertion 3: file download is within the last 7 days
    mtime = datetime.datetime.utcfromtimestamp(RRC_CSV_PATH.stat().st_mtime)
    age_days = (datetime.datetime.utcnow() - mtime).days
    if age_days > 7:
        msg = (
            f"ABORT: Source file stale — last modified {age_days} days ago "
            f"({mtime.date()}). Re-download before running. No alerts will fire."
        )
        _log_run_error(msg)
        sys.exit(1)

    logger.info("enforce_real_data_rule: PASS — source file present, schema valid, age %d day(s)", age_days)


# ---------------------------------------------------------------------------
# Required field map (Section 2)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: dict[str, str] = {
    "rrc_operator_name": "OPER_NAME",
    "rrc_p5_number":     "OPER_NO",
    "permit_number":     "PERMIT_NO",
    "county_name":       "CNTY_NAME",
    "lease_name":        "LEASE_NAME",
    "well_number":       "WELL_NO",
    "permit_date":       "PERMIT_DATE",
    "field_name":        "FIELD_NAME",
    "well_type":         "WELL_TYPE",
}


def _parse_row(row: dict, row_index: int, source_file: Path) -> tuple[dict, list[str]]:
    """
    Extract required fields from a CSV row.
    Returns (parsed_lead, list_of_missing_field_names).
    """
    parsed: dict = {
        "source_file_path": str(source_file),
        "source_row_index": row_index,
    }
    missing: list[str] = []

    for lead_field, csv_col in REQUIRED_FIELDS.items():
        value = row.get(csv_col, "").strip()
        if not value:
            missing.append(lead_field)
        else:
            parsed[lead_field] = value

    return parsed, missing


# ---------------------------------------------------------------------------
# Section 3: Quarantine logic
# ---------------------------------------------------------------------------

QUARANTINE_COLUMNS = [
    "timestamp",
    "operator_name",
    "p5_number",
    "permit_no",
    "missing_fields",
    "raw_source_row",
    "quarantine_reason",
]


def _ensure_quarantine_csv() -> None:
    if not QUARANTINE_CSV.exists():
        with open(QUARANTINE_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=QUARANTINE_COLUMNS)
            writer.writeheader()


def quarantine_record(
    row: dict,
    row_index: int,
    missing_fields: list[str],
    reason: str,
) -> None:
    _ensure_quarantine_csv()
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "operator_name": row.get("OPER_NAME", ""),
        "p5_number": row.get("OPER_NO", ""),
        "permit_no": row.get("PERMIT_NO", ""),
        "missing_fields": "|".join(missing_fields),
        "raw_source_row": ",".join(str(v) for v in row.values()),
        "quarantine_reason": reason,
    }
    with open(QUARANTINE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=QUARANTINE_COLUMNS)
        writer.writerow(entry)
    logger.info(
        "QUARANTINE row %d — missing: %s — %s",
        row_index,
        "|".join(missing_fields),
        reason,
    )


# ---------------------------------------------------------------------------
# Section 4: Dry-run proof output
# ---------------------------------------------------------------------------

def _dry_run_block(parsed: dict, raw_row: dict) -> str:
    raw_line = ",".join(str(v) for v in raw_row.values())
    lines = [
        "── ACCEPTED LEAD ──────────────────────────────",
        f"SOURCE FILE : {parsed['source_file_path']}",
        f"SOURCE ROW  : {parsed['source_row_index']}",
        f"RAW ROW     : {raw_line}",
        "",
        "PARSED FIELDS:",
        f"  rrc_operator_name : {parsed.get('rrc_operator_name', '')}",
        f"  rrc_p5_number     : {parsed.get('rrc_p5_number', '')}",
        f"  permit_number     : {parsed.get('permit_number', '')}",
        f"  county_name       : {parsed.get('county_name', '')}",
        f"  lease_name        : {parsed.get('lease_name', '')}",
        f"  well_number       : {parsed.get('well_number', '')}",
        f"  permit_date       : {parsed.get('permit_date', '')}",
        f"  field_name        : {parsed.get('field_name', '')}",
        f"  well_type         : {parsed.get('well_type', '')}",
        f"  source_file_path  : {parsed.get('source_file_path', '')}",
        f"  source_row_index  : {parsed.get('source_row_index', '')}",
        "",
        "VALIDATION    : PASS — all required fields present from RRC W-1 source",
        "ALERT STATUS  : DRY-RUN (no Telegram sent)",
        "───────────────────────────────────────────────",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 5: Live mode gate
# ---------------------------------------------------------------------------

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"

_DRY_RUN_PASS_COUNT = 0
_DRY_RUN_MIN_REQUIRED = 3


def _live_mode_gate_check(dry_run_accepted: int) -> bool:
    """
    Returns True only when all live-mode preconditions are satisfied.
    Logs the gate status either way.
    """
    if not LIVE_MODE:
        return False

    if dry_run_accepted < _DRY_RUN_MIN_REQUIRED:
        msg = (
            f"LIVE MODE BLOCKED: only {dry_run_accepted} accepted leads in dry-run "
            f"(minimum {_DRY_RUN_MIN_REQUIRED} required). No Telegram alerts sent."
        )
        _log_run_error(msg)
        return False

    # Check quarantine log has zero invalid alerts
    if QUARANTINE_CSV.exists():
        with open(QUARANTINE_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            quarantine_rows = list(reader)
        if quarantine_rows:
            msg = (
                f"LIVE MODE BLOCKED: {len(quarantine_rows)} record(s) in quarantine.csv. "
                "Resolve before enabling live alerts."
            )
            _log_run_error(msg)
            return False

    logger.info("LIVE MODE GATE: OPEN — all preconditions met.")
    return True


# ---------------------------------------------------------------------------
# Alert stub (Telegram)
# ---------------------------------------------------------------------------

def _send_telegram_alert(lead: dict) -> None:
    """Stub: replace with real Telegram Bot API call in production."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping alert")
        return

    import urllib.request
    import urllib.parse
    import json

    text = (
        f"NEW FRAC LEAD — {lead['county_name']} County\n"
        f"Operator : {lead['rrc_operator_name']} (P5: {lead['rrc_p5_number']})\n"
        f"Lease    : {lead['lease_name']} #{lead['well_number']}\n"
        f"Permit   : {lead['permit_number']}  ({lead['permit_date']})\n"
        f"Field    : {lead['field_name']}  |  Type: {lead['well_type']}\n"
        f"Source   : row {lead['source_row_index']} of {Path(lead['source_file_path']).name}"
    )
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        logger.info("Telegram alert sent: HTTP %d", resp.status)


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process_permits(county_filter: Optional[str] = None, dry_run: bool = True) -> None:
    assert RRC_CSV_PATH is not None
    accepted: list[dict] = []
    quarantine_count = 0
    dry_run_log_lines: list[str] = []

    with open(RRC_CSV_PATH, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_index, row in enumerate(reader, start=2):  # row 1 = header
            if county_filter:
                row_county = row.get("CNTY_NAME", "").strip().upper()
                if row_county != county_filter.upper():
                    continue

            parsed, missing = _parse_row(row, row_index, RRC_CSV_PATH)

            if missing:
                quarantine_record(
                    row=row,
                    row_index=row_index,
                    missing_fields=missing,
                    reason=f"Missing required fields: {', '.join(missing)}",
                )
                quarantine_count += 1
                continue

            accepted.append(parsed)

            if dry_run:
                block = _dry_run_block(parsed, row)
                print(block)
                dry_run_log_lines.append(block)
            else:
                live_ok = _live_mode_gate_check(len(accepted))
                if live_ok:
                    _send_telegram_alert(parsed)

    # Write dry-run log
    if dry_run and dry_run_log_lines:
        DRY_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DRY_RUN_LOG, "w", encoding="utf-8") as f:
            f.write("\n\n".join(dry_run_log_lines) + "\n")

    logger.info(
        "Run complete — accepted: %d  quarantined: %d  mode: %s",
        len(accepted),
        quarantine_count,
        "DRY-RUN" if dry_run else "LIVE",
    )

    if dry_run and len(accepted) < _DRY_RUN_MIN_REQUIRED:
        logger.warning(
            "DRY-RUN: only %d accepted lead(s) — minimum %d required before live mode is permitted.",
            len(accepted),
            _DRY_RUN_MIN_REQUIRED,
        )

    if dry_run and quarantine_count > 0:
        logger.info("Quarantine log written to: %s", QUARANTINE_CSV)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Frac Lead OSINT Agent — RRC W-1 Permit Monitor")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Path to the RRC W-1 permit CSV (overrides RRC_CSV_PATH env var)",
    )
    parser.add_argument(
        "--county",
        dest="county",
        default="ECTOR",
        help="Filter to a single county (default: ECTOR)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live Telegram alerts (requires dry-run gate to be passed first)",
    )
    args = parser.parse_args()

    if args.csv_path:
        RRC_CSV_PATH = Path(args.csv_path)

    if args.live:
        os.environ["LIVE_MODE"] = "true"

    # Hard gate — must pass before any processing
    enforce_real_data_rule()

    process_permits(county_filter=args.county, dry_run=not args.live)
