#!/usr/bin/env python3
"""
browser_county_scraper.py

Playwright-based county property portal scraper.
Re-verifies BLOCKED positions from sec_county_agent_results.csv using
real browser automation instead of requests.

Usage:
    python3 scrapers/browser_county_scraper.py
    python3 scrapers/browser_county_scraper.py --visible
"""

import argparse
import asyncio
import csv
import io
import os
import re
import sys
import textwrap
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Optional
import urllib.request

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
REPORTS_DIR = PIPELINE_DIR / "reports"
SCREENSHOTS_DIR = PIPELINE_DIR / "logs" / "screenshots"
RESULTS_CSV = REPORTS_DIR / "browser_verification_results.csv"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = "8436321336:AAE93YWFbr-fn90RddWGbpPJPpg9rKtoHcY"
TELEGRAM_CHAT_ID = "1335704674"

# ---------------------------------------------------------------------------
# Browser config
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
PAGE_TIMEOUT_MS = 30_000


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class VerificationResult:
    company_name: str
    county: str
    state: str
    source_type: str          # CAD / PROPERTY_APPRAISER / TAX_DELINQUENT_PDF
    result_status: str        # VERIFIED_PARCEL / POSSIBLE_MATCH / NO_MATCH / BLOCKED_CAPTCHA / ERROR
    parcel_numbers_found: str = ""
    addresses_found: str = ""
    evidence_summary: str = ""
    search_url: str = ""


CSV_COLUMNS = [f.name for f in fields(VerificationResult)]

# ---------------------------------------------------------------------------
# Target matrix
# ---------------------------------------------------------------------------
TARGETS = [
    # (company_display, search_variants, county, state, source_type, scraper_fn_name)
    ("BEAZER HOMES USA INC", ["BEAZER HOMES", "BEAZER"],
     "Harris", "TX", "CAD", "scrape_harris_tx"),
    ("LGI Homes Inc",        ["LGI HOMES", "LGI"],
     "Harris", "TX", "CAD", "scrape_harris_tx"),
    ("LENNAR CORP",          ["LENNAR"],
     "Harris", "TX", "CAD", "scrape_harris_tx"),
    ("Meritage Homes CORP",  ["MERITAGE HOMES", "MERITAGE"],
     "Harris", "TX", "CAD", "scrape_harris_tx"),
    ("Century Communities Inc", ["CENTURY COMMUNITIES"],
     "Harris", "TX", "CAD", "scrape_harris_tx"),

    ("BEAZER HOMES USA INC", ["BEAZER HOMES", "BEAZER"],
     "Brevard", "FL", "PROPERTY_APPRAISER", "scrape_brevard_fl"),
    ("LGI Homes Inc",        ["LGI HOMES", "LGI"],
     "Brevard", "FL", "PROPERTY_APPRAISER", "scrape_brevard_fl"),
    ("LENNAR CORP",          ["LENNAR"],
     "Brevard", "FL", "PROPERTY_APPRAISER", "scrape_brevard_fl"),
    ("Meritage Homes CORP",  ["MERITAGE HOMES", "MERITAGE"],
     "Brevard", "FL", "PROPERTY_APPRAISER", "scrape_brevard_fl"),
    ("Century Communities Inc", ["CENTURY COMMUNITIES"],
     "Brevard", "FL", "PROPERTY_APPRAISER", "scrape_brevard_fl"),

    ("BEAZER HOMES USA INC", ["BEAZER HOMES", "BEAZER"],
     "St Lucie", "FL", "PROPERTY_APPRAISER", "scrape_stlucie_fl"),
    ("LGI Homes Inc",        ["LGI HOMES", "LGI"],
     "St Lucie", "FL", "PROPERTY_APPRAISER", "scrape_stlucie_fl"),
    ("LENNAR CORP",          ["LENNAR"],
     "St Lucie", "FL", "PROPERTY_APPRAISER", "scrape_stlucie_fl"),
    ("Meritage Homes CORP",  ["MERITAGE HOMES", "MERITAGE"],
     "St Lucie", "FL", "PROPERTY_APPRAISER", "scrape_stlucie_fl"),
    ("Century Communities Inc", ["CENTURY COMMUNITIES"],
     "St Lucie", "FL", "PROPERTY_APPRAISER", "scrape_stlucie_fl"),

    # Clark County NV — single PDF covers all companies
    ("LGI Homes Inc",        ["LGI HOMES", "LGI"],
     "Clark", "NV", "TAX_DELINQUENT_PDF", "scrape_clark_nv_pdf"),
    ("BEAZER HOMES USA INC", ["BEAZER HOMES", "BEAZER"],
     "Clark", "NV", "TAX_DELINQUENT_PDF", "scrape_clark_nv_pdf"),
    ("LENNAR CORP",          ["LENNAR"],
     "Clark", "NV", "TAX_DELINQUENT_PDF", "scrape_clark_nv_pdf"),
    ("Meritage Homes CORP",  ["MERITAGE HOMES", "MERITAGE"],
     "Clark", "NV", "TAX_DELINQUENT_PDF", "scrape_clark_nv_pdf"),
    ("Century Communities Inc", ["CENTURY COMMUNITIES"],
     "Clark", "NV", "TAX_DELINQUENT_PDF", "scrape_clark_nv_pdf"),

    ("BEAZER HOMES USA INC", ["BEAZER HOMES", "BEAZER"],
     "Dallas", "TX", "CAD", "scrape_dallas_tx"),
    ("LGI Homes Inc",        ["LGI HOMES", "LGI"],
     "Dallas", "TX", "CAD", "scrape_dallas_tx"),
    ("LENNAR CORP",          ["LENNAR"],
     "Dallas", "TX", "CAD", "scrape_dallas_tx"),
    ("Meritage Homes CORP",  ["MERITAGE HOMES", "MERITAGE"],
     "Dallas", "TX", "CAD", "scrape_dallas_tx"),
    ("Century Communities Inc", ["CENTURY COMMUNITIES"],
     "Dallas", "TX", "CAD", "scrape_dallas_tx"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _screenshot_path(label: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", label)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SCREENSHOTS_DIR / f"{safe}_{ts}.png"


def _captcha_detected(page_text: str) -> bool:
    signals = ["captcha", "recaptcha", "hcaptcha", "are you a robot",
               "verify you are human", "i'm not a robot"]
    low = page_text.lower()
    return any(s in low for s in signals)


def _cookie_dismiss_selectors() -> list[str]:
    return [
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('I Agree')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "[id*='cookie'] button",
        "[class*='cookie'] button",
    ]


async def _dismiss_cookies(page) -> None:
    for sel in _cookie_dismiss_selectors():
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await btn.click(timeout=2000)
                await page.wait_for_timeout(500)
                return
        except Exception:
            pass


async def _new_page(context, url: str):
    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    await _dismiss_cookies(page)
    return page


# ---------------------------------------------------------------------------
# PDF helpers (no playwright needed)
# ---------------------------------------------------------------------------
_clark_pdf_text_cache: Optional[str] = None
CLARK_PDF_URL = (
    "https://www.clarkcountynv.gov/assets/documents/government/"
    "elected_officials/county_treasurer/delinquent-tax-final.pdf"
)


def _download_and_parse_pdf(url: str) -> str:
    """Download a PDF and return its full text via pypdf."""
    try:
        import pypdf  # type: ignore
    except ImportError:
        log("pypdf not found — installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "-q"])
        import pypdf  # type: ignore

    log(f"Downloading PDF: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        pdf_bytes = resp.read()

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    return "\n".join(pages_text)


def _search_pdf_for_variants(text: str, variants: list[str]) -> tuple[str, list[str]]:
    """Return (status, matching_lines) for the given name variants in PDF text."""
    lines = text.splitlines()
    matches = []
    for variant in variants:
        pattern = re.compile(re.escape(variant), re.IGNORECASE)
        for line in lines:
            if pattern.search(line):
                matches.append(line.strip())
    if not matches:
        return "NO_MATCH", []
    return "POSSIBLE_MATCH", list(dict.fromkeys(matches))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# HARRIS COUNTY TX — hcad.org
# ---------------------------------------------------------------------------
async def scrape_harris_tx(context, company: str, variants: list[str]) -> VerificationResult:
    base_url = "https://hcad.org/property-search/real-property/"
    result = VerificationResult(
        company_name=company, county="Harris", state="TX",
        source_type="CAD", result_status="NO_MATCH", search_url=base_url,
    )

    for variant in variants:
        log(f"  Harris TX → searching '{variant}'")
        try:
            page = await _new_page(context, base_url)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                await page.screenshot(path=str(_screenshot_path(f"harris_captcha_{company}")))
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA detected on HCAD portal"
                await page.close()
                return result

            # Try owner name field
            owner_selectors = [
                "input[name='owner_name']",
                "input[placeholder*='owner' i]",
                "input[placeholder*='name' i]",
                "#owner_name",
                "#ownerName",
                "input[id*='owner' i]",
            ]
            field_found = False
            for sel in owner_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=2000):
                        await loc.fill(variant)
                        field_found = True
                        break
                except Exception:
                    pass

            if not field_found:
                await page.screenshot(path=str(_screenshot_path(f"harris_no_field_{company}")))
                result.result_status = "ERROR"
                result.evidence_summary = "Could not locate owner name input on HCAD"
                await page.close()
                continue

            # Submit
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Search')",
                "[value='Search']",
            ]
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        break
                except Exception:
                    pass

            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                await page.screenshot(path=str(_screenshot_path(f"harris_captcha_post_{company}")))
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA detected after search submission"
                await page.close()
                return result

            parcels, addresses = _extract_parcel_table(body_text)
            if parcels:
                result.result_status = "VERIFIED_PARCEL"
                result.parcel_numbers_found = "; ".join(parcels[:10])
                result.addresses_found = "; ".join(addresses[:10])
                result.evidence_summary = f"Found {len(parcels)} parcel(s) for '{variant}'"
                await page.close()
                return result

            await page.close()

        except Exception as exc:
            log(f"  Harris TX error for '{variant}': {exc}")
            try:
                await page.screenshot(path=str(_screenshot_path(f"harris_error_{company}")))
            except Exception:
                pass
            result.result_status = "ERROR"
            result.evidence_summary = str(exc)[:200]

    return result


# ---------------------------------------------------------------------------
# BREVARD COUNTY FL — bcpao.us
# ---------------------------------------------------------------------------
async def scrape_brevard_fl(context, company: str, variants: list[str]) -> VerificationResult:
    base_url = "https://www.bcpao.us/asp/search.asp"
    result = VerificationResult(
        company_name=company, county="Brevard", state="FL",
        source_type="PROPERTY_APPRAISER", result_status="NO_MATCH", search_url=base_url,
    )

    for variant in variants:
        log(f"  Brevard FL → searching '{variant}'")
        try:
            page = await _new_page(context, base_url)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                await page.screenshot(path=str(_screenshot_path(f"brevard_captcha_{company}")))
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA detected on BCPAO"
                await page.close()
                return result

            # Brevard uses a named form field "sName" for owner
            owner_selectors = [
                "input[name='sName']",
                "input[name='owner']",
                "input[placeholder*='owner' i]",
                "input[placeholder*='name' i]",
                "#sName",
                "input[id*='name' i]",
            ]
            field_found = False
            for sel in owner_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=2000):
                        await loc.fill(variant)
                        field_found = True
                        break
                except Exception:
                    pass

            if not field_found:
                await page.screenshot(path=str(_screenshot_path(f"brevard_no_field_{company}")))
                result.result_status = "ERROR"
                result.evidence_summary = "Could not locate owner name input on BCPAO"
                await page.close()
                continue

            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']",
                "button:has-text('Search')",
                "input[value='Search']",
            ]
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        break
                except Exception:
                    pass

            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA after search"
                await page.close()
                return result

            parcels, addresses = _extract_parcel_table(body_text)
            if parcels:
                result.result_status = "VERIFIED_PARCEL"
                result.parcel_numbers_found = "; ".join(parcels[:10])
                result.addresses_found = "; ".join(addresses[:10])
                result.evidence_summary = f"Found {len(parcels)} parcel(s) for '{variant}'"
                await page.close()
                return result

            # Check for "no records found" vs possible partial match
            low = body_text.lower()
            if variant.lower() in low:
                result.result_status = "POSSIBLE_MATCH"
                result.evidence_summary = f"Name '{variant}' appears in page but no structured parcel table extracted"

            await page.close()

        except Exception as exc:
            log(f"  Brevard FL error for '{variant}': {exc}")
            try:
                await page.screenshot(path=str(_screenshot_path(f"brevard_error_{company}")))
            except Exception:
                pass
            result.result_status = "ERROR"
            result.evidence_summary = str(exc)[:200]

    return result


# ---------------------------------------------------------------------------
# ST LUCIE COUNTY FL — paslc.gov
# ---------------------------------------------------------------------------
async def scrape_stlucie_fl(context, company: str, variants: list[str]) -> VerificationResult:
    base_url = "https://www.paslc.gov/"
    result = VerificationResult(
        company_name=company, county="St Lucie", state="FL",
        source_type="PROPERTY_APPRAISER", result_status="NO_MATCH", search_url=base_url,
    )

    for variant in variants:
        log(f"  St Lucie FL → searching '{variant}'")
        try:
            page = await _new_page(context, base_url)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                await page.screenshot(path=str(_screenshot_path(f"stlucie_captcha_{company}")))
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA detected on PASLC"
                await page.close()
                return result

            # Try to find a search link/tab first
            search_nav_selectors = [
                "a:has-text('Search')",
                "a:has-text('Property Search')",
                "a:has-text('Owner')",
                "li:has-text('Search') a",
            ]
            for sel in search_nav_selectors:
                try:
                    nav = page.locator(sel).first
                    if await nav.is_visible(timeout=1500):
                        await nav.click()
                        await page.wait_for_load_state("networkidle", timeout=10_000)
                        break
                except Exception:
                    pass

            owner_selectors = [
                "input[name='owner']",
                "input[name='ownerName']",
                "input[placeholder*='owner' i]",
                "input[id*='owner' i]",
                "input[placeholder*='name' i]",
            ]
            field_found = False
            for sel in owner_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=2000):
                        await loc.fill(variant)
                        field_found = True
                        break
                except Exception:
                    pass

            if not field_found:
                await page.screenshot(path=str(_screenshot_path(f"stlucie_no_field_{company}")))
                result.result_status = "ERROR"
                result.evidence_summary = "Could not locate owner name input on PASLC"
                await page.close()
                continue

            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Search')",
            ]
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        break
                except Exception:
                    pass

            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA after search"
                await page.close()
                return result

            parcels, addresses = _extract_parcel_table(body_text)
            if parcels:
                result.result_status = "VERIFIED_PARCEL"
                result.parcel_numbers_found = "; ".join(parcels[:10])
                result.addresses_found = "; ".join(addresses[:10])
                result.evidence_summary = f"Found {len(parcels)} parcel(s) for '{variant}'"
                await page.close()
                return result

            low = body_text.lower()
            if variant.lower() in low:
                result.result_status = "POSSIBLE_MATCH"
                result.evidence_summary = f"Name '{variant}' present in page text"

            await page.close()

        except Exception as exc:
            log(f"  St Lucie FL error for '{variant}': {exc}")
            try:
                await page.screenshot(path=str(_screenshot_path(f"stlucie_error_{company}")))
            except Exception:
                pass
            result.result_status = "ERROR"
            result.evidence_summary = str(exc)[:200]

    return result


# ---------------------------------------------------------------------------
# CLARK COUNTY NV — PDF
# ---------------------------------------------------------------------------
async def scrape_clark_nv_pdf(context, company: str, variants: list[str]) -> VerificationResult:
    global _clark_pdf_text_cache
    result = VerificationResult(
        company_name=company, county="Clark", state="NV",
        source_type="TAX_DELINQUENT_PDF", result_status="NO_MATCH",
        search_url=CLARK_PDF_URL,
    )

    try:
        if _clark_pdf_text_cache is None:
            _clark_pdf_text_cache = await asyncio.get_event_loop().run_in_executor(
                None, _download_and_parse_pdf, CLARK_PDF_URL
            )

        status, matched_lines = _search_pdf_for_variants(_clark_pdf_text_cache, variants)
        result.result_status = status
        if matched_lines:
            result.evidence_summary = f"PDF matches for {variants}: " + " | ".join(matched_lines[:5])
            result.addresses_found = "; ".join(matched_lines[:10])
        else:
            result.evidence_summary = f"No mention of {variants} in Clark County tax delinquent PDF"

    except Exception as exc:
        log(f"  Clark NV PDF error for {company}: {exc}")
        result.result_status = "ERROR"
        result.evidence_summary = str(exc)[:200]

    return result


# ---------------------------------------------------------------------------
# DALLAS COUNTY TX — dallascad.org
# ---------------------------------------------------------------------------
async def scrape_dallas_tx(context, company: str, variants: list[str]) -> VerificationResult:
    base_url = "https://www.dallascad.org/"
    result = VerificationResult(
        company_name=company, county="Dallas", state="TX",
        source_type="CAD", result_status="NO_MATCH", search_url=base_url,
    )

    for variant in variants:
        log(f"  Dallas TX → searching '{variant}'")
        try:
            page = await _new_page(context, base_url)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                await page.screenshot(path=str(_screenshot_path(f"dallas_captcha_{company}")))
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA detected on Dallas CAD"
                await page.close()
                return result

            # Try to navigate to owner search
            nav_selectors = [
                "a:has-text('Owner Name')",
                "a:has-text('Search by Owner')",
                "a:has-text('Property Search')",
                "a[href*='search' i]",
            ]
            for sel in nav_selectors:
                try:
                    nav = page.locator(sel).first
                    if await nav.is_visible(timeout=1500):
                        await nav.click()
                        await page.wait_for_load_state("networkidle", timeout=10_000)
                        break
                except Exception:
                    pass

            owner_selectors = [
                "input[name='OwnerName']",
                "input[name='owner_name']",
                "input[placeholder*='owner' i]",
                "input[id*='owner' i]",
                "input[placeholder*='name' i]",
                "input[name='q']",
            ]
            field_found = False
            for sel in owner_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=2000):
                        await loc.fill(variant)
                        field_found = True
                        break
                except Exception:
                    pass

            if not field_found:
                await page.screenshot(path=str(_screenshot_path(f"dallas_no_field_{company}")))
                result.result_status = "ERROR"
                result.evidence_summary = "Could not locate owner name input on Dallas CAD"
                await page.close()
                continue

            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Search')",
                "input[value='Search']",
            ]
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        break
                except Exception:
                    pass

            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            body_text = await page.inner_text("body")

            if _captcha_detected(body_text):
                result.result_status = "BLOCKED_CAPTCHA"
                result.evidence_summary = "CAPTCHA after search on Dallas CAD"
                await page.close()
                return result

            parcels, addresses = _extract_parcel_table(body_text)
            if parcels:
                result.result_status = "VERIFIED_PARCEL"
                result.parcel_numbers_found = "; ".join(parcels[:10])
                result.addresses_found = "; ".join(addresses[:10])
                result.evidence_summary = f"Found {len(parcels)} parcel(s) for '{variant}'"
                await page.close()
                return result

            low = body_text.lower()
            if variant.lower() in low:
                result.result_status = "POSSIBLE_MATCH"
                result.evidence_summary = f"Name '{variant}' present in page text"

            await page.close()

        except Exception as exc:
            log(f"  Dallas TX error for '{variant}': {exc}")
            try:
                await page.screenshot(path=str(_screenshot_path(f"dallas_error_{company}")))
            except Exception:
                pass
            result.result_status = "ERROR"
            result.evidence_summary = str(exc)[:200]

    return result


# ---------------------------------------------------------------------------
# Generic parcel extractor — works on plain-text page dumps
# ---------------------------------------------------------------------------
# Parcel number patterns for TX (13-digit), FL (various), NV
_PARCEL_PATTERNS = [
    re.compile(r"\b(\d{3}[-\s]\d{3}[-\s]\d{3}[-\s]\d{4})\b"),   # Harris TX: ###-###-###-####
    re.compile(r"\b(\d{14})\b"),                                   # Harris TX raw 14-digit
    re.compile(r"\b(\d{2}[-\s]\d{2}[-\s]\d{26,30}[-\s]\d+)\b"),  # Brevard FL
    re.compile(r"\b([A-Z0-9]{3}-\d{2}-\d{2}-\d+)\b"),            # St Lucie FL
    re.compile(r"\b(\d{3}-\d{2}-\d{3}-\d{3})\b"),                 # Dallas TX
    re.compile(r"\b(\d{2}-\d{2}-\d{2}-\d+)\b"),                   # generic
]
_ADDRESS_PATTERN = re.compile(
    r"\b(\d{1,5}\s+[A-Z][A-Z\s]{2,30}(?:ST|AVE|BLVD|DR|RD|LN|WAY|CT|CIR|PL|TRL|HWY)\b[^,\n]*)",
    re.IGNORECASE,
)


def _extract_parcel_table(text: str) -> tuple[list[str], list[str]]:
    parcels: list[str] = []
    for pat in _PARCEL_PATTERNS:
        parcels.extend(pat.findall(text))
    parcels = list(dict.fromkeys(parcels))

    addresses = list(dict.fromkeys(m.group(1).strip() for m in _ADDRESS_PATTERN.finditer(text)))
    return parcels, addresses


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
SCRAPER_MAP = {
    "scrape_harris_tx":   scrape_harris_tx,
    "scrape_brevard_fl":  scrape_brevard_fl,
    "scrape_stlucie_fl":  scrape_stlucie_fl,
    "scrape_clark_nv_pdf": scrape_clark_nv_pdf,
    "scrape_dallas_tx":   scrape_dallas_tx,
}


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------
def write_results(results: list[VerificationResult]) -> None:
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow({col: getattr(r, col) for col in CSV_COLUMNS})
    log(f"Results written to {RESULTS_CSV}")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def send_telegram(message: str) -> None:
    import json
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                log("Telegram notification sent.")
            else:
                log(f"Telegram responded with status {resp.status}")
    except Exception as exc:
        log(f"Telegram send failed: {exc}")


def build_telegram_message(results: list[VerificationResult]) -> str:
    lines = ["HERMES BROWSER VERIFICATION", "=" * 32]
    for r in results:
        county_label = f"{r.county} {r.state}"
        lines.append(f"{r.company_name[:20]:20s} | {county_label:12s}: {r.result_status}")
        if r.parcel_numbers_found:
            lines.append(f"  Parcels: {r.parcel_numbers_found[:60]}")
        if r.evidence_summary:
            lines.append(f"  {r.evidence_summary[:80]}")

    totals: dict[str, int] = {}
    for r in results:
        totals[r.result_status] = totals.get(r.result_status, 0) + 1

    lines.append("=" * 32)
    lines.append("SUMMARY: " + " | ".join(f"{k}:{v}" for k, v in sorted(totals.items())))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(headless: bool) -> None:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        log("Playwright not found — installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.async_api import async_playwright  # type: ignore

    results: list[VerificationResult] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        context.set_default_timeout(PAGE_TIMEOUT_MS)

        # De-duplicate PDF targets so we only parse Clark NV PDF once per company
        seen_pdf: set[tuple[str, str]] = set()

        for company, variants, county, state, source_type, fn_name in TARGETS:
            dedup_key = (company, fn_name)
            if fn_name == "scrape_clark_nv_pdf" and dedup_key in seen_pdf:
                continue
            if fn_name == "scrape_clark_nv_pdf":
                seen_pdf.add(dedup_key)

            log(f"\n--- {company} | {county} {state} ---")
            scraper_fn = SCRAPER_MAP[fn_name]
            result = await scraper_fn(context, company, variants)
            results.append(result)
            log(f"  => {result.result_status}")

        await browser.close()

    write_results(results)
    msg = build_telegram_message(results)
    print("\n" + msg)
    send_telegram(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Browser-based county property scraper")
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run browser in visible (non-headless) mode",
    )
    args = parser.parse_args()

    asyncio.run(main(headless=not args.visible))
