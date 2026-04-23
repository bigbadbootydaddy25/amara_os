"""
Oklahoma scraper — OKC, Edmond (Oklahoma County), Tulsa (Tulsa County), Yukon (Canadian County).

Target ZIPs:
  OKC:    73111, 73117, 73129
  Edmond: 73013, 73034
  Tulsa:  74110, 74112, 74106
  Yukon:  73099

Sources:
  - Oklahoma County Assessor: https://www.oklahomacountyassessor.com/
  - Oklahoma County Treasurer: https://www.treasurer.oklahomacounty.org/
  - Tulsa County Assessor: https://www.assessor.tulsacounty.org/
  - Canadian County Assessor: https://www.canadiancountyassessor.com/
  - OK OSCN (court records/lis pendens): https://www.oscn.net/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.oklahoma_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

# Oklahoma County
OKC_ASSESSOR_URL   = "https://www.oklahomacountyassessor.com/PropertySearch"
OKC_TREASURER_URL  = "https://www.treasurer.oklahomacounty.org/DelinquentTaxes"

# Tulsa County
TULSA_ASSESSOR_URL = "https://www.assessor.tulsacounty.org/assessor-property-search.php"
TULSA_TREASURER_URL= "https://www.treasurer.tulsacounty.org/delinquent"

# Canadian County
CANADIAN_ASSESSOR  = "https://www.canadiancountyassessor.com/search"
CANADIAN_TREASURER = "https://www.canadiancounty.org/259/Treasurer"

# OSCN — Oklahoma State Courts Network (lis pendens)
OSCN_SEARCH_URL    = "https://www.oscn.net/dockets/GetCaseInformation.aspx"


class OklahomaScraper(BaseScraper):
    """Multi-county Oklahoma real estate OSINT scraper."""

    SOURCE = "OklahomaCounty"

    def __init__(self):
        super().__init__(
            name="OklahomaScraper",
            target_zips=(
                TARGET_ZIPS["okc"]
                + TARGET_ZIPS["edmond"]
                + TARGET_ZIPS["tulsa"]
                + TARGET_ZIPS["yukon"]
            ),
        )
        self._oklahoma_county_zips = set(TARGET_ZIPS["okc"] + TARGET_ZIPS["edmond"])
        self._tulsa_zips           = set(TARGET_ZIPS["tulsa"])
        self._canadian_zips        = set(TARGET_ZIPS["yukon"])

    def _assessor_url_for_zip(self, zip_code: str) -> str:
        if zip_code in self._tulsa_zips:
            return TULSA_ASSESSOR_URL
        if zip_code in self._canadian_zips:
            return CANADIAN_ASSESSOR
        return OKC_ASSESSOR_URL

    def _treasurer_url_for_zip(self, zip_code: str) -> str:
        if zip_code in self._tulsa_zips:
            return TULSA_TREASURER_URL
        if zip_code in self._canadian_zips:
            return CANADIAN_TREASURER
        return OKC_TREASURER_URL

    def scrape_vacant_land(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            url = self._assessor_url_for_zip(zip_code)
            params = {"zip": zip_code, "proptype": "vacant", "pagesize": 200}
            resp = self.get(url, params=params)
            if not resp:
                continue
            try:
                data = resp.json()
                props = data.get("properties") or data.get("results") or []
                for p in props:
                    imprv = float(p.get("improvement_value") or p.get("imprv_val") or 1)
                    if imprv == 0:
                        records.append(self.canonical_record(
                            owner_name=p.get("owner_name", ""),
                            address=p.get("address", ""),
                            zip_code=zip_code,
                            parcel_id=p.get("parcel_id", ""),
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
            url = self._treasurer_url_for_zip(zip_code)
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
                    source="OK_Treasurer",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        """
        Oklahoma State Courts Network (OSCN) — search for lis pendens filings
        in the target counties. OSCN provides a public docket search.
        """
        records = []
        county_map = {
            "oklahoma": list(self._oklahoma_county_zips),
            "tulsa":    list(self._tulsa_zips),
            "canadian": list(self._canadian_zips),
        }
        for county_name, zips in county_map.items():
            if not zips:
                continue
            params = {
                "db": county_name,
                "number": "",
                "cmsa": "LM",   # Lis Pendens case type
                "casetype": "CV",
            }
            resp = self.get(OSCN_SEARCH_URL, params=params)
            if not resp:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for tr in (soup.select("table.result tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 3:
                    continue
                # Map to first ZIP in this county's list as approximation
                zip_code = zips[0]
                records.append(self.canonical_record(
                    owner_name=tds[2] if len(tds) > 2 else "",
                    address=tds[3] if len(tds) > 3 else "",
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source=f"OSCN_{county_name}_LP",
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
        self.save_raw(all_records, "oklahoma_raw.csv")
        return all_records


if __name__ == "__main__":
    OklahomaScraper().run()
