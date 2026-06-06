"""
Builds the corrected OR for parcel 11-409-19 in Marcus Strunk's exact format.
Three sheets: 11-409-19 (full OR) | Index (chain) | Map (placeholder)
Output: WS_11-409-19_OR_2026-06-04_CORRECTED.xlsx

Usage: cd /Users/user/aegis_os && PYTHONPATH=. python3 deed/build_marcus_or.py
"""
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("MARCUS_OR")

_BASE      = Path(os.getenv("DEED_BASE", "/Users/user/aegis_os/deed"))
OUTPUT_DIR = _BASE / "output"
OUT_FILE   = OUTPUT_DIR / "WS_11-409-19_OR_2026-06-04_CORRECTED.xlsx"

# ── Color palette (matches Marcus's dark OR style) ────────────────────────────
C_DARK   = "1A1A1A"   # near-black section headers
C_NAVY   = "1F3864"   # deep navy table headers
C_GOLD   = "C8A855"   # gold text
C_WHITE  = "FFFFFF"
C_LITE   = "F5F0E0"   # warm cream alternating rows
C_AMBER  = "FFF2CC"   # research-required flag
C_GREEN  = "CCFFCC"   # ok / vesting
C_RED    = "FFCCCC"   # error
C_GRAY   = "F2F2F2"   # light alternating


def build():
    try:
        import openpyxl
        from openpyxl.styles import (Font, PatternFill, Alignment,
                                     Border, Side, numbers)
    except ImportError:
        log.error("openpyxl not installed — pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.Workbook()

    def _fill(hex_color):
        return PatternFill("solid", fgColor=hex_color)

    thin   = Side(style="thin",   color="AAAAAA")
    thick  = Side(style="medium", color="555555")
    BORD   = Border(left=thin, right=thin, top=thin, bottom=thin)
    TBORD  = Border(left=thick, right=thick, top=thick, bottom=thick)
    CTR    = Alignment(horizontal="center", vertical="center",  wrap_text=True)
    LEFT   = Alignment(horizontal="left",   vertical="center",  wrap_text=True)
    WRAP   = Alignment(horizontal="left",   vertical="top",     wrap_text=True)

    def _font(bold=False, color=C_DARK, size=10, italic=False, name="Calibri"):
        return Font(name=name, bold=bold, color=color, size=size, italic=italic)

    NUM_COLS = 6  # A B C D E F

    def _merge_row(ws, row, col_start, col_end, value, bg, fg, sz=10,
                   bold=False, align=LEFT, border=BORD, height=None):
        ws.merge_cells(start_row=row, start_column=col_start,
                       end_row=row,   end_column=col_end)
        c = ws.cell(row=row, column=col_start, value=value)
        c.font      = Font(name="Calibri", bold=bold, color=fg, size=sz)
        c.fill      = _fill(bg)
        c.alignment = align
        c.border    = border
        if height:
            ws.row_dimensions[row].height = height
        return c

    def _section(ws, row, text, height=18):
        _merge_row(ws, row, 1, NUM_COLS, text, C_DARK, C_GOLD,
                   sz=11, bold=True, align=LEFT, border=TBORD, height=height)

    def _lv(ws, row, label, value, label_fill=C_LITE, val_fill=C_WHITE,
            val_bold=False, val_color=C_DARK, val_col_span=5, height=15):
        """Label in col A, value merged across remaining cols."""
        c_lbl = ws.cell(row=row, column=1, value=label)
        c_lbl.font      = _font(bold=True, size=10)
        c_lbl.fill      = _fill(label_fill)
        c_lbl.alignment = LEFT
        c_lbl.border    = BORD

        ws.merge_cells(start_row=row, start_column=2,
                       end_row=row,   end_column=val_col_span + 1)
        c_val = ws.cell(row=row, column=2, value=value)
        c_val.font      = Font(name="Calibri", bold=val_bold,
                               color=val_color, size=10)
        c_val.fill      = _fill(val_fill)
        c_val.alignment = WRAP
        c_val.border    = BORD
        ws.row_dimensions[row].height = height
        return c_lbl, c_val

    def _blank(ws, row, height=6):
        ws.row_dimensions[row].height = height

    def _tbl_hdr(ws, row, cols_labels, col_start=1):
        for i, lbl in enumerate(cols_labels):
            c = ws.cell(row=row, column=col_start + i, value=lbl)
            c.font      = Font(name="Calibri", bold=True, color=C_WHITE, size=9)
            c.fill      = _fill(C_NAVY)
            c.alignment = CTR
            c.border    = BORD
        ws.row_dimensions[row].height = 16

    def _tbl_row(ws, row, values, col_start=1, alt=False, fill_override=None):
        bg = fill_override or (C_LITE if alt else C_WHITE)
        for i, v in enumerate(values):
            c = ws.cell(row=row, column=col_start + i, value=v)
            c.font      = Font(name="Calibri", size=9)
            c.fill      = _fill(bg)
            c.alignment = WRAP
            c.border    = BORD
        ws.row_dimensions[row].height = max(14, min(40,
            max((len(str(v)) // 20 for v in values if v), default=1) * 14))

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 1 — 11-409-19  (Main OR in Marcus format)
    # ══════════════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "11-409-19"
    ws1.sheet_view.showGridLines = False
    ws1.page_setup.orientation   = "landscape"

    # Column widths
    for col, w in zip("ABCDEF", [24, 32, 16, 13, 16, 34]):
        ws1.column_dimensions[col].width = w

    r = 1

    # ── Title banner ──────────────────────────────────────────────────────────
    _merge_row(ws1, r, 1, NUM_COLS, "OPINION OF RECORD",
               C_DARK, C_GOLD, sz=16, bold=True, align=CTR, height=32); r += 1
    _merge_row(ws1, r, 1, NUM_COLS, "Scott Schufford  |  Aces N 8s",
               C_DARK, C_WHITE, sz=10, bold=False, align=CTR, height=16); r += 1
    _blank(ws1, r); r += 1

    # ── Parcel identification ─────────────────────────────────────────────────
    _section(ws1, r, "PARCEL IDENTIFICATION"); r += 1
    fields = [
        ("PROSPECT",        "Elk"),
        ("TRID",            "WS"),
        ("UNIT",            "None"),
        ("TAX PARCEL ID",   "11-409-19"),
        ("GROSS ACRES",     "121.072"),
        ("DISTRICT",        "Elk-Outside"),
        ("COUNTY",          "Harrison"),
        ("STATE",           "WV"),
        ("PREPARED BY",     "Scott Schufford"),
        ("DATE",            "06/04/2026"),
        ("LAST BK/PG",      "DB 1441/1269  dated  01/19/2010"),
    ]
    for lbl, val in fields:
        _lv(ws1, r, lbl, val); r += 1

    _blank(ws1, r); r += 1

    # ── Surface owner ─────────────────────────────────────────────────────────
    _section(ws1, r, "SURFACE OWNER"); r += 1
    for line in ["Burns family", "Knoll View Road", "Mount Clare WV 26408", "TMP 11-409-19"]:
        _lv(ws1, r, "", line, label_fill=C_WHITE); r += 1

    _blank(ws1, r); r += 1

    # ── Acquired title ────────────────────────────────────────────────────────
    _section(ws1, r, "TITLE"); r += 1
    _lv(ws1, r, "ACQUIRED TITLE", "DB 1441/1269"); r += 1

    _blank(ws1, r); r += 1

    # ── Mineral owners ────────────────────────────────────────────────────────
    _section(ws1, r, "MINERAL OWNERS"); r += 1
    _tbl_hdr(ws1, r, ["OWNER", "INTEREST", "NET ACRES", "STATUS", "INSTRUMENT", "NOTES"]); r += 1
    _tbl_row(ws1, r, ["Master Mineral Holdings Inc. (Texas corporation)",
                       "1/6", "20.179", "UNLEASED", "DB 1441/1269", ""],
             fill_override=C_GREEN); r += 1
    _tbl_row(ws1, r, ["Shuttleworth heirs (5 of 6 — Lillie A., Lorene, Mary, Samuel, Betty Jane)",
                       "5/6", "100.893", "UNLEASED", "RESEARCH REQUIRED", "Heir chain incomplete"],
             fill_override=C_AMBER); r += 1
    # Total row
    _tbl_row(ws1, r, ["TOTAL", "1.0", "121.072", "", "", ""]); r += 1

    _blank(ws1, r); r += 1

    # ── Working interest owners ───────────────────────────────────────────────
    _section(ws1, r, "WORKING INTEREST OWNERS"); r += 1
    _tbl_hdr(ws1, r, ["STATUS", "DECIMAL", "GROSS ACRES", "DESCRIPTION", "", ""]); r += 1
    _tbl_row(ws1, r, ["UNLEASED", "1.0", "121.072", "White Space — no active OGL of record", "", ""]); r += 1

    _blank(ws1, r); r += 1

    # ── Leasehold block ───────────────────────────────────────────────────────
    _section(ws1, r, "LEASEHOLD / ASSIGNMENTS"); r += 1
    _lv(ws1, r, "ORRI",               "Subject to None"); r += 1
    _lv(ws1, r, "LEASEHOLD",
        "No active OGL of record — White Space tract — UNLEASED",
        val_fill=C_AMBER); r += 1
    _lv(ws1, r, "ASSIGNMENTS",        "None"); r += 1
    _lv(ws1, r, "UNRELEASED OGLs",    "None"); r += 1

    _blank(ws1, r); r += 1

    # ── Production data ───────────────────────────────────────────────────────
    _section(ws1, r, "PRODUCTION DATA"); r += 1
    _tbl_hdr(ws1, r, ["API#", "DRILLING OPERATOR", "SPUD DATE",
                       "STATUS", "LAST REPORTED PROD", "DEP STATUS"]); r += 1
    wells = [
        ("47-033-01920", "Diversified Production LLC", "1978",
         "Active", "1,221 MCF — 2024", "Active — no plugging date"),
        ("47-033-04093", "Diversified Production LLC", "1995",
         "Active — adjacent parcel", "759 MCF — 2024", "Active"),
        ("47-033-05416", "Key Oil Company",            "07/26/2010",
         "Active — north adjacent (Simpson District)", "2,254 MCF — 2024",
         "Active — no plugging date"),
    ]
    for i, w in enumerate(wells):
        _tbl_row(ws1, r, list(w), alt=(i % 2 == 1)); r += 1

    _blank(ws1, r); r += 1

    # ── Notes ─────────────────────────────────────────────────────────────────
    _section(ws1, r, "NOTES"); r += 1
    note1 = ("NOTE 1 — SOURCE DEED:  DB 1441/1269 — January 19, 2010 — Burns, A. Dean, "
             "Executor Estate of Helen S. Kramer → Master Mineral Holdings Inc. — "
             "Undivided 1/6 oil, gas, and coalbed methane — Elk-Outside District — "
             "Harrison County WV — 121.072 acres — Gnatty Creek watershed.")
    note2 = ("NOTE 2 — EXAMINER NOTES:  White Space tract — chain built from scratch. "
             "Key finding: DB 136/259 (1903) Shuttleworth to Stewart reserved 1/2 minerals — "
             "SPLIT ESTATE. Master Mineral Holdings holds 1/6 undivided O&G. "
             "Remaining 5/6 Shuttleworth heirs research required. "
             "Well data corrected via coordinate radius search — initial parcel ID search "
             "returned zero which is a known TAGIS limitation.")
    for note in [note1, note2]:
        ws1.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NUM_COLS)
        c = ws1.cell(row=r, column=1, value=note)
        c.font      = Font(name="Calibri", size=9, italic=True, color=C_DARK)
        c.fill      = _fill(C_LITE)
        c.alignment = WRAP
        c.border    = BORD
        ws1.row_dimensions[r].height = 40; r += 1

    _blank(ws1, r); r += 1

    # ── Easements / mortgages ─────────────────────────────────────────────────
    _section(ws1, r, "EASEMENTS / MORTGAGES"); r += 1
    _lv(ws1, r, "EASEMENTS",           "Not examined"); r += 1
    _lv(ws1, r, "UNRELEASED MORTGAGES","Only if they apply to minerals"); r += 1

    _blank(ws1, r); r += 1

    # ── Tax assessment — surface ──────────────────────────────────────────────
    _section(ws1, r, "TAX ASSESSMENT DATA — SURFACE"); r += 1
    tax_surface = [
        ("ACCT NO",       "pending"),
        ("TICKET NO",     "pending"),
        ("NAME",          "Burns family"),
        ("DESCRIPTION",   "Elk-Outside District parcel 11-409-19"),
        ("MAP/PARCEL",    "409-0019-0000-000"),
        ("LAND VALUE",    "pending — pull from Harrison County Sheriff"),
        ("MINERAL VALUE", "pending"),
        ("CLASS",         "pending"),
        ("TAXES",         "pending"),
    ]
    for lbl, val in tax_surface:
        _lv(ws1, r, lbl, val); r += 1

    _blank(ws1, r); r += 1

    # ── Tax assessment — O&G ──────────────────────────────────────────────────
    _section(ws1, r, "TAX ASSESSMENT DATA — OIL AND GAS"); r += 1
    tax_og = [
        ("NAME",          "Shuttleworth Maynard Heirs"),
        ("DESCRIPTION",   ".50 INT  121.072 AC O&G  Gnatty Creek  Elk-Outside"),
        ("ACCT NO",       "pending — pull from Harrison County Sheriff"),
        ("TICKET NO",     "pending"),
        ("MINERAL VALUE", "pending"),
        ("CLASS",         "pending"),
        ("TAXES",         "pending"),
    ]
    for lbl, val in tax_og:
        _lv(ws1, r, lbl, val); r += 1

    _blank(ws1, r); r += 1

    # Footer
    _merge_row(ws1, r, 1, NUM_COLS,
               "Prepared by Scott Schufford  |  Aces N 8s  |  06/04/2026",
               C_DARK, C_GOLD, sz=9, bold=False, align=CTR, height=14)

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 2 — Index (chain of title)
    # ══════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Index")
    ws2.sheet_view.showGridLines = False
    ws2.page_setup.orientation   = "landscape"

    for col, w in zip("ABCDEFG", [14, 12, 12, 28, 28, 8, 55]):
        ws2.column_dimensions[col].width = w

    r2 = 1
    _merge_row(ws2, r2, 1, 7, "CHAIN OF TITLE INDEX — Parcel 11-409-19 | Elk-Outside District | Harrison County WV",
               C_DARK, C_GOLD, sz=12, bold=True, align=CTR, height=24); r2 += 1
    _merge_row(ws2, r2, 1, 7, "Prepared by Scott Schufford  |  Aces N 8s  |  06/04/2026",
               C_DARK, C_WHITE, sz=9, align=CTR, height=14); r2 += 1
    _blank(ws2, r2); r2 += 1

    hdrs2 = ["TYPE", "BOOK/PAGE", "INSTR DATE", "GRANTOR", "GRANTEE", "ACRES", "DESCRIPTION / NOTES"]
    for i, h in enumerate(hdrs2):
        c = ws2.cell(row=r2, column=i + 1, value=h)
        c.font      = Font(name="Calibri", bold=True, color=C_WHITE, size=10)
        c.fill      = _fill(C_NAVY)
        c.alignment = CTR
        c.border    = BORD
    ws2.row_dimensions[r2].height = 18; r2 += 1

    CHAIN = [
        ("Deed",         "DB 57/238",    "1874",       "Davisson, Edgar M.",
         "Monroe, Benjamin T.",          "51",
         "51 acres near Gnatty Creek"),
        ("Deed",         "DB 61/434",    "1879",       "Shuttleworth, S.A.",
         "Monroe, B.T.",                 "",
         "Romines Mills tract"),
        ("Deed",         "DB 68/329",    "1884",       "Bumgardner, Adam",
         "Monroe, B.T.",                 "60",
         "60 acres fraction"),
        ("Deed",         "DB 75/97",     "1888",       "Bumgardner, Adam",
         "Monroe, B.T.",                 "10",
         "10 acres fraction"),
        ("Deed",         "DB 109/403",   "1899",       "Thompson, M.M., Commissioner",
         "Shuttleworth, M.N.",           "",
         "Circuit Court order"),
        ("Deed",         "DB 136/259",   "1903",       "Shuttleworth, Maynard N. & Lillie",
         "Stewart, William A.",          "121.5",
         "121.5 ac Elk Creek — ⚠ RESERVED 1/2 MINERALS — KEY INSTRUMENT — SPLIT ESTATE"),
        ("Estate",       "Fid Bk 10/247","1919",       "Shuttleworth, Maynard N. — DIED",
         "Heirs: Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane Shuttleworth", "",
         "Estate settlement — reserved mineral interest distributed to 6 heirs"),
        ("Mineral Deed", "DB 1441/1269", "01/19/2010", "Burns, A. Dean, Exec. Estate of Helen S. Kramer",
         "Master Mineral Holdings Inc. (Texas corporation)", "121.072",
         "1/6 undivided O&G + coalbed methane — $11,137.50 — rec. 02/10/2010 — VESTING INSTRUMENT"),
    ]

    for i, row_data in enumerate(CHAIN):
        bk = row_data[1]
        if "1441" in bk:
            fill_color = C_GREEN
        elif "136" in bk:
            fill_color = C_AMBER
        else:
            fill_color = C_LITE if i % 2 == 0 else C_WHITE

        for j, val in enumerate(row_data):
            c = ws2.cell(row=r2, column=j + 1, value=val)
            c.font      = Font(name="Calibri", size=9)
            c.fill      = _fill(fill_color)
            c.alignment = WRAP
            c.border    = BORD
        ws2.row_dimensions[r2].height = max(16, min(50, len(row_data[-1]) // 3)); r2 += 1

    # Legend
    r2 += 1
    for txt, color in [
        ("Green = Vesting instrument (BK 1441/1269)",        C_GREEN),
        ("Amber = Key reservation / split estate instrument", C_AMBER),
    ]:
        ws2.merge_cells(start_row=r2, start_column=1, end_row=r2, end_column=7)
        c = ws2.cell(row=r2, column=1, value=txt)
        c.font  = Font(name="Calibri", size=9, italic=True)
        c.fill  = _fill(color)
        c.border = BORD
        ws2.row_dimensions[r2].height = 14; r2 += 1

    # ══════════════════════════════════════════════════════════════════════════
    #  SHEET 3 — Map (placeholder)
    # ══════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Map")
    ws3.sheet_view.showGridLines = False

    _merge_row(ws3, 1, 1, 6,
               f"Maps — Parcel 11-409-19 | Elk-Outside District | Harrison County WV",
               C_DARK, C_GOLD, sz=13, bold=True, align=CTR, height=28)
    _merge_row(ws3, 2, 1, 6,
               "Prepared by Scott Schufford  |  Aces N 8s  |  06/04/2026",
               C_DARK, C_WHITE, sz=9, align=CTR, height=14)
    c = ws3.cell(row=4, column=1,
                 value="Map images — Keller Farm Map | Selection Map | Well Spot Map")
    c.font = Font(name="Calibri", italic=True, color="888888", size=10)
    for col, w in zip("ABCDEF", [24, 30, 20, 15, 15, 30]):
        ws3.column_dimensions[col].width = w

    # ── Save ──────────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(str(OUT_FILE))
    log.info("Saved → %s", OUT_FILE)
    return OUT_FILE


if __name__ == "__main__":
    out = build()
    log.info("Done: %s", out)
    print(f"\nOR built: {out}")
    print("Next: upload to Elk Turn-in folder in Dropbox (mntstrunk@gmail.com)")
