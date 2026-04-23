"""
Zillow public listing scraper — pulls properties with 90+ days on market.

Zillow exposes listing data through their public search endpoint.
No login required. Scrapes the public search results page per ZIP.

Strategy:
  1. Build a Zillow search URL for each target ZIP
  2. Use the internal JSON endpoint that the search page calls
  3. Filter for DOM >= 90
  4. Capture: address, ZIP, list price, original price, DOM, beds/baths/sqft

Zillow rate-limits aggressively — we use randomized 2-3s delays and
rotate User-Agent headers. If a ZIP returns 403/429, back off and skip.

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.zillow_scraper
"""

import json
import re
import time

from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper
from config import ALL_ZIPS, ZIP_COUNTY_MAP

ZILLOW_SEARCH_URL  = "https://www.zillow.com/search/GetSearchPageState.htm"
ZILLOW_BASE_URL    = "https://www.zillow.com/"

MIN_DOM = 90


class ZillowScraper(BaseScraper):
    """Scrapes Zillow public listings for 90+ DOM properties across all target ZIPs."""

    SOURCE = "Zillow"

    def __init__(self, target_zips: list[str] = None):
        super().__init__(
            name="ZillowScraper",
            target_zips=target_zips or sorted(ALL_ZIPS),
        )
        # Zillow needs specific headers to avoid bot detection
        self.session.headers.update({
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.zillow.com/",
        })

    def _build_search_payload(self, zip_code: str, page: int = 1) -> dict:
        """
        Build the search state payload for Zillow's internal search API.
        This mirrors what the browser sends when filtering by ZIP + DOM.
        """
        return {
            "searchQueryState": {
                "pagination": {"currentPage": page},
                "isMapVisible": False,
                "filterState": {
                    "sort":    {"value": "days"},
                    "doz":     {"min": MIN_DOM},           # days on Zillow
                    "price":   {"min": 0, "max": 999999999},
                    "mf":      {"value": True},            # multi-family
                    "land":    {"value": True},
                    "apa":     {"value": True},            # apartments
                    "ah":      {"value": True},
                    "singleStory": {"value": False},
                },
                "usersSearchTerm": zip_code,
                "mapBounds": {},
            },
            "wants": {
                "cat1": ["listResults"],
                "cat2": ["total"],
            },
            "requestId": 2,
        }

    def _scrape_zip(self, zip_code: str) -> list[dict]:
        """Scrape all 90+ DOM listings for a single ZIP code."""
        records = []
        page = 1

        while True:
            params = {
                "searchQueryState": json.dumps(
                    self._build_search_payload(zip_code, page)["searchQueryState"]
                ),
                "wants": '{"cat1":["listResults"],"cat2":["total"]}',
                "requestId": page,
            }

            resp = self.get(ZILLOW_SEARCH_URL, params=params)
            if not resp:
                self.log.warning("Zillow: no response for ZIP %s page %d", zip_code, page)
                break

            # Zillow may return 403 if rate-limited — back off and continue
            if resp.status_code == 403:
                self.log.warning("Zillow 403 on ZIP %s — rate limited, skipping", zip_code)
                time.sleep(10)
                break

            try:
                data = resp.json()
            except ValueError:
                # Try parsing from the HTML source (public listing data embedded in <script>)
                data = self._extract_json_from_html(resp.text)
                if not data:
                    break

            cat1 = data.get("cat1", {})
            search_results = cat1.get("searchResults", {})
            listings = search_results.get("listResults") or []

            if not listings:
                break

            for listing in listings:
                dom = int(listing.get("daysOnZillow", 0) or listing.get("brokerIdeas", {}).get("daysOnMarket", 0) or 0)
                if dom < MIN_DOM:
                    continue

                # Parse address components
                address_parts = listing.get("addressStreet", "")
                city_val  = listing.get("addressCity", "")
                state_val = listing.get("addressState", "")
                zip_val   = listing.get("addressZipcode", zip_code)

                records.append(self.canonical_record(
                    owner_name="",  # Zillow doesn't expose owner
                    address=address_parts,
                    city=city_val,
                    state=state_val,
                    zip_code=zip_val,
                    distress_type="dom90",
                    source=self.SOURCE,
                    raw_data={
                        "list_price":     listing.get("price"),
                        "original_price": listing.get("zestimate"),
                        "dom":            dom,
                        "beds":           listing.get("beds"),
                        "baths":          listing.get("baths"),
                        "sqft":           listing.get("area"),
                        "prop_type":      listing.get("hdpData", {}).get("homeInfo", {}).get("homeType", ""),
                        "zpid":           listing.get("zpid"),
                        "url":            f"https://www.zillow.com{listing.get('detailUrl', '')}",
                    },
                ))

            # Check for additional pages
            total_pages = cat1.get("searchList", {}).get("totalPages", 1)
            if page >= total_pages or page >= 20:  # cap at 20 pages
                break
            page += 1

        self.log.info("Zillow ZIP %s: %d listings (DOM >= %d)", zip_code, len(records), MIN_DOM)
        return records

    @staticmethod
    def _extract_json_from_html(html: str) -> dict:
        """
        Fallback: extract the embedded listing JSON from a Zillow HTML page.
        Zillow embeds search results in a <script id="__NEXT_DATA__"> tag.
        """
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script:
            try:
                return json.loads(script.string)
            except (ValueError, TypeError):
                pass
        # Try extracting from window.globalSearch
        match = re.search(r"window\.__INITIAL_DATA__\s*=\s*({.+?});\s*</script>", html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except ValueError:
                pass
        return {}

    def scrape(self) -> list[dict]:
        all_records = []
        for zip_code in self.target_zips:
            try:
                recs = self._scrape_zip(zip_code)
                all_records.extend(recs)
            except Exception as exc:
                self.log.error("Zillow ZIP %s failed: %s", zip_code, exc, exc_info=True)
        self.save_raw(all_records, "zillow_dom90_raw.csv")
        return all_records


if __name__ == "__main__":
    ZillowScraper().run()
