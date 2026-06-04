"""
DEP Agent — WV Department of Environmental Protection OOG (Office of Oil & Gas).
Target: tagis.dep.wv.gov/oog/
Confirms well status, permits, plugging records for parcel 11-409-19.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from config import PARCEL_ID, PARCEL_DISTRICT, PARCEL_COUNTY
from core.logger import get_logger, write_section_header, write_finding, write_missing, write_error
from core.scraper import DeedScraper
from core.telegram_client import send_hard_fail

log = get_logger("DEP")

BASE_URL   = "https://tagis.dep.wv.gov"
OOG_URL    = f"{BASE_URL}/oog/"
IRIS_URL   = "https://apps.dep.wv.gov/oogwells"

# WV DEP TAGIS ArcGIS services (public)
TAGIS_ARCGIS = f"{BASE_URL}/arcgis/rest/services"
OOG_ARCGIS   = f"{TAGIS_ARCGIS}/OOG/WellStatus/MapServer/0/query"


@dataclass
class DepRecord:
    api_number: str = ""
    well_name: str = ""
    operator: str = ""
    county: str = ""
    district: str = ""
    permit_number: str = ""
    permit_date: str = ""
    permit_status: str = ""
    well_status: str = ""
    plug_date: str = ""
    plug_bond_release: str = ""
    violation_count: str = ""
    spill_count: str = ""
    raw: dict = field(default_factory=dict)


class DepAgent:
    def __init__(self):
        self.scraper = DeedScraper("DEP")
        self.records: list[DepRecord] = []
        self.errors: list[str] = []
        self.status = "NOT_RUN"

    def run(self) -> dict:
        write_section_header(log, f"DEP AGENT — {PARCEL_COUNTY} County / {PARCEL_DISTRICT} District | WV DEP OOG")
        log.info("Target: %s", OOG_URL)
        log.info("Parcel: %s | County: %s | District: %s", PARCEL_ID, PARCEL_COUNTY, PARCEL_DISTRICT)

        try:
            self._fetch_dep_records()
            self.status = "COMPLETE"
        except Exception as e:
            err = f"Unhandled exception: {e}"
            self.errors.append(err)
            write_error(log, "DEP", err)
            send_hard_fail("DEP", err)
            self.status = "HARD_FAIL"

        self._report_records()
        return self._build_result()

    def _fetch_dep_records(self) -> None:
        # Strategy 1: TAGIS ArcGIS REST (public WV DEP map service)
        arcgis_queries = [
            {
                "url": OOG_ARCGIS,
                "params": {
                    "where": f"COUNTY_NAME='Harrison' AND DISTRICT_NAME='Elk'",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "f": "json",
                },
            },
            {
                "url": OOG_ARCGIS,
                "params": {
                    "where": f"COUNTY='17' AND DISTRICT='Elk'",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "f": "json",
                },
            },
        ]

        for query in arcgis_queries:
            log.info("Trying DEP ArcGIS: %s", query["url"])
            soup = self.scraper.get(query["url"], params=query["params"])
            if soup:
                text = soup.get_text()
                records = self._parse_arcgis_json(text)
                if records:
                    self.records = records
                    log.info("Found %d DEP records via ArcGIS", len(records))
                    return

        # Strategy 2: WV DEP OOG main portal
        log.info("Trying WV DEP OOG portal: %s", OOG_URL)
        soup = self.scraper.get(OOG_URL)
        if soup is None:
            err = (
                f"Cannot reach {OOG_URL}. "
                "tagis.dep.wv.gov blocks cloud IPs. Must run from Mac."
            )
            self.errors.append(err)
            write_error(log, "DEP-LOAD", err)
            send_hard_fail("DEP", err)
            # Try IRIS fallback
            self._try_iris_fallback()
            return

        log.info("DEP OOG portal loaded. Searching for Harrison County / Elk District...")
        viewstate = self.scraper.extract_viewstate(soup)
        post_data = {
            **viewstate,
            "ddlCounty":   "Harrison",
            "ddlDistrict": "Elk",
            "btnSearch":   "Search",
        }
        result_soup = self.scraper.post(OOG_URL, data=post_data)
        if result_soup:
            records = self._parse_html_table(result_soup)
            if records:
                self.records = records
                return

        self._try_iris_fallback()

    def _try_iris_fallback(self) -> None:
        """Try WV DEP IRIS well database as fallback."""
        log.info("Trying WV DEP IRIS fallback: %s", IRIS_URL)
        params = {
            "county": "Harrison",
            "district": "Elk",
            "status": "all",
        }
        soup = self.scraper.get(IRIS_URL, params=params)
        if soup:
            records = self._parse_html_table(soup)
            if records:
                self.records = records
                log.info("IRIS fallback: %d records", len(records))

    def _parse_arcgis_json(self, text: str) -> list[DepRecord]:
        try:
            data = json.loads(text)
            features = data.get("features", [])
            if not features:
                return []
            records = []
            for f in features:
                attrs = f.get("attributes", {})
                r = DepRecord(raw=attrs)
                r.api_number     = str(attrs.get("API", attrs.get("api_number", "")))
                r.well_name      = attrs.get("WELL_NAME", attrs.get("WellName", ""))
                r.operator       = attrs.get("OPERATOR", attrs.get("Operator", ""))
                r.county         = attrs.get("COUNTY_NAME", "Harrison")
                r.district       = attrs.get("DISTRICT_NAME", "Elk")
                r.permit_number  = str(attrs.get("PERMIT_NUMBER", attrs.get("PermitNo", "")))
                r.permit_date    = str(attrs.get("PERMIT_DATE", attrs.get("PermitDate", "")))
                r.permit_status  = attrs.get("PERMIT_STATUS", "")
                r.well_status    = attrs.get("WELL_STATUS", attrs.get("Status", ""))
                r.plug_date      = str(attrs.get("PLUG_DATE", attrs.get("PlugDate", "")))
                if r.api_number or r.well_name:
                    records.append(r)
            return records
        except Exception as e:
            log.debug("ArcGIS JSON parse failed: %s", e)
            return []

    def _parse_html_table(self, soup) -> list[DepRecord]:
        rows = self.scraper.table_to_rows(soup)
        records = []
        for row in rows:
            r = DepRecord()
            for key, val in row.items():
                k = key.lower()
                if "api" in k:
                    r.api_number = val
                elif "well" in k and "name" in k:
                    r.well_name = val
                elif "operator" in k:
                    r.operator = val
                elif "permit" in k and "num" in k:
                    r.permit_number = val
                elif "permit" in k and "date" in k:
                    r.permit_date = val
                elif "permit" in k and "stat" in k:
                    r.permit_status = val
                elif "well" in k and "stat" in k:
                    r.well_status = val
                elif "plug" in k and "date" in k:
                    r.plug_date = val
                elif "violat" in k:
                    r.violation_count = val
            if r.api_number or r.well_name or r.permit_number:
                records.append(r)
        return records

    def _report_records(self) -> None:
        if not self.records:
            log.info("NO DEP RECORDS FOUND for %s County / %s District", PARCEL_COUNTY, PARCEL_DISTRICT)
            if self.errors:
                log.info("Search was blocked — DEP status is UNKNOWN (site unreachable from cloud IP)")
            else:
                log.info("This is a definitive finding if search completed: no DEP records on file")
        else:
            log.info("DEP records found: %d", len(self.records))
            for i, r in enumerate(self.records, 1):
                log.info("  DEP Record %d:", i)
                write_finding(log, "API Number",      r.api_number    or "N/A")
                write_finding(log, "Well Name",       r.well_name     or "N/A")
                write_finding(log, "Operator",        r.operator      or "N/A")
                write_finding(log, "Permit #",        r.permit_number or "N/A")
                write_finding(log, "Permit Date",     r.permit_date   or "N/A")
                write_finding(log, "Permit Status",   r.permit_status or "N/A")
                write_finding(log, "Well Status",     r.well_status   or "N/A")
                write_finding(log, "Plug Date",       r.plug_date     or "N/A")
                write_finding(log, "Violations",      r.violation_count or "N/A")
                log.info("")

    def _build_result(self) -> dict:
        records_found = len(self.records) > 0
        return {
            "agent":   "DEP",
            "status":  self.status,
            "count":   len(self.records),
            "records": [
                {
                    "api_number":    r.api_number,
                    "well_name":     r.well_name,
                    "operator":      r.operator,
                    "county":        r.county,
                    "district":      r.district,
                    "permit_number": r.permit_number,
                    "permit_date":   r.permit_date,
                    "permit_status": r.permit_status,
                    "well_status":   r.well_status,
                    "plug_date":     r.plug_date,
                    "violations":    r.violation_count,
                }
                for r in self.records
            ],
            "errors": self.errors,
            "note": (
                "NO DEP RECORDS — CONFIRMED ABSENT" if self.status == "COMPLETE" and not records_found
                else "DEP RECORDS FOUND" if records_found
                else "SEARCH FAILED — site unreachable from current IP"
            ),
        }
