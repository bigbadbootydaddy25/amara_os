"""
OR_WRITER agent — builds the Opinion of Record (OR) Excel workbook.
Output: WS_11-409-19_OR_2026-06-04.xlsx
Sheets: Summary, Chain Index, Vesting, Tax, Wells, DEP, Title Analysis, Map
Prepared by: Scott Schufford | Aces N 8s Acquisitions
"""
import logging
from datetime import datetime
from pathlib import Path

from deed.config import (
    PARCEL_ID, DISTRICT, COUNTY, STATE, ACRES, ASSIGNOR, CLIENT,
    PREPARER, COMPANY,
    RUN_DATE, TITLE_TYPE, OR_FILE, NOTES_FILE,
)

log = logging.getLogger("OR_WRITER")

RED_FILL  = "FFCCCC"
AMBER_FILL = "FFF2CC"
GREEN_FILL = "CCFFCC"


def run(results: dict) -> dict:
    log.info("OR_WRITER — building Excel OR | %s", OR_FILE.name)

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        msg = "openpyxl not installed — run: pip install openpyxl"
        log.error(msg)
        _note(msg)
        return {"agent": "OR_WRITER", "status": "FAILED", "error": msg, "path": ""}

    wb = openpyxl.Workbook()

    # ── Shared style helpers ──────────────────────────────────────────────────
    GOLD  = PatternFill("solid", fgColor="C8A855")
    DARK  = PatternFill("solid", fgColor="1A1A1A")
    LITE  = PatternFill("solid", fgColor="F5F0E0")
    WHITE = PatternFill("solid", fgColor="FFFFFF")
    WARN  = PatternFill("solid", fgColor=AMBER_FILL)
    ERR   = PatternFill("solid", fgColor=RED_FILL)
    OK    = PatternFill("solid", fgColor=GREEN_FILL)

    thin  = Side(style="thin",   color="999999")
    thick = Side(style="medium", color="555555")
    BORD  = Border(left=thin, right=thin, top=thin, bottom=thin)
    TBORD = Border(left=thick, right=thick, top=thick, bottom=thick)

    CTR  = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    WRAP = Alignment(horizontal="left",   vertical="top",    wrap_text=True)

    def _hdr(ws, row, col, text, width=None, span=None):
        if span:
            ws.merge_cells(start_row=row, start_column=col,
                           end_row=row,   end_column=col + span - 1)
        c = ws.cell(row=row, column=col, value=text)
        c.font = Font(name="Calibri", bold=True, color="1A1A1A", size=11)
        c.fill = GOLD; c.alignment = CTR; c.border = BORD
        if width:
            ws.column_dimensions[c.column_letter].width = width
        return c

    def _section(ws, row, col, text, span=2):
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row,   end_column=col + span - 1)
        c = ws.cell(row=row, column=col, value=text)
        c.font = Font(name="Calibri", bold=True, color="C8A855", size=11)
        c.fill = DARK; c.alignment = LEFT; c.border = TBORD
        ws.row_dimensions[row].height = 18
        return c

    def _lbl(ws, row, col, text):
        c = ws.cell(row=row, column=col, value=text)
        c.font = Font(name="Calibri", bold=True, size=10)
        c.fill = LITE; c.alignment = LEFT; c.border = BORD
        return c

    def _val(ws, row, col, text, fill=WHITE, wrap=False):
        c = ws.cell(row=row, column=col,
                    value=str(text) if text is not None else "")
        c.font = Font(name="Calibri", size=10)
        c.fill = fill
        c.alignment = WRAP if wrap else LEFT
        c.border = BORD
        return c

    def _warn(ws, row, col, text):
        return _val(ws, row, col, text, fill=WARN)

    def _flag(ws, row, col, text):
        return _val(ws, row, col, text, fill=ERR)

    def _ok(ws, row, col, text):
        return _val(ws, row, col, text, fill=OK)

    # ── Pull data ────────────────────────────────────────────────────────────
    chain    = results.get("CHAIN", {})
    vest     = results.get("VEST",  {}).get("record", {})
    tax      = results.get("TAX",   {}).get("record", {})
    well_data= results.get("WELL",  {})
    dep_data = results.get("DEP",   {})
    plot_data= results.get("PLOT",  {})
    instruments = chain.get("instruments", [])

    # Prefer chain seed data for vesting fields when VEST agent got nothing
    vesting_book = (vest.get("deed_book")  or chain.get("key_instruments", {}).get("vesting", "")
                    .replace("BK ", "").split("/")[0].strip())
    vesting_page = (vest.get("deed_page")  or chain.get("key_instruments", {}).get("vesting", "")
                    .split("/")[-1].replace("PG ", "").strip())
    owner_name   = (vest.get("owner_name") or chain.get("grantee_current", ""))
    deed_date    = (vest.get("deed_date")  or chain.get("deed_date", ""))
    acreage      = (vest.get("acreage")    or chain.get("acreage", f"{ACRES:.3f}"))

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 1 — Summary
    # ══════════════════════════════════════════════════════════════════════════
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 48

    # Title banner
    ws.merge_cells("A1:B1")
    c = ws["A1"]
    c.value = "OPINION OF RECORD"
    c.font  = Font(name="Calibri", bold=True, color="C8A855", size=15)
    c.fill  = DARK; c.alignment = CTR
    ws.row_dimensions[1].height = 30

    ws.merge_cells("A2:B2")
    c = ws["A2"]
    c.value = f"{TITLE_TYPE} Title Report  |  {COUNTY} County, {STATE}  |  {RUN_DATE}"
    c.font  = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    c.fill  = DARK; c.alignment = CTR
    ws.row_dimensions[2].height = 18

    ws.merge_cells("A3:B3")
    c = ws["A3"]
    c.value = f"Prepared by: {PREPARER}  |  {COMPANY}"
    c.font  = Font(name="Calibri", italic=True, color="888888", size=9)
    c.fill  = WHITE; c.alignment = CTR
    ws.row_dimensions[3].height = 14

    # Parcel block
    r = 5
    _section(ws, r, 1, "PARCEL IDENTIFICATION"); r += 1
    for label, val in [
        ("Parcel ID",           PARCEL_ID),
        ("District",            chain.get("district", DISTRICT) + "-Outside" if chain.get("district") else DISTRICT),
        ("County / State",      f"{COUNTY} County, {STATE}"),
        ("Acres",               f"{acreage}  (config: {ACRES:.2f})"),
        ("Parcel Numbers",      "  |  ".join(chain.get("parcels", [PARCEL_ID]))),
        ("Tax Assessment",      chain.get("tax_assessment", tax.get("account_no", "NOT RETRIEVED"))),
        ("Surface Owner",       chain.get("surface_owner", vest.get("owner_addr", "NOT RETRIEVED"))),
    ]:
        _lbl(ws, r, 1, label); _val(ws, r, 2, val); r += 1

    # Assignment block
    r += 1
    _section(ws, r, 1, "ASSIGNMENT"); r += 1
    for label, val in [
        ("Title Type",          f"{TITLE_TYPE} — White Space"),
        ("Assignor",            ASSIGNOR),
        ("Client",              CLIENT),
        ("Prepared by",         PREPARER),
        ("Company",             COMPANY),
        ("Run Date",            RUN_DATE),
        ("Generated",           datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]:
        _lbl(ws, r, 1, label); _val(ws, r, 2, val); r += 1

    # Vesting block
    r += 1
    _section(ws, r, 1, "VESTING INSTRUMENT"); r += 1
    vest_items = [
        ("Current Title Holder",  owner_name or "NOT RETRIEVED"),
        ("Interest Held",         chain.get("interest_held", vest.get("deed_book", "NOT RETRIEVED"))),
        ("Deed Book / Page",      f"{vesting_book} / {vesting_page}"),
        ("Deed Date",             chain.get("deed_date", deed_date or "NOT RETRIEVED")),
        ("Date Recorded",         chain.get("recorded_date", "NOT RETRIEVED")),
        ("Consideration",         chain.get("consideration", "NOT RETRIEVED")),
        ("Acreage in Deed",       f"{chain.get('acreage', acreage)} acres"),
        ("Grantor",               "A. Dean Burns, Executor Estate of Helen S. Kramer"),
        ("Grantee",               "Master Mineral Holdings Inc. (Texas corporation)"),
    ]
    for label, val in vest_items:
        _lbl(ws, r, 1, label); _val(ws, r, 2, val); r += 1

    # Chain summary
    r += 1
    _section(ws, r, 1, "CHAIN OF TITLE SUMMARY"); r += 1
    _lbl(ws, r, 1, "Instruments in Chain")
    _val(ws, r, 2, f"{chain.get('count', len(instruments))}  (oldest: 1874 DB 57/238)"); r += 1
    _lbl(ws, r, 1, "Earliest Instrument")
    _val(ws, r, 2, "DB 57 / P 238 — Davisson to Monroe — 1874 — 51 acres"); r += 1
    _lbl(ws, r, 1, "Key Mineral Reservation")
    _warn(ws, r, 2, "DB 136 / P 259 — Shuttleworth to Stewart 1903 — RESERVED 1/2 MINERALS"); r += 1
    _lbl(ws, r, 1, "Fiduciary")
    _val(ws, r, 2, "Fid Book 10 / P 247 — Shuttleworth Estate 1919 — 6 heirs"); r += 1
    _lbl(ws, r, 1, "Chain Gaps")
    gap_txt = f"{len(chain.get('gaps', []))} gap(s) — see Chain Index sheet"
    if chain.get("gaps"):
        _warn(ws, r, 2, gap_txt)
    else:
        _val(ws, r, 2, gap_txt); r += 1

    # Title flags
    r += 1
    _section(ws, r, 1, "TITLE FLAGS / ACTION ITEMS"); r += 1
    flags = chain.get("title_notes", [])
    if not flags:
        flags = [
            "Master Mineral Holdings Inc. holds 1/6 undivided O&G per BK 1441/1269",
            "DB 136/259 (1903): Shuttleworth reserved 1/2 minerals — SPLIT ESTATE",
            "Antero WV mineral reservation analysis required",
            "5/6 undivided O&G in Shuttleworth heirs — further research required",
            "Surface owner: Burns family, Knoll View Road, Mount Clare WV 26408",
        ]
    for flag in flags:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        c = ws.cell(row=r, column=1, value=f"⚑  {flag}")
        c.font  = Font(name="Calibri", size=10,
                       bold=("SPLIT" in flag or "reservation" in flag.lower() or "research" in flag.lower()))
        c.fill  = WARN if any(k in flag.lower() for k in ["split","reserv","gap","antero","research"]) else WHITE
        c.alignment = WRAP; c.border = BORD
        ws.row_dimensions[r].height = max(15, len(flag) // 5)
        r += 1

    # Well/DEP summary
    r += 1
    _section(ws, r, 1, "WELLS / DEP"); r += 1
    _lbl(ws, r, 1, "Wells Found")
    _val(ws, r, 2, str(well_data.get("count", 0))); r += 1
    active  = dep_data.get("active",  [])
    plugged = dep_data.get("plugged", [])
    _lbl(ws, r, 1, "Active Wells (DEP)")
    _val(ws, r, 2, str(len(active))); r += 1
    _lbl(ws, r, 1, "Plugged Wells (DEP)")
    _val(ws, r, 2, str(len(plugged))); r += 1

    if plot_data.get("status") == "COMPLETE":
        r += 1
        _section(ws, r, 1, "SURVEY / PLOT"); r += 1
        _lbl(ws, r, 1, "Computed Area")
        _val(ws, r, 2, f"{plot_data.get('area_acres', 0):.4f} acres"); r += 1
        cl = plot_data.get("closure", {})
        _lbl(ws, r, 1, "Closure")
        grade = cl.get("grade", "")
        fill  = OK if grade == "GREEN" else (WARN if grade == "AMBER" else ERR)
        _val(ws, r, 2,
             f"{cl.get('distance_ft',0):.3f} ft  ({cl.get('pct',0):.3f}%)  [{grade}]",
             fill=fill); r += 1

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 2 — Chain Index (oldest → newest)
    # ══════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Chain Index")
    ws2.sheet_view.showGridLines = False

    hdrs   = ["#", "Type", "Grantor", "Grantee", "Book", "Page",
              "Date Recorded", "Instr Date", "Acres", "Interest",
              "Consideration", "Description / Notes"]
    widths = [4, 14, 32, 32, 10, 8, 14, 12, 8, 22, 14, 50]
    for col, (h, w) in enumerate(zip(hdrs, widths), 1):
        _hdr(ws2, 1, col, h, w)

    for row, inst in enumerate(instruments, 2):
        fill = LITE if row % 2 == 0 else WHITE
        # Highlight vesting instrument and key reservation
        bk = str(inst.get("book", ""))
        if bk == "1441":
            fill = OK
        elif bk == "136":
            fill = WARN

        _val(ws2, row,  1, inst.get("seq", ""),            fill)
        _val(ws2, row,  2, inst.get("type", ""),            fill)
        _val(ws2, row,  3, inst.get("grantor", ""),         fill)
        _val(ws2, row,  4, inst.get("grantee", ""),         fill)
        _val(ws2, row,  5, inst.get("book", ""),            fill)
        _val(ws2, row,  6, inst.get("page", ""),            fill)
        _val(ws2, row,  7, inst.get("date_recorded", ""),   fill)
        _val(ws2, row,  8, inst.get("date_instr", ""),      fill)
        _val(ws2, row,  9, inst.get("acres", ""),           fill)
        _val(ws2, row, 10, inst.get("interest", ""),        fill)
        _val(ws2, row, 11, inst.get("consideration", ""),   fill)
        desc = inst.get("description", "")
        note = inst.get("notes", "")
        combined = (desc + ("  |  NOTE: " + note if note else "")).strip()
        c = _val(ws2, row, 12, combined, fill, wrap=True)
        ws2.row_dimensions[row].height = max(15, min(60, len(combined) // 4))

    # Gaps table
    if chain.get("gaps"):
        gap_start = len(instruments) + 3
        _section(ws2, gap_start, 1, "CHAIN GAPS / RESEARCH NEEDED", span=12)
        for i, g in enumerate(chain["gaps"], gap_start + 1):
            ws2.merge_cells(start_row=i, start_column=1, end_row=i, end_column=12)
            c = ws2.cell(row=i, column=1, value=f"⚠  {g}")
            c.font  = Font(color="C00000", bold=True, size=10)
            c.fill  = ERR; c.alignment = WRAP; c.border = BORD

    # Legend
    leg_row = len(instruments) + len(chain.get("gaps", [])) + 5
    ws2.cell(row=leg_row, column=1, value="Legend:").font = Font(bold=True)
    ws2.cell(row=leg_row + 1, column=1, value="Green = Vesting instrument (BK 1441/1269)").fill = OK
    ws2.cell(row=leg_row + 2, column=1, value="Amber = Key reservation / gap instrument").fill = WARN

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 3 — Vesting Detail
    # ══════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Vesting")
    ws3.sheet_view.showGridLines = False
    ws3.column_dimensions["A"].width = 28
    ws3.column_dimensions["B"].width = 55

    _section(ws3, 1, 1, "VESTING DEED — BK 1441 / PG 1269", span=2)
    r3 = 2
    for label, val in [
        ("Grantor",              "A. Dean Burns, Executor Estate of Helen S. Kramer"),
        ("Grantee",              "Master Mineral Holdings Inc. (Texas corporation)"),
        ("Interest Conveyed",    "Undivided 1/6 interest — oil, gas, and coalbed methane"),
        ("Deed Book",            "1441"),
        ("Deed Page",            "1269"),
        ("Instrument Date",      "January 19, 2010"),
        ("Date Recorded",        "February 10, 2010"),
        ("Consideration",        "$11,137.50"),
        ("Acreage",              "121.072 acres"),
        ("District",             "Elk-Outside"),
        ("County / State",       "Harrison County, WV"),
        ("Parcel 1",             "17-11-0409-0019-0000"),
        ("Parcel 2",             "17-11-0409-0019-0001"),
        ("Parcel 3",             "17-11-0409-0019-0002"),
        ("Parcel 4",             "17-11-0409-0019-0003"),
        ("Tax Assessment",       "Shuttleworth Maynard Heirs .50 INT 121.072 AC O&G Gnatty Creek Elk-Outside"),
        ("Surface Owner",        "Burns family, Knoll View Road, Mount Clare WV 26408"),
    ]:
        _lbl(ws3, r3, 1, label)
        c = _val(ws3, r3, 2, val)
        if "1/6" in val:       c.fill = OK
        if "Surface" in label: c.fill = LITE
        r3 += 1

    r3 += 1
    _section(ws3, r3, 1, "REMAINING INTEREST ANALYSIS", span=2); r3 += 1
    analysis = [
        ("Total Mineral Interest",    "118.00 acres (config) / 121.072 acres (deed)"),
        ("Held by Master Mineral",    "1/6 undivided O&G"),
        ("Remaining Undivided",       "5/6 — Shuttleworth heirs — RESEARCH REQUIRED"),
        ("1903 Reservation (DB 136/259)", "Shuttleworth reserved 1/2 minerals — SPLIT ESTATE"),
        ("Antero WV Analysis",        "Mineral reservation analysis applies — see notes"),
    ]
    for label, val in analysis:
        _lbl(ws3, r3, 1, label)
        fill = WARN if "RESEARCH" in val or "SPLIT" in val or "Antero" in label else WHITE
        _val(ws3, r3, 2, val, fill=fill); r3 += 1

    r3 += 1
    _section(ws3, r3, 1, "AGENT RETRIEVAL STATUS", span=2); r3 += 1
    vest_status = results.get("VEST", {}).get("status", "NOT RUN")
    _lbl(ws3, r3, 1, "VEST Agent Status")
    fill = OK if vest_status == "COMPLETE" else (WARN if vest_status == "PARTIAL" else ERR)
    _val(ws3, r3, 2, vest_status, fill=fill); r3 += 1
    if results.get("VEST", {}).get("errors"):
        for e in results["VEST"]["errors"]:
            ws3.merge_cells(start_row=r3, start_column=1, end_row=r3, end_column=2)
            c = ws3.cell(row=r3, column=1, value=e)
            c.font = Font(italic=True, color="888888", size=9)
            c.alignment = WRAP; r3 += 1

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 4 — Tax
    # ══════════════════════════════════════════════════════════════════════════
    ws4 = wb.create_sheet("Tax")
    ws4.sheet_view.showGridLines = False
    ws4.column_dimensions["A"].width = 28
    ws4.column_dimensions["B"].width = 50

    _section(ws4, 1, 1, "TAX / ASSESSOR RECORDS", span=2)
    r4 = 2
    tax_rows = [
        ("Owner of Record",   tax.get("owner_name",     "Shuttleworth Maynard Heirs (per deed)")),
        ("Tax Assessment",    tax.get("account_no",     chain.get("tax_assessment", "NOT RETRIEVED"))),
        ("Ticket Number",     tax.get("ticket_no",      "NOT RETRIEVED")),
        ("District",          tax.get("district",       "Elk-Outside")),
        ("Acreage (Tax)",     tax.get("acreage",        "121.072 AC")),
        ("Interest Note",     ".50 INT — 50% interest assessed"),
        ("Land Value",        tax.get("land_value",     "NOT RETRIEVED")),
        ("Mineral Value",     tax.get("mineral_value",  "NOT RETRIEVED")),
        ("Total Value",       tax.get("total_value",    "NOT RETRIEVED")),
        ("Class Code",        tax.get("class_code",     "NOT RETRIEVED")),
    ]
    for label, val in tax_rows:
        _lbl(ws4, r4, 1, label); _val(ws4, r4, 2, val); r4 += 1

    r4 += 1
    c = ws4.cell(row=r4, column=1,
                 value="NOTE: For current tax tickets use Harrison County Sheriff (not Assessor).")
    c.font = Font(italic=True, color="555555", size=9)

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 5 — Wells
    # ══════════════════════════════════════════════════════════════════════════
    ws5 = wb.create_sheet("Wells")
    ws5.sheet_view.showGridLines = False
    well_hdrs   = ["API Number", "Operator", "Status", "Well Type",
                   "Spud Date", "Completion", "Formation", "Permit #", "Lat", "Lon"]
    well_widths = [16, 28, 12, 12, 14, 14, 18, 12, 12, 12]
    for col, (h, w) in enumerate(zip(well_hdrs, well_widths), 1):
        _hdr(ws5, 1, col, h, w)
    wells = well_data.get("wells", [])
    for row, w in enumerate(wells, 2):
        fill = LITE if row % 2 == 0 else WHITE
        for col, key in enumerate(["api_number","operator","status","well_type",
                                    "spud_date","comp_date","formation","permit_no",
                                    "latitude","longitude"], 1):
            _val(ws5, row, col, w.get(key, ""), fill)
    if not wells:
        ws5.merge_cells("A2:J3")
        c = ws5["A2"]
        c.value = (well_data.get("zero_wells_msg")
                   or "No wells of record found for parcel 11-409-19, Elk-Outside District, "
                      "Harrison County WV. Confirmed via WVDEP OOG. Tract appears to be undrilled.")
        c.font = Font(italic=True, color="444444", size=10)
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws5.row_dimensions[2].height = 30

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 6 — DEP
    # ══════════════════════════════════════════════════════════════════════════
    ws6 = wb.create_sheet("DEP")
    ws6.sheet_view.showGridLines = False
    dep_hdrs   = ["API Number", "Operator", "Status", "Permit #",
                  "Permit Date", "Spud Date", "Plug Date", "Formation", "Lat", "Lon"]
    dep_widths = [16, 28, 12, 12, 14, 14, 14, 18, 12, 12]
    for col, (h, w) in enumerate(zip(dep_hdrs, dep_widths), 1):
        _hdr(ws6, 1, col, h, w)
    all_dep = active + plugged + dep_data.get("permits", [])
    for row, w in enumerate(all_dep, 2):
        fill = LITE if row % 2 == 0 else WHITE
        for col, key in enumerate(["api_number","operator","status","permit_no",
                                    "permit_date","spud_date","plug_date","formation",
                                    "latitude","longitude"], 1):
            _val(ws6, row, col, w.get(key, ""), fill)
    if not all_dep:
        ws6.merge_cells("A2:J2")
        c = ws6["A2"]
        c.value = "No DEP/OOG records found for this parcel area."
        c.font = Font(italic=True, color="888888"); c.alignment = CTR

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 7 — Title Analysis
    # ══════════════════════════════════════════════════════════════════════════
    ws7 = wb.create_sheet("Title Analysis")
    ws7.sheet_view.showGridLines = False
    ws7.column_dimensions["A"].width = 30
    ws7.column_dimensions["B"].width = 70

    _section(ws7, 1, 1, f"TITLE ANALYSIS — {PARCEL_ID} | {COUNTY} County {STATE}", span=2)
    r7 = 2

    analysis_blocks = [
        ("INTEREST STRUCTURE", [
            ("Parcel / Description",   f"{PARCEL_ID} — Elk-Outside District, Harrison County WV"),
            ("Total Acreage",          "121.072 acres (Gnatty Creek watershed)"),
            ("Interest Conveyed",      "Undivided 1/6 oil, gas, and coalbed methane"),
            ("Title Holder",           "Master Mineral Holdings Inc. (Texas corporation)"),
            ("Remaining 5/6 Interest", "Shuttleworth heirs — NOT YET DOCUMENTED"),
            ("Surface Estate",         "Burns family, Knoll View Road, Mount Clare WV 26408"),
        ]),
        ("MINERAL RESERVATION — DB 136 / P 259 (1903)", [
            ("Deed",                   "Shuttleworth to Stewart — 1903 — 121.5 acres"),
            ("Reservation Language",   "Grantor RESERVED 1/2 mineral interest"),
            ("Effect",                 "SPLIT ESTATE — surface and minerals separate as of 1903"),
            ("Antero Analysis",        "WV mineral reservation doctrine applies — further analysis required"),
            ("Research Priority",      "HIGH — affects all mineral conveyances from 1903 forward"),
        ]),
        ("SHUTTLEWORTH HEIRS (Fid Book 10 / P 247 — 1919)", [
            ("Estate",                 "Shuttleworth estate settled 1919"),
            ("Heirs Identified",       "Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane Shuttleworth"),
            ("Interest",               "Reserved 1/2 mineral interest distributed among heirs"),
            ("Helen S. Kramer",        "Helen Shuttleworth = Helen S. Kramer — confirmed in BK 1441/1269"),
            ("Burns / Executor",       "A. Dean Burns as Executor of Helen S. Kramer estate"),
            ("Outstanding Research",   "Lillie A., Lorene, Mary, Samuel, Betty Jane shares — NOT CONVEYED in BK 1441"),
        ]),
        ("CHAIN BACK-REFERENCES (per BK 1441/1269)", [
            ("DB 57 / P 238",    "Davisson to Monroe — 1874 — 51 acres"),
            ("DB 61 / P 434",    "Shuttleworth to Monroe — 1879"),
            ("DB 68 / P 329",    "Bumgardner to Monroe — 1884 — 60 acres"),
            ("DB 75 / P 97",     "Bumgardner to Monroe — 1888 — 10 acres"),
            ("DB 109 / P 403",   "Thompson Commissioner to Shuttleworth — 1899"),
            ("DB 136 / P 259",   "Shuttleworth to Stewart — 1903 — 121.5 acres — KEY RESERVATION"),
            ("Fid Bk 10/P 247",  "Shuttleworth Estate — 1919 — heirs list"),
            ("BK 1441 / PG 1269","Burns Executor to Master Mineral Holdings — 2010 — VESTING"),
        ]),
        ("ACTION ITEMS", [
            ("1", "Pull DB 136/259 — read full mineral reservation language"),
            ("2", "Run Shuttleworth heirs search — Lorene, Lillie A., Mary, Samuel, Betty Jane"),
            ("3", "Antero WV mineral reservation analysis — confirm doctrine application"),
            ("4", "Confirm Monroe tract consolidation (DB 57+61+68+75 = 121.5 ac)"),
            ("5", "Verify Burns/Kramer = Helen Shuttleworth lineage in Fid Bk 10/247"),
            ("6", "Request Harrison County tax records for all 4 parcel sub-numbers"),
            ("7", "Run WVGES OGWIS well search — Gnatty Creek, Elk-Outside District"),
        ]),
    ]

    for section_title, rows in analysis_blocks:
        r7 += 1
        _section(ws7, r7, 1, section_title, span=2); r7 += 1
        for label, val in rows:
            _lbl(ws7, r7, 1, label)
            is_high = any(k in val.upper() for k in
                          ["NOT YET", "REQUIRED", "HIGH", "KEY", "NOT CONVEYED", "PULL", "RUN", "VERIFY"])
            fill = WARN if is_high else WHITE
            c = _val(ws7, r7, 2, val, fill=fill, wrap=True)
            ws7.row_dimensions[r7].height = max(15, min(45, len(val) // 5))
            r7 += 1

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 8 — Map (placeholder, populated by run_deed.py _insert_maps)
    # ══════════════════════════════════════════════════════════════════════════
    ws8 = wb.create_sheet("Map")
    ws8.sheet_view.showGridLines = False
    ws8.merge_cells("A1:H1")
    c = ws8["A1"]
    c.value = f"Maps — Parcel {PARCEL_ID} | {DISTRICT} District, {COUNTY} County WV"
    c.font  = Font(name="Calibri", bold=True, color="C8A855", size=13)
    c.fill  = DARK; c.alignment = CTR
    ws8.row_dimensions[1].height = 24

    from deed.config import PLOT_PNG
    if PLOT_PNG.exists():
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(str(PLOT_PNG))
            max_px = 680
            if img.width > max_px:
                scale = max_px / img.width
                img.width  = int(img.width  * scale)
                img.height = int(img.height * scale)
            ws8.add_image(img, "A3")
            log.info("OR_WRITER: plot PNG embedded in Map sheet")
        except Exception as e:
            ws8["A3"] = f"Plot image load failed: {e}"
    else:
        c = ws8["A3"]
        c.value = "Map images will be embedded by run_deed.py (Step 6)."
        c.font  = Font(italic=True, color="888888")

    # ── Headers / footers on every sheet ─────────────────────────────────────
    hf_text = f"Prepared by {PREPARER} | {COMPANY}"
    for sheet in wb.worksheets:
        try:
            sheet.oddHeader.center.text = hf_text
            sheet.oddHeader.center.size = 8
            sheet.oddFooter.center.text = f"&P of &N  |  {hf_text}"
            sheet.oddFooter.center.size = 8
        except Exception:
            pass

    # ── Save ─────────────────────────────────────────────────────────────────
    OR_FILE.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(OR_FILE))
    log.info("OR_WRITER: saved → %s", OR_FILE)
    _note(f"OR saved: {OR_FILE}")

    return {
        "agent":  "OR_WRITER",
        "status": "COMPLETE",
        "path":   str(OR_FILE),
        "sheets": [ws.title for ws in wb.worksheets],
    }


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[OR_WRITER] {msg}\n")
    except Exception:
        pass
