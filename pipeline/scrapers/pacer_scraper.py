"""
PACER bankruptcy scraper — pulls Chapter 7/13 filings for target ZIPs.

PACER (Public Access to Court Electronic Records) is free up to $30/quarter.
This scraper uses the PACER public search API to find bankruptcy filings
where the debtor address matches a target ZIP code.

PACER endpoints:
  - Case search: https://pcl.uscourts.gov/pcl/pages/search/find.jsf
  - Court finder: https://www.uscourts.gov/federal-court-finder/search

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.pacer_scraper
"""

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import ALL_ZIPS, ZIP_COUNTY_MAP

# PACER Case Locator — free public search
PACER_CASE_LOCATOR = "https://pcl.uscourts.gov/pcl/pages/search/find.jsf"
PACER_SEARCH_API   = "https://pcl.uscourts.gov/pcl/api/search"

# Maps states to their PACER bankruptcy court districts
STATE_TO_COURT = {
    "TX": ["txnb", "txeb", "txsb", "txwb"],  # TX Northern/Eastern/Southern/Western
    "NV": ["nvb"],
    "AZ": ["azb"],
    "NM": ["nmb"],
    "OK": ["oknb", "okeb", "okwb"],
    "FL": ["flmb", "flnb", "flsb"],
    "NC": ["nceb", "ncmb", "ncwb"],
    "TN": ["tneb", "tnmb", "tnwb"],
    "VA": ["vaeb", "vawb"],
    "SC": ["scb"],
    "GA": ["ganb", "gamb", "gasb"],
    "LA": ["laeb", "lamb", "lawb"],
    "MI": ["mieb", "miwb"],
    "IN": ["innb", "insb"],
    "OH": ["ohnb", "ohsb"],
    "KY": ["kyeb", "kywb"],
    "PA": ["paeb", "pamb", "pawb"],
    "NH": ["nhb"],
    "CA": ["cacb", "caeb", "canb", "casb"],
}


class PACERScraper(BaseScraper):
    """
    PACER Case Locator scraper for bankruptcy filings (Chapter 7 & 13).
    Filters debtors whose ZIP matches our target list.
    """

    SOURCE = "PACER"

    def __init__(self):
        super().__init__(
            name="PACERScraper",
            target_zips=sorted(ALL_ZIPS),
        )

    def _state_for_zip(self, zip_code: str) -> str:
        return ZIP_COUNTY_MAP.get(zip_code, {}).get("state", "")

    def _courts_for_zip(self, zip_code: str) -> list[str]:
        state = self._state_for_zip(zip_code)
        return STATE_TO_COURT.get(state, [])

    def _search_pacer(self, zip_code: str, court: str, chapter: str) -> list[dict]:
        """
        Search PACER Case Locator for bankruptcy filings in a specific
        court district and chapter matching the given ZIP.
        """
        params = {
            "zip":        zip_code,
            "court":      court,
            "chapter":    chapter,
            "dateRange":  "1",
            "dateFrom":   "01/01/2022",
            "dateTo":     "",
            "resultCount": 50,
        }
        resp = self.get(PACER_CASE_LOCATOR, params=params)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        records = []

        # PACER renders results in a table with case number, name, chapter, date
        result_table = soup.find("table", {"id": "search-results"}) or soup.find("table")
        if not result_table:
            return []

        for tr in result_table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 4:
                continue
            # Typical columns: [Case Number, Debtor Name, Chapter, Filed Date, Court]
            case_number = tds[0] if tds else ""
            debtor_name = tds[1] if len(tds) > 1 else ""
            chapter_num = tds[2] if len(tds) > 2 else ""
            filed_date  = tds[3] if len(tds) > 3 else ""

            records.append(self.canonical_record(
                owner_name=debtor_name,
                address="",   # Address not always visible in search results
                zip_code=zip_code,
                distress_type="bankruptcy",
                filing_date=filed_date,
                source=f"{self.SOURCE}_{court}_Ch{chapter}",
                raw_data={
                    "case_number": case_number,
                    "chapter":     chapter_num,
                    "court":       court,
                },
            ))
        return records

    def scrape(self) -> list[dict]:
        all_records = []
        seen_zips = set()

        for zip_code in self.target_zips:
            if zip_code in seen_zips:
                continue
            seen_zips.add(zip_code)

            courts = self._courts_for_zip(zip_code)
            if not courts:
                self.log.debug("No PACER courts found for ZIP %s", zip_code)
                continue

            for court in courts[:2]:  # limit to 2 courts per ZIP to control volume
                for chapter in ["7", "13"]:
                    try:
                        recs = self._search_pacer(zip_code, court, chapter)
                        all_records.extend(recs)
                        if recs:
                            self.log.info(
                                "PACER ZIP %s court %s Ch%s: %d cases",
                                zip_code, court, chapter, len(recs),
                            )
                    except Exception as exc:
                        self.log.error(
                            "PACER ZIP %s court %s Ch%s: %s", zip_code, court, chapter, exc
                        )

        self.save_raw(all_records, "pacer_bankruptcy_raw.csv")
        return all_records


if __name__ == "__main__":
    PACERScraper().run()
