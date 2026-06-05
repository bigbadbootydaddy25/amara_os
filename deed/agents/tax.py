"""
TAX agent — Harrison County Assessor property tax lookup.
URL: https://harrisoncountyassessor.com/ownershipsearch.aspx
Pulls account number, ticket number, owner, land value, mineral value, class.
NOTE: Use Sheriff of Harrison County for tax tickets, not Assessor portal.
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, DISTRICT, COUNTY, HEADERS, TIMEOUT, NOTES_FILE

log = logging.getLogger("TAX")

ASSESSOR_URL = "https://harrisoncountyassessor.com/ownershipsearch.aspx"
SHERIFF_URL  = "https://www.harrisoncountywv.com/sheriff.aspx"


def run() -> dict:
    log.info("TAX — Harrison County Assessor | parcel %s", PARCEL_ID)
    record = {}
    errors = []

    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: load assessor search page for viewstate
    try:
        r = session.get(ASSESSOR_URL, timeout=TIMEOUT)
        if r.status_code == 403:
            msg = "Assessor returned 403 — cloud IP blocked (must run from Mac)"
            log.error(msg)
            errors.append(msg)
            _note(msg)
            return _result(record, errors, "FAILED")
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        log.info("Assessor search page loaded (HTTP 200)")
    except Exception as e:
        msg = f"Assessor unreachable: {e}"
        log.error(msg)
        errors.append(msg)
        _note(msg)
        return _result(record, errors, "FAILED")

    vs = _viewstate(soup)

    # Step 2: search strategies
    district_code = "11"  # District 11 = Elk
    map_num       = "409"
    parcel_num    = "19"

    searches = [
        # by parcel number fields
        {**vs, "txtDistrict": district_code, "txtMap": map_num,
               "txtParcel": parcel_num, "btnSearch": "Search"},
        # full parcel string
        {**vs, "txtParcelID": PARCEL_ID, "btnSearch": "Search"},
        {**vs, "txtParcelID": PARCEL_ID.replace("-",""), "btnSearch": "Search"},
        # owner name fallback
        {**vs, "txtOwner": "STRUNK", "btnSearch": "Search"},
    ]

    for i, payload in enumerate(searches, 1):
        log.info("Tax search %d/%d: %s", i, len(searches),
                 {k: v for k, v in payload.items() if k not in vs})
        try:
            r = session.post(ASSESSOR_URL, data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            soup2 = BeautifulSoup(r.content, "lxml")
            rec = _parse_assessor(soup2)
            if rec:
                record = rec
                log.info("Tax record found on search %d", i)
                break
            log.info("  → 0 results")
        except Exception as e:
            log.warning("Tax search %d failed: %s", i, e)
        time.sleep(1)

    if record:
        _log_record(record)
    else:
        msg = (f"No tax record found for parcel {PARCEL_ID} — "
               "site may block non-Mac IPs or parcel may be listed under different owner/district")
        log.warning(msg)
        _note(msg)
        errors.append(msg)

    status = "COMPLETE" if record and not errors else ("PARTIAL" if record else "FAILED")
    return _result(record, errors, status)


def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
                 "__EVENTTARGET", "__EVENTARGUMENT"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_assessor(soup: BeautifulSoup) -> dict | None:
    """Extract property record from assessor results page."""
    result = {}

    # Try structured table first
    table = soup.find("table", id=re.compile(r"grid|result|property", re.I))
    if not table:
        table = soup.find("table")

    if table:
        rows = table.find_all("tr")
        headers = []
        if rows:
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not any(cells):
                continue
            for h, v in zip(headers, cells):
                if not v:
                    continue
                if   "owner"   in h:                    result["owner_name"]   = v
                elif "account" in h or "acct" in h:     result["account_no"]   = v
                elif "ticket"  in h:                    result["ticket_no"]    = v
                elif "district" in h:                   result["district"]     = v
                elif "map"     in h:                    result["map_num"]      = v
                elif "parcel"  in h:                    result["parcel_id"]    = v
                elif "class"   in h:                    result["class_code"]   = v
                elif "land"    in h and "value" in h:   result["land_value"]   = v
                elif "mineral" in h:                    result["mineral_value"]= v
                elif "total"   in h and "value" in h:   result["total_value"]  = v
                elif "address" in h or "addr" in h:     result["owner_addr"]   = v
            if result.get("owner_name") or result.get("account_no"):
                return result

    # Fall back: full-page text scan
    text = soup.get_text(" ", strip=True)
    for field, pattern in [
        ("owner_name",    r"Owner[:\s]+([A-Z][A-Z\s,&.'-]{2,60})"),
        ("account_no",    r"Account[:\s#]+([A-Z0-9\-]+)"),
        ("ticket_no",     r"Ticket[:\s#]+([A-Z0-9\-]+)"),
        ("district",      r"District[:\s]+([A-Za-z0-9\s\-]{1,30})"),
        ("land_value",    r"Land\s+Value[:\s\$]+([\d,]+)"),
        ("mineral_value", r"Mineral\s+Value[:\s\$]+([\d,]+)"),
        ("total_value",   r"Total\s+(?:Assessed\s+)?Value[:\s\$]+([\d,]+)"),
        ("class_code",    r"Class[:\s]+([A-Z0-9]{1,5})"),
    ]:
        m = re.search(pattern, text, re.I | re.M)
        if m:
            result[field] = m.group(1).strip()

    return result if result.get("owner_name") or result.get("account_no") else None


def _log_record(r: dict) -> None:
    for label, key in [
        ("Owner Name",     "owner_name"),
        ("Owner Address",  "owner_addr"),
        ("Account Number", "account_no"),
        ("Ticket Number",  "ticket_no"),
        ("District",       "district"),
        ("Land Value",     "land_value"),
        ("Mineral Value",  "mineral_value"),
        ("Total Value",    "total_value"),
        ("Class Code",     "class_code"),
    ]:
        val = r.get(key, "NOT FOUND")
        log.info("  %-25s %s", label + ":", val)
        _note(f"TAX {label}: {val}")


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[TAX] {msg}\n")
    except Exception:
        pass


def _result(record: dict, errors: list, status: str) -> dict:
    return {
        "agent":   "TAX",
        "status":  status,
        "record":  record,
        "errors":  errors,
    }
