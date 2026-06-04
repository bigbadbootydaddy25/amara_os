"""
VEST Agent — WV Parcel Viewer / mapwv.gov
Target: mapwv.gov/parcel/
Pulls current owner, vesting deed BK/PG, legal description for parcel 11-409-19.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from config import PARCEL_ID, PARCEL_COUNTY, PARCEL_DISTRICT
from core.logger import get_logger, write_section_header, write_finding, write_missing, write_error
from core.scraper import DeedScraper
from core.telegram_client import send_hard_fail

log = get_logger("VEST")

BASE_URL    = "https://mapwv.gov/parcel"
API_URL     = f"{BASE_URL}/api"
SEARCH_URL  = f"{BASE_URL}/"

# District number for Elk District, Harrison County
ELK_DISTRICT_NUM = "11"


@dataclass
class VestingRecord:
    parcel_id: str = ""
    owner_name: str = ""
    owner_address: str = ""
    deed_book: str = ""
    deed_page: str = ""
    deed_date: str = ""
    legal_description: str = ""
    acreage: str = ""
    district: str = ""
    map_number: str = ""
    account_number: str = ""
    raw: dict = field(default_factory=dict)


class VestAgent:
    def __init__(self):
        self.scraper = DeedScraper("VEST")
        self.record: Optional[VestingRecord] = None
        self.missing: list[str] = []
        self.errors: list[str] = []
        self.status = "NOT_RUN"

    def run(self) -> dict:
        write_section_header(log, f"VEST AGENT — Parcel {PARCEL_ID} | mapwv.gov")
        log.info("Target: %s", SEARCH_URL)

        try:
            self._fetch_parcel_data()
            self.status = "COMPLETE" if self.record else "FAILED"
        except Exception as e:
            err = f"Unhandled exception: {e}"
            self.errors.append(err)
            write_error(log, "VEST", err)
            send_hard_fail("VEST", err)
            self.status = "HARD_FAIL"

        return self._build_result()

    def _fetch_parcel_data(self) -> None:
        # Strategy 1: mapwv.gov ArcGIS REST service (public JSON API)
        # WV GIS parcels are typically served via ArcGIS FeatureServer
        arcgis_endpoints = [
            # Harrison County parcel layer
            "https://mapwv.gov/arcgis/rest/services/Parcels/Harrison/MapServer/0/query",
            "https://mapwv.gov/arcgis/rest/services/wvgis/Parcels/MapServer/0/query",
        ]

        parcel_num = PARCEL_ID.replace("-", "")  # Try without dashes too

        for endpoint in arcgis_endpoints:
            log.info("Trying ArcGIS endpoint: %s", endpoint)
            for parcel_query in [PARCEL_ID, parcel_num, f"11409{parcel_num}"]:
                result = self._try_arcgis(endpoint, parcel_query)
                if result:
                    self.record = result
                    self._log_record()
                    return

        # Strategy 2: Direct page search
        log.info("Trying direct mapwv.gov parcel search...")
        soup = self.scraper.get(SEARCH_URL, params={"parcel": PARCEL_ID})
        if soup is None:
            err = (
                f"Cannot reach {SEARCH_URL}. "
                "mapwv.gov blocks cloud IPs. Must run from Mac."
            )
            self.errors.append(err)
            write_error(log, "VEST-LOAD", err)
            send_hard_fail("VEST", err)
            return

        self._parse_page(soup)

    def _try_arcgis(self, endpoint: str, parcel_id: str) -> Optional[VestingRecord]:
        params = {
            "where": f"PARCEL_ID='{parcel_id}' OR ParcelNumber='{parcel_id}'",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }
        soup = self.scraper.get(endpoint, params=params)
        if soup is None:
            return None
        try:
            text = soup.get_text()
            data = json.loads(text)
            features = data.get("features", [])
            if features:
                attrs = features[0].get("attributes", {})
                return self._attrs_to_record(attrs)
        except Exception as e:
            log.debug("ArcGIS parse failed: %s", e)
        return None

    def _attrs_to_record(self, attrs: dict) -> VestingRecord:
        r = VestingRecord(raw=attrs)
        r.parcel_id = (
            attrs.get("PARCEL_ID") or attrs.get("ParcelNumber") or PARCEL_ID
        )
        r.owner_name = (
            attrs.get("OWNER_NAME") or attrs.get("OwnerName") or attrs.get("OWNERNAME", "")
        )
        r.owner_address = (
            attrs.get("OWNER_ADDRESS") or attrs.get("OwnerAddress", "")
        )
        r.deed_book = (
            attrs.get("DEED_BOOK") or attrs.get("DeedBook", "")
        )
        r.deed_page = (
            attrs.get("DEED_PAGE") or attrs.get("DeedPage", "")
        )
        r.deed_date = (
            attrs.get("DEED_DATE") or attrs.get("DeedDate", "")
        )
        r.legal_description = (
            attrs.get("LEGAL_DESCRIPTION") or attrs.get("LegalDesc", "")
        )
        r.acreage = str(
            attrs.get("ACREAGE") or attrs.get("Acres") or attrs.get("ACRES", "")
        )
        r.district = (
            attrs.get("DISTRICT") or attrs.get("District", ELK_DISTRICT_NUM)
        )
        r.account_number = (
            attrs.get("ACCOUNT_NUMBER") or attrs.get("AccountNo", "")
        )
        return r

    def _parse_page(self, soup) -> None:
        text = soup.get_text()
        log.debug("Page text length: %d chars", len(text))
        r = VestingRecord(parcel_id=PARCEL_ID)

        # Common patterns in WV parcel viewers
        patterns = {
            "owner_name":       r"Owner[:\s]+([A-Z][A-Z\s,&.]+?)(?:\n|$)",
            "deed_book":        r"Book[:\s#]+(\d+)",
            "deed_page":        r"Page[:\s#]+(\d+)",
            "acreage":          r"(\d+\.?\d*)\s*(?:acres?|AC)",
            "legal_description": r"Legal[:\s]+(.+?)(?:\n|$)",
        }
        for field, pattern in patterns.items():
            m = re.search(pattern, text, re.I | re.M)
            if m:
                setattr(r, field, m.group(1).strip())

        if r.owner_name or r.deed_book:
            self.record = r
            self._log_record()
        else:
            write_missing(log, "Owner/vesting data — page may be JS-rendered or search failed")
            self.missing.extend(["owner_name", "deed_book", "deed_page", "legal_description"])

    def _log_record(self) -> None:
        r = self.record
        log.info("Vesting record found:")
        write_finding(log, "Parcel ID",          r.parcel_id or "N/A")
        write_finding(log, "Current Owner",       r.owner_name or "NOT FOUND")
        write_finding(log, "Owner Address",       r.owner_address or "NOT FOUND")
        write_finding(log, "Vesting Deed Book",   r.deed_book or "NOT FOUND")
        write_finding(log, "Vesting Deed Page",   r.deed_page or "NOT FOUND")
        write_finding(log, "Deed Date",           r.deed_date or "NOT FOUND")
        write_finding(log, "Legal Description",   r.legal_description or "NOT FOUND")
        write_finding(log, "Acreage",             r.acreage or "NOT FOUND")
        write_finding(log, "District",            r.district or "NOT FOUND")
        write_finding(log, "Account Number",      r.account_number or "NOT FOUND")

        for fname in ["owner_name", "deed_book", "deed_page", "legal_description"]:
            if not getattr(r, fname):
                self.missing.append(fname)
                write_missing(log, fname)

    def _build_result(self) -> dict:
        rec = {}
        if self.record:
            rec = {
                "parcel_id":         self.record.parcel_id,
                "owner_name":        self.record.owner_name,
                "owner_address":     self.record.owner_address,
                "deed_book":         self.record.deed_book,
                "deed_page":         self.record.deed_page,
                "deed_date":         self.record.deed_date,
                "legal_description": self.record.legal_description,
                "acreage":           self.record.acreage,
                "district":          self.record.district,
                "account_number":    self.record.account_number,
            }
        return {
            "agent":   "VEST",
            "status":  self.status,
            "record":  rec,
            "missing": self.missing,
            "errors":  self.errors,
        }
