"""
WELL agent — WV Geological & Economic Survey Pipeline Plus (OGWIS).
URL: https://wvgs.wvnet.edu/pipe2/OGWISHelp.aspx
Pulls oil/gas well API numbers, operator, spud date, completion, production
for Harrison County, Elk District (11-409-19 area).
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, DISTRICT, COUNTY, HEADERS, TIMEOUT, NOTES_FILE

log = logging.getLogger("WELL")

OGWIS_BASE   = "https://wvgs.wvnet.edu/pipe2"
OGWIS_SEARCH = f"{OGWIS_BASE}/OGWISHelp.aspx"
# Alternative WVDEP OOG well search
OOG_SEARCH   = "https://tagis.dep.wv.gov/oog/"

# Harrison County code in OGWIS
COUNTY_CODE  = "17"   # Harrison = 17 in WV FIPS / OGWIS numbering
DISTRICT_NUM = "11"   # Elk District


def run() -> dict:
    log.info("WELL — WVGES OGWIS | parcel %s | %s District, %s County",
             PARCEL_ID, DISTRICT, COUNTY)
    wells  = []
    errors = []

    session = requests.Session()
    session.headers.update(HEADERS)

    # Try OGWIS
    wells = _search_ogwis(session, errors)

    # If OGWIS blocked, try OOG TAGIS
    if not wells:
        log.info("OGWIS returned no results — trying TAGIS OOG...")
        wells = _search_tagis(session, errors)

    if wells:
        _log_wells(wells)
    else:
        msg = (f"No wells found for {PARCEL_ID} area ({DISTRICT} District, {COUNTY} County). "
               "This may be correct for a WS parcel. Confirm with WVGES OGWIS directly.")
        log.info(msg)
        _note(msg)

    status = "COMPLETE" if not errors else ("PARTIAL" if wells else "FAILED")
    return {
        "agent":  "WELL",
        "status": status,
        "count":  len(wells),
        "wells":  wells,
        "errors": errors,
    }


def _search_ogwis(session: requests.Session, errors: list) -> list:
    """Search WVGES OGWIS for wells in Harrison County, Elk District."""
    wells = []
    try:
        r = session.get(OGWIS_SEARCH, timeout=TIMEOUT)
        if r.status_code == 403:
            msg = "OGWIS returned 403 — cloud IP blocked (must run from Mac)"
            log.error(msg)
            errors.append(msg)
            _note(msg)
            return wells
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        log.info("OGWIS search page loaded")
    except Exception as e:
        msg = f"OGWIS unreachable: {e}"
        log.warning(msg)
        errors.append(msg)
        _note(msg)
        return wells

    vs = _viewstate(soup)

    searches = [
        {**vs, "selCounty": COUNTY_CODE, "selDistrict": DISTRICT_NUM,
               "btnSearch": "Search", "selStatus": "ALL"},
        {**vs, "txtCounty": COUNTY, "txtDistrict": DISTRICT,
               "btnSearch": "Search"},
        # parcel-level search
        {**vs, "txtParcel": PARCEL_ID, "btnSearch": "Search"},
        {**vs, "txtParcel": PARCEL_ID.replace("-",""), "btnSearch": "Search"},
    ]

    for i, payload in enumerate(searches, 1):
        log.info("OGWIS search %d/%d", i, len(searches))
        try:
            r = session.post(OGWIS_SEARCH, data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            soup2 = BeautifulSoup(r.content, "lxml")
            found = _parse_wells(soup2, wells)
            if found:
                log.info("  → %d wells found", found)
                break
            log.info("  → 0 results")
        except Exception as e:
            log.warning("OGWIS search %d failed: %s", i, e)
        time.sleep(1)

    return wells


def _search_tagis(session: requests.Session, errors: list) -> list:
    """Search WVDEP TAGIS OOG for wells."""
    wells = []
    try:
        # TAGIS OOG has a REST-like query interface
        params = {
            "county":   COUNTY,
            "district": DISTRICT,
            "status":   "ALL",
            "format":   "json",
        }
        r = session.get(OOG_SEARCH, params=params, timeout=TIMEOUT)
        if r.status_code == 403:
            msg = "TAGIS OOG returned 403 — cloud IP blocked"
            log.error(msg)
            errors.append(msg)
            _note(msg)
            return wells
        r.raise_for_status()

        # Try JSON parse first
        try:
            data = r.json()
            features = data.get("features") or data.get("results") or []
            for feat in features:
                a = feat.get("attributes") or feat
                well = _normalize_well(a)
                if well:
                    wells.append(well)
            if wells:
                log.info("TAGIS OOG: %d wells via JSON", len(wells))
                return wells
        except Exception:
            pass

        # Fall back to HTML parse
        soup = BeautifulSoup(r.content, "lxml")
        _parse_wells(soup, wells)
        if wells:
            log.info("TAGIS OOG: %d wells via HTML", len(wells))

    except Exception as e:
        msg = f"TAGIS OOG failed: {e}"
        log.warning(msg)
        errors.append(msg)
        _note(msg)

    return wells


def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_wells(soup: BeautifulSoup, wells: list) -> int:
    """Parse well table from HTML results page."""
    table = (soup.find("table", id=re.compile(r"grid|result|well", re.I))
             or soup.find("table"))
    if not table:
        return 0

    rows = table.find_all("tr")
    if len(rows) < 2:
        return 0

    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
    start = len(wells)

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not any(cells):
            continue
        well = {}
        for h, v in zip(headers, cells):
            if not v:
                continue
            if   "api"      in h:                        well["api_number"]  = v
            elif "operator" in h or "company" in h:      well["operator"]    = v
            elif "spud"     in h:                        well["spud_date"]   = v
            elif "complet"  in h:                        well["comp_date"]   = v
            elif "status"   in h:                        well["status"]      = v
            elif "type"     in h:                        well["well_type"]   = v
            elif "county"   in h:                        well["county"]      = v
            elif "district" in h:                        well["district"]    = v
            elif "formation" in h or "zone" in h:        well["formation"]   = v
            elif "permit"   in h:                        well["permit_no"]   = v
            elif "lat"      in h:                        well["latitude"]    = v
            elif "lon"      in h or "lng" in h:          well["longitude"]   = v
        if well.get("api_number") or well.get("operator"):
            wells.append(well)

    return len(wells) - start


def _normalize_well(a: dict) -> dict | None:
    def g(*keys):
        for k in keys:
            v = a.get(k) or a.get(k.upper()) or a.get(k.lower())
            if v:
                return str(v).strip()
        return ""
    w = {
        "api_number":  g("API","api","API_NUMBER","apino"),
        "operator":    g("OPERATOR","Operator","COMPANY","company"),
        "spud_date":   g("SPUD_DATE","SpudDate","spuddate"),
        "comp_date":   g("COMP_DATE","CompDate","completiondate"),
        "status":      g("STATUS","Status","wellstatus"),
        "well_type":   g("WELL_TYPE","WellType","type"),
        "county":      g("COUNTY","County"),
        "district":    g("DISTRICT","District"),
        "formation":   g("FORMATION","Formation","zone"),
        "permit_no":   g("PERMIT","PermitNo","permit"),
        "latitude":    g("LAT","Latitude","lat","LATITUDE"),
        "longitude":   g("LON","Longitude","lon","LONGITUDE"),
    }
    return w if w["api_number"] or w["operator"] else None


def _log_wells(wells: list) -> None:
    log.info("Wells found: %d", len(wells))
    for w in wells:
        log.info(
            "  API %-14s | %-30s | Status %-12s | Spud %s",
            w.get("api_number", "—"), w.get("operator", "—"),
            w.get("status", "—"), w.get("spud_date", "—"),
        )
        _note(
            f"WELL API={w.get('api_number','—')} "
            f"OP={w.get('operator','—')} "
            f"STATUS={w.get('status','—')} "
            f"SPUD={w.get('spud_date','—')}"
        )


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[WELL] {msg}\n")
    except Exception:
        pass
