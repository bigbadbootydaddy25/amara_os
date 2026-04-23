"""
Multi-state scraper — covers all remaining target markets:

  NC:  Cumberland (Fayetteville), Gaston (Gastonia), Buncombe (Asheville)
  TN:  Montgomery (Clarksville), Knox (Knoxville)
  VA:  Richmond City
  SC:  Richland (Columbia), Greenville
  GA:  Muscogee (Columbus)
  LA:  Bossier Parish, Caddo Parish (Shreveport)
  MI:  Wayne County (Detroit)
  IN:  Marion County (Indianapolis)
  OH:  Franklin (Columbus), Montgomery (Dayton), Lucas (Toledo)
  KY:  Jefferson County (Louisville)
  PA:  Berks County (Reading)
  NH:  Hillsborough County (Manchester)
  CA:  Fresno County
  NM:  Bernalillo County (Albuquerque)

Each county/state uses the same scraper pattern as HCAD:
  1. Try county assessor/appraiser API or bulk download
  2. Fall back to HTML search
  3. Scrape county clerk for lis pendens

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.multi_state_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS, ZIP_COUNTY_MAP

# ── Assessor portal URLs by county ─────────────────────────────────────────
ASSESSOR_URLS = {
    # NC
    "Cumberland":  "https://tax.co.cumberland.nc.us/Property/Search",
    "Gaston":      "https://tax.co.gaston.nc.us/PropertySearch",
    "Buncombe":    "https://www.buncombecounty.org/governing/depts/TAX/propertySearch.aspx",
    # TN
    "Montgomery":  "https://www.assessoroftaxes.com/ClarksvilleSearch",
    "Knox":        "https://www.knoxcounty.org/assessor/property_search.php",
    # VA
    "Richmond City":"https://eservices.richmondgov.com/applications/propertysearch/",
    # SC
    "Richland":    "https://www.richlandcountysc.gov/Departments/Assessor/property-search",
    "Greenville":  "https://www.greenvillecounty.org/apps/RealPropertySearch/",
    # GA
    "Muscogee":    "https://qpublic.schneidercorp.com/Application.aspx?AppID=623",
    # LA
    "Bossier":     "https://www.bossiersheriff.com/assessment/",
    "Caddo":       "https://assessor.caddo.org/property-search",
    # MI
    "Wayne":       "https://www.waynecounty.com/elected/treasurer/property-tax-information.aspx",
    # IN
    "Marion":      "https://www.indy.gov/activity/search-for-property-tax-information",
    # OH
    "Franklin":    "https://property.franklincountyauditor.com/_web/search/commonsearch.aspx",
    "Montgomery":  "https://www.mcrealestate.org/",
    "Lucas":       "https://lucascountyauditor.org/property-search/",
    # KY
    "Jefferson":   "https://www.loucollector.com/search/",
    # PA
    "Berks":       "https://www.berkscounty.us/AssessorSearchPage",
    # NH
    "Hillsborough":"https://www.nhdeeds.com/",
    # CA
    "Fresno":      "https://www.co.fresno.ca.us/departments/assessor-recorder",
    # NM
    "Bernalillo":  "https://www.bernco.gov/assessor/search-property/",
}

# ── Clerk portal URLs for lis pendens ──────────────────────────────────────
CLERK_URLS = {
    "Cumberland":  "https://www2.nccourts.org/onlineservices/",
    "Gaston":      "https://www2.nccourts.org/onlineservices/",
    "Buncombe":    "https://www2.nccourts.org/onlineservices/",
    "Montgomery":  "https://www.tncourts.gov/courts/circuit-court/montgomery/clerk",
    "Knox":        "https://www.knoxcountyclerk.net/real-estate/",
    "Richmond City":"https://www.richmondcircuitcourt.com/",
    "Richland":    "https://www.richlandclerk.com/",
    "Greenville":  "https://www.greenvillecounty.org/clerkofcourt/",
    "Muscogee":    "https://www.columbusga.gov/clerk/",
    "Bossier":     "https://www.bossiersheriff.com/",
    "Caddo":       "https://www.caddoclerk.com/",
    "Wayne":       "https://www.waynecounty.com/elected/clerk/real-property.aspx",
    "Marion":      "https://www.indy.gov/activity/recorder-property-records",
    "Franklin":    "https://www.franklincountyohio.gov/recorder/",
    "Montgomery":  "https://www.mcohio.org/recorder/",
    "Lucas":       "https://www.co.lucas.oh.us/recorder/",
    "Jefferson":   "https://jeffersoncountyclerk.org/",
    "Berks":       "https://recorder.berkscounty.us/",
    "Hillsborough":"https://www.nhdeeds.com/",
    "Fresno":      "https://www.fresnocountyca.gov/Departments/Assessor-Recorder",
    "Bernalillo":  "https://www.bernco.gov/clerk/",
}


class MultiStateScraper(BaseScraper):
    """
    Generic scraper for all non-Texas/NV/AZ/OK/FL target markets.
    Uses the same 3-method pattern: vacant land, tax delinquent, lis pendens.
    """

    SOURCE = "MultiState"

    def __init__(self):
        all_zips = (
            TARGET_ZIPS["fayetteville_nc"]
            + TARGET_ZIPS["gastonia"]
            + TARGET_ZIPS["asheville"]
            + TARGET_ZIPS["clarksville"]
            + TARGET_ZIPS["knoxville"]
            + TARGET_ZIPS["richmond"]
            + TARGET_ZIPS["south_carolina"]
            + TARGET_ZIPS["columbus_ga"]
            + TARGET_ZIPS["bossier_city"]
            + TARGET_ZIPS["shreveport"]
            + TARGET_ZIPS["detroit"]
            + TARGET_ZIPS["indianapolis"]
            + TARGET_ZIPS["columbus_oh"]
            + TARGET_ZIPS["dayton"]
            + TARGET_ZIPS["toledo"]
            + TARGET_ZIPS["louisville"]
            + TARGET_ZIPS["reading"]
            + TARGET_ZIPS["manchester"]
            + TARGET_ZIPS["fresno"]
            + TARGET_ZIPS["albuquerque"]
        )
        super().__init__(name="MultiStateScraper", target_zips=all_zips)

    def _county_for(self, zip_code: str) -> str:
        return ZIP_COUNTY_MAP.get(zip_code, {}).get("county", "")

    def _assessor_url_for(self, zip_code: str) -> str | None:
        county = self._county_for(zip_code)
        return ASSESSOR_URLS.get(county)

    def _clerk_url_for(self, zip_code: str) -> str | None:
        county = self._county_for(zip_code)
        return CLERK_URLS.get(county)

    # ------------------------------------------------------------------ #

    def scrape_vacant_land(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            url = self._assessor_url_for(zip_code)
            if not url:
                self.log.debug("No assessor URL for ZIP %s", zip_code)
                continue
            params = {"zip": zip_code, "proptype": "L", "improvement": "0"}
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
                            parcel_id=p.get("parcel_id", p.get("account", "")),
                            distress_type="vacant_land",
                            source=f"Assessor_{self._county_for(zip_code)}",
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
                        source=f"Assessor_{self._county_for(zip_code)}",
                        raw_data={"row": tds},
                    ))
        return records

    def scrape_tax_delinquent(self) -> list[dict]:
        """
        Most counties publish delinquent tax lists on their treasurer/tax
        collector websites. We make a best-effort GET and parse the result.
        """
        records = []
        for zip_code in self.target_zips:
            county = self._county_for(zip_code)
            state  = ZIP_COUNTY_MAP.get(zip_code, {}).get("state", "")
            url    = self._assessor_url_for(zip_code)
            if not url:
                continue
            resp = self.get(url, params={"zip": zip_code, "delinquent": "1"})
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
                    source=f"{state}_{county}_Treasurer",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            url = self._clerk_url_for(zip_code)
            if not url:
                continue
            params = {"doctype": "LP", "zip": zip_code, "datefrom": "01/01/2022"}
            resp = self.get(url, params=params)
            if not resp:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for tr in (soup.select("table tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                county = self._county_for(zip_code)
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[2] if len(tds) > 2 else "",
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source=f"Clerk_LP_{county}",
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
        self.save_raw(all_records, "multi_state_raw.csv")
        return all_records


if __name__ == "__main__":
    MultiStateScraper().run()
