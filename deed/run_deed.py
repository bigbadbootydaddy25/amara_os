"""
AMARA DEED crew — main runner.
Usage: PYTHONPATH=. python3 deed/run_deed.py
Target: parcel 11-409-19, Elk District, Harrison County WV, 118 acres (WS title)
"""
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Logging setup (before any imports that log) ───────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-12s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("DEED")

from deed.config import (
    PARCEL_ID, DISTRICT, COUNTY, STATE, ACRES, ASSIGNOR, CLIENT,
    RUN_DATE, TITLE_TYPE, OUTPUT_DIR, NOTES_FILE,
    TELEGRAM_TOKEN, TELEGRAM_CHAT,
    ensure_dirs,
)

# ── Telegram ──────────────────────────────────────────────────────────────────

def _telegram(msg: str) -> None:
    if not TELEGRAM_TOKEN:
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg}, timeout=10)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


def _hard_fail(agent: str, reason: str) -> None:
    msg = f"[AMARA DEED] HARD FAIL — {agent}: {reason}"
    log.critical(msg)
    _telegram(msg)
    # Hard fails log but do NOT exit — collect all data possible
    _note(f"HARD FAIL: {agent}: {reason}")


# ── Note helper ───────────────────────────────────────────────────────────────

def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[RUN] {msg}\n")
    except Exception:
        pass


# ── Phase runners ─────────────────────────────────────────────────────────────

def _run_agent(name: str, fn, *args, **kwargs) -> dict:
    log.info("=" * 60)
    log.info("PHASE: %s", name)
    log.info("=" * 60)
    start = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - start
        status = result.get("status", "UNKNOWN")
        log.info("%s completed in %.1fs — status: %s", name, elapsed, status)
        if status == "FAILED":
            errs = result.get("errors", [])
            for e in errs:
                _hard_fail(name, e)
        return result
    except Exception as e:
        elapsed = time.time() - start
        msg = f"Unhandled exception after {elapsed:.1f}s: {e}"
        log.exception("%s CRASHED: %s", name, e)
        _hard_fail(name, msg)
        return {"agent": name, "status": "FAILED", "error": str(e)}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    ensure_dirs()

    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║           AMARA DEED CREW — STARTING                    ║")
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info("  Parcel:    %s", PARCEL_ID)
    log.info("  District:  %s", DISTRICT)
    log.info("  County:    %s, %s", COUNTY, STATE)
    log.info("  Acres:     %.2f", ACRES)
    log.info("  Title:     %s (White Space)", TITLE_TYPE)
    log.info("  Assignor:  %s", ASSIGNOR)
    log.info("  Client:    %s", CLIENT)
    log.info("  Run Date:  %s", RUN_DATE)
    log.info("  Output:    %s", OUTPUT_DIR)
    log.info("")

    _note(f"RUN START: {datetime.now().isoformat()}")
    _telegram(f"[AMARA DEED] Starting run for parcel {PARCEL_ID} ({COUNTY} County WV)")

    results = {}

    # ── Phase 1: Vesting (WV Property Viewer / ArcGIS) ────────────────────────
    from deed.agents import vest
    results["VEST"] = _run_agent("VEST", vest.run)

    # ── Phase 2: Chain of Title (Harrison County Clerk IDX) ───────────────────
    from deed.agents import chain
    results["CHAIN"] = _run_agent("CHAIN", chain.run)

    # ── Phase 3: Tax (Harrison County Assessor) ───────────────────────────────
    from deed.agents import tax
    results["TAX"] = _run_agent("TAX", tax.run)

    # ── Phase 4: Wells (WVGES OGWIS + WVDEP OOG) ─────────────────────────────
    from deed.agents import well
    results["WELL"] = _run_agent("WELL", well.run)

    # ── Phase 4b: DEP (WV DEP OOG TAGIS) ─────────────────────────────────────
    from deed.agents import dep
    results["DEP"] = _run_agent("DEP", dep.run)

    # ── Phase 5: Plot (Metes & Bounds — if legal desc available) ─────────────
    from deed.agents import plot as plot_agent
    legal_text = (
        results.get("CHAIN", {}).get("legal_desc", "")
        or results.get("VEST", {}).get("record", {}).get("legal_desc", "")
    )
    results["PLOT"] = _run_agent("PLOT", plot_agent.run, legal_text)

    # ── Phase 6: OR Writer ────────────────────────────────────────────────────
    from deed.agents import or_writer
    results["OR_WRITER"] = _run_agent("OR_WRITER", or_writer.run, results)

    # ── Final report ──────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║           AMARA DEED CREW — COMPLETE                    ║")
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info("  Total time: %.1fs", elapsed)
    log.info("")

    statuses = []
    for agent, r in results.items():
        status = r.get("status", "UNKNOWN")
        statuses.append(f"{agent}={status}")
        log.info("  %-12s %s", agent + ":", status)

    log.info("")
    log.info("  Notes file: %s", NOTES_FILE)
    log.info("  OR file:    %s", results.get("OR_WRITER", {}).get("path", "not generated"))

    if results.get("PLOT", {}).get("plot_png"):
        log.info("  Plot PNG:   %s", results["PLOT"]["plot_png"])

    _note(f"RUN COMPLETE: {datetime.now().isoformat()} | elapsed={elapsed:.1f}s")

    summary = (
        f"[AMARA DEED] Run complete for {PARCEL_ID}\n"
        f"Elapsed: {elapsed:.0f}s\n"
        + "\n".join(f"  {a}: {r.get('status','?')}" for a, r in results.items())
    )
    _telegram(summary)

    # ── Launch plot viewer if we have a plot ──────────────────────────────────
    if (results.get("PLOT", {}).get("status") == "COMPLETE"
            and "--no-viewer" not in sys.argv):
        log.info("")
        log.info("Launching PLOT viewer at http://localhost:5050 ...")
        log.info("(Press Ctrl+C to stop)")
        plot_agent.launch_viewer(results["PLOT"])

    return results


if __name__ == "__main__":
    main()
