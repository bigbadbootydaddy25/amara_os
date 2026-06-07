"""
IDX Agent — Harrison County WV Deed Index
URL: https://lookup.harrisoncountywv.com

Two search modes:
  1. Individual name  — last name search, returns all instruments for that person
  2. Book / Page      — returns the specific instrument record

Returns structured instrument list:
  [{"seq","type","grantor","grantee","book","page","date_instr","date_rec",
    "acres","consideration","description","doc_url","notes"}]

NOTE: Returns 403 from cloud IPs — must run from Mac with Texhoma VPN.
      Falls back to seed data (deed/chain_seed.py) when unreachable.
"""
import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from deed.config import HEADERS, TIMEOUT, OUTPUT_DIR
from deed.state import TitleState

log = logging.getLogger("IDX")

IDX_BASE = "https://lookup.harrisoncountywv.com"
_SEARCH  = f"{IDX_BASE}/searchresults.aspx"
_HOME    = f"{IDX_BASE}/default.aspx"


# ══════════════════════════════════════════════════════════════════════════════
#  Public entry point (LangGraph node)
# ══════════════════════════════════════════════════════════════════════════════

def run(state: TitleState) -> dict:
    """LangGraph node — searches IDX, returns partial state update."""
    parcel_id    = state.get("parcel_id", "11-409-19")
    search_names = state.get("search_names", ["Burns", "Shuttleworth"])
    seed_bk_pg   = state.get("seed_bk_pg",  ["1441/1269", "1197/1258"])

    log.info("IDX — parcel %s | names=%s bk_pg=%s",
             parcel_id, search_names, seed_bk_pg)

    instruments: list[dict] = []
    errors:      list[str]  = []
    session = _session()

    # ── Try live IDX search ───────────────────────────────────────────────────
    try:
        vs = _get_viewstate(session)
        live_ok = vs is not None

        if live_ok:
            # Search by each individual name
            for name in search_names:
                found = _search_individual(session, vs, name)
                for inst in found:
                    if not _dup(inst, instruments):
                        instruments.append(inst)
                vs = _get_viewstate(session)  # refresh for next request
                time.sleep(0.5)

            # Search by each Book/Page
            for bk_pg in seed_bk_pg:
                book, page = _parse_bk_pg(bk_pg)
                if book and page:
                    found = _search_bk_pg(session, vs, book, page)
                    for inst in found:
                        if not _dup(inst, instruments):
                            instruments.append(inst)
                    vs = _get_viewstate(session)
                    time.sleep(0.5)

            log.info("IDX live: found %d instruments", len(instruments))
        else:
            errors.append("IDX: could not load search page (403 or timeout) — using seed data")

    except Exception as e:
        errors.append(f"IDX: {e} — falling back to seed data")
        live_ok = False

    # ── Merge seed data ───────────────────────────────────────────────────────
    seed = _load_seed(parcel_id)
    seed_added = 0
    for inst in seed:
        if not _dup(inst, instruments):
            inst["_source"] = "seed"
            instruments.append(inst)
            seed_added += 1

    if seed_added:
        log.info("IDX seed: merged %d pre-digital instruments", seed_added)

    status = ("COMPLETE" if (live_ok and instruments) else
              "SEED_ONLY" if instruments else
              "FAILED")

    return {
        "idx_instruments": instruments,
        "idx_status":      status,
        "errors":          errors,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP helpers
# ══════════════════════════════════════════════════════════════════════════════

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get_viewstate(session: requests.Session) -> dict | None:
    """GET the IDX homepage and extract ASP.NET hidden fields."""
    try:
        r = session.get(_HOME, timeout=TIMEOUT)
        if r.status_code == 403:
            log.warning("IDX: 403 — cloud IP blocked. Run from Mac with Texhoma VPN.")
            return None
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        return _extract_vs(soup)
    except Exception as e:
        log.warning("IDX: homepage unreachable — %s", e)
        return None


def _extract_vs(soup: BeautifulSoup) -> dict:
    """Extract ASP.NET ViewState/EventValidation hidden fields."""
    vs = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
                 "__EVENTTARGET", "__EVENTARGUMENT"):
        el = soup.find("input", {"name": name})
        if el:
            vs[name] = el.get("value", "")
    return vs


def _search_individual(session: requests.Session, vs: dict, last_name: str) -> list[dict]:
    """POST individual name search — returns list of instrument dicts."""
    payload = {
        **vs,
        "ctl00$ContentPlaceHolder1$txtLastName": last_name.upper(),
        "ctl00$ContentPlaceHolder1$ddlSearchType": "Individual",
        "ctl00$ContentPlaceHolder1$btnSearch": "Search",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
    }
    # Try alternate field name patterns (different IDX installs vary)
    fallback_payloads = [
        {**vs, "LastName": last_name.upper(), "SearchType": "Individual", "btnSearch": "Search"},
        {**vs, "txtLastName": last_name.upper(), "rdSearchType": "I", "btnSearch": "Search"},
    ]

    for pl in [payload] + fallback_payloads:
        try:
            r = session.post(_SEARCH, data=pl, timeout=TIMEOUT)
            if r.ok:
                instruments = _parse_results(r.content, source=f"IDX-name:{last_name}")
                if instruments:
                    log.info("IDX individual '%s': %d instruments", last_name, len(instruments))
                    return instruments
        except Exception as e:
            log.debug("IDX individual search failed (%s): %s", last_name, e)
    return []


def _search_bk_pg(session: requests.Session, vs: dict, book: str, page: str) -> list[dict]:
    """POST Book/Page search — returns list (usually 1) of instrument dicts."""
    payload = {
        **vs,
        "ctl00$ContentPlaceHolder1$txtBookNum": book,
        "ctl00$ContentPlaceHolder1$txtPageNum": page,
        "ctl00$ContentPlaceHolder1$ddlSearchType": "Book",
        "ctl00$ContentPlaceHolder1$btnSearch": "Search",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
    }
    fallback_payloads = [
        {**vs, "BookNumber": book, "PageNumber": page, "SearchType": "Book", "btnSearch": "Search"},
        {**vs, "txtBook": book, "txtPage": page, "rdSearchType": "B", "btnSearch": "Search"},
    ]
    for pl in [payload] + fallback_payloads:
        try:
            r = session.post(_SEARCH, data=pl, timeout=TIMEOUT)
            if r.ok:
                instruments = _parse_results(r.content, source=f"IDX-bkpg:{book}/{page}")
                if instruments:
                    log.info("IDX Book/Page %s/%s: %d instruments", book, page, len(instruments))
                    return instruments
        except Exception as e:
            log.debug("IDX Book/Page search failed (%s/%s): %s", book, page, e)
    return []


# ══════════════════════════════════════════════════════════════════════════════
#  HTML result parser
# ══════════════════════════════════════════════════════════════════════════════

# Column label patterns (case-insensitive) → normalized field name
_COL_MAP = {
    r"type|instr.*type":            "type",
    r"grantor":                     "grantor",
    r"grantee":                     "grantee",
    r"book":                        "book",
    r"page":                        "page",
    r"record.*date|date.*rec":      "date_rec",
    r"instr.*date|date.*instr":     "date_instr",
    r"acres?|acreage":              "acres",
    r"consider":                    "consideration",
    r"desc|legal":                  "description",
    r"doc|link|image|view":         "doc_url",
}


def _parse_results(html: bytes, source: str = "") -> list[dict]:
    """Parse IDX results HTML table into list of instrument dicts."""
    soup = BeautifulSoup(html, "lxml")
    instruments = []

    # Find the primary results table
    tables = soup.find_all("table")
    best_table = None
    best_rows  = 0
    for tbl in tables:
        rows = tbl.find_all("tr")
        if len(rows) > best_rows:
            best_table = tbl
            best_rows  = len(rows)

    if not best_table or best_rows < 2:
        return []

    rows = best_table.find_all("tr")
    # Map header columns
    col_idx: dict[str, int] = {}
    hdr_row = rows[0]
    for i, th in enumerate(hdr_row.find_all(["th", "td"])):
        text = th.get_text(strip=True).lower()
        for pattern, field in _COL_MAP.items():
            if re.search(pattern, text):
                col_idx[field] = i
                break

    for seq, row in enumerate(rows[1:], 1):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        def _cell(field: str) -> str:
            idx = col_idx.get(field)
            if idx is None or idx >= len(cells):
                return ""
            return cells[idx].get_text(" ", strip=True)

        def _href(field: str) -> str:
            idx = col_idx.get(field, col_idx.get("doc_url"))
            if idx is None or idx >= len(cells):
                return ""
            a = cells[idx].find("a")
            return (IDX_BASE + a["href"]) if (a and a.get("href", "").startswith("/")) else (a["href"] if a else "")

        inst = {
            "seq":          seq,
            "type":         _cell("type") or "DEED",
            "grantor":      _cell("grantor").upper(),
            "grantee":      _cell("grantee").upper(),
            "book":         _cell("book"),
            "page":         _cell("page"),
            "date_rec":     _cell("date_rec"),
            "date_instr":   _cell("date_instr"),
            "acres":        _cell("acres"),
            "consideration":_cell("consideration"),
            "description":  _cell("description"),
            "doc_url":      _href("doc_url"),
            "notes":        "",
            "_source":      source,
        }

        # Skip blank/header rows
        if inst["grantor"] or inst["book"]:
            instruments.append(inst)

    return instruments


# ══════════════════════════════════════════════════════════════════════════════
#  Seed data fallback
# ══════════════════════════════════════════════════════════════════════════════

def _load_seed(parcel_id: str) -> list[dict]:
    """Load pre-digital chain seed from deed/chain_seed.py."""
    try:
        from deed.chain_seed import INSTRUMENTS
        # Only return pre-1970 instruments (not in digital system)
        return [
            {**i, "_source": "seed"}
            for i in INSTRUMENTS
            if int(i.get("date_instr", "9999")[:4] or 9999) < 1970
        ]
    except ImportError:
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_bk_pg(bk_pg: str) -> tuple[str, str]:
    """Parse "1441/1269" or "DB 1441/1269" → ("1441", "1269")."""
    m = re.search(r"(\d+)\s*/\s*(\d+)", bk_pg)
    return (m.group(1), m.group(2)) if m else ("", "")


def _dup(inst: dict, existing: list[dict]) -> bool:
    """True if this instrument (same book/page) is already in the list."""
    if not inst.get("book") or not inst.get("page"):
        return False
    for e in existing:
        if e.get("book") == inst["book"] and e.get("page") == inst["page"]:
            return True
    return False
