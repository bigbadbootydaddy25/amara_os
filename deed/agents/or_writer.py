"""
OR_WRITER agent — builds the Opinion of Record (OR) Excel workbook.
Output: WS_11-409-19_OR_2026-06-04.xlsx
Sheets: Summary, Index, Vesting, Tax, Wells, DEP, Map
"""
import logging
from datetime import datetime
from pathlib import Path

from deed.config import (
    PARCEL_ID, DISTRICT, COUNTY, STATE, ACRES, ASSIGNOR, CLIENT,
    RUN_DATE, TITLE_TYPE, OR_FILE, NOTES_FILE,
)

log = logging.getLogger("OR_WRITER")


def run(results: dict) -> dict:
    log.info("OR_WRITER — building Excel OR | %s", OR_FILE.name)

    try:
        import openpyxl
        from openpyxl.styles import (
            Font, PatternFill, Alignment, Border, Side,
        )
    except ImportError:
        msg = "openpyxl not installed — run: pip install openpyxl"
        log.error(msg)
        _note(msg)
        return {"agent": "OR_WRITER", "status": "FAILED", "error": msg, "path": ""}

    wb = openpyxl.Workbook()

    # ── Style helpers ─────────────────────────────────────────────────────────
    GOLD   = PatternFill("solid", fgColor="C8A855")
    DARK   = PatternFill("solid", fgColor="1A1A1A")
    LITE   = PatternFill("solid", fgColor="F5F0E0")
    GRAY   = PatternFill("solid", fgColor="DDDDDD")
    WHITE  = PatternFill("solid", fgColor="FFFFFF")
    HDRF   = Font(name="Calibri", bold=True, color="1A1A1A", size=11)
    TITF   = Font(name="Calibri", bold=True, color="C8A855", size=14)
    LBLF   = Font(name="Calibri", bold=True, size=10)
    VALF   = Font(name="Calibri", size=10)
    CTR    = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    thin   = Side(style="thin", color="999999")
    BORD   = Border(left=thin, right=thin, top=thin, bottom=thin)

    def _hdr(ws, row, col, text, width=None):
        c = ws.cell(row=row, column=col, value=text)
        c.font = HDRF; c.fill = GOLD; c.alignment = CTR; c.border = BORD
        if width:
            ws.column_dimensions[c.column_letter].width = width
        return c

    def _lbl(ws, row, col, text):
        c = ws.cell(row=row, column=col, value=text)
        c.font = LBLF; c.fill = LITE; c.alignment = LEFT; c.border = BORD
        return c

    def _val(ws, row, col, text, fill=WHITE):
        c = ws.cell(row=row, column=col, value=str(text) if text is not None else "")
        c.font = VALF; c.fill = fill; c.alignment = LEFT; c.border = BORD
        return c

    # ── Sheet 1: Summary ─────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False

    # Title block
    ws.merge_cells("A1:F1")
    t = ws["A1"]
    t.value = "AMARA DEED — OPINION OF RECORD"
    t.font = TITF; t.fill = DARK; t.alignment = CTR

    ws.merge_cells("A2:F2")
    s = ws["A2"]
    s.value = f"{TITLE_TYPE} Title Report | {COUNTY} County, {STATE} | {RUN_DATE}"
    s.font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    s.fill = DARK; s.alignment = CTR

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 18

    info = [
        ("Parcel ID",     PARCEL_ID),
        ("District",      DISTRICT),
        ("County",        COUNTY),
        ("State",         STATE),
        ("Acres",         f"{ACRES:.2f}"),
        ("Title Type",    TITLE_TYPE),
        ("Assignor",      ASSIGNOR),
        ("Client",        CLIENT),
        ("Run Date",      RUN_DATE),
        ("Generated",     datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]

    # Vesting data
    vest = results.get("VEST", {}).get("record", {})
    info += [
        ("Current Owner",    vest.get("owner_name", "NOT RETRIEVED")),
        ("Owner Address",    vest.get("owner_addr", "NOT RETRIEVED")),
        ("Vesting Deed Bk",  vest.get("deed_book",  "NOT RETRIEVED")),
        ("Vesting Deed Pg",  vest.get("deed_page",  "NOT RETRIEVED")),
        ("Deed Date",        vest.get("deed_date",  "NOT RETRIEVED")),
        ("Acreage (Vesting)", vest.get("acreage",   "NOT RETRIEVED")),
    ]

    # Tax data
    tax = results.get("TAX", {}).get("record", {})
    info += [
        ("Tax Account #",   tax.get("account_no", "NOT RETRIEVED")),
        ("Tax Ticket #",    tax.get("ticket_no",  "NOT RETRIEVED")),
        ("Land Value",      tax.get("land_value", "NOT RETRIEVED")),
        ("Mineral Value",   tax.get("mineral_value", "NOT RETRIEVED")),
    ]

    for i, (label, value) in enumerate(info, start=4):
        _lbl(ws, i, 1, label)
        _val(ws, i, 2, value)

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 40

    # Chain summary
    chain = results.get("CHAIN", {})
    chain_row = len(info) + 5
    _hdr(ws, chain_row, 1, "Chain of Title Summary")
    _val(ws, chain_row, 2, f"{chain.get('count', 0)} instruments found")
    _lbl(ws, chain_row + 1, 1, "Gaps Detected")
    _val(ws, chain_row + 1, 2, str(len(chain.get("gaps", []))))
    _lbl(ws, chain_row + 2, 1, "Title Type")
    _val(ws, chain_row + 2, 2, "WS — White Space (no prior title on file)")

    # Well summary
    well_data = results.get("WELL", {})
    well_row  = chain_row + 4
    _hdr(ws, well_row, 1, "Well Summary")
    _val(ws, well_row, 2, f"{well_data.get('count', 0)} wells found")

    # DEP summary
    dep_data = results.get("DEP", {})
    dep_row  = well_row + 2
    _hdr(ws, dep_row, 1, "DEP/OOG Summary")
    active  = dep_data.get("active", [])
    plugged = dep_data.get("plugged", [])
    _lbl(ws, dep_row + 1, 1, "Active Wells")
    _val(ws, dep_row + 1, 2, str(len(active)))
    _lbl(ws, dep_row + 2, 1, "Plugged Wells")
    _val(ws, dep_row + 2, 2, str(len(plugged)))

    # Plot summary
    plot_data = results.get("PLOT", {})
    if plot_data.get("status") == "COMPLETE":
        plot_row = dep_row + 4
        _hdr(ws, plot_row, 1, "Survey / Plot")
        _lbl(ws, plot_row + 1, 1, "Computed Area")
        _val(ws, plot_row + 1, 2, f"{plot_data.get('area_acres', 0):.4f} acres")
        _lbl(ws, plot_row + 2, 1, "Closure")
        cl = plot_data.get("closure", {})
        _val(ws, plot_row + 2, 2,
             f"{cl.get('distance_ft', 0):.3f} ft ({cl.get('pct', 0):.3f}%) [{cl.get('grade','—')}]")

    # ── Sheet 2: Chain Index ──────────────────────────────────────────────────
    ws2 = wb.create_sheet("Chain Index")
    ws2.sheet_view.showGridLines = False
    hdrs = ["#", "Type", "Grantor", "Grantee", "Book", "Page",
            "Date Recorded", "Date Instr", "Description", "Doc URL"]
    widths = [5, 18, 25, 25, 8, 8, 14, 14, 40, 30]
    for col, (h, w) in enumerate(zip(hdrs, widths), 1):
        _hdr(ws2, 1, col, h, w)

    instruments = chain.get("instruments", [])
    for row, inst in enumerate(instruments, 2):
        fill = LITE if row % 2 == 0 else WHITE
        _val(ws2, row, 1, inst.get("seq", ""), fill)
        _val(ws2, row, 2, inst.get("type", ""), fill)
        _val(ws2, row, 3, inst.get("grantor", ""), fill)
        _val(ws2, row, 4, inst.get("grantee", ""), fill)
        _val(ws2, row, 5, inst.get("book", ""), fill)
        _val(ws2, row, 6, inst.get("page", ""), fill)
        _val(ws2, row, 7, inst.get("date_recorded", ""), fill)
        _val(ws2, row, 8, inst.get("date_instr", ""), fill)
        _val(ws2, row, 9, inst.get("description", ""), fill)
        _val(ws2, row, 10, inst.get("doc_url", ""), fill)

    if not instruments:
        ws2.merge_cells("A2:J2")
        c = ws2["A2"]
        c.value = ("WS (White Space) — No instruments on file. "
                   "Confirm with Harrison County Clerk.")
        c.font = Font(italic=True, color="888888")
        c.alignment = CTR

    # Chain gaps sub-table
    if chain.get("gaps"):
        gap_row = max(len(instruments) + 3, 3)
        ws2.cell(row=gap_row, column=1, value="CHAIN GAPS").font = Font(bold=True, color="C00000")
        for i, g in enumerate(chain["gaps"], gap_row + 1):
            ws2.cell(row=i, column=1, value=g).font = Font(color="C00000")

    # ── Sheet 3: Vesting ──────────────────────────────────────────────────────
    ws3 = wb.create_sheet("Vesting")
    ws3.sheet_view.showGridLines = False
    _hdr(ws3, 1, 1, "Vesting Deed Information", 30)
    _hdr(ws3, 1, 2, "Value", 50)
    for i, (label, key) in enumerate([
        ("Owner Name",        "owner_name"),
        ("Owner Address",     "owner_addr"),
        ("Deed Book",         "deed_book"),
        ("Deed Page",         "deed_page"),
        ("Deed Date",         "deed_date"),
        ("Legal Description", "legal_desc"),
        ("Acreage",           "acreage"),
        ("District",          "district"),
        ("Account Number",    "account_no"),
        ("Map Number",        "map_number"),
        ("Parcel ID",         "parcel_id"),
    ], start=2):
        _lbl(ws3, i, 1, label)
        _val(ws3, i, 2, vest.get(key, "NOT RETRIEVED"))

    vest_status = results.get("VEST", {}).get("status", "UNKNOWN")
    ws3.cell(row=14, column=1, value=f"Agent Status: {vest_status}").font = LBLF
    if results.get("VEST", {}).get("errors"):
        ws3.cell(row=15, column=1, value="Errors:").font = LBLF
        for j, e in enumerate(results["VEST"]["errors"], 16):
            ws3.cell(row=j, column=1, value=e).font = Font(color="C00000", italic=True)

    # ── Sheet 4: Tax ──────────────────────────────────────────────────────────
    ws4 = wb.create_sheet("Tax")
    ws4.sheet_view.showGridLines = False
    _hdr(ws4, 1, 1, "Tax / Assessor Information", 30)
    _hdr(ws4, 1, 2, "Value", 50)
    for i, (label, key) in enumerate([
        ("Owner Name",     "owner_name"),
        ("Account Number", "account_no"),
        ("Ticket Number",  "ticket_no"),
        ("District",       "district"),
        ("Land Value",     "land_value"),
        ("Mineral Value",  "mineral_value"),
        ("Total Value",    "total_value"),
        ("Class Code",     "class_code"),
    ], start=2):
        _lbl(ws4, i, 1, label)
        _val(ws4, i, 2, tax.get(key, "NOT RETRIEVED"))

    ws4.cell(row=11, column=1,
             value="NOTE: For tax ticket records use Harrison County Sheriff, not Assessor.").font = Font(
        italic=True, color="555555")

    # ── Sheet 5: Wells ────────────────────────────────────────────────────────
    ws5 = wb.create_sheet("Wells")
    ws5.sheet_view.showGridLines = False
    well_hdrs = ["API Number", "Operator", "Status", "Well Type",
                 "Spud Date", "Completion", "Formation", "Permit #", "Lat", "Lon"]
    well_widths = [15, 28, 12, 12, 14, 14, 18, 12, 12, 12]
    for col, (h, w) in enumerate(zip(well_hdrs, well_widths), 1):
        _hdr(ws5, 1, col, h, w)

    wells = well_data.get("wells", [])
    for row, w in enumerate(wells, 2):
        fill = LITE if row % 2 == 0 else WHITE
        _val(ws5, row, 1,  w.get("api_number", ""), fill)
        _val(ws5, row, 2,  w.get("operator", ""), fill)
        _val(ws5, row, 3,  w.get("status", ""), fill)
        _val(ws5, row, 4,  w.get("well_type", ""), fill)
        _val(ws5, row, 5,  w.get("spud_date", ""), fill)
        _val(ws5, row, 6,  w.get("comp_date", ""), fill)
        _val(ws5, row, 7,  w.get("formation", ""), fill)
        _val(ws5, row, 8,  w.get("permit_no", ""), fill)
        _val(ws5, row, 9,  w.get("latitude", ""), fill)
        _val(ws5, row, 10, w.get("longitude", ""), fill)

    if not wells:
        ws5.merge_cells("A2:J2")
        c = ws5["A2"]
        c.value = "No wells found — verify with WVGES OGWIS and WVDEP OOG directly."
        c.font = Font(italic=True, color="888888")
        c.alignment = CTR

    # ── Sheet 6: DEP ─────────────────────────────────────────────────────────
    ws6 = wb.create_sheet("DEP")
    ws6.sheet_view.showGridLines = False
    dep_hdrs = ["API Number", "Operator", "Status", "Permit #",
                "Permit Date", "Spud Date", "Plug Date", "Formation", "Lat", "Lon"]
    dep_widths = [15, 28, 12, 12, 14, 14, 14, 18, 12, 12]
    for col, (h, w) in enumerate(zip(dep_hdrs, dep_widths), 1):
        _hdr(ws6, 1, col, h, w)

    all_dep = active + plugged + dep_data.get("permits", [])
    for row, w in enumerate(all_dep, 2):
        fill = LITE if row % 2 == 0 else WHITE
        _val(ws6, row, 1,  w.get("api_number", ""), fill)
        _val(ws6, row, 2,  w.get("operator", ""), fill)
        _val(ws6, row, 3,  w.get("status", ""), fill)
        _val(ws6, row, 4,  w.get("permit_no", ""), fill)
        _val(ws6, row, 5,  w.get("permit_date", ""), fill)
        _val(ws6, row, 6,  w.get("spud_date", ""), fill)
        _val(ws6, row, 7,  w.get("plug_date", ""), fill)
        _val(ws6, row, 8,  w.get("formation", ""), fill)
        _val(ws6, row, 9,  w.get("latitude", ""), fill)
        _val(ws6, row, 10, w.get("longitude", ""), fill)

    if not all_dep:
        ws6.merge_cells("A2:J2")
        c = ws6["A2"]
        c.value = "No DEP/OOG records found for this parcel area."
        c.font = Font(italic=True, color="888888")
        c.alignment = CTR

    # ── Sheet 7: Map (placeholder / plot embed) ───────────────────────────────
    ws7 = wb.create_sheet("Map")
    ws7.sheet_view.showGridLines = False
    ws7.merge_cells("A1:E1")
    t7 = ws7["A1"]
    t7.value = f"Plot / Map — Parcel {PARCEL_ID}"
    t7.font = TITF; t7.fill = DARK; t7.alignment = CTR

    plot_png = plot_data.get("plot_png", "")
    if plot_png and Path(plot_png).exists():
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(plot_png)
            img.width  = 600
            img.height = 600
            ws7.add_image(img, "A3")
            log.info("OR_WRITER: plot image embedded in Map sheet")
        except Exception as e:
            log.warning("OR_WRITER: could not embed plot image: %s", e)
            ws7["A3"] = f"Plot image: {plot_png}"
    else:
        ws7["A3"] = ("No plot image available. "
                     "Run PLOT agent with legal description to generate.")
        ws7["A3"].font = Font(italic=True, color="888888")

    # ── Save ─────────────────────────────────────────────────────────────────
    OR_FILE.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(OR_FILE))
    log.info("OR_WRITER: saved → %s", OR_FILE)
    _note(f"OR saved: {OR_FILE}")

    return {
        "agent":  "OR_WRITER",
        "status": "COMPLETE",
        "path":   str(OR_FILE),
        "sheets": ["Summary", "Chain Index", "Vesting", "Tax", "Wells", "DEP", "Map"],
    }


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[OR_WRITER] {msg}\n")
    except Exception:
        pass
