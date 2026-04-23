"""
Travis Central Appraisal District (TCAD) scraper — Austin, TX.

Target ZIPs: 78721, 78724, 78744, 78745

Sources:
  - TCAD property search: https://www.traviscad.org/property-search/
  - TCAD bulk data: https://www.traviscad.org/data-downloads/
  - Travis County Clerk: https://www.traviscountytx.gov/county-clerk/
  - Travis County Tax Office: https://www.tax.co.travis.tx.us/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.tcad_scraper
"""

import io
import zipfile

import pandas as pd
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

TCAD_SEARCH_URL  = "https://www.traviscad.org/property-search/"
TCAD_BULK_URL    = "https://www.traviscad.org/data-downloads/"
TRAVIS_CLERK_URL = "https://www.traviscountytx.gov/county-clerk/real-property-records"
TRAVIS_TAX_URL   = "https://www.tax.co.travis.tx.us/Appraisal/"


class TCADScraper(BaseScraper):
    """Travis Central Appraisal District scraper."""

    SOURCE = "TCAD"

    def __init__(self):
        super().__init__(
            name="TCADScraper",
            target_zips=TARGET_ZIPS["austin"],
        )
        self._bulk_df: pd.DataFrame | None = None

    def _download_bulk(self) -> pd.DataFrame | None:
        resp = self.get(TCAD_BULK_URL)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        zip_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if a["href"].lower().endswith(".zip")
        ]
        if not zip_links:
            self.log.warning("No TCAD bulk zip found")
            return None
        url = zip_links[0] if zip_links[0].startswith("http") else f"https://www.traviscad.org{zip_links[0]}"
        r = self.get(url)
        if not r:
            return None
        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            csv_name = next(
                (n for n in zf.namelist() if n.lower().endswith(".csv")),
                zf.namelist()[0] if zf.namelist() else None,
            )
            if not csv_name:
                return None
            with zf.open(csv_name) as f:
                df = pd.read_csv(f, dtype=str, low_memory=False, encoding="latin-1")
            df.columns = [c.strip().lower() for c in df.columns]
            zip_col = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
            if zip_col:
                df = df[df[zip_col].str.strip().isin(set(self.target_zips))].copy()
            self.log.info("TCAD bulk: %d records", len(df))
            return df
        except Exception as exc:
            self.log.error("TCAD bulk parse: %s", exc)
            return None

    def _ensure_bulk(self) -> pd.DataFrame | None:
        if self._bulk_df is None:
            self._bulk_df = self._download_bulk()
        return self._bulk_df

    def scrape_vacant_land(self) -> list[dict]:
        df = self._ensure_bulk()
        records = []
        if df is not None:
            imprv_col = next((c for c in df.columns if "imprv" in c or "improvement" in c), None)
            if imprv_col:
                df[imprv_col] = pd.to_numeric(df[imprv_col], errors="coerce").fillna(0)
                vacant_df = df[df[imprv_col] == 0]
                addr_col  = next((c for c in df.columns if "addr" in c and "mail" not in c), "")
                owner_col = next((c for c in df.columns if "owner" in c or "own" in c), "")
                zip_col   = next((c for c in df.columns if "zip" in c and "mail" not in c), "")
                for _, row in vacant_df.iterrows():
                    records.append(self.canonical_record(
                        owner_name=str(row.get(owner_col, "")),
                        address=str(row.get(addr_col, "")),
                        zip_code=str(row.get(zip_col, "")).strip(),
                        parcel_id=str(row.get("account", row.get("acct", ""))),
                        distress_type="vacant_land",
                        source=f"{self.SOURCE}_bulk",
                        raw_data=row.to_dict(),
                    ))
        return records

    def scrape_absentee_owners(self) -> list[dict]:
        df = self._ensure_bulk()
        if df is None:
            return []
        addr_zip = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
        mail_zip = next((c for c in df.columns if "mail" in c and "zip" in c), None)
        if not addr_zip or not mail_zip:
            return []
        absentee = df[df[addr_zip].str.strip() != df[mail_zip].str.strip()]
        records = []
        owner_col = next((c for c in df.columns if "owner" in c or "own" in c), "")
        addr_col  = next((c for c in df.columns if "addr" in c and "mail" not in c), "")
        for _, row in absentee.iterrows():
            records.append(self.canonical_record(
                owner_name=str(row.get(owner_col, "")),
                address=str(row.get(addr_col, "")),
                zip_code=str(row.get(addr_zip, "")).strip(),
                parcel_id=str(row.get("account", row.get("acct", ""))),
                distress_type="absentee_owner",
                source=f"{self.SOURCE}_bulk",
                raw_data={"mail_zip": row.get(mail_zip, "")},
            ))
        return records

    def scrape_tax_delinquent(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(TRAVIS_TAX_URL, params={"zip": zip_code})
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
                    source="Travis_Tax_Office",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(TRAVIS_CLERK_URL, params={"doctype": "LP", "zip": zip_code})
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
                    source="Travis_County_Clerk_LP",
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
        self.save_raw(all_records, "tcad_raw.csv")
        return all_records


if __name__ == "__main__":
    TCADScraper().run()
