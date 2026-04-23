"""
Dallas Central Appraisal District (DCAD) scraper.

Target ZIPs: 75210, 75216, 75217, 75232, 75215 (Dallas County)

Sources:
  - DCAD property search: https://www.dcad.org/property/
  - DCAD bulk data: https://www.dcad.org/data/
  - Dallas County Clerk: https://www.dallascounty.org/departments/countyclerk/
  - Dallas County Tax Assessor: https://www.dallascad.org/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.dcad_scraper
"""

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

DCAD_SEARCH_URL  = "https://www.dcad.org/property/search"
DCAD_BULK_URL    = "https://www.dcad.org/data/"
DCAD_PARCEL_API  = "https://www.dcad.org/api/property/search"

# Dallas County Clerk document search
DALLAS_CLERK_URL = "https://countyclerk.dallascounty.org/departments/real-property/"

# Dallas County Tax Assessor delinquent list
DALLAS_TAX_URL   = "https://www.dallascad.org/DelinquentList.aspx"


class DCaDScraper(BaseScraper):
    """Dallas Central Appraisal District scraper."""

    SOURCE = "DCAD"

    def __init__(self):
        super().__init__(
            name="DCADScraper",
            target_zips=TARGET_ZIPS["dallas"],
        )
        self._bulk_df: pd.DataFrame | None = None

    # ------------------------------------------------------------------ #
    #  Bulk data                                                           #
    # ------------------------------------------------------------------ #

    def _download_bulk(self) -> pd.DataFrame | None:
        """Download DCAD bulk property export. DCAD publishes CSV/ZIP files."""
        resp = self.get(DCAD_BULK_URL)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        # Find the most recent data file link
        zip_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if a["href"].endswith(".zip") and ("prop" in a["href"].lower() or "acct" in a["href"].lower())
        ]
        if not zip_links:
            self.log.warning("No DCAD bulk zip found on %s", DCAD_BULK_URL)
            return None

        url = zip_links[0] if zip_links[0].startswith("http") else f"https://www.dcad.org{zip_links[0]}"
        self.log.info("Downloading DCAD bulk data: %s", url)
        r = self.get(url)
        if not r:
            return None

        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            csv_name = next(
                (n for n in zf.namelist() if n.lower().endswith(".csv") and "prop" in n.lower()),
                zf.namelist()[0] if zf.namelist() else None,
            )
            if not csv_name:
                return None
            with zf.open(csv_name) as f:
                df = pd.read_csv(f, dtype=str, low_memory=False, encoding="latin-1")
            df.columns = [c.strip().lower() for c in df.columns]
            # Filter to target ZIPs
            zip_col = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
            if zip_col:
                df = df[df[zip_col].str.strip().isin(set(self.target_zips))].copy()
            self.log.info("DCAD bulk: %d records in target ZIPs", len(df))
            return df
        except Exception as exc:
            self.log.error("DCAD bulk parse error: %s", exc)
            return None

    def _ensure_bulk(self) -> pd.DataFrame | None:
        if self._bulk_df is None:
            self._bulk_df = self._download_bulk()
        return self._bulk_df

    # ------------------------------------------------------------------ #
    #  DCAD API search (per ZIP)                                           #
    # ------------------------------------------------------------------ #

    def _api_search(self, zip_code: str, page: int = 1) -> list[dict]:
        """
        DCAD exposes a JSON API for property search.
        Returns raw property objects.
        """
        params = {
            "searchtype": "A",
            "zip": zip_code,
            "page": page,
            "pagesize": 200,
        }
        resp = self.get(DCAD_PARCEL_API, params=params)
        if not resp:
            return []
        try:
            data = resp.json()
            return data.get("properties") or data.get("results") or (data if isinstance(data, list) else [])
        except ValueError:
            return []

    # ------------------------------------------------------------------ #
    #  Vacant / infill land                                                #
    # ------------------------------------------------------------------ #

    def scrape_vacant_land(self) -> list[dict]:
        df = self._ensure_bulk()
        records = []

        if df is not None:
            imprv_col = next((c for c in df.columns if "imprv" in c or "improvement" in c), None)
            lu_col    = next((c for c in df.columns if "land_use" in c or "luse" in c or "use_code" in c), None)

            if imprv_col:
                df[imprv_col] = pd.to_numeric(df[imprv_col], errors="coerce").fillna(0)
                vacant_df = df[df[imprv_col] == 0]
                if lu_col:
                    vacant_df = vacant_df[
                        vacant_df[lu_col].str.upper().str.contains("VAC|UNIMPROVE|LAND|IDLE|A1|B1", na=False)
                    ]
                addr_col  = next((c for c in df.columns if "addr" in c and "mail" not in c), "")
                owner_col = next((c for c in df.columns if "owner" in c or "own1" in c), "")
                zip_col   = next((c for c in df.columns if "zip" in c and "mail" not in c), "")

                for _, row in vacant_df.iterrows():
                    records.append(self.canonical_record(
                        owner_name=str(row.get(owner_col, "")),
                        address=str(row.get(addr_col, "")),
                        zip_code=str(row.get(zip_col, "")).strip(),
                        parcel_id=str(row.get("acct", row.get("account", ""))),
                        distress_type="vacant_land",
                        source=f"{self.SOURCE}_bulk",
                        raw_data=row.to_dict(),
                    ))
            return records

        # Fallback: API search per ZIP
        for zip_code in self.target_zips:
            props = self._api_search(zip_code)
            for p in props:
                if str(p.get("improvement_value", "1")) in ("0", "0.0", ""):
                    records.append(self.canonical_record(
                        owner_name=p.get("owner_name", ""),
                        address=p.get("address", ""),
                        zip_code=zip_code,
                        parcel_id=p.get("account_number", ""),
                        distress_type="vacant_land",
                        source=f"{self.SOURCE}_api",
                        raw_data=p,
                    ))
        return records

    # ------------------------------------------------------------------ #
    #  Absentee owners                                                     #
    # ------------------------------------------------------------------ #

    def scrape_absentee_owners(self) -> list[dict]:
        df = self._ensure_bulk()
        if df is None:
            return []
        addr_zip_col = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
        mail_zip_col = next((c for c in df.columns if "mail" in c and "zip" in c), None)
        if not addr_zip_col or not mail_zip_col:
            return []
        absentee = df[df[addr_zip_col].str.strip() != df[mail_zip_col].str.strip()]
        records = []
        owner_col = next((c for c in df.columns if "owner" in c or "own1" in c), "")
        addr_col  = next((c for c in df.columns if "addr" in c and "mail" not in c), "")
        for _, row in absentee.iterrows():
            records.append(self.canonical_record(
                owner_name=str(row.get(owner_col, "")),
                address=str(row.get(addr_col, "")),
                zip_code=str(row.get(addr_zip_col, "")).strip(),
                parcel_id=str(row.get("acct", row.get("account", ""))),
                distress_type="absentee_owner",
                source=f"{self.SOURCE}_bulk",
                raw_data={"mail_zip": row.get(mail_zip_col, "")},
            ))
        return records

    # ------------------------------------------------------------------ #
    #  Tax delinquent                                                      #
    # ------------------------------------------------------------------ #

    def scrape_tax_delinquent(self) -> list[dict]:
        """
        Dallas County Tax Office delinquent list.
        https://www.dallascad.org/DelinquentList.aspx
        Also try: https://www.dallascounty.org/departments/tax/
        """
        records = []
        for zip_code in self.target_zips:
            params = {"zip": zip_code, "type": "delinquent"}
            soup = self.soup(DALLAS_TAX_URL, params=params)
            if not soup:
                continue
            table = soup.find("table", {"class": "GridView"}) or soup.find("table")
            if not table:
                continue
            for tr in table.find_all("tr")[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[0],
                    zip_code=zip_code,
                    distress_type="tax_delinquent",
                    amount_owed=tds[2] if len(tds) > 2 else "",
                    source="Dallas_Tax_Office",
                    raw_data={"row": tds},
                ))
        return records

    # ------------------------------------------------------------------ #
    #  Lis pendens                                                         #
    # ------------------------------------------------------------------ #

    def scrape_lis_pendens(self) -> list[dict]:
        """Dallas County Clerk lis pendens search."""
        records = []
        for zip_code in self.target_zips:
            params = {
                "doctype": "LP",
                "zip": zip_code,
                "datefrom": "01/01/2022",
            }
            soup = self.soup(DALLAS_CLERK_URL, params=params)
            if not soup:
                continue
            for tr in (soup.select("table tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 3:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[2] if len(tds) > 2 else "",
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source="Dallas_County_Clerk_LP",
                    raw_data={"row": tds},
                ))
        return records

    # ------------------------------------------------------------------ #
    #  Main entry                                                          #
    # ------------------------------------------------------------------ #

    def scrape(self) -> list[dict]:
        all_records = []
        for label, fn in [
            ("vacant_land",     self.scrape_vacant_land),
            ("absentee_owners", self.scrape_absentee_owners),
            ("tax_delinquent",  self.scrape_tax_delinquent),
            ("lis_pendens",     self.scrape_lis_pendens),
        ]:
            try:
                recs = fn()
                all_records.extend(recs)
                self.log.info("[%s] %d records", label, len(recs))
            except Exception as exc:
                self.log.error("[%s] failed: %s", label, exc, exc_info=True)
        self.save_raw(all_records, "dcad_raw.csv")
        return all_records


if __name__ == "__main__":
    DCaDScraper().run()
