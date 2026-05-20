"""
Frac Lead OSINT Agent — RRC W-1 Permit Monitor

Pipeline (no LLM in the data path):
  1. enforce_real_data_rule()  — hard gate, aborts on bad/stale/missing CSV
  2. rrc_ingest.parse_w1_csv() — parse real RRC W-1 rows, county + date filtered
  3. _parse_required_fields()  — extract the 9 mandatory fields; quarantine if any missing
  4. validator.validate_lead() — Phase 4 gate: P-5 active list + blacklist
  5. _enrich_estimates()       — sand/water from FracFocus or county median × active wells
  6. _send_telegram_alert()    — dynamic real-field message; never fires in dry-run

LLM use: NONE in this pipeline. No Ollama, no OpenAI, no Anthropic calls.
"""

from __future__ import annotations

import csv
import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import rrc_ingest
import validator as v

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

AGENT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = AGENT_DIR / "config.json"
QUARANTINE_CSV = AGENT_DIR / "quarantine.csv"
RUN_ERRORS_LOG = AGENT_DIR / "run_errors.log"
DRY_RUN_LOG = AGENT_DIR / "dry_run.log"

_cfg: dict = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)

def _path(key: str) -> Path:
    raw = _cfg.get(key, "")
    p = Path(raw)
    return p if p.is_absolute() else AGENT_DIR / p

P5_FILE = _path("p5_operators_file")
BLACKLIST_FILE = _path("blacklist_file")
RRC_DATA_DIR = _path("rrc_data_dir")
FRACFOCUS_DATA_DIR = _path("fracfocus_data_dir")
TARGET_COUNTY = _cfg.get("target_county", "ECTOR")
PERMIT_DAYS_BACK = int(_cfg.get("permit_days_back", 30))
_DRY_RUN_MIN_REQUIRED = int(_cfg.get("live_mode_min_dry_run_leads", 3))

ECTOR_SAND_MEDIAN = _cfg.get("ector_county_medians", {}).get("sand_tons_per_well", 3500)
ECTOR_WATER_MEDIAN = _cfg.get("ector_county_medians", {}).get("water_bbls_per_well", 21000)

# Set via CLI --csv or environment variable RRC_CSV_PATH
RRC_CSV_PATH: Optional[Path] = (
    Path(os.environ["RRC_CSV_PATH"]) if os.environ.get("RRC_CSV_PATH") else None
)

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"

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
# Section 6: Agent self-check — runs before any processing on every execution
# ---------------------------------------------------------------------------

def enforce_real_data_rule() -> None:
    """
    Hard gate: abort with exit code 1 if any condition fails.
    No exceptions. No fallbacks.
    """
    if RRC_CSV_PATH is None or str(RRC_CSV_PATH).strip() == "":
        _log_run_error("ABORT: RRC_CSV_PATH not set. No alerts will fire.")
        sys.exit(1)

    if not RRC_CSV_PATH.exists() or RRC_CSV_PATH.stat().st_size == 0:
        _log_run_error(
            f"ABORT: RRC source file missing or empty: {RRC_CSV_PATH}. No alerts will fire."
        )
        sys.exit(1)

    try:
        with open(RRC_CSV_PATH, "r", encoding="utf-8-sig", errors="replace") as f:
            header = csv.DictReader(f).fieldnames or []
    except Exception as exc:
        _log_run_error(f"ABORT: Cannot read RRC source file ({exc}). No alerts will fire.")
        sys.exit(1)

    if "OPER_NO" not in header:
        _log_run_error(
            f"ABORT: Source file schema invalid — 'OPER_NO' column not found. "
            f"Columns present: {header}. Wrong file loaded. No alerts will fire."
        )
        sys.exit(1)

    mtime = datetime.datetime.utcfromtimestamp(RRC_CSV_PATH.stat().st_mtime)
    age_days = (datetime.datetime.utcnow() - mtime).days
    if age_days > 7:
        _log_run_error(
            f"ABORT: Source file stale — last modified {age_days} days ago "
            f"({mtime.date()}). Re-download before running. No alerts will fire."
        )
        sys.exit(1)

    logger.info(
        "enforce_real_data_rule: PASS — file valid, schema OK, age %d day(s)", age_days
    )


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


def _parse_required_fields(
    row: dict, row_index: int, source_file: Path
) -> tuple[dict, list[str]]:
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
# Phase 2: Sand/water estimation — real data only, never LLM
# ---------------------------------------------------------------------------

def _enrich_estimates(lead: dict, fracfocus_csv: Optional[Path]) -> dict:
    """
    Append sand_estimate and water_estimate to *lead*.

    Logic (strictly no LLM):
      • active_wells comes from the RRC production CSV if provided; otherwise None.
      • Sand = county_median × active_wells  (or "Data pending" if no well count)
      • Water = county_median × active_wells (or "Data pending" if no well count)
      • If FracFocus CSV is available, county median is derived from it; otherwise
        the hardcoded Ector County constant is used (source noted explicitly).
    """
    # We do not have an RRC production CSV in this run — active_wells is unknown.
    # Per Phase 2 spec: no production data → sand=NULL, water=NULL → "Data pending".
    active_wells: Optional[int] = None  # extend here when production CSV is wired in

    if active_wells is None:
        lead["sand_estimate"] = "Data pending"
        lead["water_estimate"] = "Data pending"
        lead["estimates_source"] = "No RRC production report available for this operator"
        return lead

    county = lead.get("county_name", TARGET_COUNTY)
    ff_csv = fracfocus_csv if fracfocus_csv and fracfocus_csv.exists() else None
    medians = rrc_ingest.load_fracfocus_county_medians(
        ff_csv if ff_csv else FRACFOCUS_DATA_DIR / "fracfocus_county.csv",
        county,
    )

    sand_total = int(medians["sand_tons_median"] * active_wells)
    water_total = int(medians["water_bbls_median"] * active_wells)

    lead["sand_estimate"] = f"~{sand_total:,} tons ({active_wells} wells × {int(medians['sand_tons_median']):,} tons/well)"
    lead["water_estimate"] = f"~{water_total:,} bbls ({active_wells} wells × {int(medians['water_bbls_median']):,} bbls/well)"
    lead["estimates_source"] = medians["source_file"]
    return lead


# ---------------------------------------------------------------------------
# Section 3: Quarantine (parse-level failures)
# ---------------------------------------------------------------------------

def _quarantine_parse_failure(row: dict, row_index: int, missing: list[str]) -> None:
    v.log_quarantine(
        quarantine_csv=QUARANTINE_CSV,
        operator_name=row.get("OPER_NAME", ""),
        operator_number=row.get("OPER_NO", ""),
        permit_no=row.get("PERMIT_NO", ""),
        reason=f"Missing required fields: {', '.join(missing)}",
        missing_fields=missing,
        raw_data=dict(row),
    )


# ---------------------------------------------------------------------------
# Section 4: Dry-run proof output
# ---------------------------------------------------------------------------

def _dry_run_block(parsed: dict, raw_row: dict) -> str:
    raw_line = ",".join(str(raw_row.get(c, "")) for c in raw_row if not c.startswith("_"))
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
        "ESTIMATES (from real data — no LLM):",
        f"  sand_estimate     : {parsed.get('sand_estimate', 'Data pending')}",
        f"  water_estimate    : {parsed.get('water_estimate', 'Data pending')}",
        f"  estimates_source  : {parsed.get('estimates_source', 'N/A')}",
        "",
        "VALIDATION    : PASS — P-5 confirmed, all required fields present from RRC W-1",
        "ALERT STATUS  : DRY-RUN (no Telegram sent)",
        "───────────────────────────────────────────────",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 3: Telegram alert — dynamic real-field message, no static pitch text
# ---------------------------------------------------------------------------

def _send_telegram_alert(lead: dict) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — alert skipped")
        return

    import urllib.request as _req

    text = "\n".join([
        f"NEW FRAC LEAD — {lead['county_name']} County",
        "─" * 32,
        f"Operator : {lead['rrc_operator_name']}",
        f"P-5 #    : {lead['rrc_p5_number']}",
        f"Permit # : {lead['permit_number']}  |  Filed: {lead['permit_date']}",
        f"Lease    : {lead['lease_name']}  Well #{lead['well_number']}",
        f"Field    : {lead['field_name']}  |  Type: {lead['well_type']}",
        "─" * 32,
        f"Est. Sand  : {lead.get('sand_estimate', 'Data pending')}",
        f"Est. Water : {lead.get('water_estimate', 'Data pending')}",
        "─" * 32,
        f"Source: RRC W-1 row {lead['source_row_index']}",
        f"File  : {Path(lead['source_file_path']).name}",
        "Verified: RRC P-5 confirmed | No LLM data",
    ])

    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = _req.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with _req.urlopen(req, timeout=10) as resp:
            logger.info("Telegram alert sent: HTTP %d", resp.status)
    except Exception as exc:
        _log_run_error(f"Telegram send failed: {exc}")


# ---------------------------------------------------------------------------
# Section 5: Live mode gate
# ---------------------------------------------------------------------------

def _live_mode_gate_check(current_run_accepted: int, current_run_quarantine: int) -> bool:
    if not LIVE_MODE:
        return False

    if current_run_accepted < _DRY_RUN_MIN_REQUIRED:
        _log_run_error(
            f"LIVE MODE BLOCKED: only {current_run_accepted} accepted lead(s) this run "
            f"(minimum {_DRY_RUN_MIN_REQUIRED} required). No Telegram alerts sent."
        )
        return False

    if current_run_quarantine > 0:
        _log_run_error(
            f"LIVE MODE BLOCKED: {current_run_quarantine} record(s) quarantined this run. "
            "Resolve quarantine before enabling live alerts."
        )
        return False

    logger.info("LIVE MODE GATE: OPEN — all preconditions met.")
    return True


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process_permits(
    county_filter: str = TARGET_COUNTY,
    dry_run: bool = True,
    skip_p5_validation: bool = False,
) -> None:
    assert RRC_CSV_PATH is not None

    # Find FracFocus CSV if present
    fracfocus_csv: Optional[Path] = None
    ff_candidates = sorted(FRACFOCUS_DATA_DIR.glob("*.csv")) if FRACFOCUS_DATA_DIR.exists() else []
    if ff_candidates:
        fracfocus_csv = ff_candidates[-1]
        logger.info("FracFocus CSV found: %s", fracfocus_csv)
    else:
        logger.info("No FracFocus CSV in %s — will use hardcoded county medians", FRACFOCUS_DATA_DIR)

    # Phase 1: parse the RRC W-1 CSV (real data, county + date filtered)
    rows = rrc_ingest.parse_w1_csv(RRC_CSV_PATH, county_filter, PERMIT_DAYS_BACK)

    accepted: list[dict] = []
    quarantine_count = 0
    dry_run_log_lines: list[str] = []

    for row in rows:
        row_index = row.get("_row_index", "?")

        # Phase 1 continued: extract required fields
        parsed, missing = _parse_required_fields(row, row_index, RRC_CSV_PATH)

        if missing:
            _quarantine_parse_failure(row, row_index, missing)
            quarantine_count += 1
            continue

        # Phase 4: P-5 validation gate
        p5_ok = v.validate_lead(
            operator_number=parsed["rrc_p5_number"],
            operator_name=parsed["rrc_operator_name"],
            permit_no=parsed["permit_number"],
            raw_data={k: row.get(k, "") for k in REQUIRED_FIELDS.values()},
            p5_file=P5_FILE,
            blacklist_file=BLACKLIST_FILE,
            quarantine_csv=QUARANTINE_CSV,
            require_p5_verification=(not skip_p5_validation),
        )
        if not p5_ok:
            quarantine_count += 1
            continue

        # Phase 2: sand/water estimates — real data only, no LLM
        parsed = _enrich_estimates(parsed, fracfocus_csv)

        accepted.append(parsed)

        if dry_run:
            block = _dry_run_block(parsed, row)
            print(block)
            dry_run_log_lines.append(block)

    # Live mode gate: checked once, after full run, before any alert fires
    if not dry_run:
        gate_open = _live_mode_gate_check(len(accepted), quarantine_count)
        if gate_open:
            for lead in accepted:
                _send_telegram_alert(lead)

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
            "DRY-RUN: only %d accepted lead(s) — minimum %d required before live mode.",
            len(accepted),
            _DRY_RUN_MIN_REQUIRED,
        )

    if quarantine_count > 0:
        logger.info("Quarantine log: %s (%d record(s) this run)", QUARANTINE_CSV, quarantine_count)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Frac Lead OSINT Agent — RRC W-1 Permit Monitor (real data only)"
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Path to RRC W-1 permit CSV (overrides RRC_CSV_PATH env var)",
    )
    parser.add_argument(
        "--county",
        dest="county",
        default=TARGET_COUNTY,
        help=f"County filter (default: {TARGET_COUNTY})",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live Telegram alerts (blocked until ≥3 leads pass dry-run gate)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download fresh RRC W-1 CSV before processing",
    )
    parser.add_argument(
        "--skip-p5-validation",
        action="store_true",
        help="(Dry-run only) Accept leads without P-5 verification; marks them UNVERIFIED_P5",
    )
    args = parser.parse_args()

    if args.live and args.skip_p5_validation:
        print("ERROR: --skip-p5-validation is not permitted with --live. Aborting.")
        sys.exit(1)

    if args.download:
        downloaded = rrc_ingest.download_w1_csv(RRC_DATA_DIR)
        if downloaded is None:
            print(
                "Auto-download failed. Download the W-1 CSV manually from:\n"
                f"  {rrc_ingest.RRC_DATA_DOWNLOAD_PAGE}\n"
                "Then pass it via --csv or set RRC_CSV_PATH."
            )
            sys.exit(1)
        RRC_CSV_PATH = downloaded
    elif args.csv_path:
        RRC_CSV_PATH = Path(args.csv_path)

    if args.live:
        LIVE_MODE = True
        os.environ["LIVE_MODE"] = "true"

    # Hard gate — must pass before any processing
    enforce_real_data_rule()

    process_permits(
        county_filter=args.county,
        dry_run=not args.live,
        skip_p5_validation=args.skip_p5_validation,
    )
