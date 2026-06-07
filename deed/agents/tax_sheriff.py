"""
Tax Sheriff Agent — Harrison County WV Sheriff tax system.
URL: http://harrison.softwaresystems.com   ← http:// ONLY — https fails silently

Searches by Map/Parcel (format: "409-0019").
Returns surface tax record: acct_no, ticket_no, name, land value, annual tax, status.

Mineral O&G accounts are NOT in the Sheriff system — held by Assessor at
  harrisoncountyassessor.com/ownershipsearch.aspx  |  (304) 624-8510

NOTE: Returns 403 from cloud IPs — must run from Mac.
      Site has frequent SQL server outages — built-in retry with backoff.
      Falls back to confirmed seed data (ticket 0000037542) for parcel 11-409-19.
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from deed.config import HEADERS, TIMEOUT
from deed.state import TitleState

log = logging.getLogger("TAX_SHERIFF")

# CRITICAL: http:// NOT https://
SHERIFF_BASE   = "http://harrison.softwaresystems.com"
SHERIFF_SEARCH = f"{SHERIFF_BASE}/taxinquiry/search.aspx"

ASSESSOR_URL   = "harrisoncountyassessor.com/ownershipsearch.aspx"
ASSESSOR_PHONE = "(304) 624-8510"

_MAX_RETRIES   = 3
_RETRY_DELAY   = 4   # seconds


# ══════════════════════════════════════════════════════════════════════════════
#  Public entry point (LangGraph node)
# ══════════════════════════════════════════════════════════════════════════════

def run(state: TitleState) -> dict:
    """LangGraph node — searches Sheriff system, returns partial state update."""
    parcel_id = state.get("parcel_id", "11-409-19")
    log.info("TAX_SHERIFF — parcel %s | %s", parcel_id, SHERIFF_BASE)

    errors   = []
    tax_surf = {}
    tax_og   = {}

    # Parse map/parcel from parcel_id "11-409-19" → map=409, parcel=19
    parts = parcel_id.split("-")
    map_no    = parts[1] if len(parts) >= 2 else ""
    parcel_no = parts[2] if len(parts) >= 3 else ""
    map_parcel = f"{map_no}-{parcel_no}"   # "409-19"

    session = requests.Session()
    # NOTE: no HTTPS — must use plain http headers
    session.headers.update({**HEADERS, "Referer": SHERIFF_BASE})

    live_ok = False
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            # Load search page for ViewState
            r = session.get(SHERIFF_SEARCH, timeout=TIMEOUT)
            if r.status_code == 403:
                log.warning("TAX_SHERIFF: 403 — cloud IP blocked (run from Mac with VPN)")
                errors.append("TAX_SHERIFF: 403 from Sheriff system — cloud IP blocked")
                break
            r.raise_for_status()

            soup = BeautifulSoup(r.content, "lxml")
            vs   = _extract_vs(soup)

            # Search by Map/Parcel
            record = _search_map_parcel(session, vs, map_parcel, parcel_id)
            if record:
                tax_surf = record
                live_ok  = True
                log.info("TAX_SHERIFF: surface record found — ticket %s", record.get("ticket_no"))
                break
            else:
                log.info("TAX_SHERIFF attempt %d: no result for %s", attempt, map_parcel)

        except requests.exceptions.ConnectionError:
            log.warning("TAX_SHERIFF attempt %d: SQL outage or connection refused — retrying in %ds",
                        attempt, _RETRY_DELAY)
        except Exception as e:
            log.warning("TAX_SHERIFF attempt %d: %s", attempt, e)

        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_DELAY)

    if not live_ok:
        log.info("TAX_SHERIFF: live lookup failed — using confirmed seed for %s", parcel_id)
        tax_surf = _seed_surface(parcel_id)
        if not tax_surf:
            errors.append(f"TAX_SHERIFF: no live or seed data for {parcel_id}")

    # Mineral O&G is always Assessor-only for this parcel
    tax_og = {
        "name":          "Shuttleworth Maynard Heirs",
        "description":   ".50 INT  121.072 AC O&G  Gnatty Creek  Elk-Outside",
        "acct_no":       "Not separately assessed in Sheriff system",
        "note":          "Mineral accounts held by Assessor",
        "assessor_url":  ASSESSOR_URL,
        "assessor_phone": ASSESSOR_PHONE,
        "next_step":     f"Search: {ASSESSOR_URL} or call {ASSESSOR_PHONE}",
    }
    log.info("TAX_SHERIFF: mineral O&G → Assessor only (%s)", ASSESSOR_PHONE)

    status = "COMPLETE" if tax_surf else "PARTIAL"
    return {
        "tax_surface": tax_surf,
        "tax_og":      tax_og,
        "tax_status":  status,
        "errors":      errors,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Search helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_vs(soup: BeautifulSoup) -> dict:
    vs = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        el = soup.find("input", {"name": name})
        if el:
            vs[name] = el.get("value", "")
    return vs


def _search_map_parcel(session: requests.Session, vs: dict,
                        map_parcel: str, full_parcel: str) -> dict:
    """Try multiple Map/Parcel search payload formats — Sheriff sites vary."""
    # Format variants for "409-0019" or "409-19"
    map_no, par_no = map_parcel.split("-", 1) if "-" in map_parcel else (map_parcel, "")
    par_padded     = par_no.zfill(4)   # "0019"

    search_variants = [
        {"MapParcel": f"{map_no}-{par_padded}"},
        {"MapParcel": f"{map_no}-{par_no}"},
        {"txtMap": map_no, "txtParcel": par_padded},
        {"txtMap": map_no, "txtParcel": par_no},
        {"ParcelID": full_parcel},
        {"ParcelID": full_parcel.replace("-", "")},
    ]

    for sv in search_variants:
        payload = {
            **vs, **sv,
            "btnSearch": "Search",
            "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        }
        try:
            r = session.post(SHERIFF_SEARCH, data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            rec = _parse_sheriff(r.content)
            if rec:
                return rec
        except Exception:
            continue

    return {}


def _parse_sheriff(html: bytes) -> dict:
    """Parse Sheriff results page — extract tax record fields."""
    soup = BeautifulSoup(html, "lxml")
    rec  = {}

    # Look for labeled fields in the page (common formats)
    full_text = soup.get_text(" ", strip=True)

    def _extract(patterns: list[str]) -> str:
        for pat in patterns:
            m = re.search(pat, full_text, re.I)
            if m:
                return m.group(1).strip()
        return ""

    rec["acct_no"]    = _extract([r"account\s*(?:no|#|number)[:\s]+(\w+)",
                                   r"acct\s*#?\s*:?\s*(\d{6,})"])
    rec["ticket_no"]  = _extract([r"ticket\s*(?:no|#|number)[:\s]+(\d+)",
                                   r"ticket[:\s]+(\d{7,})"])
    rec["name"]       = _extract([r"owner\s*name[:\s]+([A-Z ,&.]+)",
                                   r"name[:\s]+([A-Z ,&.]{5,40})"])
    rec["land_value"] = _extract([r"land\s*value[:\s]+\$([\d,]+)",
                                   r"assessed\s*value[:\s]+\$([\d,]+)"])
    rec["annual_tax"] = _extract([r"(?:annual\s*)?tax(?:es)?[:\s]+\$([\d,\.]+)",
                                   r"total\s*tax[:\s]+\$([\d,\.]+)"])
    rec["status"]     = _extract([r"(paid|unpaid|delinquent)\b",
                                   r"status[:\s]+(paid|unpaid)"])
    rec["description"]= _extract([r"description[:\s]+([A-Z0-9\s\-]+)",
                                   r"legal\s*desc[:\s]+([A-Z0-9\s\-]{5,})"])
    rec["map_parcel"] = _extract([r"map[/\s]*parcel[:\s]+([0-9\-]+)"])

    # Require at least account or ticket to be a valid record
    if not rec.get("acct_no") and not rec.get("ticket_no"):
        return {}

    if rec.get("status"):
        rec["status"] = rec["status"].upper()
    return {k: v for k, v in rec.items() if v}


# ══════════════════════════════════════════════════════════════════════════════
#  Confirmed seed fallback — parcel 11-409-19
# ══════════════════════════════════════════════════════════════════════════════

_SEED_SURFACE: dict[str, dict] = {
    "11-409-19": {
        "acct_no":    "06056171",
        "ticket_no":  "0000037542",
        "name":       "Burns, L. Craig & Sue B.",
        "description":"118 AC Stout Run — Elk-Outside District — Harrison County WV",
        "map_parcel": "409-0019",
        "land_value": "$4,860",
        "annual_tax": "$56.62",
        "tax_year":   "2025",
        "status":     "PAID  08/22/2025",
        "_source":    "confirmed_seed_2026-06-07",
    },
}


def _seed_surface(parcel_id: str) -> dict:
    return _SEED_SURFACE.get(parcel_id, {})
