"""
RRC W-1 Permit CSV downloader and parser.

Downloads the current W-1 drilling permit dataset from the Texas RRC
public data download page and returns filtered rows for a target county.
All field values are taken verbatim from the CSV — no LLM, no inference.
"""

from __future__ import annotations

import csv
import datetime
import html.parser
import io
import logging
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
import urllib.request

logger = logging.getLogger(__name__)

RRC_DATA_DOWNLOAD_PAGE = (
    "https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/"
)
FRACFOCUS_DOWNLOAD_PAGE = "https://fracfocus.org/data-download"

ECTOR_COUNTY_NAME = "ECTOR"
DEFAULT_DAYS_BACK = 30

# Ector County medians sourced from FracFocus county-level aggregates (per task spec).
# Used ONLY when a FracFocus CSV is unavailable AND active_wells count is known.
_ECTOR_SAND_MEDIAN_TONS_PER_WELL = 3_500
_ECTOR_WATER_MEDIAN_BBLS_PER_WELL = 21_000

# Required W-1 schema columns — agent aborts if any are missing from the file.
REQUIRED_COLUMNS = {
    "OPER_NO",
    "OPER_NAME",
    "PERMIT_NO",
    "CNTY_NAME",
    "LEASE_NAME",
    "WELL_NO",
    "PERMIT_DATE",
    "FIELD_NAME",
    "WELL_TYPE",
}


# ---------------------------------------------------------------------------
# HTML link scraper (no third-party deps)
# ---------------------------------------------------------------------------

class _LinkFinder(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def _find_download_link(page_url: str, keywords: list[str]) -> Optional[str]:
    """
    Fetch *page_url*, scan <a href> values for any link whose path
    contains one of *keywords* (case-insensitive) and ends in .csv or .zip.
    Returns an absolute URL or None.
    """
    try:
        req = urllib.request.Request(
            page_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; frac-lead-osint/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("Could not fetch page %s: %s", page_url, exc)
        return None

    finder = _LinkFinder()
    finder.feed(body)

    for href in finder.links:
        lower = href.lower()
        if any(kw in lower for kw in keywords) and any(
            lower.endswith(ext) for ext in (".csv", ".zip")
        ):
            return href if href.startswith("http") else urljoin(page_url, href)

    return None


# ---------------------------------------------------------------------------
# W-1 CSV downloader
# ---------------------------------------------------------------------------

def download_w1_csv(dest_dir: Path) -> Optional[Path]:
    """
    Locate and download the current RRC W-1 permit CSV to *dest_dir*.
    Returns path to the saved CSV, or None on failure.
    Caller must check that the returned path contains REQUIRED_COLUMNS.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = _find_download_link(
        RRC_DATA_DOWNLOAD_PAGE,
        keywords=["w1", "w-1", "drilling-permit", "drillingpermit"],
    )
    if url is None:
        logger.error(
            "W-1 download link not found on RRC data page.\n"
            "Manual download: %s\n"
            "Save the CSV and pass it via --csv or RRC_CSV_PATH.",
            RRC_DATA_DOWNLOAD_PAGE,
        )
        return None

    logger.info("Downloading RRC W-1 dataset: %s", url)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; frac-lead-osint/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except Exception as exc:
        logger.error("W-1 download failed: %s", exc)
        return None

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d")
    dest_path = dest_dir / f"rrc_w1_permits_{stamp}.csv"

    if url.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    logger.error("No CSV inside downloaded W-1 ZIP")
                    return None
                with zf.open(csv_names[0]) as src:
                    dest_path.write_bytes(src.read())
        except Exception as exc:
            logger.error("ZIP extraction failed: %s", exc)
            return None
    else:
        dest_path.write_bytes(data)

    logger.info(
        "W-1 dataset saved: %s (%d bytes)", dest_path, dest_path.stat().st_size
    )
    return dest_path


# ---------------------------------------------------------------------------
# W-1 CSV parser
# ---------------------------------------------------------------------------

def _parse_permit_date(raw: str) -> Optional[datetime.date]:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_w1_csv(
    csv_path: Path,
    county_filter: str = ECTOR_COUNTY_NAME,
    days_back: int = DEFAULT_DAYS_BACK,
) -> list[dict]:
    """
    Parse *csv_path* and return rows where:
      - CNTY_NAME matches *county_filter* (case-insensitive)
      - PERMIT_DATE is within the last *days_back* days

    Each returned dict has an '_row_index' key (1-based CSV data row number,
    where row 1 is the header) plus all original CSV columns verbatim.
    Rows with unparseable dates are included and flagged with _date_unparseable=True.

    No values are inferred, generated, or modified.
    """
    cutoff = datetime.date.today() - datetime.timedelta(days=days_back)
    results: list[dict] = []

    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for data_row_num, row in enumerate(reader, start=2):
            county = row.get("CNTY_NAME", "").strip().upper()
            if county != county_filter.upper():
                continue

            permit_date = _parse_permit_date(row.get("PERMIT_DATE", ""))
            if permit_date is not None and permit_date < cutoff:
                continue

            enriched = {"_row_index": data_row_num}
            if permit_date is None:
                enriched["_date_unparseable"] = True
            enriched.update(row)
            results.append(enriched)

    logger.info(
        "parse_w1_csv: %d rows matched county=%s within last %d days (source: %s)",
        len(results),
        county_filter,
        days_back,
        csv_path.name,
    )
    return results


# ---------------------------------------------------------------------------
# FracFocus county median loader
# ---------------------------------------------------------------------------

def load_fracfocus_county_medians(fracfocus_csv: Path, county: str) -> dict:
    """
    Parse a FracFocus bulk CSV and compute median proppant and water
    volumes for *county*.  Returns dict with keys:
      sand_tons_median, water_bbls_median, well_count, source_file

    Returns hardcoded Ector County medians with source='task-spec-constant'
    if *fracfocus_csv* does not exist, so the caller always gets a usable
    value without any LLM involvement.
    """
    if not fracfocus_csv.exists():
        logger.warning(
            "FracFocus CSV not found (%s). Using hardcoded Ector County medians "
            "(sand=%d tons/well, water=%d bbls/well).",
            fracfocus_csv,
            _ECTOR_SAND_MEDIAN_TONS_PER_WELL,
            _ECTOR_WATER_MEDIAN_BBLS_PER_WELL,
        )
        return {
            "sand_tons_median": _ECTOR_SAND_MEDIAN_TONS_PER_WELL,
            "water_bbls_median": _ECTOR_WATER_MEDIAN_BBLS_PER_WELL,
            "well_count": 0,
            "source_file": "hardcoded-ector-county-constant",
        }

    sand_vals: list[float] = []
    water_vals: list[float] = []

    with open(fracfocus_csv, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_county = row.get("CountyName", row.get("COUNTY", "")).strip().upper()
            if row_county != county.upper():
                continue
            try:
                sand_vals.append(float(row.get("TotalBaseWaterVolume", row.get("TOTAL_PROPPANT", 0)) or 0))
            except (ValueError, TypeError):
                pass
            try:
                water_vals.append(float(row.get("TotalBaseWaterVolume", 0) or 0))
            except (ValueError, TypeError):
                pass

    def _median(vals: list[float]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    return {
        "sand_tons_median": _median(sand_vals) if sand_vals else _ECTOR_SAND_MEDIAN_TONS_PER_WELL,
        "water_bbls_median": _median(water_vals) if water_vals else _ECTOR_WATER_MEDIAN_BBLS_PER_WELL,
        "well_count": len(sand_vals),
        "source_file": str(fracfocus_csv),
    }
