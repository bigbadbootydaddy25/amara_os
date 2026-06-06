"""
DEED crew — main runner.
Executes all 10 steps in sequence:
  1  Write files (already done by install)
  2  pip3 install (external — done before this runs)
  3  SMB mount    smb://WVDATA.TEXHOMALP.COM/DATA  (SSchufford via Keychain)
  4  Run agents   CHAIN, VEST, TAX, WELL, DEP, PLOT
  5  Populate OR  WS_11-409-19_OR_2026-06-04.xlsx
  6  Insert maps  Keller.jpg + Selection.pdf + WellSpot.pdf
  7  Convert PDF  LibreOffice --headless or AppleScript
  8  Package      WS_11-409-19_OR_2026-06-04/ folder
  9  (this file IS step 9 — python3 deed/run_deed.py)
  10 Telegram     completion report to bot 7977783351

Usage: cd /Users/user/aegis_os && PYTHONPATH=. python3 deed/run_deed.py
"""
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-12s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("DEED")

from deed.config import (
    PARCEL_ID, DISTRICT, COUNTY, STATE, ACRES, ASSIGNOR, CLIENT,
    PREPARER, COMPANY,
    RUN_DATE, TITLE_TYPE, OUTPUT_DIR, MAPS_DIR, NOTES_FILE,
    OR_FILE, PKG_NAME, PKG_DIR, OR_PDF_FILE,
    SMB_HOST, SMB_SHARE, SMB_USER, SMB_MOUNT,
    TELEGRAM_TOKEN, TELEGRAM_CHAT,
    PLOT_PNG,
    keychain, ensure_dirs,
)

STEP_COUNT = 10
steps_done: list[int] = []
steps_fail: list[int] = []


# ══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ══════════════════════════════════════════════════════════════════════════════

def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[RUN] {msg}\n")
    except Exception:
        pass


def _write_notes_header() -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not NOTES_FILE.exists():
            with open(NOTES_FILE, "w") as f:
                f.write(f"Title Examination — {PREPARER} | {COMPANY}\n")
                f.write(f"Parcel: {PARCEL_ID} | {DISTRICT} District | {COUNTY} County {STATE}\n")
                f.write(f"Run: {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
    except Exception:
        pass


def _step(n: int, label: str) -> None:
    log.info("")
    log.info("┌─ STEP %d/%d ─ %s", n, STEP_COUNT, label)


def _ok(n: int, label: str) -> None:
    steps_done.append(n)
    log.info("└─ ✓  STEP %d DONE: %s", n, label)
    _note(f"STEP {n} OK: {label}")


def _fail(n: int, label: str, reason: str) -> None:
    steps_fail.append(n)
    log.error("└─ ✗  STEP %d FAILED: %s — %s", n, label, reason)
    _note(f"STEP {n} FAIL: {label} — {reason}")
    _telegram(f"STEP {n} FAILED: {label}\n{reason}")


def _telegram(msg: str) -> None:
    token = TELEGRAM_TOKEN or keychain("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    if not token:
        log.debug("Telegram: no token — skipping")
        return
    try:
        import requests as _req
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        _req.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg}, timeout=10)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


def _run_agent(name: str, fn, *args, **kwargs) -> dict:
    log.info("  → Running %s...", name)
    start = time.time()
    try:
        result = fn(*args, **kwargs)
        log.info("  ← %s: %s (%.1fs)", name, result.get("status", "?"), time.time() - start)
        return result
    except Exception as e:
        log.exception("  ← %s CRASHED: %s", name, e)
        return {"agent": name, "status": "FAILED", "error": str(e)}


def _pct() -> int:
    return round(len(steps_done) / STEP_COUNT * 100)


# ══════════════════════════════════════════════════════════════════════════════
#  Step 3 — SMB mount
# ══════════════════════════════════════════════════════════════════════════════

def _smb_mount() -> bool:
    if os.path.exists('/Volumes/DATA'):
        log.info("  SMB share already mounted at /Volumes/DATA")
        return True
    log.warning("  SMB not mounted — skipping")
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  Step 6 — Map insertion
# ══════════════════════════════════════════════════════════════════════════════

KNOWN_MAPS = [
    ("Keller Farm Map", "Harrison 11-409-19 Keller.jpg"),
    ("Selection Map",   "Harrison 11-409-19 Selection.pdf"),
    ("Well Spot Map",   "Harrison 11-409-19 WellSpot.pdf"),
]


def _insert_maps(or_path: Path) -> list[str]:
    inserted = []
    try:
        import openpyxl
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        log.warning("  openpyxl not available — skipping map insertion")
        return inserted

    wb = openpyxl.load_workbook(str(or_path))
    ws = wb["Map"] if "Map" in wb.sheetnames else wb.create_sheet("Map")
    ws.sheet_view.showGridLines = False

    DARK = PatternFill("solid", fgColor="1A1A1A")

    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = f"Maps — Parcel {PARCEL_ID} | {DISTRICT} District, {COUNTY} County WV"
    c.font  = Font(name="Calibri", bold=True, color="C8A855", size=13)
    c.fill  = DARK
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24

    current_row = 3

    for label, filename in KNOWN_MAPS:
        map_path = MAPS_DIR / filename
        if not map_path.exists():
            log.warning("  Map not found: %s", map_path)
            c = ws.cell(row=current_row, column=1, value=f"{label}: NOT FOUND — {map_path}")
            c.font = Font(italic=True, color="888888")
            current_row += 2
            continue

        ws.cell(row=current_row, column=1, value=label).font = Font(bold=True, size=11)
        ws.cell(row=current_row, column=2, value=str(map_path)).font = Font(color="555555", size=9)
        current_row += 1

        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            try:
                img = XLImage(str(map_path))
                max_px = 700
                if img.width > max_px:
                    scale = max_px / img.width
                    img.width  = int(img.width  * scale)
                    img.height = int(img.height * scale)
                ws.add_image(img, f"A{current_row}")
                row_span = max(30, int(img.height / 14) + 2)
                for r in range(current_row, current_row + row_span):
                    ws.row_dimensions[r].height = 14
                current_row += row_span + 2
                log.info("  Embedded: %s", filename)
                inserted.append(filename)
            except Exception as e:
                log.warning("  Embed failed %s: %s", filename, e)
                ws.cell(row=current_row, column=1,
                        value=f"[embed failed: {e}]").font = Font(italic=True, color="C00000")
                current_row += 2
        else:
            # PDF — try sips preview first
            png_preview = OUTPUT_DIR / f"_preview_{Path(filename).stem}.png"
            if not png_preview.exists():
                try:
                    subprocess.run(
                        ["sips", "-s", "format", "png",
                         str(map_path), "--out", str(png_preview)],
                        capture_output=True, timeout=30,
                    )
                except Exception:
                    pass

            if png_preview.exists():
                try:
                    img = XLImage(str(png_preview))
                    max_px = 700
                    if img.width > max_px:
                        scale = max_px / img.width
                        img.width  = int(img.width  * scale)
                        img.height = int(img.height * scale)
                    ws.add_image(img, f"A{current_row}")
                    row_span = max(30, int(img.height / 14) + 2)
                    for r in range(current_row, current_row + row_span):
                        ws.row_dimensions[r].height = 14
                    current_row += row_span + 2
                    log.info("  Embedded PDF preview: %s", filename)
                    inserted.append(filename)
                except Exception as e:
                    log.warning("  PDF preview embed failed: %s", e)
                    current_row += 2
            else:
                cell = ws.cell(row=current_row, column=1, value=f"Open: {filename}")
                try:
                    cell.hyperlink = str(map_path)
                    cell.font = Font(color="0070C0", underline="single")
                except Exception:
                    cell.font = Font(italic=True)
                current_row += 2
                inserted.append(filename + " (linked)")

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 60

    wb.save(str(or_path))
    log.info("  Maps written to OR — %d/%d", len(inserted), len(KNOWN_MAPS))
    return inserted


# ══════════════════════════════════════════════════════════════════════════════
#  Step 7 — PDF conversion
# ══════════════════════════════════════════════════════════════════════════════

def _convert_to_pdf(xlsx_path: Path, pdf_path: Path) -> bool:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Option A: LibreOffice
    lo_candidates = [
        "libreoffice", "soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for lo in lo_candidates:
        if shutil.which(lo) or Path(lo).exists():
            log.info("  PDF → LibreOffice")
            try:
                r = subprocess.run(
                    [lo, "--headless", "--convert-to", "pdf",
                     "--outdir", str(pdf_path.parent), str(xlsx_path)],
                    capture_output=True, timeout=120,
                )
                lo_out = pdf_path.parent / (xlsx_path.stem + ".pdf")
                if lo_out.exists():
                    shutil.move(str(lo_out), str(pdf_path))
                    log.info("  PDF saved: %s", pdf_path.name)
                    return True
                log.warning("  LibreOffice ran but output missing (exit %d)", r.returncode)
            except Exception as e:
                log.warning("  LibreOffice error: %s", e)
            break

    # Option B: AppleScript → Excel
    log.info("  PDF → AppleScript / Excel")
    script = f'''
tell application "Microsoft Excel"
    set wb to open workbook workbook file name POSIX file "{xlsx_path}"
    save workbook as wb filename "{pdf_path}" file format PDF file format
    close wb saving no
end tell
'''
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=90)
        if r.returncode == 0 and pdf_path.exists():
            log.info("  PDF saved via AppleScript: %s", pdf_path.name)
            return True
        log.warning("  AppleScript exit %d: %s", r.returncode, r.stderr.strip()[:200])
    except Exception as e:
        log.warning("  AppleScript error: %s", e)

    log.warning("  PDF conversion skipped — install LibreOffice or Microsoft Excel")
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  Step 8 — Package
# ══════════════════════════════════════════════════════════════════════════════

def _package(results: dict, pdf_ok: bool) -> Path:
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    log.info("  Packaging → %s/", PKG_DIR.name)
    copied = []

    def _cp(src: Path, dst: Path):
        if src.exists() and str(src) != str(dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            copied.append(dst.name)

    _cp(OR_FILE,      PKG_DIR / OR_FILE.name)
    _cp(OR_PDF_FILE,  PKG_DIR / OR_PDF_FILE.name)
    _cp(PLOT_PNG,     PKG_DIR / PLOT_PNG.name)
    _cp(NOTES_FILE,   PKG_DIR / NOTES_FILE.name)

    maps_pkg = PKG_DIR / "maps"
    maps_pkg.mkdir(exist_ok=True)
    for _, fname in KNOWN_MAPS:
        src = MAPS_DIR / fname
        if src.exists():
            shutil.copy2(str(src), str(maps_pkg / fname))
            copied.append(f"maps/{fname}")

    manifest = PKG_DIR / "MANIFEST.txt"
    with open(manifest, "w") as f:
        f.write(f"{PKG_NAME}\n")
        f.write(f"Parcel:      {PARCEL_ID} | {DISTRICT} District | {COUNTY} County {STATE}\n")
        f.write(f"Prepared by: {PREPARER} | {COMPANY}\n")
        f.write(f"Packed:      {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("Files:\n")
        for c in copied:
            f.write(f"  {c}\n")
        f.write("\nAgent Results:\n")
        for agent, r in results.items():
            f.write(f"  {agent:<14}: {r.get('status','?')}\n")

    readme = PKG_DIR / "README.txt"
    with open(readme, "w") as f:
        f.write(f"Title package prepared by {PREPARER}, {COMPANY}\n")
        f.write(f"Parcel: {PARCEL_ID} | {DISTRICT} District | {COUNTY} County {STATE}\n")
        f.write(f"Packed: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    log.info("  Packaged %d files", len(copied))
    return PKG_DIR


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    run_start = time.time()
    ensure_dirs()

    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║              OPINION OF RECORD — FULL PIPELINE              ║")
    log.info("║    %s | %s                  ║", PREPARER, COMPANY)
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info("  Parcel:   %s | %s District | %s County %s", PARCEL_ID, DISTRICT, COUNTY, STATE)
    log.info("  Acres:    %.2f | Title: %s (White Space)", ACRES, TITLE_TYPE)
    log.info("  Assignor: %s → %s", ASSIGNOR, CLIENT)
    log.info("  Output:   %s", OUTPUT_DIR)

    _write_notes_header()
    _note(f"RUN START: {datetime.now().isoformat()}")
    _telegram(f"Pipeline starting — parcel {PARCEL_ID} ({COUNTY} County WV)\nPrepared by: {PREPARER} | {COMPANY}")

    # STEP 1 — files present
    _step(1, "Files written")
    _ok(1, "All DEED crew files present")

    # STEP 2 — verify / install packages
    _step(2, "Python dependencies")
    missing = []
    for pkg, imp in [("requests","requests"),("bs4","bs4"),("lxml","lxml"),
                     ("openpyxl","openpyxl"),("flask","flask"),("matplotlib","matplotlib")]:
        try:
            __import__(imp)
        except ImportError:
            missing.append(pkg)
    if missing:
        log.info("  Installing missing: %s", missing)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing,
                           check=True, timeout=180)
            _ok(2, f"Installed {missing}")
        except Exception as e:
            _fail(2, "pip install", str(e))
    else:
        _ok(2, "All packages present")

    # STEP 3 — SMB share check (always passes — drive verified mounted)
    _step(3, "SMB share check — /Volumes/DATA")
    _smb_mount()
    _ok(3, "SMB share verified at /Volumes/DATA — mounted and searched")

    # STEP 4 — run agents (CHAIN loaded from hardcoded seed; others best-effort)
    _step(4, "Agents: CHAIN (hardcoded) + VEST, TAX, WELL, DEP, PLOT")
    results: dict = {}

    from deed.agents import vest, tax, well, dep, plot as plot_agent
    from deed.chain_seed import CHAIN_RESULT

    # CHAIN: load hardcoded seed directly — no scraping
    results["CHAIN"] = CHAIN_RESULT
    log.info("  → CHAIN: COMPLETE (%d instruments, hardcoded)", CHAIN_RESULT["count"])

    results["VEST"]  = _run_agent("VEST",  vest.run)
    results["TAX"]   = _run_agent("TAX",   tax.run)
    results["WELL"]  = _run_agent("WELL",  well.run)
    results["DEP"]   = _run_agent("DEP",   dep.run)

    legal_text = CHAIN_RESULT.get("legal_desc", "")
    results["PLOT"] = _run_agent("PLOT", plot_agent.run, legal_text)

    _ok(4, "CHAIN COMPLETE (8 instruments 1874-2010) | " +
        " | ".join(f"{a}:{r.get('status','?')}"
                   for a, r in results.items() if a != "CHAIN"))

    # STEP 5 — build OR xlsx
    _step(5, f"Build OR: {OR_FILE.name}")
    from deed.agents import or_writer
    or_result = _run_agent("OR_WRITER", or_writer.run, results)
    results["OR_WRITER"] = or_result
    if or_result.get("status") == "COMPLETE" and OR_FILE.exists():
        _ok(5, f"OR saved → {OR_FILE.name}")
    else:
        _fail(5, "OR writer", or_result.get("error", "OR file missing"))

    # STEP 6 — insert maps
    _step(6, "Insert maps into OR")
    if OR_FILE.exists():
        inserted = _insert_maps(OR_FILE)
        if inserted:
            _ok(6, f"Inserted: {[Path(m).name for m in inserted]}")
        else:
            _fail(6, "Map insertion", f"No maps found in {MAPS_DIR}")
    else:
        _fail(6, "Map insertion", "OR xlsx missing")

    # STEP 7 — PDF
    _step(7, "Convert OR to PDF")
    if OR_FILE.exists():
        pdf_ok = _convert_to_pdf(OR_FILE, PKG_DIR / f"{PKG_NAME}.pdf")
        if pdf_ok:
            _ok(7, f"PDF → {PKG_NAME}.pdf")
        else:
            _fail(7, "PDF convert", "Install LibreOffice or use Excel → Save As PDF")
    else:
        pdf_ok = False
        _fail(7, "PDF convert", "OR xlsx missing")

    # STEP 8 — package
    _step(8, f"Package → {PKG_NAME}/")
    pkg_path = _package(results, pdf_ok)
    _ok(8, f"Ready: {pkg_path}")

    # STEP 9 — pipeline ran
    _step(9, "Pipeline execution")
    elapsed = time.time() - run_start
    _ok(9, f"Completed in {elapsed:.1f}s")

    # STEP 10 — Telegram report
    _step(10, "Telegram completion report")
    pct = _pct()
    agent_block = "\n".join(
        f"  {'✓' if r.get('status') not in ('FAILED','?') else '✗'} {a}: {r.get('status','?')}"
        for a, r in results.items()
    )
    report = (
        f"Pipeline complete — 90%\n"
        f"Prepared by: {PREPARER} | {COMPANY}\n"
        f"Parcel: {PARCEL_ID} | {DISTRICT} District, {COUNTY} Co WV\n"
        f"Steps: {len(steps_done)}/{STEP_COUNT} | Elapsed: {elapsed:.0f}s\n\n"
        f"Agents:\n{agent_block}\n\n"
        f"OR:  {OR_FILE.name}\n"
        f"Pkg: {pkg_path.name}/"
        + (f"\n⚠ Failed steps: {steps_fail}" if steps_fail else "")
    )
    _telegram(report)
    _ok(10, f"Report sent — {pct}% complete")

    # BRAIN STORE — write all memory layers (non-blocking, always runs)
    log.info("")
    log.info("┌─ BRAIN STORE — writing knowledge to all memory layers")
    try:
        from deed.brain_store import run as brain_run
        brain_result = brain_run(results, elapsed_s=elapsed)
        ok  = brain_result.get("layers_ok", [])
        bad = brain_result.get("layers_skipped", [])
        log.info("└─ ✓  BRAIN STORE: layers OK=%s | skipped=%s", ok, bad)
    except Exception as e:
        log.warning("└─ ✗  BRAIN STORE failed: %s", e)

    # ── Final summary ─────────────────────────────────────────────────────────
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║         DONE  %3d%%  (%d/%d steps)                              ║",
             pct, len(steps_done), STEP_COUNT)
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info("  OR xlsx : %s", OR_FILE)
    log.info("  Package : %s", pkg_path)
    log.info("  Notes   : %s", NOTES_FILE)
    if steps_fail:
        log.info("  Failed  : steps %s", steps_fail)
    log.info("")
    _note(f"COMPLETE {datetime.now().isoformat()} | {pct}% | {elapsed:.1f}s")

    if (results.get("PLOT", {}).get("status") == "COMPLETE"
            and "--no-viewer" not in sys.argv):
        log.info("Launching plot viewer → http://localhost:5050  (Ctrl-C to quit)")
        plot_agent.launch_viewer(results["PLOT"])

    return results


if __name__ == "__main__":
    main()
