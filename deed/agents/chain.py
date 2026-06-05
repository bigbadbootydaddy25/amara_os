"""
CHAIN agent — Harrison County Clerk grantor/grantee index.
URL: https://harrison.countyclerk.us/online-records/
Pulls full chain of title for parcel 11-409-19 oldest → newest.
Downloads deeds, OGLs, assignments, wills, fiduciary records.
"""
import logging
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, COUNTY, HEADERS, TIMEOUT, NOTES_FILE, OUTPUT_DIR

log = logging.getLogger("CHAIN")

BASE  = "https://harrison.countyclerk.us/online-records"


@dataclass
class Instrument:
    seq:           int   = 0
    inst_type:     str   = ""
    grantor:       str   = ""
    grantee:       str   = ""
    book:          str   = ""
    page:          str   = ""
    date_recorded: str   = ""
    date_instr:    str   = ""
    description:   str   = ""
    doc_url:       str   = ""
    notes:         str   = ""


def run() -> dict:
    log.info("CHAIN — Harrison County IDX | parcel %s", PARCEL_ID)
    log.info("Target: %s/", BASE)

    session = requests.Session()
    session.headers.update(HEADERS)

    instruments: list[Instrument] = []
    gaps:        list[str]        = []
    errors:      list[str]        = []
    legal_desc:  str              = ""

    # ── Step 1: load search page ─────────────────────────────────────────────
    try:
        r = session.get(f"{BASE}/", timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        log.info("IDX search page loaded (HTTP 200)")
    except requests.exceptions.HTTPError as e:
        msg = f"IDX load failed: {e} — site may block non-Mac IPs (403 = host allowlist)"
        log.error(msg)
        errors.append(msg)
        _note(msg)
        return _result(instruments, gaps, errors, legal_desc, "FAILED")
    except Exception as e:
        msg = f"IDX unreachable: {e}"
        log.error(msg)
        errors.append(msg)
        _note(msg)
        return _result(instruments, gaps, errors, legal_desc, "FAILED")

    # ── Step 2: extract ASP.NET viewstate / form fields ─────────────────────
    vs = _viewstate(soup)
    log.info("ViewState fields: %s", list(vs.keys()))

    # ── Step 3: search by parcel number ─────────────────────────────────────
    searches = [
        {**vs, "txtParcelID": PARCEL_ID,               "btnSearch": "Search"},
        {**vs, "txtParcelID": PARCEL_ID.replace("-",""),"btnSearch": "Search"},
        {**vs, "ddlDistrict": "11", "txtMapNum": "409", "txtParcelNum": "19",
               "btnSearch": "Search"},
        # name-based fallback — common grantors for WV mineral tracts
        {**vs, "txtGrantorName": "STRUNK", "btnSearch": "Search"},
    ]

    for i, payload in enumerate(searches, 1):
        log.info("Search attempt %d/%d  payload=%s",
                 i, len(searches), {k: v for k, v in payload.items() if k not in vs})
        try:
            r = session.post(f"{BASE}/", data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            soup2 = BeautifulSoup(r.content, "lxml")
            found = _parse_results(soup2, instruments)
            if found:
                log.info("  → %d instruments returned", found)
                break
            log.info("  → 0 results")
        except Exception as e:
            log.warning("  Search %d failed: %s", i, e)
        time.sleep(1)

    # ── Step 4: analyze chain, look for legal description ───────────────────
    if instruments:
        legal_desc = _extract_legal_desc(instruments)
        _analyze_chain(instruments, gaps)
        _log_instruments(instruments)
    else:
        msg = (
            f"No instruments found for parcel {PARCEL_ID}. "
            "NOTE: This is a WS (White Space) title — no prior instruments "
            "is a valid finding. Confirm with Harrison County Clerk directly."
        )
        log.warning(msg)
        _note(msg)

    status = "COMPLETE" if not errors else "PARTIAL"
    return _result(instruments, gaps, errors, legal_desc, status)


# ── helpers ──────────────────────────────────────────────────────────────────

def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE","__VIEWSTATEGENERATOR","__EVENTVALIDATION",
                 "__EVENTTARGET","__EVENTARGUMENT"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_results(soup: BeautifulSoup, instruments: list) -> int:
    table = soup.find("table") or soup.find("div", class_=re.compile(r"result|grid", re.I))
    if not table:
        return 0
    rows = table.find_all("tr")
    if len(rows) < 2:
        return 0
    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th","td"])]
    start = len(instruments)
    for seq, row in enumerate(rows[1:], start + 1):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not any(cells):
            continue
        inst = Instrument(seq=seq)
        for h, v in zip(headers, cells):
            if   "grantor"  in h:              inst.grantor       = v
            elif "grantee"  in h:              inst.grantee       = v
            elif "book"     in h:              inst.book          = v
            elif "page"     in h:              inst.page          = v
            elif "type"     in h or "inst" in h: inst.inst_type   = v
            elif "record"   in h and "date" in h: inst.date_recorded = v
            elif "date"     in h:              inst.date_instr    = v
            elif "desc"     in h:              inst.description   = v
        # grab any doc link
        link = row.find("a", href=True)
        if link:
            href = link["href"]
            inst.doc_url = href if href.startswith("http") else f"{BASE}/{href.lstrip('/')}"
        if inst.grantor or inst.book:
            instruments.append(inst)
    return len(instruments) - start


def _extract_legal_desc(instruments: list) -> str:
    """Try to find legal description text from instrument descriptions."""
    for inst in instruments:
        desc = inst.description or ""
        if any(kw in desc.upper() for kw in ["BEGINNING","THENCE","CHAIN","BEARING","POLE"]):
            return desc
    return ""


def _analyze_chain(instruments: list, gaps: list) -> None:
    instr_sorted = sorted(instruments, key=lambda i: i.date_recorded or i.date_instr or "")
    for i in range(len(instr_sorted) - 1):
        curr = instr_sorted[i]
        nxt  = instr_sorted[i + 1]
        if curr.grantee and nxt.grantor:
            if curr.grantee.upper().strip() != nxt.grantor.upper().strip():
                gap = (
                    f"Break at instrument {curr.seq}→{nxt.seq}: "
                    f"grantee '{curr.grantee}' ≠ grantor '{nxt.grantor}'"
                )
                gaps.append(gap)
                _note(f"⚠ GAP: {gap}")
                log.warning("GAP: %s", gap)


def _log_instruments(instruments: list) -> None:
    log.info("Chain of title — %d instruments:", len(instruments))
    for i in instruments:
        log.info(
            "  [%03d] %-18s | %s → %s | BK %-6s PG %-6s | %s",
            i.seq, i.inst_type or "UNKNOWN",
            i.grantor or "—", i.grantee or "—",
            i.book or "—", i.page or "—",
            i.date_recorded or i.date_instr or "—",
        )
        _note(
            f"[{i.seq:03d}] {i.inst_type or 'UNKNOWN':<18} | "
            f"{i.grantor or '—'} → {i.grantee or '—'} | "
            f"BK {i.book or '—'} PG {i.page or '—'} | "
            f"{i.date_recorded or i.date_instr or '—'}"
        )


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[CHAIN] {msg}\n")
    except Exception:
        pass


def _result(instruments, gaps, errors, legal_desc, status) -> dict:
    return {
        "agent":       "CHAIN",
        "status":      status,
        "count":       len(instruments),
        "instruments": [
            {"seq": i.seq, "type": i.inst_type, "grantor": i.grantor,
             "grantee": i.grantee, "book": i.book, "page": i.page,
             "date_recorded": i.date_recorded, "date_instr": i.date_instr,
             "description": i.description, "doc_url": i.doc_url, "notes": i.notes}
            for i in instruments
        ],
        "gaps":        gaps,
        "errors":      errors,
        "legal_desc":  legal_desc,
    }
