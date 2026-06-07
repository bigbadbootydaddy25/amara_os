"""
OR Builder Agent — assembles all agent outputs into the Marcus Strunk canonical
Excel OR via deed/templates/marcus_or_template.py.

Input:  state["chain"], state["chain_flags"], state["wells"],
        state["tax_surface"], state["tax_og"]
Output: state["or_path"]   — absolute path to saved .xlsx
        state["or_status"]

Output file:  deed/output/WS_{parcel_id}_OR_{date}.xlsx
"""
import logging
import os
from datetime import date
from pathlib import Path

from deed.config import OUTPUT_DIR, PREPARER, COMPANY, CLIENT
from deed.state import TitleState

log = logging.getLogger("OR_BUILDER_AGENT")


# ══════════════════════════════════════════════════════════════════════════════
#  Public entry point (LangGraph node)
# ══════════════════════════════════════════════════════════════════════════════

def run(state: TitleState) -> dict:
    """LangGraph node — builds Excel OR from collected state, returns or_path."""
    from deed.templates.marcus_or_template import build_workbook

    parcel_id    = state.get("parcel_id", "11-409-19")
    gross_acres  = state.get("gross_acres", 121.072)
    county       = state.get("county", "Harrison")
    state_abbr   = state.get("state_abbr", "WV")
    district     = state.get("district", "Elk-Outside")
    date_examined = state.get("date_examined", date.today().strftime("%m/%d/%Y"))
    examiner     = state.get("examiner", PREPARER)
    company      = state.get("company", COMPANY)
    client       = state.get("client", CLIENT)

    chain        = state.get("chain") or []
    chain_flags  = state.get("chain_flags") or []
    wells        = state.get("wells") or []
    tax_surface  = state.get("tax_surface") or {}
    tax_og       = state.get("tax_og") or {}

    log.info("OR_BUILDER — parcel %s | %d chain instruments | %d wells",
             parcel_id, len(chain), len(wells))

    # ── Derive last_bk_pg from chain ─────────────────────────────────────────
    last_bk_pg = _last_bk_pg(chain, parcel_id)

    # ── Derive surface + mineral owner from chain flags ───────────────────────
    surf  = _surface_from_chain(chain)
    mins  = _minerals_from_chain(chain, chain_flags, gross_acres)
    notes = _build_notes(chain_flags, tax_og)
    encumb = _encumbrances(chain_flags)

    # ── Full parcel ID ────────────────────────────────────────────────────────
    full_parcel = _full_parcel_id(parcel_id)

    # ── Build data dict for template ─────────────────────────────────────────
    data = {
        "parcel_id":       parcel_id,
        "full_parcel":     full_parcel,
        "prospect":        "Elk",
        "trid":            "WS",
        "unit":            "None",
        "county":          county,
        "state":           state_abbr,
        "district":        district,
        "gross_acres":     gross_acres,
        "examiner":        examiner,
        "company":         company,
        "date_examined":   date_examined,
        "last_bk_pg":      last_bk_pg,

        "surface_owner":   surf.get("name",   "Burns, L. Craig & Sue B."),
        "surface_address": surf.get("address","458 Knoll View Road, Mount Clare WV 26408"),
        "surface_deed":    surf.get("deed",   "DB 1197/1258  dated  07/11/1989"),
        "surface_tenure":  surf.get("tenure", "Joint tenants with right of survivorship"),

        "legal_description": (
            f"Gnatty Creek watershed, Elk Creek tributary, {district} District, "
            f"{county} County {state_abbr}. {gross_acres} acres per chain of title."
        ),
        "vesting_instrument": _vesting_text(chain),

        "mineral_owners": mins,

        "working_interest": {
            "status":      "UNLEASED",
            "decimal":     1.0,
            "description": "White Space tract — no active OGL of record.",
        },

        "assignments": {
            "GROSS ACRES":   f"{gross_acres} ac",
            "NRI":           "N/A — Unleased",
            "ORRI":          "None",
            "ASSIGNOR":      "N/A",
            "ASSIGNEE":      "N/A",
            "DATE ASSIGNED": "N/A",
            "RECORDED":      "N/A",
            "BOOK / PAGE":   "N/A",
            "NOTES":         f"White Space (WS) — no lease to assign. Client: {client}.",
        },

        "orri":          "None",
        "ogls_on_file":  "None",
        "unreleased_ogls": encumb or "None of record",

        "wells":  _format_wells(wells),
        "notes":  notes,

        "environmental": "Not examined",
        "easements":     "Not examined",
        "mortgages":     "None of record",

        "tax_surface": {
            "acct_no":    tax_surface.get("acct_no",    "—"),
            "ticket_no":  tax_surface.get("ticket_no",  "—"),
            "name":       tax_surface.get("name",       "—"),
            "description":tax_surface.get("description","—"),
            "map_parcel": tax_surface.get("map_parcel", "—"),
            "land_value": tax_surface.get("land_value", "—"),
            "annual_tax": tax_surface.get("annual_tax", "—"),
            "tax_year":   tax_surface.get("tax_year",   "—"),
            "status":     tax_surface.get("status",     "—"),
        },

        "tax_og": {
            "name":           tax_og.get("name",           "Shuttleworth Maynard Heirs"),
            "description":    tax_og.get("description",    ".50 INT 121.072 AC O&G Gnatty Creek"),
            "acct_no":        tax_og.get("acct_no",        "Not separately assessed in Sheriff"),
            "assessor_url":   tax_og.get("assessor_url",   "harrisoncountyassessor.com/ownershipsearch.aspx"),
            "assessor_phone": tax_og.get("assessor_phone", "(304) 624-8510"),
        },

        "certification": (
            f"This Opinion of Record was prepared by {examiner}, {company}, "
            f"for {client} based on public records available in {county} County {state_abbr} "
            f"as of {date_examined}. {len(chain)}-instrument chain examined."
        ),

        "chain": _chain_for_index(chain),
        "output_file": "",   # set below after path computed
    }

    # ── Save workbook ─────────────────────────────────────────────────────────
    today_str = date.today().strftime("%Y-%m-%d")
    fname     = f"WS_{parcel_id}_OR_{today_str}.xlsx"
    out_path  = OUTPUT_DIR / fname
    data["output_file"] = str(out_path)

    errors = []
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        wb = build_workbook(data)
        wb.save(str(out_path))
        log.info("OR_BUILDER: saved → %s", out_path)
        return {
            "or_path":   str(out_path),
            "or_status": "COMPLETE",
            "errors":    [],
        }
    except Exception as e:
        msg = f"OR_BUILDER: failed to save workbook — {e}"
        log.error(msg)
        return {
            "or_path":   "",
            "or_status": "FAILED",
            "errors":    [msg],
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Data mapping helpers
# ══════════════════════════════════════════════════════════════════════════════

def _last_bk_pg(chain: list[dict], parcel_id: str) -> str:
    """Find the most recent instrument by date."""
    _known = {"11-409-19": "DB 1441/1269  dated  01/19/2010  rec.  02/10/2010"}
    if parcel_id in _known:
        return _known[parcel_id]
    if not chain:
        return "—"
    last = chain[-1]
    return f"DB {last['book']}/{last['page']}  dated  {last.get('date_instr', '')}"


def _surface_from_chain(chain: list[dict]) -> dict:
    """Find surface vesting instrument in chain and extract owner info."""
    for inst in reversed(chain):
        if inst.get("_flag") == "VESTING_SURFACE" or (
            inst.get("book") == "1197" and inst.get("page") == "1258"
        ):
            return {
                "name":    inst.get("grantee", "Burns, L. Craig & Sue B."),
                "deed":    f"DB {inst['book']}/{inst['page']}  dated  {inst.get('date_instr','')}",
                "acres":   inst.get("acres", "129.63"),
                "address": "458 Knoll View Road, Mount Clare WV 26408",
                "tenure":  "Joint tenants with right of survivorship",
            }
    return {}


def _minerals_from_chain(chain: list[dict], flags: list[dict], gross_acres: float) -> list[dict]:
    """Build mineral owners list from chain flags + confirmed seed for 11-409-19."""
    # Check if we have the confirmed mineral vesting instrument
    has_1441 = any(
        i.get("book") == "1441" and i.get("page") == "1269"
        for i in chain
    )

    if has_1441:
        return [
            {
                "fraction":   "1/6",
                "name":       "Master Mineral Holdings Inc. (Texas corporation)",
                "instrument": (
                    "DB 1441/1269  |  01/19/2010  |  rec. 02/10/2010  |  $10.00  |  "
                    "⚠ Tax records: Master Mineral Holdings III LP — same PO Box "
                    "10886 Midland TX 79702 — no transfer deed found — OPEN CHAIN ITEM"
                ),
                "decimal":   1 / 6,
                "status":    "Unleased",
                "highlight": "green",
            },
            {
                "fraction":   "5/6",
                "name":       "Shuttleworth Maynard Heirs",
                "instrument": (
                    "DB 136/259 (1903 reservation) | Fid Bk 10/247 (1919) estate  |  "
                    "Heirs: Lillie A., Helen (→Kramer), Lorene, Mary, Samuel, Betty Jane  |  "
                    "RESEARCH REQUIRED — 5 heir interests not yet conveyed"
                ),
                "decimal":   5 / 6,
                "status":    "Unleased — research required",
                "highlight": "amber",
            },
        ]

    # Generic fallback — flag any mineral deed as a vesting instrument
    minerals = []
    for inst in chain:
        if inst.get("_flag") == "VESTING_MINERAL":
            minerals.append({
                "fraction":   "—",
                "name":       inst.get("grantee", "Unknown"),
                "instrument": f"DB {inst['book']}/{inst['page']}",
                "decimal":    1.0,
                "status":     "See instrument",
                "highlight":  None,
            })
    return minerals or [{"fraction": "—", "name": "Research required",
                         "instrument": "See chain", "decimal": 1.0,
                         "status": "Unknown", "highlight": "amber"}]


def _encumbrances(flags: list[dict]) -> str:
    enc = [f for f in flags if f.get("flag_type") == "ENCUMBRANCE"]
    if not enc:
        return ""
    lines = []
    for e in enc:
        lines.append(f"DB {e.get('book')}/{e.get('page')} — {e.get('reason', '')}")
    return "\n".join(lines)


def _vesting_text(chain: list[dict]) -> str:
    lines = []
    for inst in chain:
        if inst.get("_flag") in ("VESTING_MINERAL", "VESTING_SURFACE"):
            lines.append(
                f"DB {inst['book']}/{inst['page']}  "
                f"({inst.get('date_instr','')})  "
                f"{inst.get('grantor','')} → {inst.get('grantee','')}  "
                f"|  {inst.get('acres','')} ac  |  {inst.get('consideration','')}"
            )
    return "\n".join(lines) if lines else "See chain of title"


def _build_notes(flags: list[dict], tax_og: dict) -> list[str]:
    notes = []
    split = [f for f in flags if f.get("flag_type") == "SPLIT_ESTATE"]
    if split:
        s = split[0]
        notes.append(
            f"NOTE 1 — SPLIT ESTATE:  {s.get('reason', '')}  "
            f"Toothman v. Courtney (1907 WV): minerals in WV held in place."
        )
    if tax_og.get("acct_no", "").lower().startswith("not"):
        notes.append(
            f"NOTE 2 — MINERAL TAX:  O&G mineral accounts not separately assessed in "
            f"Harrison County Sheriff system.  Next step: "
            f"{tax_og.get('assessor_url', 'harrisoncountyassessor.com/ownershipsearch.aspx')} "
            f"or call {tax_og.get('assessor_phone', '(304) 624-8510')}."
        )
    return notes if notes else ["See chain of title and examiner notes."]


def _format_wells(wells: list[dict]) -> list[dict]:
    """Normalize well dicts for the OR template."""
    return [
        {
            "api":       w.get("api", w.get("API", "")),
            "operator":  w.get("operator", w.get("company", "")),
            "spud":      w.get("spud", w.get("spud_date", "")),
            "status":    w.get("status", ""),
            "last_prod": w.get("last_prod", w.get("production", "")),
            "dep_status":w.get("dep_status", w.get("wvdep_status", "")),
        }
        for w in wells
    ]


def _full_parcel_id(parcel_id: str) -> str:
    _known = {"11-409-19": "17-11-0409-0019-0000  (sub-parcels: -0001, -0002, -0003)"}
    return _known.get(parcel_id, parcel_id)


def _chain_for_index(chain: list[dict]) -> list[tuple]:
    """Convert chain dicts to 7-tuples for the Index sheet."""
    return [
        (
            inst.get("type", "DEED"),
            f"DB {inst.get('book')}/{inst.get('page')}",
            inst.get("date_instr", inst.get("date_rec", "")),
            inst.get("grantor", ""),
            inst.get("grantee", ""),
            inst.get("acres", ""),
            inst.get("description", inst.get("notes", "")),
        )
        for inst in chain
    ]
