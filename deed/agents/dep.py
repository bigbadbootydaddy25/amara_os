"""
DEP agent — WV DEP Office of Oil & Gas (TAGIS OOG).
URL: https://tagis.dep.wv.gov/oog/
Confirms well status, active permits, and plugging records
for parcel 11-409-19 area (Harrison County, Elk District).
"""
import logging
import re

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, DISTRICT, COUNTY, HEADERS, TIMEOUT, NOTES_FILE

log = logging.getLogger("DEP")

OOG_BASE   = "https://tagis.dep.wv.gov/oog"
OOG_QUERY  = f"{OOG_BASE}/query"
OOG_SEARCH = f"{OOG_BASE}/"

COUNTY_FIPS = "17"   # Harrison County WV FIPS


def run() -> dict:
    log.info("DEP — WV DEP OOG | parcel %s | %s District %s County",
             PARCEL_ID, DISTRICT, COUNTY)
    permits  = []
    plugged  = []
    active   = []
    errors   = []

    session = requests.Session()
    session.headers.update(HEADERS)

    # Try REST/JSON query endpoint first
    _query_oog_json(session, permits, plugged, active, errors)

    # Fall back to HTML scrape
    if not permits and not active:
        log.info("JSON query empty — trying HTML scrape...")
        _scrape_oog_html(session, permits, plugged, active, errors)

    _log_summary(permits, plugged, active)

    status = "COMPLETE" if not errors else ("PARTIAL" if (permits or active) else "FAILED")
    return {
        "agent":      "DEP",
        "status":     status,
        "permits":    permits,
        "active":     active,
        "plugged":    plugged,
        "errors":     errors,
    }


def _query_oog_json(session, permits, plugged, active, errors):
    """Try TAGIS ArcGIS-style REST query for Harrison County wells."""
    # TAGIS OOG often exposes an ArcGIS FeatureServer
    arcgis_urls = [
        f"{OOG_BASE}/rest/services/WellSearch/MapServer/0/query",
        "https://tagis.dep.wv.gov/arcgis/rest/services/OOG/WellSearch/MapServer/0/query",
    ]
    for url in arcgis_urls:
        params = {
            "where":        f"COUNTY_CODE='{COUNTY_FIPS}' AND DISTRICT='{DISTRICT}'",
            "outFields":    "*",
            "returnGeometry": "false",
            "f":            "json",
        }
        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            if r.status_code not in (200, 400):
                continue
            data = r.json()
            feats = data.get("features", [])
            if feats:
                for feat in feats:
                    a = feat.get("attributes", {})
                    _classify_well(a, permits, plugged, active)
                log.info("DEP ArcGIS: %d wells (%d active, %d plugged)",
                         len(feats), len(active), len(plugged))
                return
        except Exception as e:
            log.debug("DEP ArcGIS %s: %s", url, e)


def _scrape_oog_html(session, permits, plugged, active, errors):
    """Scrape TAGIS OOG HTML search page."""
    try:
        r = session.get(OOG_SEARCH, timeout=TIMEOUT)
        if r.status_code == 403:
            msg = "TAGIS OOG returned 403 — cloud IP blocked (must run from Mac)"
            log.error(msg)
            errors.append(msg)
            _note(msg)
            return
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        vs = _viewstate(soup)
        log.info("TAGIS OOG search page loaded")
    except Exception as e:
        msg = f"TAGIS OOG unreachable: {e}"
        log.warning(msg)
        errors.append(msg)
        _note(msg)
        return

    searches = [
        {**vs, "selCounty": COUNTY, "selDistrict": DISTRICT, "btnSearch": "Search"},
        {**vs, "txtCounty": COUNTY_FIPS, "btnSearch": "Search"},
        {**vs, "txtParcel": PARCEL_ID, "btnSearch": "Search"},
    ]

    for i, payload in enumerate(searches, 1):
        try:
            r = session.post(OOG_SEARCH, data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            soup2 = BeautifulSoup(r.content, "lxml")
            found = _parse_oog_table(soup2, permits, plugged, active)
            if found:
                log.info("DEP HTML search %d: %d wells", i, found)
                break
        except Exception as e:
            log.warning("DEP search %d failed: %s", i, e)


def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_oog_table(soup: BeautifulSoup, permits: list, plugged: list, active: list) -> int:
    table = (soup.find("table", id=re.compile(r"grid|result|well", re.I))
             or soup.find("table"))
    if not table:
        return 0
    rows = table.find_all("tr")
    if len(rows) < 2:
        return 0
    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
    count = 0
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not any(cells):
            continue
        a = {}
        for h, v in zip(headers, cells):
            a[h] = v
        _classify_well(a, permits, plugged, active)
        count += 1
    return count


def _classify_well(a: dict, permits: list, plugged: list, active: list) -> None:
    def g(*keys):
        for k in keys:
            for ak in [k, k.upper(), k.lower()]:
                v = a.get(ak)
                if v:
                    return str(v).strip()
        return ""

    well = {
        "api_number": g("API", "api", "API_NUMBER", "apino"),
        "operator":   g("OPERATOR", "Operator", "COMPANY", "operator"),
        "status":     g("STATUS", "Status", "WELL_STATUS", "wellstatus"),
        "permit_no":  g("PERMIT", "PermitNo", "permit_number"),
        "permit_date":g("PERMIT_DATE", "PermitDate", "permit date"),
        "spud_date":  g("SPUD_DATE", "SpudDate", "spud date"),
        "plug_date":  g("PLUG_DATE", "PlugDate", "plugged date"),
        "formation":  g("FORMATION", "Formation", "zone"),
        "county":     g("COUNTY", "County"),
        "district":   g("DISTRICT", "District"),
        "latitude":   g("LAT", "Latitude", "lat"),
        "longitude":  g("LON", "Longitude", "lon"),
    }

    status = well["status"].upper()
    if "PLUG" in status or "ABANDON" in status:
        plugged.append(well)
        _note(f"PLUGGED: API={well['api_number']} OP={well['operator']} DATE={well['plug_date']}")
    elif "PERMIT" in status or "DRILL" in status or "ACTIVE" in status or "PRODUC" in status:
        active.append(well)
        _note(f"ACTIVE: API={well['api_number']} OP={well['operator']} STATUS={well['status']}")
    else:
        permits.append(well)
        _note(f"PERMIT/OTHER: API={well['api_number']} OP={well['operator']} STATUS={well['status']}")


def _log_summary(permits: list, plugged: list, active: list) -> None:
    total = len(permits) + len(plugged) + len(active)
    log.info("DEP OOG summary: %d total | %d active | %d plugged | %d permit/other",
             total, len(active), len(plugged), len(permits))
    _note(f"DEP SUMMARY: total={total} active={len(active)} plugged={len(plugged)} permits={len(permits)}")
    for w in active:
        log.info("  ACTIVE  API %-14s %-30s %s", w["api_number"], w["operator"], w["status"])
    for w in plugged:
        log.info("  PLUGGED API %-14s %-30s plugged=%s", w["api_number"], w["operator"], w["plug_date"])


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[DEP] {msg}\n")
    except Exception:
        pass
