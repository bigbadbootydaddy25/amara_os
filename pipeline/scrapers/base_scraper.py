"""
Base scraper class — all county scrapers inherit from this.

Provides: session management, rate limiting, retry logic, logging,
CSV output helpers, and address normalization utilities.
"""

import csv
import json
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import SCRAPER_SETTINGS, ALL_ZIPS, ZIP_COUNTY_MAP

# Module-level logger — each subclass uses its own named logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


class BaseScraper(ABC):
    """
    Abstract base for all OSINT scrapers in this pipeline.

    Subclasses implement `scrape()` and optionally override
    `scrape_tax_delinquent()`, `scrape_vacant_land()`, etc.
    All scrapers return a list of dicts with the canonical schema.
    """

    # Canonical output field names — every scraper must populate these
    CANONICAL_FIELDS = [
        "owner_name",
        "address",
        "city",
        "state",
        "zip_code",
        "county",
        "parcel_id",
        "distress_type",      # preforeclosure|tax_delinquent|vacant_land|ghost_plat|
                               # cash_buyer|dom90|code_violation|probate|
                               # absentee_owner|nod|bankruptcy
        "amount_owed",
        "filing_date",
        "source",
        "scrape_date",
        "raw_data",           # JSON blob of all raw fields for audit trail
    ]

    def __init__(self, name: str, target_zips: list[str]):
        self.name = name
        self.target_zips = target_zips
        self.log = logging.getLogger(name)
        self.session = self._build_session()
        self._last_request_time = 0.0

    # ------------------------------------------------------------------ #
    #  Session / HTTP helpers                                              #
    # ------------------------------------------------------------------ #

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": random.choice(SCRAPER_SETTINGS["user_agents"]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })
        return s

    def _rotate_agent(self):
        self.session.headers["User-Agent"] = random.choice(
            SCRAPER_SETTINGS["user_agents"]
        )

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        delay = random.uniform(
            SCRAPER_SETTINGS["request_delay_min"],
            SCRAPER_SETTINGS["request_delay_max"],
        )
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str, params: dict = None, **kwargs) -> requests.Response | None:
        """Rate-limited GET with retry logic."""
        self._rate_limit()
        retries = SCRAPER_SETTINGS["max_retries"]
        backoff = SCRAPER_SETTINGS["retry_backoff"]
        for attempt in range(retries):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    timeout=SCRAPER_SETTINGS["timeout"],
                    **kwargs,
                )
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                self.log.warning(
                    "GET %s attempt %d/%d failed: %s", url, attempt + 1, retries, exc
                )
                if attempt < retries - 1:
                    time.sleep(backoff * (2 ** attempt))
                    self._rotate_agent()
        self.log.error("All retries exhausted for %s", url)
        return None

    def post(self, url: str, data: dict = None, json_body: dict = None, **kwargs) -> requests.Response | None:
        """Rate-limited POST with retry logic."""
        self._rate_limit()
        retries = SCRAPER_SETTINGS["max_retries"]
        backoff = SCRAPER_SETTINGS["retry_backoff"]
        for attempt in range(retries):
            try:
                resp = self.session.post(
                    url,
                    data=data,
                    json=json_body,
                    timeout=SCRAPER_SETTINGS["timeout"],
                    **kwargs,
                )
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                self.log.warning(
                    "POST %s attempt %d/%d failed: %s", url, attempt + 1, retries, exc
                )
                if attempt < retries - 1:
                    time.sleep(backoff * (2 ** attempt))
        self.log.error("All retries exhausted for POST %s", url)
        return None

    def soup(self, url: str, params: dict = None, **kwargs) -> BeautifulSoup | None:
        resp = self.get(url, params=params, **kwargs)
        if resp is None:
            return None
        return BeautifulSoup(resp.text, "lxml")

    # ------------------------------------------------------------------ #
    #  Data helpers                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def normalize_address(raw: str) -> str:
        """Basic address normalization: uppercase, strip extra whitespace."""
        if not raw:
            return ""
        addr = " ".join(raw.upper().split())
        replacements = {
            " STREET": " ST", " AVENUE": " AVE", " BOULEVARD": " BLVD",
            " DRIVE": " DR", " ROAD": " RD", " LANE": " LN",
            " COURT": " CT", " PLACE": " PL", " CIRCLE": " CIR",
            " NORTH ": " N ", " SOUTH ": " S ", " EAST ": " E ",
            " WEST ": " W ",
        }
        for old, new in replacements.items():
            addr = addr.replace(old, new)
        return addr.strip()

    @staticmethod
    def normalize_owner(raw: str) -> str:
        if not raw:
            return ""
        return " ".join(raw.upper().split()).strip()

    @staticmethod
    def canonical_record(
        *,
        owner_name: str = "",
        address: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
        county: str = "",
        parcel_id: str = "",
        distress_type: str = "",
        amount_owed: str = "",
        filing_date: str = "",
        source: str = "",
        raw_data: dict = None,
    ) -> dict:
        info = ZIP_COUNTY_MAP.get(zip_code, {})
        return {
            "owner_name": BaseScraper.normalize_owner(owner_name),
            "address": BaseScraper.normalize_address(address),
            "city": city or info.get("city", ""),
            "state": state or info.get("state", ""),
            "zip_code": zip_code,
            "county": county or info.get("county", ""),
            "parcel_id": parcel_id,
            "distress_type": distress_type,
            "amount_owed": amount_owed,
            "filing_date": filing_date,
            "source": source,
            "scrape_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "raw_data": json.dumps(raw_data or {}),
        }

    def in_target_zip(self, zip_code: str) -> bool:
        return zip_code in set(self.target_zips)

    # ------------------------------------------------------------------ #
    #  CSV output                                                          #
    # ------------------------------------------------------------------ #

    def save_raw(self, records: list[dict], filename: str) -> Path:
        """Write records to /data/raw/<filename>. Returns path written."""
        if not records:
            self.log.info("No records to save for %s", filename)
            return RAW_DIR / filename
        out_path = RAW_DIR / filename
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.CANONICAL_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        self.log.info("Saved %d records → %s", len(records), out_path)
        return out_path

    # ------------------------------------------------------------------ #
    #  Abstract interface                                                  #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Entry point. Must return a list of canonical record dicts.
        Call self.save_raw() before returning.
        """
        ...

    def run(self) -> list[dict]:
        """Public runner — wraps scrape() with top-level error handling."""
        self.log.info("Starting scraper: %s (ZIPs: %s)", self.name, self.target_zips)
        try:
            records = self.scrape()
            self.log.info(
                "Finished %s — %d records collected", self.name, len(records)
            )
            return records
        except Exception as exc:
            self.log.error("Scraper %s crashed: %s", self.name, exc, exc_info=True)
            return []
