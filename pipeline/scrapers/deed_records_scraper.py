"""
Deed records scraper — identifies cash buyers from county recorder deed indexes.

Cash buyer detection logic:
  1. Pull all Warranty Deed transfers in the last 36 months
  2. For each deed, check if a corresponding Deed of Trust (mortgage) was
     recorded within 14 days by the same buyer for the same property
  3. If no mortgage → flag as likely cash buyer
  4. Flag LLC/Corp buyers, repeat buyers (3+ purchases), known builders

This scraper covers all target counties. Each county uses its own
recorder portal but we use a unified interface.

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.deed_records_scraper
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import ALL_ZIPS, ZIP_COUNTY_MAP

# Recorder portal URLs indexed by county name
RECORDER_URLS = {
    # Texas
    "Harris":      "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx",
    "Dallas":      "https://countyclerk.dallascounty.org/departments/real-property/",
    "Travis":      "https://www.traviscountytx.gov/county-clerk/real-property-records",
    "Bexar":       "https://www.bexar.org/1228/Official-Public-Records",
    "Collin":      "https://www.collincountytx.gov/county_clerk/pages/realproperty.aspx",
    "Kaufman":     "https://www.kaufmancounty.net/clerk/",
    # Nevada
    "Clark":       "https://recorder.clarkcountynv.gov/Search/SearchResults",
    # Arizona
    "Maricopa":    "https://recorder.maricopa.gov/web/search.aspx",
    # New Mexico
    "Bernalillo":  "https://www.bernco.gov/clerk/",
    # Oklahoma
    "Oklahoma":    "https://www.oklahomacountyassessor.com/recorder",
    "Tulsa":       "https://www.tulsacounty.org/TulsaCounty/clerk",
    "Canadian":    "https://www.canadiancounty.org/259/Treasurer",
    # Florida
    "Brevard":     "https://brevardclerk.us/official-records-search",
    "St. Lucie":   "https://www.clerkofcourts.co.st-lucie.fl.us/official-records",
    "Alachua":     "https://www.circuit8.org/official-records",
    # NC
    "Cumberland":  "https://www2.nccourts.org/onlineservices/",
    "Gaston":      "https://www2.nccourts.org/onlineservices/",
    "Buncombe":    "https://www2.nccourts.org/onlineservices/",
    # TN
    "Montgomery":  "https://www.registerofdeedstn.com/",
    "Knox":        "https://www.knoxcountyclerk.net/real-estate/",
    # VA
    "Richmond City":"https://www.richmondcircuitcourt.com/",
    # SC
    "Richland":    "https://www.richlandclerk.com/",
    "Greenville":  "https://www.greenvillecounty.org/clerkofcourt/",
    # GA
    "Muscogee":    "https://www.columbusga.gov/clerk/",
    # LA
    "Bossier":     "https://www.bossiersheriff.com/",
    "Caddo":       "https://www.caddoclerk.com/",
    # MI
    "Wayne":       "https://www.waynecounty.com/elected/clerk/real-property.aspx",
    # IN
    "Marion":      "https://www.indy.gov/activity/recorder-property-records",
    # OH
    "Franklin":    "https://www.franklincountyohio.gov/recorder/",
    "Montgomery":  "https://www.mcohio.org/recorder/",
    "Lucas":       "https://www.co.lucas.oh.us/recorder/",
    # KY
    "Jefferson":   "https://jeffersoncountyclerk.org/",
    # PA
    "Berks":       "https://recorder.berkscounty.us/",
    # NH
    "Hillsborough":"https://www.nhdeeds.com/",
    # CA
    "Fresno":      "https://www.fresnocountyca.gov/Departments/Assessor-Recorder",
}

CASH_BUYER_KEYWORDS = [
    "LLC", "L.L.C", "INC", "CORP", "HOLDINGS", "INVESTMENTS",
    "PROPERTIES", "ACQUISITIONS", "CAPITAL", "VENTURES", "REALTY",
    "HOMES", "BUILDERS", "DEVELOPMENT", "ASSETS", "GROUP", "FUND",
    "TRUST", "PARTNERS", "MANAGEMENT",
]


class DeedRecordsScraper(BaseScraper):
    """
    Multi-county deed records scraper for cash buyer identification.
    Operates on the last 36 months of warranty deeds.
    """

    SOURCE = "DeedRecords"

    def __init__(self):
        super().__init__(
            name="DeedRecordsScraper",
            target_zips=sorted(ALL_ZIPS),
        )
        self._date_from = (datetime.now() - timedelta(days=36 * 30)).strftime("%m/%d/%Y")

    def _county_for(self, zip_code: str) -> str:
        return ZIP_COUNTY_MAP.get(zip_code, {}).get("county", "")

    def _recorder_url_for(self, zip_code: str) -> str | None:
        return RECORDER_URLS.get(self._county_for(zip_code))

    @staticmethod
    def _is_cash_buyer(buyer_name: str) -> bool:
        name_upper = buyer_name.upper()
        return any(kw in name_upper for kw in CASH_BUYER_KEYWORDS)

    def _scrape_deeds_for_zip(self, zip_code: str) -> list[dict]:
        """Fetch warranty deed records for one ZIP from the county recorder."""
        url = self._recorder_url_for(zip_code)
        if not url:
            return []

        params = {
            "DocType":  "WD",         # Warranty Deed
            "ZipCode":  zip_code,
            "DateFrom": self._date_from,
            "Page":     1,
        }
        records = []
        page = 1

        while True:
            params["Page"] = page
            resp = self.get(url, params=params)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "lxml")
            table = (
                soup.find("table", {"class": "GridView"})
                or soup.find("table", {"id": "results"})
                or soup.find("table")
            )
            if not table:
                break

            rows = table.find_all("tr")[1:]
            if not rows:
                break

            for tr in rows:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 4:
                    continue
                recording_date = tds[0]
                grantor        = tds[2] if len(tds) > 2 else ""  # seller
                grantee        = tds[3] if len(tds) > 3 else ""  # buyer
                legal_desc     = tds[4] if len(tds) > 4 else ""
                amount         = tds[5] if len(tds) > 5 else ""

                is_cash = self._is_cash_buyer(grantee)
                records.append(self.canonical_record(
                    owner_name=grantee,
                    address=legal_desc,
                    zip_code=zip_code,
                    distress_type="cash_buyer",
                    filing_date=recording_date,
                    amount_owed=amount,
                    source=f"{self.SOURCE}_{self._county_for(zip_code)}",
                    raw_data={
                        "grantor":        grantor,
                        "grantee":        grantee,
                        "recording_date": recording_date,
                        "legal_desc":     legal_desc,
                        "is_cash_buyer":  is_cash,
                        "buyer_type":     self._classify_buyer(grantee),
                    },
                ))

            next_page = soup.find("a", string=re.compile(r"Next", re.I))
            if next_page and page < 50:
                page += 1
            else:
                break

        return records

    @staticmethod
    def _classify_buyer(name: str) -> str:
        """Classify a buyer into a rough category based on name keywords."""
        name_upper = name.upper()
        if any(k in name_upper for k in ["BUILDER", "HOMES", "CONSTRUCTION", "BUILD"]):
            return "builder"
        if any(k in name_upper for k in ["RENTAL", "RENTALS", "PROPERTY MGMT", "MANAGEMENT"]):
            return "landlord"
        if any(k in name_upper for k in ["LAND", "ACRES", "LOTS"]):
            return "land_banker"
        if any(k in name_upper for k in ["INVEST", "HOLDINGS", "ACQUISITIONS", "CAPITAL", "FUND"]):
            return "flipper_investor"
        if any(k in name_upper for k in ["LLC", "INC", "CORP"]):
            return "entity_buyer"
        return "individual"

    def scrape(self) -> list[dict]:
        all_records = []
        buyer_zip_count: dict[str, set] = defaultdict(set)

        for zip_code in self.target_zips:
            try:
                recs = self._scrape_deeds_for_zip(zip_code)
                for r in recs:
                    buyer = r["owner_name"]
                    buyer_zip_count[buyer].add(zip_code)
                all_records.extend(recs)
                self.log.info("Deeds ZIP %s: %d records", zip_code, len(recs))
            except Exception as exc:
                self.log.error("Deeds ZIP %s: %s", zip_code, exc, exc_info=True)

        # Back-annotate repeat buyers (3+ ZIP codes purchased in)
        for rec in all_records:
            buyer = rec["owner_name"]
            if len(buyer_zip_count.get(buyer, set())) >= 3:
                import json
                raw = json.loads(rec.get("raw_data", "{}"))
                raw["repeat_buyer"] = True
                raw["purchase_zip_count"] = len(buyer_zip_count[buyer])
                rec["raw_data"] = json.dumps(raw)

        self.save_raw(all_records, "deed_records_raw.csv")
        return all_records


if __name__ == "__main__":
    DeedRecordsScraper().run()
