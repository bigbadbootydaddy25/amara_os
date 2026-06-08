"""
deed/templates/marcus_or_template.py

Canonical Marcus Strunk OR format for Texhoma Land Partners.
This module is the single source of truth for OR layout, widths, heights,
section order, and assignment fields.  Import build_workbook() for every
future Texhoma parcel — never hand-code column widths or section order again.

Column widths  : A=8.664  B=36.664  C=10.664  D=13.0  E=36.664  F=1.664 (spacer)
Default row h  : 12.75  |  title row: 21  |  section headers: 15  |  blanks: 6
Merge policy   : A1:E1 only — F always a narrow spacer, never merged
Gross acres    : D24 — all net-acres use formula =Cxx*D$24
Sections       : 20 in SECTION_ORDER  |  Assignments: 9 in ASSIGNMENT_FIELDS

Usage
-----
    from deed.templates.marcus_or_template import build_workbook, SECTION_ORDER
    wb = build_workbook(data)      # see DATA_SCHEMA for required keys
    wb.save("output.xlsx")
"""

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
except ImportError as _e:
    raise ImportError("pip install openpyxl") from _e

# ── Exact column widths ────────────────────────────────────────────────────────
COL_WIDTHS: dict[str, float] = {
    "A": 8.664,
    "B": 36.664,
    "C": 10.664,
    "D": 13.0,
    "E": 36.664,
    "F": 1.664,     # narrow spacer — never merged
}

# ── Row heights ────────────────────────────────────────────────────────────────
ROW_H       = 12.75   # default — every row unless overridden
ROW_H_TITLE = 21.0    # row 1 title banner
ROW_H_SECT  = 15.0    # section header rows
ROW_H_BLANK = 6.0     # spacer rows

# ── Merge columns ──────────────────────────────────────────────────────────────
MERGE_END = 5          # columns 1-5 = A through E; F is excluded

# ── 20 canonical section names (exact order) ───────────────────────────────────
SECTION_ORDER: tuple[str, ...] = (
    "PARCEL IDENTIFICATION",            #  1
    "SURFACE OWNER",                    #  2
    "LEGAL DESCRIPTION",                #  3
    "TITLE / VESTING",                  #  4
    "MINERAL OWNERS",                   #  5
    "ROYALTY OWNERS",                   #  6
    "WORKING INTEREST",                 #  7
    "LEASEHOLD",                        #  8
    "ASSIGNMENTS",                      #  9
    "ORRI",                             # 10
    "OGLs ON FILE",                     # 11
    "UNRELEASED OGLs / ENCUMBRANCES",   # 12
    "PRODUCTION DATA",                  # 13
    "NOTES",                            # 14
    "ENVIRONMENTAL",                    # 15
    "EASEMENTS",                        # 16
    "MORTGAGES",                        # 17
    "TAX ASSESSMENT — SURFACE",         # 18
    "TAX ASSESSMENT — OIL AND GAS",     # 19
    "CERTIFICATION",                    # 20
)

# ── 9 assignment fields ────────────────────────────────────────────────────────
ASSIGNMENT_FIELDS: tuple[str, ...] = (
    "GROSS ACRES",
    "NRI",
    "ORRI",
    "ASSIGNOR",
    "ASSIGNEE",
    "DATE ASSIGNED",
    "RECORDED",
    "BOOK / PAGE",
    "NOTES",
)

# ── Data dict schema ───────────────────────────────────────────────────────────
DATA_SCHEMA: dict = {
    # Identity
    "parcel_id":          str,   # "11-409-19"
    "full_parcel":        str,   # "17-11-0409-0019-0000"
    "prospect":           str,   # "Elk"
    "trid":               str,   # "WS"
    "unit":               str,   # "None"
    "county":             str,   # "Harrison"
    "state":              str,   # "WV"
    "district":           str,   # "Elk-Outside"
    "gross_acres":        float, # 121.072  ← written to D24
    "examiner":           str,   # "Scott Schufford"
    "company":            str,   # "Aces N 8s"
    "date_examined":      str,   # "06/04/2026"
    "last_bk_pg":         str,   # "DB 1441/1269  dated  01/19/2010"
    # Surface
    "surface_owner":      str,
    "surface_address":    str,
    "surface_deed":       str,
    "surface_tenure":     str,
    # Sections 3-4
    "legal_description":  str,
    "vesting_instrument": str,
    # Mineral owners — list of dicts
    "mineral_owners": list,
    # Each mineral owner dict:
    #   {"fraction": "1/6", "name": str, "instrument": str,
    #    "decimal": float, "status": str, "notes": str,
    #    "highlight": "green"|"amber"|None}
    # Working interest
    "working_interest": dict,
    # {"status": str, "decimal": float, "description": str}
    # Leasehold / assignments — dict with ASSIGNMENT_FIELDS keys
    "assignments": dict,
    # ORRI, OGLs on file, Unreleased OGLs/encumbrances
    "orri":              str,
    "ogls_on_file":      str,
    "unreleased_ogls":   str,
    # Wells — list of dicts
    "wells": list,
    # Each well dict:
    #   {"api": str, "operator": str, "spud": str, "status": str,
    #    "last_prod": str, "dep_status": str}
    # Notes — list of str
    "notes": list,
    # Sections 15-17
    "environmental":     str,
    "easements":         str,
    "mortgages":         str,
    # Tax surface
    "tax_surface": dict,
    # {"acct_no","ticket_no","name","description","map_parcel",
    #  "land_value","annual_tax","tax_year","status"}
    # Tax O&G
    "tax_og": dict,
    # {"name","description","acct_no","assessor_url","assessor_phone"}
    # Certification
    "certification": str,
    # Index sheet chain — list of 7-tuples
    # (type, book_page, instr_date, grantor, grantee, acres, description)
    "chain": list,
    # Output
    "output_file": str,   # full path string
}


# ── Color palette ──────────────────────────────────────────────────────────────
_C = {
    "hdr":   "1A2035",
    "navy":  "1F3864",
    "gold":  "C8A855",
    "white": "FFFFFF",
    "cream": "F5F0E0",
    "amber": "FFF2CC",
    "green": "D9F2DD",
    "gray":  "F2F2F2",
    "silv":  "D9D9D9",
    "red":   "FFD6D6",
}
_THIN  = Side(style="thin",   color="CCCCCC")
_THICK = Side(style="medium", color="888888")
_BORD  = Border(left=_THIN,  right=_THIN,  top=_THIN,  bottom=_THIN)
_TBORD = Border(left=_THICK, right=_THICK, top=_THICK, bottom=_THICK)
_LEFT  = Alignment(horizontal="left",   vertical="center", wrap_text=True)
_CTR   = Alignment(horizontal="center", vertical="center", wrap_text=True)
_WRAP  = Alignment(horizontal="left",   vertical="top",    wrap_text=True)


def _fill(key: str) -> PatternFill:
    return PatternFill("solid", fgColor=_C[key])


def _font(bold=False, color="1A2035", size=9, italic=False) -> Font:
    return Font(name="Calibri", bold=bold, color=color, size=size, italic=italic)


# ══════════════════════════════════════════════════════════════════════════════
#  Sheet builder helper
# ══════════════════════════════════════════════════════════════════════════════

class _B:
    """Stateful row-cursor builder for one worksheet."""

    def __init__(self, ws):
        self.ws = ws
        self.r  = 1
        ws.sheet_view.showGridLines = False
        ws.page_setup.orientation   = "landscape"
        for col, w in COL_WIDTHS.items():
            ws.column_dimensions[col].width = w

    # ── internal helpers ───────────────────────────────────────────────────────

    def _h(self, row: int, h: float):
        self.ws.row_dimensions[row].height = h

    def _cell(self, row, col, val, fg, bg_key, bold=False, italic=False,
              size=9, align=_WRAP, border=_BORD) -> openpyxl.cell.Cell:
        c = self.ws.cell(row=row, column=col, value=val)
        c.font      = Font(name="Calibri", bold=bold, italic=italic,
                           color=fg, size=size)
        c.fill      = _fill(bg_key)
        c.alignment = align
        c.border    = border
        return c

    # ── public layout methods ──────────────────────────────────────────────────

    def merged(self, val, c1, c2, fg, bg, bold=False, italic=False,
               sz=9, align=_LEFT, h=ROW_H, border=_BORD):
        """Merge c1:c2 on current row."""
        r = self.r
        self.ws.merge_cells(start_row=r, start_column=c1,
                            end_row=r,   end_column=c2)
        self._cell(r, c1, val, fg, bg, bold=bold, italic=italic,
                   size=sz, align=align, border=border)
        self._h(r, h)
        self.r += 1

    def banner(self, text: str):
        """Row 1 title banner — A:E merged, gold on dark."""
        self.merged(text, 1, MERGE_END, _C["gold"], "hdr",
                    bold=True, sz=14, align=_CTR,
                    h=ROW_H_TITLE, border=_TBORD)

    def subtitle(self, text: str):
        """Preparer subtitle — A:E merged, white on dark."""
        self.merged(text, 1, MERGE_END, _C["white"], "hdr",
                    sz=9, align=_CTR, h=ROW_H)

    def blank(self):
        self._h(self.r, ROW_H_BLANK)
        self.r += 1

    def section(self, name: str):
        """Dark header bar — gold text, thick border, A:E merged."""
        self.merged(name, 1, MERGE_END, _C["gold"], "hdr",
                    bold=True, sz=11, align=_LEFT,
                    h=ROW_H_SECT, border=_TBORD)

    def lv(self, label: str, value, bg_val="white", bold_val=False,
           h=ROW_H, note=None):
        """Label in A, value merged B:E. Optional note appended to value."""
        r = self.r
        disp = f"{value}  ←  {note}" if note else value
        # Label cell
        cl = self.ws.cell(row=r, column=1, value=label)
        cl.font      = _font(bold=True, size=9)
        cl.fill      = _fill("cream")
        cl.alignment = _LEFT
        cl.border    = _BORD
        # Value cell (B:E merged)
        self.ws.merge_cells(start_row=r, start_column=2,
                            end_row=r,   end_column=MERGE_END)
        cv = self.ws.cell(row=r, column=2, value=disp)
        cv.font      = _font(bold=bold_val, size=9)
        cv.fill      = _fill(bg_val)
        cv.alignment = _WRAP
        cv.border    = _BORD
        self._h(r, h)
        self.r += 1
        return cv

    def tbl_hdr(self, labels: list[str], col_start=1):
        """Navy column-header row."""
        r = self.r
        for i, lbl in enumerate(labels):
            c = self.ws.cell(row=r, column=col_start + i, value=lbl)
            c.font      = _font(bold=True, color="FFFFFF", size=9)
            c.fill      = _fill("navy")
            c.alignment = _CTR
            c.border    = _BORD
        self._h(r, ROW_H_SECT)
        self.r += 1

    def tbl_row(self, values: list, col_start=1, bg="white", h=ROW_H):
        r = self.r
        for i, v in enumerate(values):
            c = self.ws.cell(row=r, column=col_start + i, value=v)
            c.font      = _font(size=9)
            c.fill      = _fill(bg)
            c.alignment = _WRAP
            c.border    = _BORD
        self._h(r, h)
        self.r += 1

    def raw5(self, a, b, c, d, e,
             fg_a="hdr", fg_cde="1A2035",
             bg_a="hdr", bg_b="navy", bg_c="navy", bg_d="navy", bg_e="navy",
             bold_a=True, bold_b=False, bold_cde=True,
             h=ROW_H_SECT):
        """Place five individual cells A-E without merging (used for row 24)."""
        r = self.r
        specs = [
            (1, a, _C[fg_a] if fg_a in _C else fg_a, bg_a, bold_a),
            (2, b, _C["white"],                        bg_b, bold_b),
            (3, c, _C["white"],                        bg_c, bold_cde),
            (4, d, _C["white"],                        bg_d, bold_cde),
            (5, e, _C["white"],                        bg_e, bold_cde),
        ]
        for col, val, fg, bg, bold in specs:
            cell = self.ws.cell(row=r, column=col, value=val)
            cell.font      = _font(bold=bold, color=fg, size=9)
            cell.fill      = _fill(bg)
            cell.alignment = _CTR
            cell.border    = _BORD
        self._h(r, h)
        self.r += 1

    def formula_row(self, fraction: str, name: str, instrument: str,
                    decimal: float, gross_acres_row: int,
                    status: str, bg="white"):
        """
        Mineral owner data row with net-acres formula.
        E = =Cxx*D$<gross_acres_row>
        """
        r = self.r
        row_data = [
            (1, fraction,    "1A2035", bg, False),
            (2, f"{name}\n{instrument}", "1A2035", bg, False),
            (3, decimal,     "1A2035", bg, False),
            (4, None,        "1A2035", bg, False),
            (5, f"=C{r}*D${gross_acres_row}", "1A2035", bg, False),
        ]
        for col, val, fg, bg_key, bold in row_data:
            c = self.ws.cell(row=r, column=col, value=val)
            c.font      = _font(bold=bold, color=fg, size=9)
            c.fill      = _fill(bg_key)
            c.alignment = _WRAP
            c.border    = _BORD
            if col == 3:
                c.number_format = "0.000000"
            if col == 5:
                c.number_format = "#,##0.000"
        self._h(r, ROW_H)
        self.r += 1

    def footer(self, text: str):
        self.merged(text, 1, MERGE_END, _C["gold"], "hdr",
                    sz=9, align=_CTR, h=ROW_H)


# ══════════════════════════════════════════════════════════════════════════════
#  Main builder
# ══════════════════════════════════════════════════════════════════════════════

def build_workbook(data: dict) -> openpyxl.Workbook:
    """
    Build and return an openpyxl Workbook in Marcus Strunk's exact OR format.
    Caller is responsible for wb.save().
    """
    wb = openpyxl.Workbook()

    _build_or_sheet(wb.active, data)
    _build_index_sheet(wb.create_sheet("Index"), data)
    _build_map_sheet(wb.create_sheet("Map"), data)

    return wb


# ══════════════════════════════════════════════════════════════════════════════
#  Sheet 1 — OR (parcel number as tab name)
# ══════════════════════════════════════════════════════════════════════════════

def _build_or_sheet(ws, data: dict):  # noqa: C901
    ws.title = data["parcel_id"]
    b = _B(ws)

    ga      = data["gross_acres"]
    exam    = data["examiner"]
    company = data["company"]
    dated   = data["date_examined"]

    # ── Rows 1-2: banner + preparer ───────────────────────────────────────────
    b.banner("OPINION OF RECORD")                                      # row 1  h=21
    b.subtitle(f"Scott Schufford  |  {company}")                      # row 2
    b.blank()                                                           # row 3

    # ── Row 4: PARCEL IDENTIFICATION ──────────────────────────────────────────
    b.section("PARCEL IDENTIFICATION")                                 # row 4
    b.lv("PROSPECT",      data["prospect"])                            # row 5
    b.lv("TRID",          data["trid"])                                # row 6
    b.lv("UNIT",          data["unit"])                                # row 7
    b.lv("COUNTY",        data["county"])                              # row 8
    b.lv("STATE",         data["state"])                               # row 9
    b.lv("DISTRICT",      data["district"])                            # row 10
    b.lv("TAX PARCEL ID", data["parcel_id"])                           # row 11
    b.lv("MAP / PARCEL",  data["full_parcel"])                         # row 12
    b.lv("EXAMINER",      exam)                                        # row 13
    b.lv("DATE EXAMINED", dated)                                       # row 14
    b.lv("LAST BK / PG",  data["last_bk_pg"])                         # row 15
    b.blank()                                                           # row 16

    # ── Row 17: SURFACE OWNER ─────────────────────────────────────────────────
    b.section("SURFACE OWNER")                                         # row 17
    b.lv("OWNER",         data["surface_owner"])                       # row 18
    b.lv("ADDRESS",       data["surface_address"])                     # row 19
    b.lv("VESTING DEED",  data["surface_deed"])                        # row 20
    b.lv("TENURE",        data["surface_tenure"])                      # row 21
    b.blank()                                                           # row 22

    # ── Row 23: MINERAL OWNERS section header ─────────────────────────────────
    b.section("MINERAL OWNERS")                                        # row 23

    # ── Row 24: gross-acres anchor + column labels ────────────────────────────
    # D24 = gross_acres — all net-acres formulae use =Cxx*D$24
    GROSS_ACRES_ROW = b.r    # must be 24
    assert GROSS_ACRES_ROW == 24, (
        f"Row alignment error: gross acres landed on row {GROSS_ACRES_ROW}, expected 24. "
        "Count parcel fields (must be 11) and surface fields (must be 4)."
    )
    b.raw5(
        "FRACTION", "OWNER  /  INSTRUMENT", "DECIMAL", ga, "NET ACRES",
        fg_a="gold", bg_a="navy", bg_b="navy", bg_c="navy", bg_d="navy", bg_e="navy",
        bold_a=True, bold_cde=True,
    )

    # ── Rows 25+: mineral owner data rows ─────────────────────────────────────
    for owner in data.get("mineral_owners", []):
        bg = {"green": "green", "amber": "amber"}.get(owner.get("highlight"), "white")
        b.formula_row(
            fraction=owner["fraction"],
            name=owner["name"],
            instrument=owner.get("instrument", ""),
            decimal=owner["decimal"],
            gross_acres_row=GROSS_ACRES_ROW,
            status=owner.get("status", ""),
            bg=bg,
        )

    # Total row
    tot_row = b.r
    b.tbl_row(["TOTAL", "", 1.0, ga, ga], bg="silv")

    b.blank()

    # ── LEGAL DESCRIPTION (#3) ────────────────────────────────────────────────
    b.section("LEGAL DESCRIPTION")
    b.lv("LEGAL DESC", data.get("legal_description", "See vesting instrument"))

    b.blank()

    # ── TITLE / VESTING (#4) ──────────────────────────────────────────────────
    b.section("TITLE / VESTING")
    b.lv("VESTING INSTRUMENT", data.get("vesting_instrument", "See mineral owners"))

    b.blank()

    # ── ROYALTY OWNERS (#6) ───────────────────────────────────────────────────
    b.section("ROYALTY OWNERS")
    b.lv("STATUS", "Same as mineral owners — no separate royalty conveyance")

    b.blank()

    # ── WORKING INTEREST (#7) ────────────────────────────────────────────────
    b.section("WORKING INTEREST")
    wi = data.get("working_interest", {})
    b.lv("STATUS",      wi.get("status", "UNLEASED"))
    b.lv("DECIMAL",     wi.get("decimal", 1.0))
    b.lv("DESCRIPTION", wi.get("description", "No active OGL"))

    b.blank()

    # ── LEASEHOLD (#8) ────────────────────────────────────────────────────────
    b.section("LEASEHOLD")
    asgn = data.get("assignments", {})
    b.lv("GROSS ACRES", asgn.get("GROSS ACRES", ga))
    b.lv("NRI",         asgn.get("NRI",         "N/A — Unleased"))

    b.blank()

    # ── ASSIGNMENTS (#9) — 9 canonical fields ─────────────────────────────────
    b.section("ASSIGNMENTS")
    for field in ASSIGNMENT_FIELDS:
        b.lv(field, asgn.get(field, "None"))

    b.blank()

    # ── ORRI (#10) ────────────────────────────────────────────────────────────
    b.section("ORRI")
    b.lv("ORRI", data.get("orri", "None"))

    b.blank()

    # ── OGLs ON FILE (#11) ────────────────────────────────────────────────────
    b.section("OGLs ON FILE")
    b.lv("OGLs ON FILE", data.get("ogls_on_file", "None"))

    b.blank()

    # ── UNRELEASED OGLs / ENCUMBRANCES (#12) ─────────────────────────────────
    b.section("UNRELEASED OGLs / ENCUMBRANCES")
    b.lv("ENCUMBRANCES", data.get("unreleased_ogls", "None of record"),
         bg_val="amber" if data.get("unreleased_ogls") else "white")

    b.blank()

    # ── PRODUCTION DATA (#13) — vertical per well ─────────────────────────────
    b.section("PRODUCTION DATA")
    wells = data.get("wells", [])
    if wells:
        for i, w in enumerate(wells):
            if i > 0:
                b.blank()
            b.lv("API #",            w.get("api", ""),        bg_val="gray")
            b.lv("OPERATOR",         w.get("operator", ""))
            b.lv("SPUD DATE",        w.get("spud", ""))
            b.lv("WELL STATUS",      w.get("status", ""))
            b.lv("LAST REPORTED PROD", w.get("last_prod", ""))
            b.lv("DEP STATUS",       w.get("dep_status", ""))
    else:
        b.lv("WELLS", "No wells of record — coordinate-radius search confirmed")

    b.blank()

    # ── NOTES (#14) ───────────────────────────────────────────────────────────
    b.section("NOTES")
    for note in data.get("notes", []):
        b.merged(note, 1, MERGE_END, _C["hdr"], "cream",
                 italic=True, sz=9, align=_WRAP, h=36)

    b.blank()

    # ── ENVIRONMENTAL (#15) ───────────────────────────────────────────────────
    b.section("ENVIRONMENTAL")
    b.lv("ENVIRONMENTAL", data.get("environmental", "Not examined"))

    b.blank()

    # ── EASEMENTS (#16) ───────────────────────────────────────────────────────
    b.section("EASEMENTS")
    b.lv("EASEMENTS", data.get("easements", "Not examined"))

    b.blank()

    # ── MORTGAGES (#17) ───────────────────────────────────────────────────────
    b.section("MORTGAGES")
    b.lv("MORTGAGES", data.get("mortgages", "None of record"))

    b.blank()

    # ── TAX ASSESSMENT — SURFACE (#18) ────────────────────────────────────────
    b.section("TAX ASSESSMENT — SURFACE")
    ts = data.get("tax_surface", {})
    for field, key in [
        ("ACCT NO",       "acct_no"),
        ("TICKET NO",     "ticket_no"),
        ("NAME",          "name"),
        ("DESCRIPTION",   "description"),
        ("MAP / PARCEL",  "map_parcel"),
        ("LAND VALUE",    "land_value"),
        ("ANNUAL TAX",    "annual_tax"),
        ("TAX YEAR",      "tax_year"),
        ("STATUS",        "status"),
    ]:
        b.lv(field, ts.get(key, "—"))

    b.blank()

    # ── TAX ASSESSMENT — OIL AND GAS (#19) ───────────────────────────────────
    b.section("TAX ASSESSMENT — OIL AND GAS")
    tog = data.get("tax_og", {})
    b.lv("NAME",           tog.get("name", "—"),
         bg_val="amber" if tog.get("name") else "white")
    b.lv("DESCRIPTION",    tog.get("description", "—"))
    b.lv("ACCT NO",        tog.get("acct_no", "—"),
         bg_val="amber" if "assessor" in tog.get("acct_no", "").lower() else "white")
    b.lv("ASSESSOR URL",   tog.get("assessor_url", "—"))
    b.lv("ASSESSOR PHONE", tog.get("assessor_phone", "—"))

    b.blank()

    # ── CERTIFICATION (#20) ───────────────────────────────────────────────────
    b.section("CERTIFICATION")
    cert = data.get("certification",
                    f"Title examination prepared by {exam}, {company}. "
                    f"Information is based on public records available as of {dated}.")
    b.merged(cert, 1, MERGE_END, _C["hdr"], "cream",
             sz=9, align=_WRAP, h=30)

    b.blank()

    # Footer
    b.footer(f"Prepared by {exam}  |  {company}  |  {dated}")

    # Sheet-level headers / footers
    ws.oddHeader.center.text = f"Prepared by {exam}  |  {company}"
    ws.oddFooter.center.text = "&P of &N"


# ══════════════════════════════════════════════════════════════════════════════
#  Sheet 2 — Index (chain of title)
# ══════════════════════════════════════════════════════════════════════════════

def _build_index_sheet(ws, data: dict):
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation   = "landscape"
    pid    = data["parcel_id"]
    dated  = data["date_examined"]
    exam   = data["examiner"]
    comp   = data["company"]

    # Index uses 7 columns
    for col, w in zip("ABCDEFG", [12, 12, 12, 28, 28, 8, 44]):
        ws.column_dimensions[col].width = w

    b = _B(ws)
    # override column widths already set (7-col index)
    b.merged(
        f"CHAIN OF TITLE INDEX — Parcel {pid}  |  {data['district']} District  |  {data['county']} County {data['state']}",
        1, 7, _C["gold"], "hdr", bold=True, sz=12, align=_CTR,
        h=24, border=_TBORD,
    )
    b.merged(
        f"Prepared by {exam}  |  {comp}  |  {dated}",
        1, 7, _C["white"], "hdr", sz=9, align=_CTR, h=ROW_H,
    )
    b.blank()

    b.tbl_hdr(["TYPE", "BOOK/PAGE", "INSTR DATE", "GRANTOR", "GRANTEE", "ACRES", "DESCRIPTION / NOTES"],
              col_start=1)

    chain = data.get("chain", [])
    for i, row in enumerate(chain):
        # row = (type, book_page, date, grantor, grantee, acres, notes)
        bp = row[1] if len(row) > 1 else ""
        if "1441" in str(bp) or "1197" in str(bp):
            bg = "green"
        elif "136/259" in str(bp) or "183/260" in str(bp) or "136/88" in str(bp):
            bg = "amber"
        else:
            bg = "cream" if i % 2 == 0 else "white"

        r = b.r
        vals = list(row) + [""] * (7 - len(row))
        for j, v in enumerate(vals[:7]):
            c = ws.cell(row=r, column=j + 1, value=v)
            c.font      = _font(size=9)
            c.fill      = _fill(bg)
            c.alignment = _WRAP
            c.border    = _BORD
        ws.row_dimensions[r].height = max(ROW_H, min(48, len(str(vals[-1])) // 3))
        b.r += 1

    b.blank()
    for txt, color in [
        ("Green = Vesting instrument", "green"),
        ("Amber = Key reservation / split estate / encumbrance", "amber"),
    ]:
        b.merged(txt, 1, 7, _C["hdr"], color, italic=True, sz=9, h=ROW_H)


# ══════════════════════════════════════════════════════════════════════════════
#  Sheet 3 — Map (placeholder)
# ══════════════════════════════════════════════════════════════════════════════

def _build_map_sheet(ws, data: dict):
    ws.sheet_view.showGridLines = False
    pid   = data["parcel_id"]
    dist  = data["district"]
    cty   = data["county"]
    st    = data["state"]
    exam  = data["examiner"]
    comp  = data["company"]
    dated = data["date_examined"]

    for col, w in zip("ABCDEF", [24, 30, 20, 15, 15, 30]):
        ws.column_dimensions[col].width = w

    b = _B(ws)
    b.merged(
        f"MAPS — Parcel {pid}  |  {dist} District  |  {cty} County {st}",
        1, 5, _C["gold"], "hdr", bold=True, sz=13, align=_CTR,
        h=28, border=_TBORD,
    )
    b.merged(
        f"Prepared by {exam}  |  {comp}  |  {dated}",
        1, 5, _C["white"], "hdr", sz=9, align=_CTR, h=ROW_H,
    )
    b.blank()
    b.merged(
        "Map images — Keller Farm Map  |  Selection Map  |  Well Spot Map",
        1, 5, "888888", "white", italic=True, sz=10,
    )
