"""
Kaufman Central Appraisal District scraper.

Target ZIPs: 75126 (Forney), 75142 (Kaufman), 75160 (Terrell), 75114 (Crandall)

Sources:
  - Kaufman CAD: https://www.kaufmancad.org/
  - Kaufman County Clerk: https://www.kaufmancounty.net/clerk/
  - Kaufman County Tax: https://www.kaufmancounty.net/tax/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.kaufman_cad_scraper
"""

import io
import zipfile

import pandas as pd
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

KAUFMAN_CAD_URL   = "https://www.kaufmancad.org/propertysearch"
KAUFMAN_CLERK_URL = "https://www.kaufmancounty.net/clerk/"
KAUFMAN_TAX_URL   = "https://www.kaufmancounty.net/tax/"


class KaufmanCADScraper(BaseScraper):
    """Kaufman County Appraisal District scraper."""

    SOURCE = "KaufmanCAD"

    def __init__(self):
        super().__init__(
            name="KaufmanCADScraper",
            target_zips=TARGET_ZIPS["kaufman_county"],
        )

    def _col(self, row, candidates, default=""):
        for c in candidates:
            v = row.get(c)
            if v and str(v).strip() not in ("", "nan", "None"):
                return str(v).strip()
        return default

    def _search_by_zip(self, zip_code: str, prop_type: str = "") -> list[dict]:
        """Search Kaufman CAD public portal for a given ZIP."""
        params = {
            "zip": zip_code,
            "searchtype": "A",
            "proptype": prop_type,
        }
        soup = self.soup(KAUFMAN_CAD_URL, params=params)
        if not soup:
            return []
        rows = soup.select("table tr")[1:] or []
        results = []
        for tr in rows:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 3:
                continue
            results.append({
                "address": tds[0],
                "owner": tds[1] if len(tds) > 1 else "",
                "parcel_id": tds[2] if len(tds) > 2 else "",
                "imprv_val": tds[3] if len(tds) > 3 else "1",
                "zip_code": zip_code,
            })
        return results

    def scrape_vacant_land(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            props = self._search_by_zip(zip_code, prop_type="L")
            for p in props:
                imprv = p.get("imprv_val", "1")
                if str(imprv) in ("0", "0.0", ""):
                    records.append(self.canonical_record(
                        owner_name=p["owner"],
                        address=p["address"],
                        zip_code=zip_code,
                        parcel_id=p["parcel_id"],
                        distress_type="vacant_land",
                        source=f"{self.SOURCE}_search",
                        raw_data=p,
                    ))
        return records

    def scrape_tax_delinquent(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(KAUFMAN_TAX_URL, params={"zip": zip_code, "delinquent": "1"})
            if not soup:
                continue
            for tr in (soup.select("table tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[0],
                    zip_code=zip_code,
                    distress_type="tax_delinquent",
                    amount_owed=tds[2] if len(tds) > 2 else "",
                    source="Kaufman_Tax",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(KAUFMAN_CLERK_URL, params={"doctype": "LP", "zip": zip_code})
            if not soup:
                continue
            for tr in (soup.select("table tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[0],
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source="Kaufman_Clerk_LP",
                    raw_data={"row": tds},
                ))
        return records

    def scrape(self) -> list[dict]:
        all_records = []
        for label, fn in [
            ("vacant_land",    self.scrape_vacant_land),
            ("tax_delinquent", self.scrape_tax_delinquent),
            ("lis_pendens",    self.scrape_lis_pendens),
        ]:
            try:
                recs = fn()
                all_records.extend(recs)
                self.log.info("[%s] %d records", label, len(recs))
            except Exception as exc:
                self.log.error("[%s] failed: %s", label, exc, exc_info=True)
        self.save_raw(all_records, "kaufman_cad_raw.csv")
        return all_records


if __name__ == "__main__":
    KaufmanCADScraper().run()
