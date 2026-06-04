"""
HTTP scraping core for AMARA DEED crew.
Uses requests + BeautifulSoup only — NOT Playwright.
Handles cookies, redirects, form submissions, and retries.
"""

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import SCRAPER_HEADERS, SCRAPER_TIMEOUT

log = logging.getLogger(__name__)


class DeedScraper:
    """
    Stateful scraper with session, cookie jar, and retry logic.
    One instance per agent run to share session/cookies across requests.
    """

    def __init__(self, agent_name: str):
        self.agent = agent_name
        self.session = requests.Session()
        self.session.headers.update(SCRAPER_HEADERS)
        self._last_url: str = ""

    def get(
        self,
        url: str,
        params: dict = None,
        retries: int = 3,
        delay: float = 2.0,
    ) -> Optional[BeautifulSoup]:
        for attempt in range(1, retries + 1):
            try:
                r = self.session.get(url, params=params, timeout=SCRAPER_TIMEOUT,
                                     allow_redirects=True)
                self._last_url = r.url
                log.debug("[%s] GET %s → HTTP %s", self.agent, url, r.status_code)
                if r.status_code == 200:
                    return BeautifulSoup(r.content, "lxml")
                if r.status_code == 403:
                    log.error("[%s] 403 Forbidden — %s (host not in allowlist or "
                              "IP blocked; must run from Mac)", self.agent, url)
                    return None
                log.warning("[%s] HTTP %s for %s (attempt %d/%d)",
                            self.agent, r.status_code, url, attempt, retries)
            except requests.exceptions.ConnectionError as e:
                log.error("[%s] Connection refused — %s: %s", self.agent, url, e)
                return None
            except requests.exceptions.Timeout:
                log.warning("[%s] Timeout %s (attempt %d/%d)", self.agent, url, attempt, retries)
            except Exception as e:
                log.error("[%s] GET error %s: %s", self.agent, url, e)
                return None
            if attempt < retries:
                time.sleep(delay * attempt)
        log.error("[%s] All %d attempts failed for %s", self.agent, retries, url)
        return None

    def post(
        self,
        url: str,
        data: dict = None,
        json: dict = None,
        retries: int = 3,
        delay: float = 2.0,
    ) -> Optional[BeautifulSoup]:
        for attempt in range(1, retries + 1):
            try:
                r = self.session.post(url, data=data, json=json,
                                      timeout=SCRAPER_TIMEOUT, allow_redirects=True)
                self._last_url = r.url
                log.debug("[%s] POST %s → HTTP %s", self.agent, url, r.status_code)
                if r.status_code == 200:
                    return BeautifulSoup(r.content, "lxml")
                if r.status_code == 403:
                    log.error("[%s] 403 Forbidden — %s", self.agent, url)
                    return None
                log.warning("[%s] HTTP %s for POST %s (attempt %d/%d)",
                            self.agent, r.status_code, url, attempt, retries)
            except requests.exceptions.ConnectionError as e:
                log.error("[%s] Connection refused POST %s: %s", self.agent, url, e)
                return None
            except Exception as e:
                log.error("[%s] POST error %s: %s", self.agent, url, e)
                return None
            if attempt < retries:
                time.sleep(delay * attempt)
        log.error("[%s] All %d POST attempts failed for %s", self.agent, retries, url)
        return None

    def extract_viewstate(self, soup: BeautifulSoup) -> dict:
        """Extract ASP.NET ViewState and EventValidation fields for form posts."""
        fields = {}
        for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
                     "__EVENTTARGET", "__EVENTARGUMENT"]:
            tag = soup.find("input", {"name": name})
            if tag:
                fields[name] = tag.get("value", "")
        return fields

    def table_to_rows(self, soup: BeautifulSoup, table_id: str = None,
                      class_: str = None) -> list[dict]:
        """Parse an HTML table into a list of dicts keyed by header text."""
        if table_id:
            table = soup.find("table", {"id": table_id})
        elif class_:
            table = soup.find("table", class_=class_)
        else:
            table = soup.find("table")
        if not table:
            return []
        rows = table.find_all("tr")
        if not rows:
            return []
        headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        result = []
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if cells:
                result.append(dict(zip(headers, cells)))
        return result
