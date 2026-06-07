"""
deed/state.py — LangGraph TitleState for the Texhoma WV Title Examination stack.

Each node in deed/graph.py reads from and returns partial updates to TitleState.
Keys with Annotated[list, add] accumulate across nodes (errors, warnings).
All other keys are replaced on update.
"""
from operator import add
from typing import Annotated, TypedDict


class TitleState(TypedDict, total=False):
    # ── Input (set at graph entry) ────────────────────────────────────────────
    parcel_id:      str            # "11-409-19"
    county:         str            # "Harrison"
    state_abbr:     str            # "WV"
    district:       str            # "Elk-Outside"
    district_num:   str            # "11"
    gross_acres:    float          # 121.072
    search_names:   list[str]      # ["Burns", "Shuttleworth"] — IDX individual searches
    seed_bk_pg:     list[str]      # ["1441/1269", "1197/1258"] — IDX Book/Page lookups
    examiner:       str            # "Scott Schufford"
    company:        str            # "Aces N 8s"
    client:         str            # "Texhoma Land Partners"
    date_examined:  str            # "06/04/2026"

    # ── IDX agent output ──────────────────────────────────────────────────────
    idx_instruments: list[dict]    # raw instrument records from IDX
    idx_status:      str           # "COMPLETE" | "PARTIAL" | "FAILED" | "SEED_ONLY"

    # ── Chain builder output ──────────────────────────────────────────────────
    chain:           list[dict]    # ordered instruments (oldest → newest)
    chain_flags:     list[dict]    # flagged instruments with flag_type + reason
    chain_status:    str

    # ── Well agent output ─────────────────────────────────────────────────────
    wells:           list[dict]    # [{"api","operator","spud","status","last_prod","dep_status"}]
    well_count:      int
    well_status:     str

    # ── Tax agent output ──────────────────────────────────────────────────────
    tax_surface:     dict          # surface tax record from Harrison Sheriff
    tax_og:          dict          # O&G mineral tax (Assessor path)
    tax_status:      str

    # ── OR builder output ─────────────────────────────────────────────────────
    or_path:         str           # absolute path to saved .xlsx
    or_status:       str

    # ── Brain store output ────────────────────────────────────────────────────
    brain_results:   dict

    # ── Accumulated across all nodes ──────────────────────────────────────────
    errors:          Annotated[list[str], add]
    warnings:        Annotated[list[str], add]

    # ── Overall pipeline status ───────────────────────────────────────────────
    status:          str           # "RUNNING" | "COMPLETE" | "FAILED"


# ── Default input for Harrison County 11-409-19 ───────────────────────────────
DEFAULT_INPUT: TitleState = {
    "parcel_id":     "11-409-19",
    "county":        "Harrison",
    "state_abbr":    "WV",
    "district":      "Elk-Outside",
    "district_num":  "11",
    "gross_acres":   121.072,
    "search_names":  ["Burns", "Shuttleworth", "Monroe", "Davisson"],
    "seed_bk_pg":    ["1441/1269", "1197/1258", "136/259", "136/88", "183/260"],
    "examiner":      "Scott Schufford",
    "company":       "Aces N 8s",
    "client":        "Texhoma Land Partners",
    "date_examined": "06/04/2026",
    "errors":        [],
    "warnings":      [],
    "status":        "RUNNING",
}
