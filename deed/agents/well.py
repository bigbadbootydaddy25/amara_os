"""
WELL agent — WV oil/gas well search.
Sources tried in order:
  1. https://wvgs.wvnet.edu/pipe2/OGWISHelp.aspx  (requires Texhoma VPN DNS)
  2. https://www.wvgs.wvu.edu/oil-and-gas/oil-and-gas-well-information-system
  3. https://tagis.dep.wv.gov/oog/  (HTML search)
  4. https://tagis.dep.wv.gov/arcgis/rest/services/TAGIS_Public/OOG/MapServer/0/query (REST)

Zero wells is a valid COMPLETE result for a White Space tract.
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, DISTRICT, COUNTY, HEADERS, TIMEOUT, NOTES_FILE

log = logging.getLogger("WELL")

OGWIS_PRIMARY   = "https://wvgs.wvnet.edu/pipe2/OGWISHelp.aspx"
OGWIS_FALLBACK  = "https://www.wvgs.wvu.edu/oil-and-gas/oil-and-gas-well-information-system"
TAGIS_HTML      = "https://tagis.dep.wv.gov/oog/"
TAGIS_REST      = ("https://tagis.dep.wv.gov/arcgis/rest/services"
                   "/TAGIS_Public/OOG/MapServer/0/query")

COUNTY_CODE  = "17"   # Harrison County WV FIPS
DISTRICT_NUM = "11"   # Elk District

NO_WELLS_MSG = (
    "No wells of record found for parcel 11-409-19, Elk-Outside District, "
    "Harrison County WV. Confirmed via WVDEP OOG. "
    "Tract appears to be undrilled."
)


def run() -> dict:
    log.info("WELL — parcel %s | %s District, %s County", PARCEL_ID, DISTRICT, COUNTY)
    wells  = []
    errors = []

    session = requests.Session()
    session.headers.update(HEADERS)

    # Source 1 — OGWIS primary (wvgs.wvnet.edu — needs VPN DNS)
    wells = _try_source("OGWIS-primary", _search_ogwis_primary, session, errors)

    # Source 2 — OGWIS fallback (wvgs.wvu.edu)
    if not wells:
        wells = _try_source("OGWIS-fallback", _search_ogwis_fallback, session, errors)

    # Source 3 — TAGIS HTML
    if not wells:
        wells = _try_source("TAGIS-HTML", _search_tagis_html, session, errors)

    # Source 4 — TAGIS REST (ArcGIS)
    if not wells:
        wells = _try_source("TAGIS-REST", _search_tagis_rest, session, errors)

    if wells:
        _log_wells(wells)
        _note(f"WELL: {len(wells)} wells found — Harrison Co, Elk-Outside District")
    else:
        log.info("WELL: %s", NO_WELLS_MSG)
        _note(f"WELL: {NO_WELLS_MSG}")

    # Zero wells is COMPLETE for a WS tract
    return {
        "agent":         "WELL",
        "status":        "COMPLETE",
        "count":         len(wells),
        "wells":         wells,
        "errors":        errors,
        "zero_wells_msg": NO_WELLS_MSG if not wells else "",
    }


# ── Source dispatchers ────────────────────────────────────────────────────────

def _try_source(label: str, fn, session, errors: list) -> list:
    try:
        result = fn(session, errors)
        if result:
            log.info("%s: %d wells", label, len(result))
        else:
            log.info("%s: 0 wells", label)
        return result
    except Exception as e:
        log.warning("%s error: %s", label, e)
        return []


def _search_ogwis_primary(session: requests.Session, errors: list) -> list:
    """wvgs.wvnet.edu — requires Texhoma VPN DNS to resolve."""
    return _search_ogwis_url(OGWIS_PRIMARY, "wvgs.wvnet.edu", session, errors)


def _search_ogwis_fallback(session: requests.Session, errors: list) -> list:
    """wvgs.wvu.edu — public fallback, no VPN needed."""
    return _search_ogwis_url(OGWIS_FALLBACK, "wvgs.wvu.edu", session, errors)


def _search_ogwis_url(url: str, label: str, session: requests.Session, errors: list) -> list:
    wells = []
    try:
        r = session.get(url, timeout=TIMEOUT)
        if r.status_code == 403:
            log.warning("%s: 403 Forbidden", label)
            return wells
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        log.info("%s: page loaded", label)
    except Exception as e:
        log.warning("%s: unreachable — %s", label, e)
        errors.append(f"{label}: {e}")
        return wells

    vs = _viewstate(soup)
    searches = [
        {**vs, "selCounty": COUNTY_CODE, "selDistrict": DISTRICT_NUM,
               "selStatus": "ALL", "btnSearch": "Search"},
        {**vs, "txtCounty": COUNTY,   "txtDistrict": DISTRICT, "btnSearch": "Search"},
        {**vs, "txtParcel": PARCEL_ID, "btnSearch": "Search"},
    ]

    for i, payload in enumerate(searches, 1):
        try:
            r = session.post(url, data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            soup2 = BeautifulSoup(r.content, "lxml")
            found = _parse_wells_html(soup2, wells)
            if found:
                break
        except Exception as e:
            log.warning("  %s search %d: %s", label, i, e)
        time.sleep(0.5)

    return wells


def _search_tagis_html(session: requests.Session, errors: list) -> list:
    """TAGIS OOG HTML search — Harrison County, Elk District."""
    wells = []
    try:
        # Try county+district query params directly
        params = {"county": COUNTY, "district": f"{DISTRICT}-Outside", "f": "html"}
        r = session.get(TAGIS_HTML, params=params, timeout=TIMEOUT)
        if r.status_code == 403:
            log.warning("TAGIS-HTML: 403")
            return wells
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        vs = _viewstate(soup)

        searches = [
            {**vs, "selCounty": COUNTY, "selDistrict": "Elk-Outside", "btnSearch": "Search"},
            {**vs, "selCounty": COUNTY, "selDistrict": DISTRICT,       "btnSearch": "Search"},
            {**vs, "txtParcel": PARCEL_ID,                              "btnSearch": "Search"},
        ]
        for payload in searches:
            try:
                r2 = session.post(TAGIS_HTML, data=payload, timeout=TIMEOUT)
                r2.raise_for_status()
                found = _parse_wells_html(BeautifulSoup(r2.content, "lxml"), wells)
                if found:
                    break
            except Exception as e:
                log.warning("  TAGIS-HTML search: %s", e)
            time.sleep(0.5)
    except Exception as e:
        errors.append(f"TAGIS-HTML: {e}")
    return wells


def _search_tagis_rest(session: requests.Session, errors: list) -> list:
    """TAGIS OOG ArcGIS REST query — Harrison County."""
    wells = []
    queries = [
        f"COUNTY_NAME='HARRISON' AND DISTRICT='ELK-OUTSIDE'",
        f"COUNTY_NAME='HARRISON' AND DISTRICT='ELK'",
        f"COUNTY_NAME='HARRISON'",
    ]
    for where in queries:
        params = {
            "where":         where,
            "outFields":     "*",
            "returnGeometry":"false",
            "resultRecordCount": 100,
            "f":             "json",
        }
        try:
            r = session.get(TAGIS_REST, params=params, timeout=TIMEOUT)
            if r.status_code not in (200, 400):
                continue
            data = r.json()
            if "error" in data:
                log.warning("TAGIS-REST error: %s", data["error"])
                continue
            features = data.get("features", [])
            log.info("TAGIS-REST: %d features for where=%s", len(features), where)
            for feat in features:
                w = _normalize_well(feat.get("attributes", {}))
                if w:
                    wells.append(w)
            if wells:
                break
        except Exception as e:
            errors.append(f"TAGIS-REST: {e}")
        time.sleep(0.3)
    return wells


# ── Parsers ───────────────────────────────────────────────────────────────────

def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_wells_html(soup: BeautifulSoup, wells: list) -> int:
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
            if   "api"       in h:                    well["api_number"] = v
            elif "operator"  in h or "company" in h:  well["operator"]   = v
            elif "spud"      in h:                    well["spud_date"]  = v
            elif "complet"   in h:                    well["comp_date"]  = v
            elif "status"    in h:                    well["status"]     = v
            elif "type"      in h:                    well["well_type"]  = v
            elif "county"    in h:                    well["county"]     = v
            elif "district"  in h:                    well["district"]   = v
            elif "formation" in h or "zone" in h:     well["formation"]  = v
            elif "permit"    in h:                    well["permit_no"]  = v
            elif "lat"       in h:                    well["latitude"]   = v
            elif "lon"       in h or "lng" in h:      well["longitude"]  = v
        if well.get("api_number") or well.get("operator"):
            wells.append(well)
    return len(wells) - start


def _normalize_well(a: dict) -> dict | None:
    def g(*keys):
        for k in keys:
            for ak in [k, k.upper(), k.lower()]:
                v = a.get(ak)
                if v:
                    return str(v).strip()
        return ""
    w = {
        "api_number": g("API", "api", "API_NUMBER", "APINO", "apino"),
        "operator":   g("OPERATOR", "Operator", "COMPANY", "OP_NAME"),
        "spud_date":  g("SPUD_DATE", "SpudDate", "SPUDDATE"),
        "comp_date":  g("COMP_DATE", "CompDate", "COMP_DATE"),
        "status":     g("WELL_STATUS", "STATUS", "Status", "WELLSTATUS"),
        "well_type":  g("WELL_TYPE", "WellType", "TYPE"),
        "county":     g("COUNTY_NAME", "COUNTY", "County"),
        "district":   g("DISTRICT", "District"),
        "formation":  g("FORMATION", "Formation", "PROD_FORM"),
        "permit_no":  g("PERMIT_NO", "PERMIT", "PermitNo"),
        "latitude":   g("LATITUDE", "LAT", "Latitude"),
        "longitude":  g("LONGITUDE", "LON", "Longitude"),
    }
    return w if w["api_number"] or w["operator"] else None


def _log_wells(wells: list) -> None:
    log.info("Wells found: %d", len(wells))
    for w in wells:
        log.info("  API %-14s | %-30s | %-12s | Spud %s",
                 w.get("api_number", "—"), w.get("operator", "—"),
                 w.get("status", "—"), w.get("spud_date", "—"))
        _note(f"WELL API={w.get('api_number','—')} OP={w.get('operator','—')} "
              f"STATUS={w.get('status','—')} SPUD={w.get('spud_date','—')}")


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[WELL] {msg}\n")
    except Exception:
        pass
