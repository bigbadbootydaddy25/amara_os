"""
Redfin public listing scraper — 90+ days on market.

Redfin exposes a public CSV download endpoint that returns listing data
including days on market. This is the cleanest approach — no JS rendering needed.

Endpoint: https://www.redfin.com/stingray/api/gis-csv

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.redfin_scraper
"""

import io
import json
import time
import re

import pandas as pd
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import ALL_ZIPS, ZIP_COUNTY_MAP

REDFIN_GIS_CSV_URL = "https://www.redfin.com/stingray/api/gis-csv"
REDFIN_SEARCH_URL  = "https://www.redfin.com/stingray/do/location-autocomplete"
REDFIN_BASE        = "https://www.redfin.com"

MIN_DOM = 90


class RedfinScraper(BaseScraper):
    """Redfin 90+ DOM listing scraper across all target ZIPs."""

    SOURCE = "Redfin"

    def __init__(self, target_zips: list[str] = None):
        super().__init__(
            name="RedfinScraper",
            target_zips=target_zips or sorted(ALL_ZIPS),
        )
        self.session.headers.update({
            "Accept": "text/csv,application/json,*/*",
            "Referer": "https://www.redfin.com/",
            "X-Requested-With": "XMLHttpRequest",
        })

    def _get_region_id(self, zip_code: str) -> str | None:
        """
        Resolve a ZIP code to a Redfin region_id using their autocomplete API.
        Region ID is required for the GIS-CSV download.
        """
        params = {"location": zip_code, "v": "2", "market": "false", "count": "10"}
        resp = self.get(REDFIN_SEARCH_URL, params=params)
        if not resp:
            return None
        # Redfin autocomplete returns: {}&&{"payload":{"sections":[...]}}
        text = resp.text.lstrip("{}&")
        try:
            data = json.loads(text)
        except ValueError:
            return None
        sections = data.get("payload", {}).get("sections", [])
        for section in sections:
            for row in section.get("rows", []):
                if row.get("type") == "2":  # type 2 = ZIP code
                    url = row.get("url", "")
                    # URL format: /zipcode/XXXXX or /city/STATE/ZIPCODE
                    m = re.search(r"region_id=(\d+)", row.get("id", ""))
                    if m:
                        return m.group(1)
                    # Try extracting from the URL path
                    id_val = row.get("id", "")
                    if "_" in id_val:
                        return id_val.split("_")[-1]
        return None

    def _download_csv(self, region_id: str, zip_code: str) -> pd.DataFrame | None:
        """
        Download the Redfin GIS CSV for a given region.
        The CSV includes all active listings with DOM, price, beds, etc.
        """
        params = {
            "al":       1,
            "market":   "false",
            "num_homes": 350,
            "ord":      "days-on-redfin-desc",
            "page_number": 1,
            "region_id": region_id,
            "region_type": 2,  # 2 = ZIP code
            "sold_within_days": "",
            "status":   9,  # Active
            "uipt":     "1,2,3,4,5,6,7,8",
            "v":        8,
        }
        resp = self.get(REDFIN_GIS_CSV_URL, params=params)
        if not resp:
            return None
        # Response is CSV with a Redfin header disclaimer line
        text = resp.text
        # Strip Redfin's header disclaimer
        lines = text.split("\n")
        csv_start = next(
            (i for i, line in enumerate(lines) if line.startswith("ADDRESS")), 0
        )
        csv_text = "\n".join(lines[csv_start:])
        try:
            df = pd.read_csv(io.StringIO(csv_text), dtype=str)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            return df
        except Exception as exc:
            self.log.warning("Redfin CSV parse error for ZIP %s: %s", zip_code, exc)
            return None

    def _scrape_zip(self, zip_code: str) -> list[dict]:
        region_id = self._get_region_id(zip_code)
        if not region_id:
            self.log.warning("Redfin: could not resolve region_id for ZIP %s", zip_code)
            return []

        df = self._download_csv(region_id, zip_code)
        if df is None or df.empty:
            return []

        # Filter for DOM >= 90
        dom_col = next(
            (c for c in df.columns if "days_on" in c or "dom" in c.lower()), None
        )
        if dom_col:
            df[dom_col] = pd.to_numeric(df[dom_col], errors="coerce").fillna(0)
            df = df[df[dom_col] >= MIN_DOM]

        records = []
        addr_col    = next((c for c in df.columns if "address" in c), None)
        price_col   = next((c for c in df.columns if "price" in c), None)
        orig_col    = next((c for c in df.columns if "original" in c and "price" in c), None)
        beds_col    = next((c for c in df.columns if "beds" in c or "bedroom" in c), None)
        baths_col   = next((c for c in df.columns if "baths" in c or "bathroom" in c), None)
        sqft_col    = next((c for c in df.columns if "sq_ft" in c or "sqft" in c or "square_feet" in c), None)
        zip_col     = next((c for c in df.columns if "zip" in c or "postal" in c), None)
        proptype_col= next((c for c in df.columns if "property_type" in c or "prop_type" in c), None)

        for _, row in df.iterrows():
            zip_val = str(row.get(zip_col, zip_code)).strip()[:5] if zip_col else zip_code
            records.append(self.canonical_record(
                address=str(row.get(addr_col, "")) if addr_col else "",
                zip_code=zip_val,
                distress_type="dom90",
                source=self.SOURCE,
                raw_data={
                    "list_price":     row.get(price_col, "") if price_col else "",
                    "original_price": row.get(orig_col, "") if orig_col else "",
                    "dom":            row.get(dom_col, "") if dom_col else "",
                    "beds":           row.get(beds_col, "") if beds_col else "",
                    "baths":          row.get(baths_col, "") if baths_col else "",
                    "sqft":           row.get(sqft_col, "") if sqft_col else "",
                    "prop_type":      row.get(proptype_col, "") if proptype_col else "",
                },
            ))

        self.log.info("Redfin ZIP %s: %d listings (DOM >= %d)", zip_code, len(records), MIN_DOM)
        return records

    def scrape(self) -> list[dict]:
        all_records = []
        for zip_code in self.target_zips:
            try:
                recs = self._scrape_zip(zip_code)
                all_records.extend(recs)
            except Exception as exc:
                self.log.error("Redfin ZIP %s failed: %s", zip_code, exc, exc_info=True)
        self.save_raw(all_records, "redfin_dom90_raw.csv")
        return all_records


if __name__ == "__main__":
    RedfinScraper().run()
