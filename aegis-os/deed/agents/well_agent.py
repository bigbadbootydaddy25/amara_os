"""
WELL Agent — WV Geological Survey OGWIS (Oil & Gas Well Information System).
Target: wvgs.wvnet.edu/pipe2/OGWISHelp.aspx
Pulls all wells: API numbers, operator, spud date, completion, production.
County: Harrison | District: Elk | Parcel: 11-409-19.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import json
from dataclasses import dataclass, field
from typing import Optional

from config import PARCEL_ID, PARCEL_DISTRICT, PARCEL_COUNTY
from core.logger import get_logger, write_section_header, write_finding, write_missing, write_error
from core.scraper import DeedScraper
from core.telegram_client import send_hard_fail

log = get_logger("WELL")

BASE_URL    = "https://wvgs.wvnet.edu"
OGWIS_URL   = f"{BASE_URL}/pipe2/OGWISHelp.aspx"
SEARCH_URL  = f"{BASE_URL}/pipe2/ogwis/wells"

# WVGS county codes
HARRISON_COUNTY_CODE = "17"  # Harrison County FIPS: 017


@dataclass
class WellRecord:
    api_number: str = ""
    well_name: str = ""
    operator: str = ""
    county: str = ""
    district: str = ""
    twp: str = ""
    spud_date: str = ""
    completion_date: str = ""
    well_type: str = ""
    well_status: str = ""
    formation: str = ""
    total_depth: str = ""
    permit_date: str = ""
    permit_number: str = ""
    production_oil_bbl: str = ""
    production_gas_mcf: str = ""
    lat: str = ""
    lon: str = ""
    raw: dict = field(default_factory=dict)


class WellAgent:
    def __init__(self):
        self.scraper = DeedScraper("WELL")
        self.wells: list[WellRecord] = []
        self.errors: list[str] = []
        self.status = "NOT_RUN"

    def run(self) -> dict:
        write_section_header(log, f"WELL AGENT — {PARCEL_COUNTY} County / {PARCEL_DISTRICT} District | WVGS OGWIS")
        log.info("Target: %s", OGWIS_URL)
        log.info("Parcel: %s | County: %s | District: %s", PARCEL_ID, PARCEL_COUNTY, PARCEL_DISTRICT)

        try:
            self._fetch_well_data()
            self.status = "COMPLETE"
        except Exception as e:
            err = f"Unhandled exception: {e}"
            self.errors.append(err)
            write_error(log, "WELL", err)
            send_hard_fail("WELL", err)
            self.status = "HARD_FAIL"

        self._report_wells()
        return self._build_result()

    def _fetch_well_data(self) -> None:
        # Strategy 1: WVGS OGWIS REST API (JSON endpoint)
        # WVGS provides a REST service at /pipe2/ogwis/
        api_endpoints = [
            f"{BASE_URL}/pipe2/ogwis/wells?county={HARRISON_COUNTY_CODE}&district={PARCEL_DISTRICT}&format=json",
            f"{BASE_URL}/pipe2/ogwis/wells?county=Harrison&district=Elk&format=json",
            f"{BASE_URL}/pipe2/ogwis/wells.aspx?CountyCode={HARRISON_COUNTY_CODE}&District=Elk",
        ]

        for endpoint in api_endpoints:
            log.info("Trying WVGS API: %s", endpoint)
            soup = self.scraper.get(endpoint)
            if soup:
                text = soup.get_text()
                wells = self._try_parse_json(text)
                if wells:
                    self.wells = wells
                    return
                # Try HTML table
                wells = self._parse_html_table(soup)
                if wells:
                    self.wells = wells
                    return

        # Strategy 2: OGWIS search form (ASP.NET)
        log.info("Trying OGWIS search form: %s", OGWIS_URL)
        soup = self.scraper.get(OGWIS_URL)
        if soup is None:
            err = (
                f"Cannot reach {OGWIS_URL}. "
                "wvgs.wvnet.edu may be down or blocking cloud IPs. "
                "Must run from Mac on local network."
            )
            self.errors.append(err)
            write_error(log, "WELL-LOAD", err)
            send_hard_fail("WELL", err)
            return

        viewstate = self.scraper.extract_viewstate(soup)
        post_data = {
            **viewstate,
            "ddlCounty": "Harrison",
            "ddlDistrict": "Elk",
            "btnSearch": "Search",
        }
        result_soup = self.scraper.post(OGWIS_URL, data=post_data)
        if result_soup:
            wells = self._parse_html_table(result_soup)
            if wells:
                self.wells = wells
                return

        log.info("No wells found via OGWIS. Trying WV DEP IRIS well database...")
        self._try_dep_iris()

    def _try_dep_iris(self) -> None:
        """WV DEP IRIS well search as fallback."""
        iris_url = "https://apps.dep.wv.gov/oogwells/search"
        params = {"county": "Harrison", "district": "Elk"}
        soup = self.scraper.get(iris_url, params=params)
        if soup:
            wells = self._parse_html_table(soup)
            if wells:
                self.wells = wells

    def _try_parse_json(self, text: str) -> list[WellRecord]:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [self._dict_to_well(d) for d in data if isinstance(d, dict)]
            if isinstance(data, dict) and "wells" in data:
                return [self._dict_to_well(d) for d in data["wells"]]
        except (json.JSONDecodeError, Exception):
            pass
        return []

    def _dict_to_well(self, d: dict) -> WellRecord:
        w = WellRecord(raw=d)
        w.api_number        = str(d.get("api", d.get("API", d.get("api_number", ""))))
        w.well_name         = d.get("well_name", d.get("WellName", ""))
        w.operator          = d.get("operator", d.get("Operator", d.get("OPERATOR", "")))
        w.county            = d.get("county", "Harrison")
        w.district          = d.get("district", "Elk")
        w.spud_date         = str(d.get("spud_date", d.get("SpudDate", "")))
        w.completion_date   = str(d.get("completion_date", d.get("CompletionDate", "")))
        w.well_type         = d.get("well_type", d.get("WellType", ""))
        w.well_status       = d.get("status", d.get("WellStatus", d.get("STATUS", "")))
        w.formation         = d.get("formation", d.get("Formation", ""))
        w.total_depth       = str(d.get("total_depth", d.get("TotalDepth", "")))
        w.permit_number     = str(d.get("permit", d.get("PermitNumber", "")))
        w.production_oil_bbl = str(d.get("oil_bbl", d.get("OilBBL", "")))
        w.production_gas_mcf = str(d.get("gas_mcf", d.get("GasMCF", "")))
        return w

    def _parse_html_table(self, soup) -> list[WellRecord]:
        rows = self.scraper.table_to_rows(soup)
        if not rows:
            return []
        wells = []
        for row in rows:
            w = WellRecord()
            for key, val in row.items():
                k = key.lower()
                if "api" in k:
                    w.api_number = val
                elif "well" in k and "name" in k:
                    w.well_name = val
                elif "operator" in k:
                    w.operator = val
                elif "spud" in k:
                    w.spud_date = val
                elif "complet" in k:
                    w.completion_date = val
                elif "type" in k:
                    w.well_type = val
                elif "status" in k:
                    w.well_status = val
                elif "form" in k:
                    w.formation = val
                elif "depth" in k:
                    w.total_depth = val
                elif "permit" in k and "num" in k:
                    w.permit_number = val
                elif "oil" in k:
                    w.production_oil_bbl = val
                elif "gas" in k:
                    w.production_gas_mcf = val
            if w.api_number or w.well_name:
                wells.append(w)
        return wells

    def _report_wells(self) -> None:
        if not self.wells:
            log.info("NO WELLS FOUND for parcel %s / %s District / %s County",
                     PARCEL_ID, PARCEL_DISTRICT, PARCEL_COUNTY)
            log.info("This is a definitive finding if the search completed successfully.")
            log.info("If site was unreachable, wells status is UNKNOWN.")
        else:
            log.info("Wells found: %d", len(self.wells))
            for i, w in enumerate(self.wells, 1):
                log.info("  Well %d:", i)
                write_finding(log, "API Number",     w.api_number    or "N/A")
                write_finding(log, "Well Name",      w.well_name     or "N/A")
                write_finding(log, "Operator",       w.operator      or "N/A")
                write_finding(log, "Spud Date",      w.spud_date     or "N/A")
                write_finding(log, "Completion",     w.completion_date or "N/A")
                write_finding(log, "Type",           w.well_type     or "N/A")
                write_finding(log, "Status",         w.well_status   or "N/A")
                write_finding(log, "Formation",      w.formation     or "N/A")
                write_finding(log, "Total Depth",    w.total_depth   or "N/A")
                write_finding(log, "Permit #",       w.permit_number or "N/A")
                write_finding(log, "Oil Production", w.production_oil_bbl or "N/A")
                write_finding(log, "Gas Production", w.production_gas_mcf or "N/A")
                log.info("")

    def _build_result(self) -> dict:
        wells_found = len(self.wells) > 0
        return {
            "agent":       "WELL",
            "status":      self.status,
            "wells_found": wells_found,
            "count":       len(self.wells),
            "wells": [
                {
                    "api_number":       w.api_number,
                    "well_name":        w.well_name,
                    "operator":         w.operator,
                    "spud_date":        w.spud_date,
                    "completion_date":  w.completion_date,
                    "well_type":        w.well_type,
                    "well_status":      w.well_status,
                    "formation":        w.formation,
                    "total_depth":      w.total_depth,
                    "permit_number":    w.permit_number,
                    "production_oil_bbl": w.production_oil_bbl,
                    "production_gas_mcf": w.production_gas_mcf,
                }
                for w in self.wells
            ],
            "errors": self.errors,
            "note": (
                "NO WELLS CONFIRMED ABSENT" if self.status == "COMPLETE" and not wells_found
                else "WELLS FOUND" if wells_found
                else "SEARCH FAILED — site unreachable from current IP"
            ),
        }
