#!/usr/bin/env python3
"""
Harrison County WV IDX Scraper — CHAIN agent, phases 1+2
Automates grantor/grantee index searches on lookup.harrisoncountywv.com,
captures structured JSONL results, downloads document images, flags
missing images for clerk-call follow-up.

Architecture rule: navigate name-search → results grid → Image link row.
NEVER navigate by book/page — unreliable pre-~1980 (proven broken 3x).

Usage:
    python harrison_idx.py job.json
    python harrison_idx.py --job-id 11-409-19_stewart_trace  # uses embedded example job
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Page,
    BrowserContext,
    TimeoutError as PWTimeout,
)
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "http://lookup.harrisoncountywv.com"
DELAY_MIN = 1.5
DELAY_MAX = 3.0
RELEVANCE_THRESHOLD = 85
MAX_RETRIES = 3

# Default data root — override via DATA_ROOT env var
DATA_ROOT = Path(os.getenv("DATA_ROOT", Path(__file__).parent.parent / "data" / "harrison"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Bot2: 7977783351

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

ALL_INDEX_TYPES = [
    "GRANTOR", "GRANTEE", "CREDITOR", "DEBTOR", "DIRECT",
    "REVERSE", "GROOM", "BRIDE", "DECEASED", "INFANT",
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Instrument:
    instrument_id: str          # e.g. "1977042710540786"
    book: str
    page: str
    book_type: str              # DEED, MISC, etc.
    date: str                   # ISO "1977-04-27"
    doc_type: str
    grantors: list[str] = field(default_factory=list)
    grantees: list[str] = field(default_factory=list)
    legal_desc_snippet: str = ""
    relevance_score: int = 0
    image_status: str = "unknown"   # captured | missing | partial | not_attempted
    image_paths: list[str] = field(default_factory=list)
    transcription_status: str = "pending"
    flags: list[str] = field(default_factory=list)
    source_searches: list[str] = field(default_factory=list)


@dataclass
class JobSummary:
    job_id: str
    total_searches: int = 0
    total_instruments: int = 0
    tract_relevant: int = 0
    images_captured: int = 0
    images_missing: list[dict] = field(default_factory=list)  # {book, page, doc_type}
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def delay() -> None:
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def make_instrument_id(date_str: str, book: str, page: str) -> str:
    """Construct the IDX-style composite key: {YYYYMMDD}{book}{page}."""
    compact = date_str.replace("-", "")
    return f"{compact}{book.zfill(4)}{page.zfill(4)}"


def dedup_key(inst: Instrument) -> str:
    return inst.instrument_id


def score_relevance(text: str, keywords: list[str]) -> int:
    if not text or not keywords:
        return 0
    text_upper = text.upper()
    scores = [fuzz.partial_ratio(kw.upper(), text_upper) for kw in keywords]
    return max(scores) if scores else 0


def load_existing_jsonl(path: Path) -> dict[str, Instrument]:
    existing: dict[str, Instrument] = {}
    if not path.exists():
        return existing
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                inst = Instrument(**d)
                existing[dedup_key(inst)] = inst
            except Exception:
                pass
    return existing


def append_jsonl(path: Path, inst: Instrument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(inst)) + "\n")


# ---------------------------------------------------------------------------
# Selector resolution — try candidates until one is visible
# ---------------------------------------------------------------------------

SELECTOR_CANDIDATES = {
    "name_type_dropdown": [
        "#ctl00_ContentPlaceHolder1_ddlNameType",
        "select[id*='NameType' i]",
        "select[id*='nameType' i]",
        "select[name*='NameType' i]",
    ],
    "last_name": [
        "#ctl00_ContentPlaceHolder1_txtLastName",
        "input[id*='LastName' i]:not([type='hidden'])",
        "input[id*='lastName' i]:not([type='hidden'])",
        "input[id*='lname' i]:not([type='hidden'])",
    ],
    "first_name": [
        "#ctl00_ContentPlaceHolder1_txtFirstName",
        "input[id*='FirstName' i]:not([type='hidden'])",
        "input[id*='firstName' i]:not([type='hidden'])",
        "input[id*='fname' i]:not([type='hidden'])",
    ],
    "middle_name": [
        "#ctl00_ContentPlaceHolder1_txtMiddleName",
        "input[id*='Middle' i]:not([type='hidden'])",
        "input[id*='middle' i]:not([type='hidden'])",
    ],
    "search_btn": [
        "#ctl00_ContentPlaceHolder1_btnSearch",
        "#ctl00_ContentPlaceHolder1_Button1",
        "input[id*='btnSearch' i]",
        "input[value*='Search' i]",
        "button:has-text('Search')",
        "input[type='submit']",
    ],
    "results_grid": [
        "#ctl00_ContentPlaceHolder1_GridView1",
        "table[id*='Grid' i]",
        "table[id*='grid' i]",
        "#gvResults",
        "table.grid",
    ],
    "no_results_msg": [
        "span[id*='lblNoResults' i]",
        "span[id*='NoResults' i]",
        ".no-results",
    ],
}


async def find_selector(page: Page, key: str, timeout: int = 3000) -> Optional[str]:
    for sel in SELECTOR_CANDIDATES.get(key, []):
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=timeout):
                return sel
        except Exception:
            pass
    return None


async def wait_for_any(page: Page, selectors: list[str], timeout: int = 20000) -> Optional[str]:
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        for sel in selectors:
            try:
                if await page.locator(sel).first.is_visible(timeout=500):
                    return sel
            except Exception:
                pass
        await asyncio.sleep(0.3)
    return None


# ---------------------------------------------------------------------------
# Site navigation helpers
# ---------------------------------------------------------------------------

async def goto_search(page: Page) -> None:
    """Navigate to the main search page and wait for it to load."""
    await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    await delay()


async def discover_search_page(page: Page) -> dict:
    """
    Probe the search page to discover actual element IDs.
    Returns a dict mapping role → actual selector.
    """
    discovered = {}
    for key in ["name_type_dropdown", "last_name", "first_name", "search_btn"]:
        sel = await find_selector(page, key)
        if sel:
            discovered[key] = sel
    # Discover index-type checkboxes
    checkboxes = await page.evaluate("""() => {
        const inputs = [...document.querySelectorAll('input[type="checkbox"]')];
        return inputs.map(el => ({
            id: el.id,
            name: el.name,
            value: el.value || '',
            label: el.labels && el.labels[0] ? el.labels[0].innerText.trim() : ''
        }));
    }""")
    discovered["checkboxes"] = checkboxes
    return discovered


async def set_index_checkboxes(page: Page, wanted: list[str], checkboxes: list[dict]) -> None:
    """Check only the requested index types; uncheck everything else."""
    wanted_upper = [w.upper() for w in wanted]
    for cb in checkboxes:
        cb_id = cb.get("id", "")
        cb_val = cb.get("value", "").upper()
        cb_label = cb.get("label", "").upper()
        # Match wanted index types by value or label
        should_check = any(
            idx in cb_val or idx in cb_label or idx in cb_id.upper()
            for idx in wanted_upper
        )
        if not cb_id:
            continue
        try:
            is_checked = await page.is_checked(f"#{cb_id}", timeout=2000)
            if should_check and not is_checked:
                await page.check(f"#{cb_id}")
            elif not should_check and is_checked:
                await page.uncheck(f"#{cb_id}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Results grid parsing
# ---------------------------------------------------------------------------

async def parse_results_grid(page: Page) -> list[dict]:
    """
    Extract all rows from the visible results grid.
    Returns list of raw row dicts with keys:
      index_no, image_control, status, date, doc_type, book, page,
      grantors, grantees, legal_desc
    """
    rows = await page.evaluate("""() => {
        const results = [];

        // Find the main results table — usually the largest table on the page
        const tables = [...document.querySelectorAll('table')];
        if (tables.length === 0) return results;

        // Prefer tables with an id containing 'grid' or 'Grid' or 'result'
        let grid = tables.find(t =>
            /grid|result|index/i.test(t.id || '') ||
            /grid|result|index/i.test(t.className || '')
        ) || tables[tables.length - 1];

        const trs = [...grid.querySelectorAll('tr')];
        let headerParsed = false;
        let colMap = {};  // col name → index

        for (const tr of trs) {
            const cells = [...tr.querySelectorAll('th, td')];
            if (cells.length === 0) continue;

            // Header row detection
            if (!headerParsed && cells.some(c => c.tagName === 'TH' ||
                    /index|image|status|date|type|book|page/i.test(c.innerText || ''))) {
                cells.forEach((c, i) => {
                    const txt = (c.innerText || '').trim().toUpperCase();
                    if (/^INDEX|NO$/.test(txt) || txt === 'INDEX #' || txt === '#') colMap['index_no'] = i;
                    else if (/IMAGE/.test(txt)) colMap['image'] = i;
                    else if (/^FLAG/.test(txt)) colMap['flag'] = i;
                    else if (/^STATUS/.test(txt)) colMap['status'] = i;
                    else if (/^DATE/.test(txt)) colMap['date'] = i;
                    else if (/TYPE|DOC/.test(txt)) colMap['doc_type'] = i;
                    else if (/^BOOK/.test(txt)) colMap['book'] = i;
                    else if (/^PAGE/.test(txt)) colMap['page'] = i;
                });
                headerParsed = true;
                continue;
            }

            if (!headerParsed) continue;

            // Skip rows that look like sub-data (indented / smaller)
            const isDataRow = cells.length >= 4;
            if (!isDataRow) continue;

            const get = (key) => {
                const idx = colMap[key];
                if (idx === undefined) return '';
                const cell = cells[idx];
                return cell ? (cell.innerText || '').trim() : '';
            };

            // Image link — look for an <a> in the image cell
            let imageControl = null;
            let imageHref = null;
            const imgIdx = colMap['image'];
            if (imgIdx !== undefined && cells[imgIdx]) {
                const anchor = cells[imgIdx].querySelector('a');
                if (anchor) {
                    imageHref = anchor.href || '';
                    // Extract control param: /Image.aspx?control=20024
                    const m = imageHref.match(/[?&]control=(\d+)/i);
                    if (m) imageControl = m[1];
                }
            }

            // Try to get index_no from first column or dedicated column
            let indexNo = get('index_no');
            if (!indexNo) indexNo = (cells[0].innerText || '').trim();

            const row = {
                index_no: indexNo,
                image_control: imageControl,
                image_href: imageHref,
                status: get('status'),
                date: get('date'),
                doc_type: get('doc_type'),
                book: get('book'),
                page: get('page'),
                cell_count: cells.length,
                row_text: (tr.innerText || '').trim().replace(/\\s+/g, ' '),
            };

            // Only include rows that look like instruments (have a date or book)
            if (row.date || row.book) {
                results.push(row);
            }
        }

        return results;
    }""")

    return rows


async def parse_sub_rows(page: Page, row_index: int) -> tuple[list[str], list[str], str]:
    """
    Extract grantor/grantee names and legal description from sub-rows
    associated with a result row. Many ASPX deed indexes expand sub-rows
    inline or in a collapsible section below the main row.
    Returns (grantors, grantees, legal_desc_snippet).
    """
    result = await page.evaluate("""(rowIndex) => {
        const grantors = [];
        const grantees = [];
        let legalDesc = '';

        // Strategy 1: look for labeled spans/cells that follow the nth data row
        const allRows = [...document.querySelectorAll('table tr')].filter(tr => {
            const cells = tr.querySelectorAll('td');
            return cells.length > 0;
        });

        // Sub-rows are often in a secondary table nested inside or immediately following
        // the main result row. Look for rows with "GRANTOR" / "GRANTEE" label text.
        allRows.forEach(tr => {
            const text = (tr.innerText || '').toUpperCase();
            const cells = [...tr.querySelectorAll('td')];
            if (cells.length >= 2) {
                const label = cells[0].innerText.trim().toUpperCase();
                const val = cells.slice(1).map(c => c.innerText.trim()).join(' ');
                if (label === 'GRANTOR' || label.startsWith('GRANTOR')) {
                    if (val) grantors.push(val);
                } else if (label === 'GRANTEE' || label.startsWith('GRANTEE')) {
                    if (val) grantees.push(val);
                } else if (/LEGAL|DESCRIPTION|ACREAGE|DISTRICT|^(LOC|PROP)/.test(label)) {
                    if (!legalDesc && val) legalDesc = val;
                }
            }
        });

        // Strategy 2: look for cells whose text contains typical legal-desc patterns
        if (!legalDesc) {
            allRows.forEach(tr => {
                const text = (tr.innerText || '').trim();
                if (/\d+\.\d+\s*(AC|ACRES?)/i.test(text) && !legalDesc) {
                    legalDesc = text.replace(/\\s+/g, ' ').slice(0, 200);
                }
            });
        }

        return { grantors, grantees, legalDesc };
    }""", row_index)

    return result["grantors"], result["grantees"], result["legalDesc"]


async def get_pagination_links(page: Page) -> list[str]:
    """
    Return page-number texts that can be clicked to navigate to additional
    result pages. ASPX GridViews use __doPostBack for pagination.
    """
    links = await page.evaluate("""() => {
        const pagerRows = [...document.querySelectorAll('table tr td[colspan]')];
        const links = [];
        pagerRows.forEach(td => {
            td.querySelectorAll('a').forEach(a => {
                const t = (a.innerText || a.textContent || '').trim();
                if (/^\\d+$/.test(t) || t === '...' || t === 'Next' || t === '>') {
                    links.push({ text: t, href: a.href || '', onclick: a.getAttribute('onclick') || '' });
                }
            });
        });
        return links;
    }""")
    return links


# ---------------------------------------------------------------------------
# Image capture
# ---------------------------------------------------------------------------

async def capture_images(
    page: Page,
    image_control: str,
    image_href: str,
    out_dir: Path,
) -> tuple[str, list[str]]:
    """
    Navigate to Image.aspx, capture all pages of the document as PNGs.
    Returns (status, [image_paths]).
    status: 'captured' | 'missing' | 'partial'
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    target_url = image_href if image_href else f"{BASE_URL}/Image.aspx?control={image_control}"

    try:
        await page.goto(target_url, wait_until="networkidle", timeout=20000)
        await delay()
    except PWTimeout:
        return "missing", []

    page_num = 1
    while True:
        body_text = await page.inner_text("body").catch_value("") if hasattr(page, "catch_value") else ""
        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""

        # Detect "Image not Loaded" condition
        if re.search(r"image\s+not\s+loaded|no\s+image|image\s+unavailable|not\s+available", body_text, re.I):
            return "missing", paths

        # Screenshot the current image page
        img_path = out_dir / f"page_{page_num:03d}.png"
        try:
            await page.screenshot(path=str(img_path), full_page=False)
            paths.append(str(img_path))
        except Exception as e:
            pass  # non-fatal — partial capture

        # Look for a "Next Page" button / link
        next_candidates = [
            "input[value*='Next' i]",
            "a:has-text('Next')",
            "input[id*='btnNext' i]",
            "a[id*='Next' i]",
            "#ctl00_ContentPlaceHolder1_btnNext",
            "input[value='>']",
        ]
        next_el = None
        for sel in next_candidates:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    next_el = el
                    break
            except Exception:
                pass

        if next_el is None:
            break  # no more pages

        # Check if Next is disabled (end of document)
        try:
            disabled = await next_el.get_attribute("disabled")
            if disabled is not None:
                break
            css_class = await next_el.get_attribute("class") or ""
            if "disabled" in css_class.lower():
                break
        except Exception:
            pass

        await next_el.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await delay()
        page_num += 1

        if page_num > 100:  # safety cap
            status = "partial"
            break

    if not paths:
        return "missing", []
    return "captured", paths


# ---------------------------------------------------------------------------
# Core search runner
# ---------------------------------------------------------------------------

class HarrisonSearcher:
    def __init__(self, job: dict):
        self.job = job
        self.job_id = job["job_id"]
        self.keywords = job.get("tract_keywords", [])
        self.out_dir = DATA_ROOT / self.job_id
        self.jsonl_path = self.out_dir / "instruments.jsonl"
        self.summary = JobSummary(job_id=self.job_id)
        self.existing: dict[str, Instrument] = {}
        self._discovered: Optional[dict] = None  # cached selector map

    async def run(self) -> JobSummary:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.existing = load_existing_jsonl(self.jsonl_path)
        print(f"[{self.job_id}] Loaded {len(self.existing)} existing instruments from JSONL")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1400, "height": 900},
            )
            page = await context.new_page()

            # One-time site discovery
            print(f"[{self.job_id}] Loading search page for discovery...")
            await goto_search(page)
            self._discovered = await discover_search_page(page)
            print(f"[{self.job_id}] Discovered selectors: {list(self._discovered.keys())}")
            checkboxes = self._discovered.get("checkboxes", [])
            print(f"[{self.job_id}] Found {len(checkboxes)} index checkboxes")

            searches = self.job.get("searches", [])
            self.summary.total_searches = len(searches)

            for search_spec in searches:
                await self._run_search(page, search_spec, checkboxes)

            await browser.close()

        # Post-process: write runsheet, optional Neo4j, optional Telegram
        self._write_runsheet()

        if self.job.get("neo4j_write", False) and NEO4J_PASSWORD:
            self._write_neo4j()

        if self.job.get("telegram_report", False) and TELEGRAM_BOT_TOKEN:
            await self._send_telegram_report()

        return self.summary

    # ------------------------------------------------------------------
    # Single search execution
    # ------------------------------------------------------------------

    async def _run_search(
        self,
        page: Page,
        spec: dict,
        checkboxes: list[dict],
        resume_after: Optional[str] = None,
    ) -> None:
        name_last = spec.get("name_last", "")
        name_first = spec.get("name_first", "")
        name_type = spec.get("type", "individual")  # individual | company
        indexes = spec.get("indexes", ["GRANTOR"])
        search_label = f"{name_last},{name_first}[{','.join(indexes)}]"

        print(f"[{self.job_id}] Search: {search_label}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await self._fill_search_form(page, name_last, name_first, name_type, indexes, checkboxes)
                instruments = await self._collect_all_pages(page, spec, search_label, resume_after)

                for inst in instruments:
                    key = dedup_key(inst)
                    if key not in self.existing:
                        self.existing[key] = inst
                        append_jsonl(self.jsonl_path, inst)
                        self.summary.total_instruments += 1
                        if inst.relevance_score >= RELEVANCE_THRESHOLD:
                            self.summary.tract_relevant += 1
                        if inst.image_status == "captured":
                            self.summary.images_captured += 1
                        elif inst.image_status == "missing":
                            self.summary.images_missing.append({
                                "book": inst.book,
                                "page": inst.page,
                                "doc_type": inst.doc_type,
                                "instrument_id": inst.instrument_id,
                            })
                    else:
                        # Update image status on existing record if we now have images
                        existing = self.existing[key]
                        if inst.image_status == "captured" and existing.image_status != "captured":
                            existing.image_status = inst.image_status
                            existing.image_paths = inst.image_paths

                print(f"[{self.job_id}] Search {search_label}: {len(instruments)} instruments")
                break  # success

            except PWTimeout as e:
                print(f"[{self.job_id}] Timeout on attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES:
                    # Find last captured index_no for resume
                    last_key = list(self.existing.keys())[-1] if self.existing else None
                    last_inst = self.existing.get(last_key) if last_key else None
                    resume_after = last_inst.instrument_id if last_inst else None
                    print(f"[{self.job_id}] Retrying from resume_after={resume_after}")
                    await goto_search(page)
                    checkboxes = self._discovered.get("checkboxes", [])
                    await delay()
                else:
                    msg = f"Search {search_label} failed after {MAX_RETRIES} attempts: {e}"
                    print(f"[{self.job_id}] ERROR: {msg}")
                    self.summary.errors.append(msg)

            except Exception as e:
                msg = f"Search {search_label} error: {type(e).__name__}: {e}"
                print(f"[{self.job_id}] ERROR: {msg}")
                self.summary.errors.append(msg)
                if attempt < MAX_RETRIES:
                    await goto_search(page)
                    checkboxes = self._discovered.get("checkboxes", [])
                    await delay()
                break

    async def _fill_search_form(
        self,
        page: Page,
        name_last: str,
        name_first: str,
        name_type: str,
        indexes: list[str],
        checkboxes: list[dict],
    ) -> None:
        await goto_search(page)

        # Set Individual/Company dropdown
        dd_sel = self._discovered.get("name_type_dropdown")
        if dd_sel:
            try:
                # Typical option values: "I" = Individual, "C" = Company
                option_val = "C" if name_type == "company" else "I"
                await page.select_option(dd_sel, value=option_val)
            except Exception:
                try:
                    # Some sites use label text
                    option_text = "Company" if name_type == "company" else "Individual"
                    await page.select_option(dd_sel, label=option_text)
                except Exception:
                    pass
            await delay()

        # Fill last name
        ln_sel = self._discovered.get("last_name")
        if ln_sel and name_last:
            await page.click(ln_sel, click_count=3)
            await page.fill(ln_sel, name_last)
        elif name_last:
            # Fallback: try candidates
            for sel in SELECTOR_CANDIDATES["last_name"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=1500):
                        await el.click(click_count=3)
                        await el.fill(name_last)
                        break
                except Exception:
                    pass

        # Fill first name (skip for company or empty)
        fn_sel = self._discovered.get("first_name")
        if fn_sel and name_first and name_type != "company":
            await page.click(fn_sel, click_count=3)
            await page.fill(fn_sel, name_first)
        elif fn_sel:
            # Clear the first name field
            await page.fill(fn_sel, "")

        # Set index type checkboxes
        await set_index_checkboxes(page, indexes, checkboxes)
        await delay()

        # Submit
        submitted = False
        for sel in SELECTOR_CANDIDATES["search_btn"]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    await el.click()
                    submitted = True
                    break
            except Exception:
                pass
        if not submitted:
            await page.keyboard.press("Enter")

        # Wait for results grid or no-results message
        result_sel = await wait_for_any(
            page,
            SELECTOR_CANDIDATES["results_grid"] + SELECTOR_CANDIDATES["no_results_msg"],
            timeout=30000,
        )
        if result_sel is None:
            raise PWTimeout("Results grid did not appear after search submission")

        await delay()

    # ------------------------------------------------------------------
    # Page-by-page result collection
    # ------------------------------------------------------------------

    async def _collect_all_pages(
        self,
        page: Page,
        spec: dict,
        search_label: str,
        resume_after: Optional[str],
    ) -> list[Instrument]:
        instruments: list[Instrument] = []
        page_num = 1
        past_resume = resume_after is None

        while True:
            print(f"[{self.job_id}]   Grid page {page_num}...")
            rows = await parse_results_grid(page)
            print(f"[{self.job_id}]   Found {len(rows)} rows on page {page_num}")

            if not rows:
                break

            for row in rows:
                inst = await self._process_row(page, row, spec, search_label)
                if inst is None:
                    continue

                # Resume logic: skip until we're past the last captured instrument
                if not past_resume:
                    if inst.instrument_id == resume_after:
                        past_resume = True
                    continue

                instruments.append(inst)

            # Pagination
            pager_links = await get_pagination_links(page)
            next_page_text = str(page_num + 1)
            next_link = next((lnk for lnk in pager_links if lnk["text"] == next_page_text), None)

            if not next_link:
                break  # no next page

            # Click page number link (ASPX postback)
            try:
                await page.locator(f"a:has-text('{next_page_text}')").first.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
                await delay()
                page_num += 1
            except Exception as e:
                print(f"[{self.job_id}]   Pagination click failed: {e}")
                break

        return instruments

    async def _process_row(
        self,
        page: Page,
        row: dict,
        spec: dict,
        search_label: str,
    ) -> Optional[Instrument]:
        raw_date = row.get("date", "")
        book = row.get("book", "").strip()
        page_no = row.get("page", "").strip()
        doc_type = row.get("doc_type", "").strip()

        if not book and not raw_date:
            return None

        iso_date = _normalize_date(raw_date)
        instrument_id = row.get("index_no", "").strip()
        if not instrument_id:
            instrument_id = make_instrument_id(iso_date, book, page_no)

        # Grantor/grantee sub-row extraction
        # Re-parse from the full page context for this row
        # (sub-rows are often siblings in the same table)
        grantors, grantees, legal_desc = await self._extract_sub_data(page, row)

        relevance = score_relevance(legal_desc, self.keywords)

        # Determine book_type from doc_type or book prefix
        book_type = _infer_book_type(doc_type, book)

        inst = Instrument(
            instrument_id=instrument_id,
            book=book,
            page=page_no,
            book_type=book_type,
            date=iso_date,
            doc_type=doc_type,
            grantors=grantors,
            grantees=grantees,
            legal_desc_snippet=legal_desc,
            relevance_score=relevance,
            image_status="not_attempted",
            source_searches=[search_label],
        )

        # Image capture
        image_control = row.get("image_control")
        image_href = row.get("image_href")
        if image_control or image_href:
            img_out_dir = self.out_dir / f"{book}_{page_no}"
            # Don't re-capture if already done
            if dedup_key(inst) in self.existing:
                existing_inst = self.existing[dedup_key(inst)]
                inst.image_status = existing_inst.image_status
                inst.image_paths = existing_inst.image_paths
            else:
                print(f"[{self.job_id}]   Capturing images for {book}/{page_no}...")
                status, paths = await capture_images(page, image_control or "", image_href or "", img_out_dir)
                inst.image_status = status
                inst.image_paths = paths
                if status == "missing":
                    print(f"[{self.job_id}]   >> IMAGE MISSING: {book}/{page_no} — clerk call needed")
                elif status == "captured":
                    print(f"[{self.job_id}]   >> Captured {len(paths)} image page(s)")
                # Return to results grid after image capture
                await page.go_back()
                await page.wait_for_load_state("networkidle", timeout=20000)
                await delay()
        else:
            inst.image_status = "missing"

        return inst

    async def _extract_sub_data(self, page: Page, row: dict) -> tuple[list[str], list[str], str]:
        """
        Try to get grantor/grantee/legal-desc from sub-rows.
        Falls back to parsing row_text if sub-rows aren't available.
        """
        grantors, grantees, legal_desc = await parse_sub_rows(page, 0)

        # If sub-row extraction got nothing, parse row_text heuristically
        if not grantors and not grantees and not legal_desc:
            row_text = row.get("row_text", "")
            grantors, grantees, legal_desc = _parse_row_text(row_text)

        return grantors, grantees, legal_desc

    # ------------------------------------------------------------------
    # Output: runsheet CSV
    # ------------------------------------------------------------------

    def _write_runsheet(self) -> None:
        path = self.out_dir / "runsheet.csv"
        instruments = list(self.existing.values())
        # Sort: tract-relevant first (desc relevance), then by date
        instruments.sort(key=lambda i: (-i.relevance_score, i.date))

        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "instrument_id", "date", "doc_type", "book", "page",
                "grantors", "grantees", "legal_desc_snippet",
                "relevance_score", "image_status", "image_paths", "flags",
            ])
            writer.writeheader()
            for inst in instruments:
                writer.writerow({
                    "instrument_id": inst.instrument_id,
                    "date": inst.date,
                    "doc_type": inst.doc_type,
                    "book": inst.book,
                    "page": inst.page,
                    "grantors": " | ".join(inst.grantors),
                    "grantees": " | ".join(inst.grantees),
                    "legal_desc_snippet": inst.legal_desc_snippet,
                    "relevance_score": inst.relevance_score,
                    "image_status": inst.image_status,
                    "image_paths": " | ".join(inst.image_paths),
                    "flags": " | ".join(inst.flags),
                })

        print(f"[{self.job_id}] Runsheet: {path}")
        self.summary.__dict__["runsheet_path"] = str(path)

    # ------------------------------------------------------------------
    # Neo4j VEST handoff
    # ------------------------------------------------------------------

    def _write_neo4j(self) -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError:
            print("[neo4j] neo4j driver not installed — skipping graph writes")
            return

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            for inst in self.existing.values():
                try:
                    session.execute_write(_neo4j_write_instrument, inst, self.job_id)
                except Exception as e:
                    print(f"[neo4j] Write failed for {inst.instrument_id}: {e}")
        driver.close()
        print(f"[neo4j] Wrote {len(self.existing)} instruments to graph")

    # ------------------------------------------------------------------
    # Telegram report
    # ------------------------------------------------------------------

    async def _send_telegram_report(self) -> None:
        missing = self.summary.images_missing
        missing_lines = "\n".join(
            f"  • DB {m['book']}/{m['page']}  — {m['doc_type']}"
            for m in missing[:20]
        )
        msg = (
            f"CHAIN job {self.job_id} complete\n"
            f"Searches: {self.summary.total_searches} | "
            f"Instruments: {self.summary.total_instruments} | "
            f"Tract-relevant: {self.summary.tract_relevant}\n"
            f"Images captured: {self.summary.images_captured} | "
            f"MISSING IMAGES (clerk call needed): {len(missing)}\n"
        )
        if missing:
            msg += missing_lines + "\n"
        if self.summary.errors:
            msg += f"Errors: {len(self.summary.errors)}\n"
        runsheet = self.summary.__dict__.get("runsheet_path", "")
        if runsheet:
            msg += f"Runsheet: {runsheet}\n"

        try:
            import urllib.request
            import urllib.parse
            url = (
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                f"?chat_id={TELEGRAM_CHAT_ID}"
                f"&text={urllib.parse.quote(msg)}"
            )
            urllib.request.urlopen(url, timeout=10)
            print(f"[telegram] Report sent to {TELEGRAM_CHAT_ID}")
        except Exception as e:
            print(f"[telegram] Failed to send report: {e}")


# ---------------------------------------------------------------------------
# Neo4j transaction function (module-level for neo4j driver)
# ---------------------------------------------------------------------------

def _neo4j_write_instrument(tx, inst: Instrument, tract_candidate: str) -> None:
    for grantor in inst.grantors:
        tx.run("MERGE (p:Party {name: $name})", name=grantor)
    for grantee in inst.grantees:
        tx.run("MERGE (p:Party {name: $name})", name=grantee)

    tx.run("""
        MERGE (i:Instrument {id: $id})
        SET i.book       = $book,
            i.page       = $page,
            i.date       = date($date),
            i.type       = $type,
            i.county     = 'harrison_wv',
            i.legal_desc = $legal_desc,
            i.tract_candidate = $tract,
            i.image_status = $image_status
    """,
        id=inst.instrument_id,
        book=inst.book,
        page=inst.page,
        date=inst.date if inst.date else "1900-01-01",
        type=inst.doc_type,
        legal_desc=inst.legal_desc_snippet,
        tract=tract_candidate,
        image_status=inst.image_status,
    )

    for grantor in inst.grantors:
        tx.run("""
            MATCH (p:Party {name: $name}), (i:Instrument {id: $id})
            MERGE (p)-[:GRANTOR_ON]->(i)
        """, name=grantor, id=inst.instrument_id)

    for grantee in inst.grantees:
        tx.run("""
            MATCH (p:Party {name: $name}), (i:Instrument {id: $id})
            MERGE (i)-[:CONVEYS_TO]->(p)
        """, name=grantee, id=inst.instrument_id)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _normalize_date(raw: str) -> str:
    """Convert MM/DD/YYYY or MM-DD-YYYY to YYYY-MM-DD. Returns '' on failure."""
    raw = raw.strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$", raw)
    if m:
        mo, day, yr = m.group(1), m.group(2), m.group(3)
        if len(yr) == 2:
            yr = ("19" if int(yr) > 25 else "20") + yr
        return f"{yr}-{int(mo):02d}-{int(day):02d}"
    # Try to extract 4-digit year
    m2 = re.search(r"\b(\d{4})\b", raw)
    if m2:
        return m2.group(1) + "-01-01"
    return ""


def _infer_book_type(doc_type: str, book: str) -> str:
    dt_upper = doc_type.upper()
    bk_upper = book.upper()
    if "DEED" in dt_upper or bk_upper.startswith("DB") or bk_upper.startswith("D"):
        return "DEED"
    if "MISC" in dt_upper or bk_upper.startswith("MB") or bk_upper.startswith("M"):
        return "MISC"
    if "LIEN" in dt_upper or "MORT" in dt_upper or bk_upper.startswith("LB"):
        return "LIEN"
    return "DEED"  # default for Harrison County


def _parse_row_text(row_text: str) -> tuple[list[str], list[str], str]:
    """
    Heuristically parse grantor/grantee/legal from a raw row text blob
    when structured sub-rows aren't available.
    """
    grantors: list[str] = []
    grantees: list[str] = []
    legal_desc = ""

    lines = [l.strip() for l in row_text.split("\n") if l.strip()]
    mode = None
    for line in lines:
        ul = line.upper()
        if "GRANTOR" in ul:
            mode = "grantor"
            name = re.sub(r"GRANTOR[S]?[:\s]*", "", line, flags=re.I).strip()
            if name:
                grantors.append(name)
        elif "GRANTEE" in ul:
            mode = "grantee"
            name = re.sub(r"GRANTEE[S]?[:\s]*", "", line, flags=re.I).strip()
            if name:
                grantees.append(name)
        elif re.search(r"\d+\.?\d*\s*(AC|ACRES?|DIST|DISTRICT)", ul):
            legal_desc = line[:200]
            mode = None
        elif mode == "grantor" and len(line) > 2 and len(line) < 80:
            grantors.append(line)
        elif mode == "grantee" and len(line) > 2 and len(line) < 80:
            grantees.append(line)

    return grantors, grantees, legal_desc


# ---------------------------------------------------------------------------
# Example job (parcel 11-409-19 research — known-answer validation target)
# ---------------------------------------------------------------------------

EXAMPLE_JOB = {
    "job_id": "11-409-19_stewart_trace",
    "county": "harrison_wv",
    "neo4j_write": False,
    "searches": [
        {"name_last": "Stewart",      "name_first": "William", "type": "individual", "indexes": ["GRANTOR"]},
        {"name_last": "Stewart",      "name_first": "W",       "type": "individual", "indexes": ["GRANTOR"]},
        {"name_last": "Evans",        "name_first": "Betty",   "type": "individual", "indexes": ["GRANTOR", "GRANTEE"]},
        {"name_last": "Shuttleworth", "name_first": "",        "type": "individual", "indexes": ["GRANTOR", "GRANTEE"]},
        {"name_last": "Elk Valley Land Company", "name_first": "", "type": "company",    "indexes": ["GRANTOR", "GRANTEE"]},
        {"name_last": "Atlantic Richfield",      "name_first": "", "type": "company",    "indexes": ["GRANTOR", "GRANTEE"]},
        {"name_last": "Simcoe",                  "name_first": "", "type": "company",    "indexes": ["GRANTOR", "GRANTEE"]},
        {"name_last": "Lawson",       "name_first": "",        "type": "individual", "indexes": ["GRANTOR", "GRANTEE", "DECEASED"]},
    ],
    "tract_keywords": ["GNATTY", "ELK DIST", "ELK-OUTSIDE", "ELK OUTSIDE", "STOUT RUN", "ROMINES"],
    "telegram_report": True,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--job-id" and len(sys.argv) >= 3 and sys.argv[2] == EXAMPLE_JOB["job_id"]:
        job = EXAMPLE_JOB
    elif arg.endswith(".json"):
        with open(arg) as f:
            job = json.load(f)
    elif arg == "--example":
        job = EXAMPLE_JOB
    else:
        print(f"Unknown argument: {arg}")
        print("Usage: python harrison_idx.py job.json")
        print("       python harrison_idx.py --example")
        sys.exit(1)

    searcher = HarrisonSearcher(job)
    summary = asyncio.run(searcher.run())

    print("\n" + "=" * 60)
    print(f"Job complete: {summary.job_id}")
    print(f"  Searches:        {summary.total_searches}")
    print(f"  Instruments:     {summary.total_instruments}")
    print(f"  Tract-relevant:  {summary.tract_relevant}")
    print(f"  Images captured: {summary.images_captured}")
    print(f"  Missing images:  {len(summary.images_missing)}")
    if summary.images_missing:
        print("  Clerk call list (304) 624-8611:")
        for m in summary.images_missing:
            print(f"    DB {m['book']}/{m['page']}  — {m['doc_type']}")
    if summary.errors:
        print(f"  Errors ({len(summary.errors)}):")
        for e in summary.errors[:5]:
            print(f"    {e}")
    print("=" * 60)


if __name__ == "__main__":
    main()
