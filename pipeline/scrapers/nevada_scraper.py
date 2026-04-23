"""
Clark County, NV scraper — Las Vegas metro.

Target ZIPs: 89121, 89122, 89104, 89101, 89030, 89031

Sources:
  - Clark County Assessor: https://www.clarkcountynv.gov/government/departments/assessor/
  - Clark County public property portal: https://maps.clarkcountynv.gov/assrdata/
  - Clark County Recorder: https://recorder.clarkcountynv.gov/
  - Nevada delinquent taxes: via Clark County Treasurer

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.nevada_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

ASSESSOR_API   = "https://maps.clarkcountynv.gov/assrdata/api/property/search"
RECORDER_URL   = "https://recorder.clarkcountynv.gov/Search/SearchResults"
TREASURER_URL  = "https://treasurer.clarkcountynv.gov/delinquent"


class NevadaScraper(BaseScraper):
    """Clark County, NV — Las Vegas real estate OSINT."""

    SOURCE = "ClarkCountyNV"

    def __init__(self):
        super().__init__(
            name="NevadaScraper",
            target_zips=TARGET_ZIPS["las_vegas"],
        )

    # ------------------------------------------------------------------ #

    def scrape_vacant_land(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            params = {
                "zipCode": zip_code,
                "propertyType": "VACANT",
                "pageSize": 200,
                "page": 1,
            }
            resp = self.get(ASSESSOR_API, params=params)
            if not resp:
                continue
            try:
                data = resp.json()
                props = data.get("properties") or data.get("results") or []
                for p in props:
                    if str(p.get("improvementValue", "1")) in ("0", "0.0", ""):
                        records.append(self.canonical_record(
                            owner_name=p.get("ownerName", ""),
                            address=p.get("siteAddress", ""),
                            zip_code=zip_code,
                            parcel_id=p.get("parcelNumber", ""),
                            distress_type="vacant_land",
                            source=f"{self.SOURCE}_assessor",
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
                        source=f"{self.SOURCE}_assessor",
                        raw_data={"row": tds},
                    ))
        return records

    def scrape_tax_delinquent(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            resp = self.get(TREASURER_URL, params={"zip": zip_code})
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
                    source="ClarkCounty_Treasurer",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            params = {
                "DocumentType": "LIS PENDENS",
                "ZipCode": zip_code,
                "DateFrom": "01/01/2022",
            }
            resp = self.get(RECORDER_URL, params=params)
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
                    source="ClarkCounty_Recorder_LP",
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
        self.save_raw(all_records, "nevada_raw.csv")
        return all_records


if __name__ == "__main__":
    NevadaScraper().run()
