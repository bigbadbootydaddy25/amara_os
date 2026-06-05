"""
VEST agent — WV Property Viewer.
URL: https://mapwv.gov/parcel/
Pulls current owner, vesting deed BK/PG, full legal description for parcel 11-409-19.
"""
import json
import logging
import re

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, COUNTY, DISTRICT, HEADERS, TIMEOUT, NOTES_FILE

log = logging.getLogger("VEST")

VIEWER_URL  = "https://mapwv.gov/parcel/"
# WV GIS public ArcGIS parcel services (Harrison County)
ARCGIS_URLS = [
    "https://mapwv.gov/arcgis/rest/services/Parcels/Harrison_County/MapServer/0/query",
    "https://mapwv.gov/arcgis/rest/services/ParcelViewer/WV_Parcels/MapServer/0/query",
    "https://services.wvgis.wvu.edu/arcgis/rest/services/Basemap/parcels_ndi/MapServer/0/query",
]


def run() -> dict:
    log.info("VEST — WV Property Viewer | parcel %s", PARCEL_ID)
    record = {}
    missing = []
    errors  = []

    # Try ArcGIS JSON endpoints first (faster, structured)
    for url in ARCGIS_URLS:
        log.info("Trying ArcGIS: %s", url)
        r = _arcgis_query(url)
        if r:
            record = r
            log.info("Found via ArcGIS")
            break

    # Fall back to scraping the viewer page
    if not record:
        log.info("ArcGIS failed — scraping viewer page...")
        record = _scrape_viewer()

    if record:
        _log_record(record)
        missing = [k for k in ["owner_name","deed_book","deed_page","legal_desc","acreage"]
                   if not record.get(k)]
    else:
        missing = ["owner_name","deed_book","deed_page","legal_desc","acreage","district","account_no"]
        errors.append(f"No vesting data retrieved — site may block non-Mac IPs (403)")
        _note("VEST: no record returned — 403 or search failed")

    for m in missing:
        _note(f"VEST MISSING: {m}")
        log.warning("MISSING: %s", m)

    return {
        "agent":   "VEST",
        "status":  "COMPLETE" if record and not errors else "FAILED",
        "record":  record,
        "missing": missing,
        "errors":  errors,
    }


def _arcgis_query(url: str) -> dict | None:
    """Query an ArcGIS FeatureServer for the parcel."""
    session = requests.Session()
    session.headers.update(HEADERS)
    for q in [PARCEL_ID, PARCEL_ID.replace("-",""), f"11{PARCEL_ID.replace('-','')}"]:
        params = {
            "where": f"PARCEL_ID='{q}' OR MAP_NUM='{q}' OR PARCELNO='{q}'",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }
        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            data = r.json()
            feats = data.get("features", [])
            if feats:
                a = feats[0].get("attributes", {})
                return _attrs(a)
        except Exception as e:
            log.debug("ArcGIS %s failed: %s", url, e)
    return None


def _scrape_viewer() -> dict | None:
    """Scrape mapwv.gov/parcel/ search page."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        r = session.get(VIEWER_URL, params={"parcel": PARCEL_ID}, timeout=TIMEOUT)
        if r.status_code == 403:
            log.error("mapwv.gov returned 403 Forbidden — host not in allowlist (must run from Mac)")
            return None
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        text = soup.get_text(" ", strip=True)
        result = {}
        for field, pattern in [
            ("owner_name",  r"Owner[:\s]+([A-Z][A-Z\s,&.'-]{2,50})"),
            ("deed_book",   r"(?:Deed\s+)?Book[:\s#]+(\d+)"),
            ("deed_page",   r"(?:Deed\s+)?Page[:\s#]+(\d+)"),
            ("acreage",     r"([\d.]+)\s*[Aa]cres?"),
            ("account_no",  r"Account[:\s#]+([A-Z0-9\-]+)"),
            ("legal_desc",  r"Legal[:\s]+(.{10,200})"),
        ]:
            m = re.search(pattern, text, re.I | re.M)
            if m:
                result[field] = m.group(1).strip()
        return result if result.get("owner_name") or result.get("deed_book") else None
    except Exception as e:
        log.error("Viewer scrape failed: %s", e)
        return None


def _attrs(a: dict) -> dict:
    """Normalize ArcGIS attribute dict."""
    def g(*keys):
        for k in keys:
            v = a.get(k) or a.get(k.upper()) or a.get(k.lower())
            if v:
                return str(v).strip()
        return ""
    return {
        "parcel_id":   g("PARCEL_ID","ParcelNumber","PARCELNO"),
        "owner_name":  g("OWNER_NAME","OwnerName","OWNERNAME","OWNER"),
        "owner_addr":  g("OWNER_ADDRESS","OwnerAddress","OWNERADDR"),
        "deed_book":   g("DEED_BOOK","DeedBook","BKNO","BOOK"),
        "deed_page":   g("DEED_PAGE","DeedPage","PGNO","PAGE"),
        "deed_date":   g("DEED_DATE","DeedDate","DEEDDATE"),
        "legal_desc":  g("LEGAL_DESCRIPTION","LegalDesc","LEGALDESC","LEGAL"),
        "acreage":     g("ACREAGE","Acres","ACRES","CALC_ACRES"),
        "district":    g("DISTRICT","District","DIST_NAME"),
        "account_no":  g("ACCOUNT_NUMBER","AccountNo","ACCTNO"),
        "map_number":  g("MAP_NUMBER","MapNumber","MAPNO"),
    }


def _log_record(r: dict) -> None:
    for label, key in [
        ("Current Owner",    "owner_name"),
        ("Owner Address",    "owner_addr"),
        ("Vesting Deed Book","deed_book"),
        ("Vesting Deed Page","deed_page"),
        ("Deed Date",        "deed_date"),
        ("Legal Description","legal_desc"),
        ("Acreage",          "acreage"),
        ("District",         "district"),
        ("Account Number",   "account_no"),
    ]:
        val = r.get(key, "NOT FOUND")
        log.info("  %-25s %s", label + ":", val)
        _note(f"VEST {label}: {val}")


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[VEST] {msg}\n")
    except Exception:
        pass
