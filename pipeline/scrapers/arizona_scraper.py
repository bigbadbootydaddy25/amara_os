"""
Maricopa County, AZ scraper — Phoenix metro.

Target ZIPs: 85041, 85043, 85009, 85033, 85035

Sources:
  - Maricopa Assessor: https://mcassessor.maricopa.gov/
  - Maricopa Assessor API: https://mcassessor.maricopa.gov/mcs.php
  - Maricopa Recorder: https://recorder.maricopa.gov/
  - Maricopa Treasurer (delinquent): https://treasurer.maricopa.gov/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.arizona_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

ASSESSOR_SEARCH = "https://mcassessor.maricopa.gov/mcs.php"
RECORDER_SEARCH = "https://recorder.maricopa.gov/web/search.aspx"
TREASURER_URL   = "https://treasurer.maricopa.gov/PropertyTax/Default.aspx"


class ArizonaScraper(BaseScraper):
    """Maricopa County, AZ real estate OSINT scraper."""

    SOURCE = "MaricopaCountyAZ"

    def __init__(self):
        super().__init__(
            name="ArizonaScraper",
            target_zips=TARGET_ZIPS["phoenix"],
        )

    def scrape_vacant_land(self) -> list[dict]:
        """
        Maricopa Assessor public search — filter for vacant parcels.
        Uses the public MCS interface with ZIP and land-use filter.
        """
        records = []
        for zip_code in self.target_zips:
            params = {
                "q": zip_code,
                "t": "address",
                "empty_improvement": "1",
            }
            resp = self.get(ASSESSOR_SEARCH, params=params)
            if not resp:
                continue
            try:
                data = resp.json()
                parcels = data.get("results") or data.get("parcels") or []
                for p in parcels:
                    imprv = float(p.get("improvement_value") or 0)
                    if imprv == 0:
                        records.append(self.canonical_record(
                            owner_name=p.get("owner_name", ""),
                            address=p.get("situs_address", ""),
                            zip_code=zip_code,
                            parcel_id=p.get("parcel_number", ""),
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
        """
        Maricopa Treasurer delinquent tax search.
        Delinquent list published at treasurer.maricopa.gov.
        """
        records = []
        for zip_code in self.target_zips:
            resp = self.get(TREASURER_URL, params={"zip": zip_code, "status": "delinquent"})
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
                    source="Maricopa_Treasurer",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        """Maricopa County Recorder lis pendens search."""
        records = []
        for zip_code in self.target_zips:
            params = {
                "SearchType": "D",
                "DocType": "LIS PENDENS",
                "ZipCode": zip_code,
                "DateFrom": "01/01/2022",
            }
            resp = self.get(RECORDER_SEARCH, params=params)
            if not resp:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for tr in (soup.select("table.searchresults tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[2] if len(tds) > 2 else "",
                    address=tds[4] if len(tds) > 4 else "",
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source="Maricopa_Recorder_LP",
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
        self.save_raw(all_records, "arizona_raw.csv")
        return all_records


if __name__ == "__main__":
    ArizonaScraper().run()
