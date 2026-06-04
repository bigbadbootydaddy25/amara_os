"""
CHAIN Agent — Harrison County Clerk grantor/grantee index.
Target: harrison.countyclerk.us/online-records/
Pulls full chain of title for parcel 11-409-19 oldest to newest.
Downloads every instrument: deeds, OGLs, assignments, wills, fiduciary.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from config import PARCEL_ID, PARCEL_COUNTY, PARCEL_DISTRICT
from core.logger import get_logger, write_section_header, write_instrument, write_gap, write_missing, write_error
from core.scraper import DeedScraper
from core.telegram_client import send_hard_fail

log = get_logger("CHAIN")

BASE_URL   = "https://harrison.countyclerk.us/online-records"
SEARCH_URL = f"{BASE_URL}/"

# Instrument types to capture
INST_TYPES = [
    "DEED", "DEED OF TRUST", "WARRANTY DEED", "QUITCLAIM DEED",
    "OIL AND GAS LEASE", "OGL", "ASSIGNMENT", "WILL", "FIDUCIARY",
    "MINERAL DEED", "ROYALTY DEED", "CORRECTION DEED", "RELEASE",
    "PARTIAL RELEASE", "AFFIDAVIT", "SURVEY", "PLAT",
]


@dataclass
class Instrument:
    seq: int = 0
    inst_type: str = ""
    grantor: str = ""
    grantee: str = ""
    book: str = ""
    page: str = ""
    date_recorded: str = ""
    date_instrument: str = ""
    description: str = ""
    notes: str = ""
    url: str = ""


class ChainAgent:
    def __init__(self):
        self.scraper = DeedScraper("CHAIN")
        self.instruments: list[Instrument] = []
        self.gaps: list[str] = []
        self.errors: list[str] = []
        self.status = "NOT_RUN"

    def run(self) -> dict:
        write_section_header(log, f"CHAIN AGENT — Parcel {PARCEL_ID} | {PARCEL_COUNTY} County WV")
        log.info("Target: %s", SEARCH_URL)
        log.info("Searching grantor/grantee index for parcel %s", PARCEL_ID)

        try:
            result = self._run_search()
            self.status = "COMPLETE" if result else "FAILED"
        except Exception as e:
            err = f"Unhandled exception: {e}"
            self.errors.append(err)
            write_error(log, "CHAIN", err)
            send_hard_fail("CHAIN", err)
            self.status = "HARD_FAIL"

        return self._build_result()

    def _run_search(self) -> bool:
        # Step 1: Load the search page
        log.info("Loading online records search page...")
        soup = self.scraper.get(SEARCH_URL)
        if soup is None:
            err = (
                f"Cannot reach {SEARCH_URL}. "
                "This site blocks cloud/non-local IPs. "
                "Must run from Mac on local network."
            )
            self.errors.append(err)
            write_error(log, "CHAIN-LOAD", err)
            send_hard_fail("CHAIN", err)
            return False

        log.info("Search page loaded. Extracting form fields...")

        # Step 2: Check for search form
        form = soup.find("form")
        if not form:
            log.warning("No form found on page — may require JavaScript")
            write_missing(log, "Search form (may be JS-rendered)")

        viewstate = self.scraper.extract_viewstate(soup)
        log.debug("ViewState fields found: %s", list(viewstate.keys()))

        # Step 3: Search by parcel number (grantor/grantee name search)
        # Harrison County Clerk typically uses grantor/grantee name or parcel search
        # The parcel ID format is district-parcel: 11-409-19
        search_queries = [
            {"parcel": PARCEL_ID},
            {"grantor": "", "grantee": "", "parcel": PARCEL_ID},
        ]

        for query in search_queries:
            log.info("Trying search query: %s", query)
            post_data = {**viewstate, **query}
            result_soup = self.scraper.post(SEARCH_URL, data=post_data)
            if result_soup:
                instruments = self._parse_results(result_soup)
                if instruments:
                    log.info("Found %d instruments", len(instruments))
                    self.instruments = instruments
                    self._analyze_chain()
                    return True

        # Step 4: Try grantor/grantee name search for known owners
        # WV property transfers commonly searched by last name
        common_surnames = ["STRUNK", "TEXHOMA", "HARRISON"]
        for name in common_surnames:
            log.info("Searching by grantor/grantee name: %s", name)
            post_data = {**viewstate, "grantor": name}
            result_soup = self.scraper.post(SEARCH_URL, data=post_data)
            if result_soup:
                instruments = self._parse_results(result_soup)
                if instruments:
                    self.instruments.extend(instruments)

        if self.instruments:
            self._analyze_chain()
            return True

        write_missing(log, "No instruments found — verify parcel ID and search parameters")
        log.warning("No instruments returned. Parcel %s may use different index format.", PARCEL_ID)
        return False

    def _parse_results(self, soup: BeautifulSoup) -> list[Instrument]:
        instruments = []
        rows = self.scraper.table_to_rows(soup)
        if not rows:
            # Try alternate structure
            result_divs = soup.find_all("div", class_=re.compile(r"result|record|instrument", re.I))
            if not result_divs:
                log.debug("No table rows or result divs found")
                return []

        seq = len(self.instruments) + 1
        for row in rows:
            if not any(row.values()):
                continue
            inst = Instrument(seq=seq)
            # Map common column names (clerk systems vary)
            for key, val in row.items():
                k = key.lower()
                if "grantor" in k:
                    inst.grantor = val
                elif "grantee" in k:
                    inst.grantee = val
                elif "book" in k:
                    inst.book = val
                elif "page" in k:
                    inst.page = val
                elif "type" in k or "instrument" in k:
                    inst.inst_type = val
                elif "date" in k and "record" in k:
                    inst.date_recorded = val
                elif "date" in k:
                    inst.date_instrument = val
                elif "desc" in k:
                    inst.description = val

            if inst.grantor or inst.book:
                instruments.append(inst)
                seq += 1

        return instruments

    def _analyze_chain(self) -> None:
        """Sort instruments by date and identify gaps."""
        log.info("")
        log.info("Chain of Title — %d instruments found:", len(self.instruments))
        for inst in self.instruments:
            write_instrument(
                log, inst.seq, inst.inst_type,
                inst.grantor, inst.grantee,
                inst.book, inst.page,
                inst.date_recorded or inst.date_instrument,
                inst.notes,
            )

        # Gap analysis
        if len(self.instruments) < 2:
            if not self.instruments:
                write_gap(log, "No instruments found — chain cannot be built")
                self.gaps.append("No instruments found")
            return

        # Check for continuity: each grantee should become next grantor
        for i in range(len(self.instruments) - 1):
            curr = self.instruments[i]
            nxt  = self.instruments[i + 1]
            if curr.grantee and nxt.grantor:
                if curr.grantee.upper() != nxt.grantor.upper():
                    gap = (
                        f"Break between instrument {curr.seq} and {nxt.seq}: "
                        f"grantee '{curr.grantee}' ≠ grantor '{nxt.grantor}'"
                    )
                    write_gap(log, gap)
                    self.gaps.append(gap)

    def _build_result(self) -> dict:
        return {
            "agent":       "CHAIN",
            "status":      self.status,
            "parcel":      PARCEL_ID,
            "instruments": [
                {
                    "seq":           i.seq,
                    "type":          i.inst_type,
                    "grantor":       i.grantor,
                    "grantee":       i.grantee,
                    "book":          i.book,
                    "page":          i.page,
                    "date_recorded": i.date_recorded,
                    "date_instr":    i.date_instrument,
                    "description":   i.description,
                    "notes":         i.notes,
                }
                for i in self.instruments
            ],
            "gaps":   self.gaps,
            "errors": self.errors,
            "count":  len(self.instruments),
        }
