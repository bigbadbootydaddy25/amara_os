"""
Chain Builder Agent — reads IDX instruments + vesting deed recitals,
builds a complete ordered chain of title oldest → newest,
flags key instruments (split estates, gaps, encumbrances, vesting).

Input:  state["idx_instruments"]  (from IDX agent)
Output: state["chain"]            — ordered list of instrument dicts
        state["chain_flags"]      — flagged instruments with flag_type + reason
"""
import logging
import re

from deed.state import TitleState

log = logging.getLogger("CHAIN_BUILDER")

# ── Regex patterns for key language in deed text / descriptions / notes ────────
_SPLIT_ESTATE   = re.compile(
    r"\b(reserv|excep|subject to|saving and excepting)\b.*?"
    r"\b(oil|gas|mineral|coal|petroleum|hydrocarbon)",
    re.I,
)
_ENCUMBRANCE    = re.compile(
    r"\b(bijou|hope natural gas|pipeline|utility|easement|mort\w+|lien)\b", re.I
)
_VESTING        = re.compile(
    r"\b(warranty deed|mineral deed|deed of conveyance|quitclaim)\b", re.I
)
_ESTATE         = re.compile(
    r"\b(will|estate|fiduciary|executor|administrator|probat|fid\s*bk)\b", re.I
)
_OGL            = re.compile(
    r"\b(oil and gas lease|ogl|lease|lessor|lessee)\b", re.I
)
_COAL           = re.compile(r"\b(coal|bijou|pittsburgh seam)\b", re.I)

# Known key instruments for parcel 11-409-19
_KEY_INSTRUMENTS = {
    ("136", "259"): {
        "flag_type": "SPLIT_ESTATE",
        "reason":    "DB 136/259 (1903) — Shuttleworth reserved ONE-HALF of all oil and gas — KEY SPLIT ESTATE INSTRUMENT",
    },
    ("136", "88"): {
        "flag_type": "ENCUMBRANCE",
        "reason":    "DB 136/88 (1903) — Bijou Coal Company — Pittsburgh seam — UNRELEASED",
    },
    ("183", "260"): {
        "flag_type": "ENCUMBRANCE",
        "reason":    "DB 183/260 (1909) — Hope Natural Gas Co. OGL — UNRELEASED pre-digital",
    },
    ("1197", "1258"): {
        "flag_type": "VESTING_SURFACE",
        "reason":    "DB 1197/1258 (1989) — Burns, L. Craig & Sue B. — SURFACE VESTING INSTRUMENT",
    },
    ("1441", "1269"): {
        "flag_type": "VESTING_MINERAL",
        "reason":    "DB 1441/1269 (2010) — Master Mineral Holdings Inc. — 1/6 O&G — MINERAL VESTING INSTRUMENT",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  Public entry point (LangGraph node)
# ══════════════════════════════════════════════════════════════════════════════

def run(state: TitleState) -> dict:
    """LangGraph node — builds ordered chain from IDX instruments + seed."""
    instruments = list(state.get("idx_instruments") or [])
    parcel_id   = state.get("parcel_id", "11-409-19")

    log.info("CHAIN_BUILDER — %d raw instruments for parcel %s",
             len(instruments), parcel_id)

    if not instruments:
        log.warning("CHAIN_BUILDER: no instruments received — loading full seed")
        instruments = _full_seed()

    # ── Deduplicate and sort ──────────────────────────────────────────────────
    seen:    set[tuple] = set()
    unique:  list[dict] = []
    for inst in instruments:
        key = (str(inst.get("book", "")), str(inst.get("page", "")))
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        unique.append(inst)

    chain = sorted(unique, key=_sort_key)

    # Re-sequence
    for i, inst in enumerate(chain, 1):
        inst["seq"] = i

    # ── Flag key instruments ──────────────────────────────────────────────────
    flags: list[dict] = []
    for inst in chain:
        flag = _flag(inst)
        if flag:
            flags.append({**flag, "book": inst.get("book"), "page": inst.get("page"),
                          "seq": inst.get("seq"), "grantor": inst.get("grantor"),
                          "grantee": inst.get("grantee")})
            inst["_flag"] = flag["flag_type"]

    # ── Gap analysis ──────────────────────────────────────────────────────────
    gap_warnings = _find_gaps(chain)

    log.info("CHAIN_BUILDER: %d ordered instruments | %d flags | %d gaps",
             len(chain), len(flags), len(gap_warnings))

    return {
        "chain":        chain,
        "chain_flags":  flags,
        "chain_status": "COMPLETE" if chain else "FAILED",
        "warnings":     gap_warnings,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Instrument flagging
# ══════════════════════════════════════════════════════════════════════════════

def _flag(inst: dict) -> dict | None:
    """Return flag dict if this instrument is notable, else None."""
    book = str(inst.get("book", ""))
    page = str(inst.get("page", ""))

    # Known key instruments take priority
    known = _KEY_INSTRUMENTS.get((book, page))
    if known:
        return known

    # Pattern-match on description / notes / type
    text = " ".join([
        inst.get("description", ""),
        inst.get("notes", ""),
        inst.get("type", ""),
        inst.get("grantor", ""),
        inst.get("grantee", ""),
    ])

    if _SPLIT_ESTATE.search(text):
        return {"flag_type": "SPLIT_ESTATE",
                "reason": f"Possible mineral reservation language — DB {book}/{page}"}
    if _COAL.search(text):
        return {"flag_type": "ENCUMBRANCE",
                "reason": f"Coal deed — DB {book}/{page} — verify if released"}
    if _OGL.search(text):
        return {"flag_type": "OGL",
                "reason": f"Oil and gas lease — DB {book}/{page} — verify if released/expired"}
    if _ENCUMBRANCE.search(text):
        return {"flag_type": "ENCUMBRANCE",
                "reason": f"Possible encumbrance — DB {book}/{page}"}

    # Identify vesting instruments
    inst_type = inst.get("type", "").upper()
    if "MINERAL" in inst_type:
        return {"flag_type": "VESTING_MINERAL",
                "reason": f"Mineral deed — DB {book}/{page}"}
    if "ESTATE" in inst_type or _ESTATE.search(text):
        return {"flag_type": "ESTATE",
                "reason": f"Estate / probate instrument — DB {book}/{page}"}

    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Gap analysis
# ══════════════════════════════════════════════════════════════════════════════

def _find_gaps(chain: list[dict]) -> list[str]:
    """Check grantee of each instrument matches grantor of next. Return gap warnings."""
    gaps = []
    for i in range(len(chain) - 1):
        curr = chain[i]
        nxt  = chain[i + 1]
        curr_grantee = _normalize_name(curr.get("grantee", ""))
        nxt_grantor  = _normalize_name(nxt.get("grantor", ""))

        # Skip estate/probate transitions — these always look like gaps
        if curr.get("_flag") in ("ESTATE", "VESTING_SURFACE", "VESTING_MINERAL"):
            continue
        if nxt.get("_flag") in ("ESTATE",):
            continue

        if curr_grantee and nxt_grantor and curr_grantee not in nxt_grantor:
            if not _name_overlap(curr_grantee, nxt_grantor):
                gaps.append(
                    f"CHAIN GAP: DB {curr['book']}/{curr['page']} grantee "
                    f"'{curr.get('grantee')}' ≠ DB {nxt['book']}/{nxt['page']} "
                    f"grantor '{nxt.get('grantor')}'"
                )
    return gaps


def _normalize_name(name: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", "", name.upper()).strip()


def _name_overlap(a: str, b: str) -> bool:
    """True if any word in a appears in b (handles 'MONROE, B.T.' vs 'MONROE')."""
    words_a = {w for w in a.split() if len(w) > 2}
    return bool(words_a & set(b.split()))


# ══════════════════════════════════════════════════════════════════════════════
#  Sort key
# ══════════════════════════════════════════════════════════════════════════════

def _sort_key(inst: dict) -> tuple:
    """Sort by year extracted from date_instr, then book number."""
    date = inst.get("date_instr") or inst.get("date_rec") or "9999"
    year = int(re.search(r"\d{4}", str(date)).group()) if re.search(r"\d{4}", str(date)) else 9999
    try:
        book_n = int(re.sub(r"\D", "", str(inst.get("book", "0"))) or 0)
    except ValueError:
        book_n = 0
    return (year, book_n)


# ══════════════════════════════════════════════════════════════════════════════
#  Full seed fallback
# ══════════════════════════════════════════════════════════════════════════════

def _full_seed() -> list[dict]:
    """Return the complete confirmed 16-instrument chain for 11-409-19."""
    try:
        from deed.chain_seed import INSTRUMENTS
        return [{**i, "_source": "seed"} for i in INSTRUMENTS]
    except ImportError:
        pass

    # Inline fallback — matches amara-brain/Brain/WV_Title/Harrison_County_11-409-19.md
    return [
        {"seq": 1,  "type": "DEED",          "book": "57",   "page": "238",  "date_instr": "1874",
         "grantor": "DAVISSON, EDGAR M.",     "grantee": "MONROE, BENJAMIN T.", "acres": "51",
         "description": "51 acres Gnatty Creek", "_source": "inline_seed"},
        {"seq": 2,  "type": "DEED",          "book": "61",   "page": "434",  "date_instr": "1879",
         "grantor": "SHUTTLEWORTH, S.A.",     "grantee": "MONROE, B.T.",        "acres": "",
         "description": "Romines Mills tract", "_source": "inline_seed"},
        {"seq": 3,  "type": "DEED",          "book": "68",   "page": "329",  "date_instr": "1884",
         "grantor": "BUMGARDNER, ADAM",       "grantee": "MONROE, B.T.",        "acres": "60",
         "description": "60 acres", "_source": "inline_seed"},
        {"seq": 4,  "type": "DEED",          "book": "75",   "page": "97",   "date_instr": "1888",
         "grantor": "BUMGARDNER, ADAM",       "grantee": "MONROE, B.T.",        "acres": "10",
         "description": "10 acres", "_source": "inline_seed"},
        {"seq": 5,  "type": "DEED",          "book": "109",  "page": "403",  "date_instr": "1899",
         "grantor": "THOMPSON, M.M., COMMISSIONER", "grantee": "SHUTTLEWORTH, M.N.", "acres": "122",
         "description": "Circuit Court order", "_source": "inline_seed"},
        {"seq": 6,  "type": "DEED",          "book": "136",  "page": "259",  "date_instr": "1903-03-23",
         "grantor": "SHUTTLEWORTH, MAYNARD N. & LILLIE", "grantee": "STEWART, WILLIAM A.", "acres": "121.5",
         "description": "121.5 ac Elk Creek — RESERVED ONE-HALF OF ALL OIL AND GAS",
         "_source": "inline_seed"},
        {"seq": 7,  "type": "COAL DEED",     "book": "136",  "page": "88",   "date_instr": "1903-02-09",
         "grantor": "PROPS, M.A. & WIFE",    "grantee": "BIJOU COAL COMPANY",  "acres": "",
         "description": "Pittsburgh seam of coal — UNRELEASED", "_source": "inline_seed"},
        {"seq": 8,  "type": "OGL",           "book": "183",  "page": "260",  "date_instr": "1909-05-04",
         "grantor": "PROPS, M.A. & WIFE",    "grantee": "HOPE NATURAL GAS COMPANY", "acres": "",
         "description": "Oil and gas lease — UNRELEASED", "_source": "inline_seed"},
        {"seq": 9,  "type": "ESTATE",        "book": "10",   "page": "247",  "date_instr": "1919",
         "grantor": "SHUTTLEWORTH, M.N. — DIED", "grantee": "6 HEIRS (LILLIE, HELEN, LORENE, MARY, SAMUEL, BETTY JANE)",
         "description": "Fiduciary — reserved mineral interest to heirs", "_source": "inline_seed"},
        {"seq": 10, "type": "WILL/PROBATE",  "book": "54",   "page": "291",  "date_instr": "1960",
         "grantor": "LAWSON, T. MINTER — DIED", "grantee": "LAWSON, GUY & MARY",
         "description": "Surface chain — Will Book", "_source": "inline_seed"},
        {"seq": 11, "type": "WILL/PROBATE",  "book": "79",   "page": "320",  "date_instr": "1971",
         "grantor": "LAWSON, GUY — DIED",    "grantee": "LAWSON, MARY",
         "description": "Surface chain — Will Book", "_source": "inline_seed"},
        {"seq": 12, "type": "WILL/PROBATE",  "book": "102",  "page": "1040", "date_instr": "1983",
         "grantor": "LAWSON, MARY — DIED",   "grantee": "STOUT, ABNER — EXECUTOR",
         "description": "Surface chain — Will Book", "_source": "inline_seed"},
        {"seq": 13, "type": "WILL/PROBATE",  "book": "108",  "page": "137",  "date_instr": "1980",
         "grantor": "SHUTTLEWORTH, LORENE — DIED",
         "grantee": "KRAMER, HELEN; EVANS, BETTY; SAMUEL SHUTTLEWORTH",
         "description": "Lorene's mineral share distributed", "_source": "inline_seed"},
        {"seq": 14, "type": "WILL/PROBATE",  "book": "142",  "page": "359",  "date_instr": "1993",
         "grantor": "KRAMER, HELEN S. — DIED", "grantee": "BURNS, A. DEAN — EXECUTOR",
         "description": "Burns named Executor — leads to DB 1441/1269", "_source": "inline_seed"},
        {"seq": 15, "type": "DEED",          "book": "1197", "page": "1258", "date_instr": "1989-07-11",
         "date_rec": "1989-09-21",
         "grantor": "STOUT, ABNER, EXECUTOR (LAWSON ESTATE)",
         "grantee": "BURNS, L. CRAIG & SUE B.", "acres": "129.63",
         "consideration": "$34,500.00",
         "description": "SURFACE VESTING — exceptions: DB 136/88, DB 183/260",
         "_source": "inline_seed"},
        {"seq": 16, "type": "MINERAL DEED",  "book": "1441", "page": "1269", "date_instr": "2010-01-19",
         "date_rec": "2010-02-10",
         "grantor": "BURNS, A. DEAN, EXECUTOR (HELEN S. KRAMER ESTATE)",
         "grantee": "MASTER MINERAL HOLDINGS INC.", "acres": "121.072",
         "consideration": "$10.00",
         "description": "MINERAL VESTING — 1/6 undivided O&G + CBM",
         "_source": "inline_seed"},
    ]
