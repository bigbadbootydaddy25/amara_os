"""
Builds the OR for parcel 11-409-19 in Marcus Strunk's canonical format.
Three sheets: 11-409-19 (full OR) | Index (16-instrument chain) | Map

Usage: cd /Users/user/aegis_os && PYTHONPATH=. python3 deed/build_marcus_or.py
Output: deed/output/WS_11-409-19_OR_2026-06-04_CORRECTED.xlsx
"""
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("MARCUS_OR")

_BASE      = Path(os.getenv("DEED_BASE", "/Users/user/aegis_os/deed"))
OUTPUT_DIR = _BASE / "output"
OUT_FILE   = OUTPUT_DIR / "WS_11-409-19_OR_2026-06-04_CORRECTED.xlsx"


# ══════════════════════════════════════════════════════════════════════════════
#  Parcel data — Harrison County WV — 11-409-19
#  Confirmed June 4-7, 2026 | Examiner: Scott Schufford | Aces N 8s
# ══════════════════════════════════════════════════════════════════════════════

DATA = {
    # ── Identity ────────────────────────────────────────────────────────────
    "parcel_id":     "11-409-19",
    "full_parcel":   "17-11-0409-0019-0000  (sub-parcels: -0001, -0002, -0003)",
    "prospect":      "Elk",
    "trid":          "WS",
    "unit":          "None",
    "county":        "Harrison",
    "state":         "WV",
    "district":      "Elk-Outside",
    "gross_acres":   121.072,
    "examiner":      "Scott Schufford",
    "company":       "Aces N 8s",
    "date_examined": "06/04/2026",
    "last_bk_pg":    "DB 1441/1269  dated  01/19/2010  rec.  02/10/2010",

    # ── Surface owner ────────────────────────────────────────────────────────
    "surface_owner":   "Burns, L. Craig & Sue B.",
    "surface_address": "458 Knoll View Road, Mount Clare WV 26408",
    "surface_deed":    (
        "DB 1197/1258  |  Instr. Date: 07/11/1989  |  Rec. 09/21/1989  |  "
        "Grantor: Abner Stout, Executor, Estate of Mary L. Lawson  |  "
        "Consideration: $34,500.00  |  Acres: 129.63 surface"
    ),
    "surface_tenure":  "Joint tenants with right of survivorship (WROS)",

    # ── Sections 3-4 ────────────────────────────────────────────────────────
    "legal_description": (
        "Gnatty Creek watershed, Elk Creek tributary, Elk-Outside District, "
        "Harrison County WV.  121.072 acres per DB 1441/1269 page 5.  "
        "Tax description: 118 AC Stout Run.  Property Class F — Farm."
    ),
    "vesting_instrument": (
        "MINERAL — DB 1441/1269  (01/19/2010 / rec. 02/10/2010)  "
        "Burns, A. Dean, Executor Estate of Helen S. Kramer → Master Mineral Holdings Inc.  "
        "1/6 undivided O&G + CBM | 121.072 acres | $10.00 consideration\n\n"
        "SURFACE — DB 1197/1258  (07/11/1989 / rec. 09/21/1989)  "
        "Abner Stout, Executor Estate of Mary L. Lawson → Burns, L. Craig & Sue B.  "
        "129.63 acres surface | $34,500.00"
    ),

    # ── Mineral owners ───────────────────────────────────────────────────────
    "mineral_owners": [
        {
            "fraction":   "1/6",
            "name":       "Master Mineral Holdings Inc. (Texas corporation)",
            "instrument": (
                "DB 1441/1269  |  01/19/2010  |  rec. 02/10/2010  |  $10.00  |  "
                "⚠ Tax records: Master Mineral Holdings III LP — same PO Box 10886 Midland TX 79702 "
                "— no transfer deed found of record — OPEN CHAIN ITEM"
            ),
            "decimal":    1 / 6,
            "status":     "Unleased",
            "highlight":  "green",
        },
        {
            "fraction":   "5/6",
            "name":       "Shuttleworth Maynard Heirs",
            "instrument": (
                "DB 136/259 (1903) reservation — Fid Bk 10/247 (1919) estate  |  "
                "Heirs: Lillie A., Helen (→Kramer), Lorene, Mary, Samuel, Betty Jane  |  "
                "WB 108/137 (1980): Lorene → Helen Kramer, Betty Evans, Samuel  |  "
                "WB 142/359 (1993): Helen Kramer died — Burns Executor  |  "
                "RESEARCH REQUIRED — 5 heir interests not yet conveyed"
            ),
            "decimal":    5 / 6,
            "status":     "Unleased — research required",
            "highlight":  "amber",
        },
    ],

    # ── Working interest ────────────────────────────────────────────────────
    "working_interest": {
        "status":      "UNLEASED",
        "decimal":     1.0,
        "description": (
            "White Space tract — no active oil and gas lease of record.  "
            "Parcel is undrilled as to deeper formations.  "
            "Three Devonian wells found via coordinate-radius search on adjacent parcels."
        ),
    },

    # ── Assignments — 9 canonical fields ─────────────────────────────────────
    "assignments": {
        "GROSS ACRES":   "121.072 ac  (17-11-0409-0019-0000 + sub-parcels -0001/-0002/-0003)",
        "NRI":           "N/A — Unleased",
        "ORRI":          "None",
        "ASSIGNOR":      "N/A — no lease to assign",
        "ASSIGNEE":      "N/A",
        "DATE ASSIGNED": "N/A",
        "RECORDED":      "N/A",
        "BOOK / PAGE":   "N/A",
        "NOTES":         (
            "No assignments of record.  White Space (WS) tract — TRID confirms no prior OR.  "
            "Prospect: Elk — Client: Texhoma Land Partners / Marcus Strunk RPL."
        ),
    },

    # ── Leasehold subsections ────────────────────────────────────────────────
    "orri":          "None",
    "ogls_on_file":  "None",
    "unreleased_ogls": (
        "1.  DB 183/260 (May 4, 1909) — Hope Natural Gas Company OGL — "
        "Lessor: Martin A. Props & wife — UNRELEASED — pre-digital — no release of record.\n"
        "2.  DB 136/88 (Feb 9, 1903) — Bijou Coal Company — Pittsburgh seam of coal — "
        "UNRELEASED — pre-digital — specifically excepted in Burns deed DB 1197/1258 p.4."
    ),

    # ── Production data — 3 wells, vertical format ───────────────────────────
    "wells": [
        {
            "api":       "47-033-01920",
            "operator":  "Diversified Production LLC",
            "spud":      "1978",
            "status":    "Active",
            "last_prod": "1,221 MCF — 2024",
            "dep_status":"Active — no plugging date",
        },
        {
            "api":       "47-033-04093",
            "operator":  "Diversified Production LLC",
            "spud":      "1995",
            "status":    "Active — adjacent parcel",
            "last_prod": "759 MCF — 2024",
            "dep_status":"Active",
        },
        {
            "api":       "47-033-05416",
            "operator":  "Key Oil Company",
            "spud":      "07/26/2010",
            "status":    "Active — north adjacent (Simpson District)",
            "last_prod": "2,254 MCF — 2024",
            "dep_status":"Active — no plugging date",
        },
    ],

    # ── Notes ────────────────────────────────────────────────────────────────
    "notes": [
        (
            "NOTE 1 — SOURCE DEED:  DB 1441/1269 — January 19, 2010 — "
            "Burns, A. Dean, Executor Estate of Helen S. Kramer → "
            "Master Mineral Holdings Inc. (Texas corporation) — "
            "Undivided 1/6 oil, gas, and coalbed methane — "
            "Elk-Outside District, Harrison County WV — 121.072 acres — "
            "Gnatty Creek watershed.  Consideration: $10.00.  "
            "Recorded February 10, 2010.  6 pages."
        ),
        (
            "NOTE 2 — EXAMINER NOTES:  White Space tract — chain built from scratch.  "
            "Key finding: DB 136/259 (1903) Shuttleworth to Stewart reserved ONE-HALF of all "
            "oil and gas — SPLIT ESTATE established 1903.  Master Mineral Holdings holds 1/6 "
            "undivided O&G (Helen Kramer's 1/6 of the Shuttleworth reserved 1/2).  "
            "Remaining 5/6 Shuttleworth heirs — further research required.  "
            "TAGIS parcel-ID search returned zero wells — confirmed system limitation in "
            "Elk-Outside District — wells found via coordinate-radius search.  "
            "Entity discrepancy: deed = Master Mineral Holdings Inc.; "
            "tax records = Master Mineral Holdings III LP — same PO Box Midland TX — "
            "no transfer deed found — flag for examiner review."
        ),
    ],

    # ── Sections 15-17 ───────────────────────────────────────────────────────
    "environmental": "Not examined",
    "easements":     "Not examined",
    "mortgages":     "None of record",

    # ── Tax assessment — surface ──────────────────────────────────────────────
    "tax_surface": {
        "acct_no":    "06056171",
        "ticket_no":  "0000037542",
        "name":       "Burns, L. Craig & Sue B.",
        "description":"118 AC Stout Run — Elk-Outside District — Harrison County WV",
        "map_parcel": "409-0019  (sub-parcels 0000 through 0003)",
        "land_value": "$4,860",
        "annual_tax": "$56.62",
        "tax_year":   "2025",
        "status":     "PAID  08/22/2025  |  Confirmed via harrison.softwaresystems.com (http only)",
    },

    # ── Tax assessment — O&G ─────────────────────────────────────────────────
    "tax_og": {
        "name":          "Shuttleworth Maynard Heirs",
        "description":   ".50 INT  121.072 AC O&G  Gnatty Creek  Elk-Outside",
        "acct_no":       (
            "Not separately assessed in Harrison County Sheriff system.  "
            "Mineral accounts held by Assessor — search: harrisoncountyassessor.com/ownershipsearch.aspx"
        ),
        "assessor_url":  "harrisoncountyassessor.com/ownershipsearch.aspx",
        "assessor_phone":"(304) 624-8510",
    },

    # ── Certification ────────────────────────────────────────────────────────
    "certification": (
        "This Opinion of Record was prepared by Scott Schufford, Aces N 8s, "
        "for Texhoma Land Partners (Marcus Strunk RPL) based on public records "
        "available in Harrison County WV as of June 7, 2026.  "
        "Chain examined 1874–2010 (16 instruments).  "
        "White Space tract — no prior OR existed.  "
        "Open items: Shuttleworth heir chain (5/6), mineral tax account, entity discrepancy (Inc. vs III LP)."
    ),

    # ── Index chain — 16 instruments ─────────────────────────────────────────
    "chain": [
        ("Deed",         "DB 57/238",    "1874",       "Davisson, Edgar M.",
         "Monroe, Benjamin T.",           "51",
         "51 acres Gnatty Creek  [recital in DB 1441/1269]"),
        ("Deed",         "DB 61/434",    "1879",       "Shuttleworth, S.A.",
         "Monroe, B.T.",                  "—",
         "Romines Mills tract  [recital]"),
        ("Deed",         "DB 68/329",    "1884",       "Bumgardner, Adam",
         "Monroe, B.T.",                  "60",
         "60 acres fraction  [recital]"),
        ("Deed",         "DB 75/97",     "1888",       "Bumgardner, Adam",
         "Monroe, B.T.",                  "10",
         "10 acres fraction  [recital]"),
        ("Deed",         "DB 109/403",   "1899",       "Thompson, M.M., Commissioner",
         "Shuttleworth, M.N.",            "122",
         "Circuit Court order  [recital]"),
        ("Deed",         "DB 136/259",   "1903-03-23", "Shuttleworth, Maynard N. & Lillie",
         "Stewart, William A.",           "121.5",
         "⚠ RESERVED ONE-HALF OF ALL OIL AND GAS — SPLIT ESTATE KEY INSTRUMENT  [recital p.3]"),
        ("Coal Deed",    "DB 136/88",    "1903-02-09", "Props, M.A. & wife",
         "Bijou Coal Company",            "—",
         "Pittsburgh seam — UNRELEASED — pre-digital  [excepted in DB 1197/1258 p.4]"),
        ("OGL",          "DB 183/260",   "1909-05-04", "Props, M.A. & wife",
         "Hope Natural Gas Company",      "—",
         "OGL — UNRELEASED — pre-digital  [excepted in DB 1197/1258 p.4]"),
        ("Estate",       "Fid Bk 10/247","1919",       "Shuttleworth, M.N. — died",
         "6 Heirs: Lillie A., Helen, Lorene, Mary, Samuel, Betty Jane", "—",
         "Reserved mineral interest distributed to 6 heirs  [recital]"),
        ("Will / Probate","WB 54/291",   "1960",       "Lawson, T. Minter — died",
         "Lawson, Guy & Mary",            "—",
         "Surface chain — Lawson estate  [DB 1197/1258 pp.2-3]"),
        ("Will / Probate","WB 79/320",   "1971",       "Lawson, Guy — died",
         "Lawson, Mary",                  "—",
         "Surface chain  [DB 1197/1258 pp.2-3]"),
        ("Will / Probate","WB 102/1040", "1983",       "Lawson, Mary — died",
         "Stout, Abner — Executor",       "—",
         "Surface chain  [DB 1197/1258 pp.2-3]"),
        ("Will / Probate","WB 108/137",  "1980",       "Shuttleworth, Lorene — died",
         "Kramer, Helen; Evans, Betty; Samuel Shuttleworth", "—",
         "Lorene's share distributed  [recital pp.3-4]"),
        ("Will / Probate","WB 142/359",  "1993",       "Kramer, Helen S. — died",
         "Burns, A. Dean — Executor",     "—",
         "Burns named Executor — leads to DB 1441/1269  [recital p.4]"),
        ("Deed",         "DB 1197/1258", "1989-07-11", "Stout, Abner, Executor (Lawson Estate)",
         "Burns, L. Craig & Sue B.",      "129.63",
         "SURFACE VESTING — rec. 09/21/1989 — $34,500 — exceptions: DB 136/88, DB 183/260  [IDX — 5 pp.]"),
        ("Mineral Deed", "DB 1441/1269", "2010-01-19", "Burns, A. Dean, Executor (Helen S. Kramer Estate)",
         "Master Mineral Holdings Inc.",  "121.072",
         "MINERAL VESTING — 1/6 O&G+CBM — rec. 02/10/2010 — $10.00  [IDX — 6 pp.]"),
    ],

    "output_file": str(OUT_FILE),
}


# ══════════════════════════════════════════════════════════════════════════════
#  Build
# ══════════════════════════════════════════════════════════════════════════════

def build() -> Path:
    from deed.templates.marcus_or_template import build_workbook
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = build_workbook(DATA)
    wb.save(str(OUT_FILE))
    log.info("Saved → %s", OUT_FILE)
    return OUT_FILE


if __name__ == "__main__":
    out = build()
    log.info("Done: %s", out)
    print(f"\nOR built: {out}")
    print("Next: upload to Elk Turn-in folder in Dropbox (mntstrunk@gmail.com)")
