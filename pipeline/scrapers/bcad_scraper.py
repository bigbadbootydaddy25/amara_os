"""
Bexar County Appraisal District (BCAD) scraper — San Antonio, TX.

Target ZIPs: 78207, 78210, 78228, 78237

Sources:
  - BCAD property search: https://www.bcad.org/clientdb/PropertySearch.aspx
  - BCAD data: https://www.bcad.org/Portals/
  - Bexar County Clerk: https://www.bexar.org/1228/Official-Public-Records
  - Bexar County Tax: https://www.bcad.org/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.bcad_scraper
"""

import io
import zipfile

import pandas as pd
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

BCAD_SEARCH_URL = "https://www.bcad.org/clientdb/PropertySearch.aspx"
BCAD_DATA_URL   = "https://www.bcad.org/Portals/"
BEXAR_CLERK_URL = "https://www.bexar.org/1228/Official-Public-Records"
BEXAR_TAX_URL   = "https://www.bexar.org/1107/Property-Tax"


class BCADScraper(BaseScraper):
    """Bexar County Appraisal District scraper."""

    SOURCE = "BCAD"

    def __init__(self):
        super().__init__(
            name="BCADScraper",
            target_zips=TARGET_ZIPS["san_antonio"],
        )
        self._bulk_df: pd.DataFrame | None = None

    def _download_bulk(self) -> pd.DataFrame | None:
        """
        BCAD provides property export files. Try known download patterns.
        If live download fails, returns None — scrapers fall back to search.
        """
        for year in [2025, 2024]:
            url = f"https://www.bcad.org/Portals/0/PropertyDataExport/PROP{year}.zip"
            r = self.get(url)
            if not r:
                continue
            try:
                zf = zipfile.ZipFile(io.BytesIO(r.content))
                csv_name = next(
                    (n for n in zf.namelist() if n.lower().endswith(".csv")),
                    zf.namelist()[0] if zf.namelist() else None,
                )
                if not csv_name:
                    continue
                with zf.open(csv_name) as f:
                    df = pd.read_csv(f, dtype=str, low_memory=False, encoding="latin-1")
                df.columns = [c.strip().lower() for c in df.columns]
                zip_col = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
                if zip_col:
                    df = df[df[zip_col].str.strip().isin(set(self.target_zips))].copy()
                self.log.info("BCAD bulk: %d records", len(df))
                return df
            except Exception as exc:
                self.log.warning("BCAD bulk error year %d: %s", year, exc)
        return None

    def _ensure_bulk(self) -> pd.DataFrame | None:
        if self._bulk_df is None:
            self._bulk_df = self._download_bulk()
        return self._bulk_df

    def _col(self, row, candidates, default=""):
        for c in candidates:
            v = row.get(c)
            if v and str(v).strip() not in ("", "nan", "None"):
                return str(v).strip()
        return default

    def scrape_vacant_land(self) -> list[dict]:
        df = self._ensure_bulk()
        records = []
        if df is not None:
            imprv_col = next((c for c in df.columns if "imprv" in c), None)
            if imprv_col:
                df[imprv_col] = pd.to_numeric(df[imprv_col], errors="coerce").fillna(0)
                vacant_df = df[df[imprv_col] == 0]
                for _, row in vacant_df.iterrows():
                    records.append(self.canonical_record(
                        owner_name=self._col(row, ["owner_name", "own1"]),
                        address=self._col(row, ["situs_addr", "address", "addr"]),
                        zip_code=self._col(row, ["situs_zip", "zip", "addr_zip"]).strip(),
                        parcel_id=self._col(row, ["prop_id", "account", "acct"]),
                        distress_type="vacant_land",
                        source=f"{self.SOURCE}_bulk",
                        raw_data=row.to_dict(),
                    ))
        else:
            # Fallback: BCAD public property search per ZIP
            for zip_code in self.target_zips:
                params = {
                    "__EVENTTARGET": "",
                    "SearchType": "A",
                    "ZipCode": zip_code,
                    "LandOnly": "1",
                }
                soup = self.soup(BCAD_SEARCH_URL, params=params)
                if not soup:
                    continue
                for tr in (soup.select("table.SearchResults tr") or [])[1:]:
                    tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(tds) < 3:
                        continue
                    records.append(self.canonical_record(
                        owner_name=tds[1] if len(tds) > 1 else "",
                        address=tds[0],
                        zip_code=zip_code,
                        distress_type="vacant_land",
                        source=f"{self.SOURCE}_search",
                        raw_data={"row": tds},
                    ))
        return records

    def scrape_absentee_owners(self) -> list[dict]:
        df = self._ensure_bulk()
        if df is None:
            return []
        addr_zip = next((c for c in df.columns if "zip" in c and "mail" not in c and "situs" not in c), None)
        mail_zip = next((c for c in df.columns if "mail" in c and "zip" in c), None)
        if not addr_zip or not mail_zip:
            return []
        ab = df[df[addr_zip].str.strip() != df[mail_zip].str.strip()]
        records = []
        for _, row in ab.iterrows():
            records.append(self.canonical_record(
                owner_name=self._col(row, ["owner_name", "own1"]),
                address=self._col(row, ["situs_addr", "address"]),
                zip_code=self._col(row, [addr_zip]).strip(),
                parcel_id=self._col(row, ["prop_id", "account", "acct"]),
                distress_type="absentee_owner",
                source=f"{self.SOURCE}_bulk",
                raw_data={"mail_zip": row.get(mail_zip, "")},
            ))
        return records

    def scrape_tax_delinquent(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(BEXAR_TAX_URL, params={"zip": zip_code, "delinquent": "1"})
            if not soup:
                continue
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
                    source="Bexar_Tax",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(BEXAR_CLERK_URL, params={"doctype": "LP", "zip": zip_code})
            if not soup:
                continue
            for tr in (soup.select("table tr") or [])[1:]:
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                records.append(self.canonical_record(
                    owner_name=tds[1] if len(tds) > 1 else "",
                    address=tds[0],
                    zip_code=zip_code,
                    distress_type="preforeclosure",
                    filing_date=tds[0] if tds else "",
                    source="Bexar_Clerk_LP",
                    raw_data={"row": tds},
                ))
        return records

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
        self.save_raw(all_records, "bcad_raw.csv")
        return all_records


if __name__ == "__main__":
    BCADScraper().run()
