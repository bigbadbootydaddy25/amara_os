"""
TAX Agent — Harrison County Assessor ownership search.
Target: harrisoncountyassessor.com/ownershipsearch.aspx
Pulls: account number, ticket number, owner, land value, mineral value, class.
District: 11-Elk, Parcel: 11-409-19.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
from dataclasses import dataclass, field
from typing import Optional

from config import PARCEL_ID, PARCEL_DISTRICT
from core.logger import get_logger, write_section_header, write_finding, write_missing, write_error
from core.scraper import DeedScraper
from core.telegram_client import send_hard_fail

log = get_logger("TAX")

BASE_URL   = "https://harrisoncountyassessor.com"
SEARCH_URL = f"{BASE_URL}/ownershipsearch.aspx"

# Harrison County district 11 = Elk
DISTRICT_CODE = "11"
DISTRICT_NAME = "Elk"


@dataclass
class TaxRecord:
    parcel_id: str = ""
    district: str = ""
    account_number: str = ""
    ticket_number: str = ""
    owner_name: str = ""
    owner_address: str = ""
    property_description: str = ""
    land_value: str = ""
    building_value: str = ""
    mineral_value: str = ""
    total_value: str = ""
    property_class: str = ""
    tax_year: str = ""
    taxes_due: str = ""
    taxes_paid: str = ""
    raw: dict = field(default_factory=dict)


class TaxAgent:
    def __init__(self):
        self.scraper = DeedScraper("TAX")
        self.records: list[TaxRecord] = []
        self.missing: list[str] = []
        self.errors: list[str] = []
        self.status = "NOT_RUN"

    def run(self) -> dict:
        write_section_header(log, f"TAX AGENT — Parcel {PARCEL_ID} | Harrison County Assessor")
        log.info("Target: %s", SEARCH_URL)
        log.info("District: %s-%s | Parcel: %s", DISTRICT_CODE, DISTRICT_NAME, PARCEL_ID)

        try:
            self._fetch_tax_records()
            self.status = "COMPLETE" if self.records else "FAILED"
        except Exception as e:
            err = f"Unhandled exception: {e}"
            self.errors.append(err)
            write_error(log, "TAX", err)
            send_hard_fail("TAX", err)
            self.status = "HARD_FAIL"

        return self._build_result()

    def _fetch_tax_records(self) -> None:
        # Step 1: Load the search page (ASP.NET WebForms)
        log.info("Loading Harrison County Assessor search page...")
        soup = self.scraper.get(SEARCH_URL)
        if soup is None:
            err = (
                f"Cannot reach {SEARCH_URL}. "
                "Site blocks cloud IPs. Must run from Mac."
            )
            self.errors.append(err)
            write_error(log, "TAX-LOAD", err)
            send_hard_fail("TAX", err)
            return

        log.info("Search page loaded. Extracting ASP.NET form state...")
        viewstate = self.scraper.extract_viewstate(soup)
        log.debug("ViewState keys: %s", list(viewstate.keys()))

        # Step 2: Submit search by district + parcel number
        # Harrison County Assessor uses district dropdown + parcel/map number
        # District 11 = Elk
        parcel_bare = PARCEL_ID.split("-", 1)[-1] if "-" in PARCEL_ID else PARCEL_ID

        search_payloads = [
            # Try full parcel ID
            {
                **viewstate,
                "__EVENTTARGET": "btnSearch",
                "ddlDistrict": DISTRICT_CODE,
                "txtParcelID": PARCEL_ID,
            },
            # Try without district prefix
            {
                **viewstate,
                "__EVENTTARGET": "btnSearch",
                "ddlDistrict": DISTRICT_CODE,
                "txtParcelID": parcel_bare,
            },
            # Try map number format (409-19)
            {
                **viewstate,
                "ddlDistrict": DISTRICT_CODE,
                "txtMap": "409",
                "txtParcel": "19",
                "btnSearch": "Search",
            },
        ]

        for i, payload in enumerate(search_payloads):
            log.info("Search attempt %d/%d...", i + 1, len(search_payloads))
            result_soup = self.scraper.post(SEARCH_URL, data=payload)
            if result_soup is None:
                continue
            records = self._parse_results(result_soup)
            if records:
                self.records = records
                self._log_records()
                return

        log.warning("No tax records found after %d search attempts", len(search_payloads))
        write_missing(log, "Tax records — district 11-Elk, parcel 11-409-19")
        self.missing.extend([
            "account_number", "ticket_number", "owner", "land_value",
            "mineral_value", "property_class",
        ])

    def _parse_results(self, soup) -> list[TaxRecord]:
        records = []

        # Try table rows first
        rows = self.scraper.table_to_rows(soup)
        if rows:
            for row in rows:
                r = TaxRecord(parcel_id=PARCEL_ID, district=f"{DISTRICT_CODE}-{DISTRICT_NAME}")
                for key, val in row.items():
                    k = key.lower()
                    if "account" in k:
                        r.account_number = val
                    elif "ticket" in k:
                        r.ticket_number = val
                    elif "owner" in k and "address" not in k:
                        r.owner_name = val
                    elif "address" in k:
                        r.owner_address = val
                    elif "land" in k and "val" in k:
                        r.land_value = val
                    elif "mineral" in k:
                        r.mineral_value = val
                    elif "build" in k and "val" in k:
                        r.building_value = val
                    elif "total" in k and "val" in k:
                        r.total_value = val
                    elif "class" in k:
                        r.property_class = val
                    elif "year" in k:
                        r.tax_year = val
                if r.account_number or r.owner_name:
                    records.append(r)
            return records

        # Try page text extraction
        text = soup.get_text()
        if len(text) < 100:
            return []

        r = TaxRecord(parcel_id=PARCEL_ID, district=f"{DISTRICT_CODE}-{DISTRICT_NAME}")
        patterns = {
            "account_number": r"Account(?:\s*#|\s*No\.?|:)\s*([A-Z0-9\-]+)",
            "ticket_number":  r"Ticket(?:\s*#|\s*No\.?|:)\s*([A-Z0-9\-]+)",
            "owner_name":     r"Owner(?:\s*Name)?:?\s*([A-Z][A-Z\s,&.]+?)(?:\n|$)",
            "land_value":     r"Land(?:\s*Value)?:?\s*\$?([\d,]+\.?\d*)",
            "mineral_value":  r"Mineral(?:\s*Value)?:?\s*\$?([\d,]+\.?\d*)",
            "total_value":    r"Total(?:\s*Value)?:?\s*\$?([\d,]+\.?\d*)",
            "property_class": r"Class(?:ification)?:?\s*([A-Z0-9]+)",
        }
        for fname, pattern in patterns.items():
            m = re.search(pattern, text, re.I | re.M)
            if m:
                setattr(r, fname, m.group(1).strip())

        if r.account_number or r.owner_name:
            return [r]
        return []

    def _log_records(self) -> None:
        log.info("Tax records found: %d", len(self.records))
        for r in self.records:
            write_finding(log, "Parcel ID",       r.parcel_id)
            write_finding(log, "District",        r.district)
            write_finding(log, "Account Number",  r.account_number or "NOT FOUND")
            write_finding(log, "Ticket Number",   r.ticket_number  or "NOT FOUND")
            write_finding(log, "Owner",           r.owner_name     or "NOT FOUND")
            write_finding(log, "Land Value",      r.land_value     or "NOT FOUND")
            write_finding(log, "Mineral Value",   r.mineral_value  or "NOT FOUND")
            write_finding(log, "Building Value",  r.building_value or "NOT FOUND")
            write_finding(log, "Total Value",     r.total_value    or "NOT FOUND")
            write_finding(log, "Property Class",  r.property_class or "NOT FOUND")
            log.info("")

        for fname in ["account_number", "ticket_number", "owner_name",
                      "land_value", "mineral_value", "property_class"]:
            for r in self.records:
                if not getattr(r, fname):
                    self.missing.append(fname)
                    write_missing(log, fname)
                    break

    def _build_result(self) -> dict:
        return {
            "agent":   "TAX",
            "status":  self.status,
            "records": [
                {
                    "parcel_id":          r.parcel_id,
                    "district":           r.district,
                    "account_number":     r.account_number,
                    "ticket_number":      r.ticket_number,
                    "owner_name":         r.owner_name,
                    "owner_address":      r.owner_address,
                    "land_value":         r.land_value,
                    "building_value":     r.building_value,
                    "mineral_value":      r.mineral_value,
                    "total_value":        r.total_value,
                    "property_class":     r.property_class,
                    "tax_year":           r.tax_year,
                }
                for r in self.records
            ],
            "missing": self.missing,
            "errors":  self.errors,
            "count":   len(self.records),
        }
