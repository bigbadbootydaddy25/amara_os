"""
AMARA DEED Crew — main runner.
Executes all five agents in sequence, builds OR, sends Telegram report.

WHITE SPACE assignment: 11-409-19, Elk District, Harrison County WV
WS = no prior title on file. Chain of title may come up empty.
Assignment: Marcus Strunk RPL / Texhoma Land Partners.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from config import (
    OUTPUT_DIR, OR_FILENAME, NOTES_FILENAME,
    PARCEL_ID, PARCEL_DISTRICT, PARCEL_COUNTY, PARCEL_ACRES,
    ASSIGNMENT_FROM, ASSIGNMENT_CLIENT, RUN_DATE,
    OPENCLAW_BASE,
)
from core.logger import get_logger, write_section_header
from core.telegram_client import send, send_hard_fail

log = get_logger("DEED_RUN")

# ── Verify OpenClaw is reachable (hard fail per spec) ───────────────────────
def _check_openclaw() -> None:
    import requests
    try:
        r = requests.get(OPENCLAW_BASE + "/", timeout=5)
        if r.status_code >= 500:
            raise RuntimeError(f"OpenClaw returned HTTP {r.status_code}")
        log.info("OpenClaw reachable at %s (HTTP %s)", OPENCLAW_BASE, r.status_code)
    except requests.exceptions.ConnectionError as e:
        msg = f"OpenClaw DOWN at {OPENCLAW_BASE}: {e}"
        log.error("HARD FAIL — %s", msg)
        send_hard_fail("OpenClaw", msg)
        raise RuntimeError(msg)


def _step(name: str, fn, results: dict) -> dict:
    """Run one agent step with timing, hard-fail alerts, and result capture."""
    log.info("")
    log.info("▶ Starting %s agent...", name)
    t0 = time.time()
    try:
        r = fn()
        elapsed = time.time() - t0
        log.info("◀ %s complete in %.1fs — status: %s", name, elapsed, r.get("status", "?"))
        results[name.lower()] = r
        return r
    except Exception as e:
        elapsed = time.time() - t0
        msg = f"{name} crashed after {elapsed:.1f}s: {e}\n{traceback.format_exc()}"
        log.error(msg)
        send_hard_fail(name, str(e))
        results[name.lower()] = {"agent": name, "status": "HARD_FAIL", "errors": [str(e)]}
        return results[name.lower()]


def _build_telegram_report(results: dict, or_path: Path) -> str:
    def tick(key: str) -> str:
        s = results.get(key, {}).get("status", "NOT_RUN")
        return "✅" if s == "COMPLETE" else "❌"

    chain = results.get("chain", {})
    vest  = results.get("vest",  {})
    tax   = results.get("tax",   {})
    well  = results.get("well",  {})
    dep   = results.get("dep",   {})

    instruments = chain.get("count", 0)
    gaps        = len(chain.get("gaps", []))
    wells_found = well.get("count", 0)
    dep_found   = dep.get("count", 0)
    tax_records = tax.get("count", 0)

    # Count completed steps
    statuses    = [results.get(k, {}).get("status", "NOT_RUN") for k in ["chain","vest","tax","well","dep"]]
    complete    = sum(1 for s in statuses if s == "COMPLETE")
    pct         = int(complete / 5 * 100)

    found_items = []
    missing_items = []

    if instruments > 0:
        found_items.append(f"{instruments} instruments in chain of title")
    else:
        missing_items.append("Chain of title (White Space — no prior title found)")

    if vest.get("record"):
        v = vest["record"]
        owner = v.get("owner_name", "")
        bk    = v.get("deed_book", "")
        pg    = v.get("deed_page", "")
        found_items.append(f"Vesting: {owner} BK {bk} PG {pg}" if owner else "Vesting record (partial)")
    else:
        missing_items.append("Vesting deed BK/PG")

    if tax_records > 0:
        found_items.append(f"{tax_records} tax record(s)")
    else:
        missing_items.append("Tax records (assessor blocked)")

    if wells_found > 0:
        found_items.append(f"{wells_found} well(s) on record")
    elif well.get("status") == "COMPLETE":
        found_items.append("Wells: NONE ON RECORD (confirmed)")
    else:
        missing_items.append("Well records (WVGS blocked)")

    if dep_found > 0:
        found_items.append(f"{dep_found} DEP/OOG record(s)")
    elif dep.get("status") == "COMPLETE":
        found_items.append("DEP: NO RECORDS (confirmed)")
    else:
        missing_items.append("DEP records (tagis blocked)")

    gap_line = f"⚠ {gaps} BREAK(S) IN CHAIN" if gaps > 0 else ""

    or_note = f"OR saved: {or_path.name}" if or_path.exists() else "OR NOT CREATED"

    found_str   = "\n".join(f"  • {f}" for f in found_items)   or "  None confirmed"
    missing_str = "\n".join(f"  • {m}" for m in missing_items) or "  None"

    next_step = (
        "Run from Mac (on local IP) to access blocked WV sites. "
        "Request maps from Scott Marek at scottmarek@texhomalp.com. "
        "Upload OR + docs to Dropbox folder when complete."
    )
    if complete == 5:
        next_step = (
            f"All agents complete. Upload to Dropbox folder: "
            f"WS_{PARCEL_ID}_OR_{RUN_DATE}/"
        )

    msg = (
        f"📋 <b>DEED REPORT — {PARCEL_ID}</b>\n"
        f"<b>White Space</b> | {PARCEL_DISTRICT} District | {PARCEL_COUNTY} County WV | {PARCEL_ACRES} acres\n"
        f"Assignment: {ASSIGNMENT_FROM} / {ASSIGNMENT_CLIENT}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tick('chain')} CHAIN  {tick('vest')} VEST  "
        f"{tick('tax')} TAX  {tick('well')} WELL  {tick('dep')} DEP\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>COMPLETION: {pct}%</b>  ({complete}/5 agents)\n"
        f"{gap_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>FOUND:</b>\n{found_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>MISSING:</b>\n{missing_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>NOTES:</b> WS = no prior title. Sites blocked from cloud env.\n"
        f"{or_note}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>NEXT STEP:</b> {next_step}"
    )
    return msg


def main() -> dict:
    write_section_header(log, "AMARA DEED CREW — STARTING")
    log.info("Parcel:     %s", PARCEL_ID)
    log.info("District:   %s", PARCEL_DISTRICT)
    log.info("County:     %s County, WV", PARCEL_COUNTY)
    log.info("Acres:      %.4f", PARCEL_ACRES)
    log.info("Type:       WHITE SPACE (WS) — no prior title on file")
    log.info("Assignment: %s / %s", ASSIGNMENT_FROM, ASSIGNMENT_CLIENT)
    log.info("Run Date:   %s", RUN_DATE)
    log.info("Output Dir: %s", OUTPUT_DIR)
    log.info("")

    # Hard fail check for OpenClaw
    try:
        _check_openclaw()
    except RuntimeError:
        log.error("OpenClaw hard fail — agents will run without LLM synthesis")
        # Per spec: hard fail fires Telegram. Agents continue for data collection.

    results = {}
    or_path = OUTPUT_DIR / OR_FILENAME

    # ── Run all five agents ────────────────────────────────────────────────
    from deed.agents.chain_agent import ChainAgent
    from deed.agents.vest_agent  import VestAgent
    from deed.agents.tax_agent   import TaxAgent
    from deed.agents.well_agent  import WellAgent
    from deed.agents.dep_agent   import DepAgent

    _step("CHAIN", ChainAgent().run, results)
    _step("VEST",  VestAgent().run,  results)
    _step("TAX",   TaxAgent().run,   results)
    _step("WELL",  WellAgent().run,  results)
    _step("DEP",   DepAgent().run,   results)

    # ── Build OR spreadsheet ───────────────────────────────────────────────
    write_section_header(log, "BUILDING OR SPREADSHEET")
    try:
        from deed.or_builder import build_or
        or_path = build_or(results)
        log.info("OR saved: %s", or_path)
    except Exception as e:
        log.error("OR build failed: %s", e)
        send_hard_fail("OR_BUILDER", str(e))

    # ── Save JSON results ──────────────────────────────────────────────────
    json_path = OUTPUT_DIR / f"DEED_RESULTS_{PARCEL_ID}_{RUN_DATE}.json"
    try:
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        log.info("Results JSON: %s", json_path)
    except Exception as e:
        log.error("JSON save failed: %s", e)

    # ── Send Telegram completion report ────────────────────────────────────
    write_section_header(log, "SENDING TELEGRAM REPORT")
    telegram_msg = _build_telegram_report(results, or_path)
    send(telegram_msg)
    log.info("")
    log.info("=== DEED CREW COMPLETE ===")
    log.info("OR:    %s", or_path)
    log.info("Notes: %s", OUTPUT_DIR / NOTES_FILENAME)
    log.info("JSON:  %s", json_path)

    return results


if __name__ == "__main__":
    main()
