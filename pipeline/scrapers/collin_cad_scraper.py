"""
Collin Central Appraisal District (Collin CAD) scraper.

Target ZIPs: 75069, 75071, 75078 (McKinney / Prosper)

Sources:
  - Collin CAD search: https://www.collincad.org/propertysearch
  - Collin CAD bulk: https://www.collincad.org/data-downloads
  - Collin County Clerk: https://www.collincountytx.gov/county_clerk/

Run standalone:
    cd /home/user/amara_os/pipeline
    python -m scrapers.collin_cad_scraper
"""

import io
import zipfile

import pandas as pd
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from config import TARGET_ZIPS

COLLIN_CAD_SEARCH = "https://www.collincad.org/propertysearch"
COLLIN_CAD_BULK   = "https://www.collincad.org/data-downloads"
COLLIN_CLERK_URL  = "https://www.collincountytx.gov/county_clerk/pages/realproperty.aspx"
COLLIN_TAX_URL    = "https://tax.collincountytx.gov/"


class CollinCADScraper(BaseScraper):
    """Collin County Appraisal District scraper."""

    SOURCE = "CollinCAD"

    def __init__(self):
        super().__init__(
            name="CollinCADScraper",
            target_zips=TARGET_ZIPS["collin_county"],
        )
        self._bulk_df: pd.DataFrame | None = None

    def _download_bulk(self) -> pd.DataFrame | None:
        resp = self.get(COLLIN_CAD_BULK)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        zip_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if a["href"].lower().endswith(".zip") or a["href"].lower().endswith(".csv")
        ]
        if not zip_links:
            return None
        url = zip_links[0]
        if not url.startswith("http"):
            url = f"https://www.collincad.org{url}"
        r = self.get(url)
        if not r:
            return None
        try:
            if url.lower().endswith(".zip"):
                zf = zipfile.ZipFile(io.BytesIO(r.content))
                csv_name = next(
                    (n for n in zf.namelist() if n.lower().endswith(".csv")), None
                )
                if not csv_name:
                    return None
                with zf.open(csv_name) as f:
                    df = pd.read_csv(f, dtype=str, low_memory=False, encoding="latin-1")
            else:
                df = pd.read_csv(io.BytesIO(r.content), dtype=str, low_memory=False, encoding="latin-1")
            df.columns = [c.strip().lower() for c in df.columns]
            zip_col = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
            if zip_col:
                df = df[df[zip_col].str.strip().isin(set(self.target_zips))].copy()
            self.log.info("Collin CAD bulk: %d records", len(df))
            return df
        except Exception as exc:
            self.log.error("Collin CAD bulk parse: %s", exc)
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
        if df is None:
            return records
        imprv_col = next((c for c in df.columns if "imprv" in c or "improvement" in c), None)
        if not imprv_col:
            return records
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
        return records

    def scrape_absentee_owners(self) -> list[dict]:
        df = self._ensure_bulk()
        if df is None:
            return []
        addr_zip = next((c for c in df.columns if "zip" in c and "mail" not in c), None)
        mail_zip = next((c for c in df.columns if "mail" in c and "zip" in c), None)
        if not addr_zip or not mail_zip:
            return []
        ab = df[df[addr_zip].str.strip() != df[mail_zip].str.strip()]
        return [
            self.canonical_record(
                owner_name=self._col(row, ["owner_name", "own1"]),
                address=self._col(row, ["situs_addr", "address"]),
                zip_code=self._col(row, [addr_zip]).strip(),
                parcel_id=self._col(row, ["prop_id", "account", "acct"]),
                distress_type="absentee_owner",
                source=f"{self.SOURCE}_bulk",
                raw_data={"mail_zip": row.get(mail_zip, "")},
            )
            for _, row in ab.iterrows()
        ]

    def scrape_tax_delinquent(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(COLLIN_TAX_URL, params={"zip": zip_code})
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
                    source="Collin_Tax",
                    raw_data={"row": tds},
                ))
        return records

    def scrape_lis_pendens(self) -> list[dict]:
        records = []
        for zip_code in self.target_zips:
            soup = self.soup(COLLIN_CLERK_URL, params={"doctype": "LP", "zip": zip_code})
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
                    source="Collin_Clerk_LP",
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
        self.save_raw(all_records, "collin_cad_raw.csv")
        return all_records


if __name__ == "__main__":
    CollinCADScraper().run()
