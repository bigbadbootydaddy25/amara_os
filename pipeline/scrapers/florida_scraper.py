"""
Florida scraper — Brevard, St. Lucie, and Alachua (Gainesville) counties.

Target ZIPs:
  Brevard:      32935, 32907, 32955, 32940
  St. Lucie:    34953, 34983, 34984
  Gainesville:  32641, 32607, 32609

Sources:
  - Brevard County Property Appraiser: https://www.bcpao.us/
  - St. Lucie County Property Appraiser: https://www.paslc.gov/
  - Alachua County Property Appraiser: https://www.acpafl.org/
  - FL Clerk of Courts (lis pendens): county-specific clerk portals
  - FL Dept. of Revenue delinquent lists

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.florida_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

# Brevard County
BREVARD_APPRAISER  = "https://www.bcpao.us/propertysearch/"
BREVARD_CLERK      = "https://brevardclerk.us/official-records-search"

# St. Lucie County
STLUCIE_APPRAISER  = "https://www.paslc.gov/propertysearch"
STLUCIE_CLERK      = "https://www.clerkofcourts.co.st-lucie.fl.us/official-records"

# Alachua County
ALACHUA_APPRAISER  = "https://www.acpafl.org/propertysearch"
ALACHUA_CLERK      = "https://www.circuit8.org/official-records"


class FloridaScraper(BaseScraper):
    """Florida tri-county real estate OSINT scraper."""

    SOURCE = "FloridaCounties"

    def __init__(self):
        super().__init__(
            name="FloridaScraper",
            target_zips=(
                TARGET_ZIPS["brevard"]
                + TARGET_ZIPS["port_st_lucie"]
                + TARGET_ZIPS["gainesville"]
            ),
        )
        self._brevard_zips  = set(TARGET_ZIPS["brevard"])
        self._stlucie_zips  = set(TARGET_ZIPS["port_st_lucie"])
        self._alachua_zips  = set(TARGET_ZIPS["gainesville"])

    def _appraiser_url(self, zip_code: str) -> str:
        if zip_code in self._brevard_zips:
            return BREVARD_APPRAISER
        if zip_code in self._stlucie_zips:
            return STLUCIE_APPRAISER
        return ALACHUA_APPRAISER

    def _clerk_url(self, zip_code: str) -> str:
        if zip_code in self._brevard_zips:
            return BREVARD_CLERK
        if zip_code in self._stlucie_zips:
            return STLUCIE_CLERK
        return ALACHUA_CLERK

    def scrape_vacant_land(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            url = self._appraiser_url(zip_code)
            params = {"zip": zip_code, "proptype": "L"}
            resp = self.get(url, params=params)
            if not resp:
                continue
            try:
                data = resp.json()
                props = data.get("properties") or data.get("results") or []
                for p in props:
                    imprv = float(p.get("improvement_value") or p.get("building_value") or 1)
                    if imprv == 0:
                        records.append(self.canonical_record(
                            owner_name=p.get("owner_name", ""),
                            address=p.get("situs_address", p.get("address", "")),
                            zip_code=zip_code,
                            parcel_id=p.get("parcel_id", ""),
                            distress_type="vacant_land",
                            source=f"{self.SOURCE}_{zip_code}",
                            raw_data=p,
                        ))
            except ValueError:
                soup = BeautifulSoup(resp.text, "lxml")
                for tr in (soup.select("table tr") or [])[1:]:
                    tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(tds) < 2:
                        continue
                    records.append(self.canonical_record(
                        owner_name=tds[1] if len(tds) > 1 else "",
                        address=tds[0],
                        zip_code=zip_code,
                        distress_type="vacant_land",
                        source=f"FL_Appraiser_{zip_code}",
                        raw_data={"row": tds},
                    ))
        return records

    def scrape_tax_delinquent(self) -> list[dict]:
        """
        Florida tax delinquent lists are published by county tax collector.
        Some counties publish CSV files; others require search.
        """
        records = []
        # Florida delinquent tax certificate info via county tax collectors
        fl_tax_urls = {
            "brevard":  "https://www.brevardtaxcollector.com/property-tax/delinquent",
            "stlucie":  "https://www.tcslc.com/delinquent-tax",
            "alachua":  "https://www.alachuacounty.us/Depts/TC/Pages/delinquent.aspx",
        }
        county_zip_map = {
            "brevard": self._brevard_zips,
            "stlucie": self._stlucie_zips,
            "alachua": self._alachua_zips,
        }
        for county, url in fl_tax_urls.items():
            for zip_code in county_zip_map[county]:
                resp = self.get(url, params={"zip": zip_code})
                if not resp:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
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
                        source=f"FL_{county}_TaxCollector",
                        raw_data={"row": tds},
                    ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            url = self._clerk_url(zip_code)
            params = {"doctype": "LIS PENDENS", "zip": zip_code, "datefrom": "01/01/2022"}
            resp = self.get(url, params=params)
            if not resp:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for tr in (soup.select("table tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[2] if len(tds) > 2 else "",
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source=f"FL_Clerk_LP_{zip_code}",
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
        self.save_raw(all_records, "florida_raw.csv")
        return all_records


if __name__ == "__main__":
    FloridaScraper().run()
