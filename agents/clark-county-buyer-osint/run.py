#!/usr/bin/env python3
"""
Clark County Cash Buyer OSINT Agent
ZIPs: 89130, 89108, 89131, 89032 — Las Vegas, NV
Anchor: 5472 W Alexander Rd  APN: 138-01-406-008
Window: 05/01/2024 – 05/18/2026
"""

import sys
import subprocess
import importlib
import os
import re
import csv
import json
import time
import datetime
from pathlib import Path
from urllib.parse import urljoin, urlencode

# ── auto-install ──────────────────────────────────────────────────────────────
_DEPS = [
    ("playwright.sync_api", "playwright"),
    ("fuzzywuzzy.fuzz", "fuzzywuzzy"),
    ("Levenshtein", "python-Levenshtein"),
    ("pandas", "pandas"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
    ("lxml", "lxml"),
]


def _pip(pkg: str):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pkg, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


for _mod, _pkg in _DEPS:
    try:
        importlib.import_module(_mod.split(".")[0])
    except ImportError:
        print(f"  Installing {_pkg}…", flush=True)
        _pip(_pkg)

try:
    subprocess.check_call(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
except Exception:
    pass

# ── imports after install ──────────────────────────────────────────────────
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from fuzzywuzzy import fuzz, process
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── constants ─────────────────────────────────────────────────────────────
DATE_START = "05/01/2024"
DATE_END = "05/18/2026"
TARGET_ZIPS = {"89130", "89108", "89131", "89032"}
ANCHOR_APN = "138-01-406-008"
ANCHOR_ADDR = "5472 W ALEXANDER RD"

RECORDER_BASE = "https://recorderecomm.clarkcountynv.gov/AcclaimWeb"
RECORDER_NAME_URL = f"{RECORDER_BASE}/Search/SearchTypeName"
RECORDER_PARCEL_URL = f"{RECORDER_BASE}/Search/SearchTypeParcel"
ASSESSOR_URL = "https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx"
NVSOS_URL = "https://esos.nv.gov/EntitySearch/OnlineEntitySearch"

COMPANY_KEYWORDS = [
    "LLC", "Progress", "FirstKey", "Invitation", "AMH", "Opendoor",
    "Offerpad", "Homes", "Properties", "Acquisitions", "Holdings",
    "Capital", "Investments", "Realty", "Trust",
]
PARCEL_BLOCK = "13801406"

DATA_DIR = Path("/data")
DATA_DIR.mkdir(exist_ok=True)
PROPSTREAM_DIR = DATA_DIR / "propstream"

TODAY = datetime.date.today().strftime("%Y%m%d")
OUTPUT_CSV = DATA_DIR / f"clark-county-buyer-registry-{TODAY}.csv"

CSV_FIELDS = [
    "grantee_raw", "grantee_normalized", "alias_cluster", "source_layers",
    "record_date", "sale_price", "grantor", "instrument_num", "cash_flag",
    "officer_names", "registered_agent", "phone", "email", "website",
    "mailing_address", "buyer_status", "purchase_count", "total_spend",
    "local_flag", "proximity_flag",
]

FUZZY_THRESHOLD = 85

# ── helpers ───────────────────────────────────────────────────────────────

def sleep(s: float):
    time.sleep(s)


def normalize_name(name: str) -> str:
    if not name:
        return ""
    n = name.upper()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\b(LLC|INC|CORP|LTD|LP|LLP|TRUST|CO)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _parse_price(text: str) -> float:
    if not text:
        return 0.0
    clean = re.sub(r"[^\d.]", "", str(text).replace(",", ""))
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0


def _parse_date(s: str):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s.strip()[:10], fmt).date()
        except Exception:
            continue
    return None


def extract_phones(text: str) -> list:
    return re.findall(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}", text or "")


def extract_emails(text: str) -> list:
    return re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text or "")


def is_nevada_address(addr: str) -> bool:
    return bool(re.search(r"\bNV\b|\bNEVADA\b", (addr or "").upper()))


def is_local_buyer(mailing: str) -> bool:
    return any(z in (mailing or "") for z in TARGET_ZIPS)


def is_proximity_buyer(mailing: str) -> bool:
    return bool(re.search(r"W\.?\s*ALEXANDER\s*RD", (mailing or "").upper()))


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _make_browser(pw, headless: bool = False):
    """Launch Chromium with stealth patches; fall back to headless if no display."""
    use_headless = headless or not _has_display()
    try:
        browser = pw.chromium.launch(
            headless=use_headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--ignore-certificate-errors",
            ],
        )
    except Exception:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--ignore-certificate-errors"],
        )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="America/Los_Angeles",
        ignore_https_errors=True,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    ctx.add_init_script("""
        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
        Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
        window.chrome={runtime:{},loadTimes:()=>{},csi:()=>{}};
    """)
    return browser, ctx


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — CLARK COUNTY RECORDER
# ─────────────────────────────────────────────────────────────────────────────

def layer1_recorder(pw) -> list:
    print("\n" + "=" * 60)
    print("LAYER 1 — CLARK COUNTY RECORDER")
    print("=" * 60)

    records: list[dict] = []
    browser, ctx = _make_browser(pw, headless=False)  # spec: headless=False
    page = ctx.new_page()

    try:
        # ── Name / keyword searches ──────────────────────────────────────
        for kw in COMPANY_KEYWORDS:
            print(f"  Name search: '{kw}'", end="", flush=True)
            recs = _recorder_name_search(page, kw)
            print(f" → {len(recs)}")
            records.extend(recs)
            sleep(1.5)

        # ── Parcel block search ──────────────────────────────────────────
        print(f"  Parcel block: {PARCEL_BLOCK}", end="", flush=True)
        recs = _recorder_parcel_search(page, PARCEL_BLOCK)
        print(f" → {len(recs)}")
        records.extend(recs)

    except Exception as exc:
        print(f"  Layer 1 top-level error: {exc}")
    finally:
        browser.close()

    # Deduplicate by instrument number
    seen_inst: set[str] = set()
    unique: list[dict] = []
    for r in records:
        inst = r.get("instrument_num", "").strip()
        if inst:
            if inst not in seen_inst:
                seen_inst.add(inst)
                unique.append(r)
        else:
            unique.append(r)

    print(f"\n  Layer 1 total (deduped): {len(unique)}")
    return unique


def _recorder_goto_name(page):
    page.goto(RECORDER_NAME_URL, wait_until="domcontentloaded", timeout=60_000)
    sleep(2)


def _recorder_set_doctype(page):
    """Select GRANT BARGAIN SALE DEED in whatever list/select is present."""
    target = "GRANT BARGAIN SALE DEED"
    for sel in [
        "select[id*='DocType' i]",
        "select[id*='DocumentType' i]",
        "#DocType",
        "select",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=600):
                # Try by label, then partial match
                try:
                    el.select_option(label=target)
                    return
                except Exception:
                    pass
                opts = page.eval_on_selector_all(
                    sel + " option",
                    "opts => opts.map(o=>({v:o.value,t:o.text}))",
                )
                for opt in opts:
                    if "GRANT" in opt["t"].upper() and "BARGAIN" in opt["t"].upper():
                        el.select_option(value=opt["v"])
                        return
                    if "DEED" in opt["t"].upper():
                        el.select_option(value=opt["v"])
                        return
        except Exception:
            continue


def _recorder_set_dates(page):
    for sel, val in [
        (
            ["#DateFrom", "#StartDate", "input[id*='DateFrom' i]",
             "input[id*='StartDate' i]", "input[placeholder*='from' i]",
             "input[placeholder*='start' i]"],
            DATE_START,
        ),
        (
            ["#DateTo", "#EndDate", "input[id*='DateTo' i]",
             "input[id*='EndDate' i]", "input[placeholder*='to' i]",
             "input[placeholder*='end' i]"],
            DATE_END,
        ),
    ]:
        for s in sel:
            try:
                el = page.locator(s).first
                if el.is_visible(timeout=500):
                    el.click(click_count=3)
                    el.fill(val)
                    break
            except Exception:
                continue


def _recorder_submit(page):
    for sel in [
        "#SearchButton", "#btnSearch", "button:has-text('Search')",
        "input[type='submit']", "input[value*='Search' i]",
        "button[type='submit']",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=25_000)
                except Exception:
                    pass
                sleep(1.5)
                return
        except Exception:
            continue
    page.keyboard.press("Enter")
    sleep(2)


def _recorder_extract_table(page, label: str) -> list[dict]:
    """Parse results grid — handle both single-page and paginated tables."""
    records: list[dict] = []
    page_num = 0

    while True:
        page_num += 1
        sleep(1.2)

        # Scrape all table rows
        raw_rows: list[list[str]] = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('table').forEach(tbl => {
                tbl.querySelectorAll('tr').forEach(tr => {
                    const cells = [...tr.querySelectorAll('td,th')]
                        .map(c => c.innerText.replace(/\\s+/g,' ').trim());
                    if (cells.length >= 2) out.push(cells);
                });
            });
            return out;
        }""")

        headers: list[str] = []
        for row in raw_rows:
            joined = " ".join(row).upper()
            if any(k in joined for k in ["GRANTEE", "GRANTOR", "INSTRUMENT", "RECORD DATE"]):
                headers = [c.upper().strip() for c in row]
                break

        data_rows = raw_rows if not headers else raw_rows[raw_rows.index(
            [h.title() if h.title() in raw_rows[0] else h for h in headers]
        ) + 1 if any(
            h.title() in raw_rows[0] for h in headers
        ) else 1:]

        def _get(row_dict, *keys):
            for k in keys:
                for h in row_dict:
                    if k in h:
                        return row_dict[h]
            return ""

        for row in raw_rows:
            if len(row) < 2:
                continue
            joined = " ".join(row).upper()
            if any(k in joined for k in ["GRANTEE", "GRANTOR", "INSTRUMENT", "RECORD DATE"]):
                continue  # skip header rows

            if headers and len(row) >= len(headers):
                rd = dict(zip(headers, row))
            else:
                # Fallback: positional guess for AcclaimWeb default layout
                # Col order typically: Instrument# | Doc Type | Record Date | Grantor | Grantee | Consideration
                rd = {}
                if len(row) >= 5:
                    rd = {
                        "INSTRUMENT #": row[0],
                        "DOC TYPE": row[1],
                        "RECORD DATE": row[2],
                        "GRANTOR": row[3],
                        "GRANTEE": row[4],
                        "CONSIDERATION": row[5] if len(row) > 5 else "",
                    }
                elif len(row) >= 2:
                    rd = {"GRANTEE": row[0], "GRANTOR": row[1]}

            grantee = _get(rd, "GRANTEE", "BUYER")
            grantor = _get(rd, "GRANTOR", "SELLER")
            rec_date = _get(rd, "RECORD DATE", "DATE", "RECORDED")
            consideration = _get(rd, "CONSIDERATION", "AMOUNT", "PRICE")
            instrument = _get(rd, "INSTRUMENT", "DOC NO", "DOCUMENT")

            # Skip clearly empty or header-like rows
            if not grantee and not grantor:
                continue
            if grantee.upper() in ("GRANTEE", "BUYER", "NAME"):
                continue

            records.append({
                "grantee_raw": grantee,
                "grantee_normalized": normalize_name(grantee),
                "grantor": grantor,
                "record_date": rec_date,
                "sale_price": _parse_price(consideration),
                "instrument_num": instrument,
                "source_layers": "L1",
                "cash_flag": True,
                "_search_label": label,
            })

        # Pagination
        try:
            nxt = page.locator(
                "a:has-text('Next'), [aria-label='Next page'], "
                ".next-page, [title='Next']"
            ).first
            if nxt.is_visible(timeout=1000):
                nxt.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                if page_num >= 30:
                    break
                continue
        except Exception:
            pass
        break

    return records


def _recorder_name_search(page, keyword: str) -> list[dict]:
    try:
        _recorder_goto_name(page)
        _recorder_set_doctype(page)
        _recorder_set_dates(page)

        for sel in [
            "#Name", "#LastName", "#GranteeName",
            "input[id*='Name' i]", "input[placeholder*='name' i]",
            "input[type='text']",
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=700):
                    el.click(click_count=3)
                    el.fill(keyword)
                    break
            except Exception:
                continue

        _recorder_submit(page)
        return _recorder_extract_table(page, f"name:{keyword}")
    except Exception as exc:
        print(f"    name search error '{keyword}': {exc}")
        return []


def _recorder_parcel_search(page, parcel: str) -> list[dict]:
    try:
        page.goto(RECORDER_PARCEL_URL, wait_until="domcontentloaded", timeout=45_000)
        sleep(2)
        _recorder_set_doctype(page)
        _recorder_set_dates(page)

        for sel in [
            "#Parcel", "#ParcelNumber", "#BookPage",
            "input[id*='Parcel' i]", "input[id*='Book' i]",
            "input[placeholder*='parcel' i]", "input[type='text']",
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=700):
                    el.click(click_count=3)
                    el.fill(parcel)
                    break
            except Exception:
                continue

        _recorder_submit(page)
        return _recorder_extract_table(page, f"parcel:{parcel}")
    except Exception as exc:
        print(f"    parcel search error: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — CLARK COUNTY ASSESSOR
# ─────────────────────────────────────────────────────────────────────────────

def layer2_assessor(pw) -> list:
    print("\n" + "=" * 60)
    print("LAYER 2 — CLARK COUNTY ASSESSOR  (W Alexander Rd 5400–5600)")
    print("=" * 60)

    records: list[dict] = []
    browser, ctx = _make_browser(pw, headless=True)
    page = ctx.new_page()

    # House numbers 5400–5600 step 2 (even-side street)
    for num in range(5400, 5602, 2):
        addr = f"{num} W ALEXANDER RD"
        print(f"  {addr}", end="", flush=True)
        try:
            result = _assessor_lookup(page, addr)
            if result:
                owner = result.get("grantee_raw", "?")[:45]
                flag = "  [ABSENTEE]" if result.get("absentee_flag") else ""
                print(f" → {owner}{flag}")
                records.append(result)
            else:
                print(" → not found")
        except Exception as exc:
            print(f" → error: {str(exc)[:50]}")
        sleep(0.8)

    browser.close()

    absentee = sum(1 for r in records if r.get("absentee_flag"))
    print(f"\n  Layer 2: {len(records)} properties, {absentee} absentee investors")
    return records


def _assessor_lookup(page, address: str) -> dict | None:
    page.goto(ASSESSOR_URL, wait_until="domcontentloaded", timeout=35_000)
    sleep(1.5)

    # Find address input (the site defaults to address tab — no need to switch)
    filled = False
    for sel in [
        "#txtAddress",
        "#ctl00_ContentPlaceHolder1_txtAddress",
        "input[id*='Address' i]:not([type='hidden'])",
        "input[placeholder*='address' i]",
        "input[type='text']:visible",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=600):
                el.click(click_count=3)
                el.fill(address)
                filled = True
                break
        except Exception:
            continue

    if not filled:
        return None

    # Submit
    for sel in [
        "#btnSubmit", "#btnSearch",
        "#ctl00_ContentPlaceHolder1_btnSearch",
        "input[type='submit']", "input[value*='Search' i]",
        "button:has-text('Search')",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.click()
                break
        except Exception:
            continue

    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    sleep(1.5)

    # If results list, click first link
    try:
        first = page.locator("table td a").first
        if first.is_visible(timeout=2000):
            first.click()
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            sleep(1.5)
    except Exception:
        pass

    # DOM extraction
    dom: dict = page.evaluate("""() => {
        const out = {};
        document.querySelectorAll('span[id],div[id]').forEach(el => {
            const k = el.id
                .replace(/ctl\\d+_ContentPlaceHolder\\d+_/gi,'')
                .replace(/_/g,' ').trim();
            const v = (el.innerText||'').trim();
            if(k && v && v.length<300) out[k]=v;
        });
        document.querySelectorAll('table tr').forEach(tr=>{
            const cells=[...tr.querySelectorAll('td')];
            if(cells.length>=2){
                const k=cells[0].innerText.trim().replace(/[:\\s]+$/,'');
                const v=cells[1].innerText.trim();
                if(k&&v&&k.length<80&&v.length<300) out[k]=v;
            }
        });
        document.querySelectorAll('label[for]').forEach(lbl=>{
            const tgt=document.getElementById(lbl.getAttribute('for'));
            if(!tgt) return;
            const k=lbl.innerText.trim().replace(/:\\s*$/,'');
            const v=(tgt.innerText||tgt.value||'').trim();
            if(k&&v) out[k]=v;
        });
        return out;
    }""")

    page_text = page.inner_text("body")

    def fv(*keys: str) -> str:
        for k in keys:
            for dk in dom:
                if k.upper() in dk.upper():
                    return dom[dk]
        for k in keys:
            m = re.search(rf"(?i){re.escape(k)}\s*:?\s*(.{{1,150}}?)(?:\n|$)", page_text)
            if m:
                return m.group(1).strip()
        return ""

    owner = fv("Owner Name", "Owner", "Taxpayer Name", "Taxpayer")
    if not owner:
        return None

    mailing = fv("Mailing Address", "Mail Addr", "Mailing Addr")
    last_sale_date = fv("Last Sale Date", "Sale Date", "Transfer Date")
    last_sale_price = fv("Last Sale Price", "Sale Price", "Sale Amount")
    apn = fv("APN", "Parcel Number", "Parcel No", "Parcel ID")

    return {
        "grantee_raw": owner,
        "grantee_normalized": normalize_name(owner),
        "mailing_address": mailing,
        "record_date": last_sale_date,
        "sale_price": _parse_price(last_sale_price),
        "instrument_num": "",
        "grantor": "",
        "apn": apn,
        "site_address": address,
        "absentee_flag": bool(mailing and not is_nevada_address(mailing)),
        "cash_flag": False,
        "source_layers": "L2",
    }


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — NEVADA SOS
# ─────────────────────────────────────────────────────────────────────────────

def layer3_nvsos(entity_names: list) -> dict:
    print("\n" + "=" * 60)
    print(f"LAYER 3 — NEVADA SOS  ({len(entity_names)} entities)")
    print("=" * 60)

    results: dict[str, dict] = {}
    session = _http_session()

    for name in entity_names:
        print(f"  SOS: {name[:60]}", end="", flush=True)
        try:
            data = _nvsos_query(session, name)
            if data:
                print(f" → {data.get('status', 'found')}")
                results[name] = data
            else:
                print(" → not found")
        except Exception as exc:
            print(f" → error: {str(exc)[:50]}")
        sleep(0.8)

    print(f"\n  Layer 3: {len(results)} entities resolved")
    return results


def _nvsos_query(session: requests.Session, name: str) -> dict | None:
    # Load search page for view-state tokens
    resp = session.get(NVSOS_URL, timeout=20)
    soup = BeautifulSoup(resp.text, "lxml")

    # Detect Cloudflare or CAPTCHA
    title = soup.title.string if soup.title else ""
    if re.search(r"just a moment|cloudflare|checking your browser", title, re.I):
        return {"entity_name": name, "error": "CF_BLOCKED", "status": "blocked"}

    form_data: dict[str, str] = {}
    for inp in soup.find_all("input"):
        n = inp.get("name", "")
        v = inp.get("value", "")
        if n:
            form_data[n] = v

    # Set entity name field
    name_input = (
        soup.find("input", {"id": "txtEntityName"}) or
        soup.find("input", id=lambda x: x and "EntityName" in x if x else False) or
        soup.find("input", {"type": "text"})
    )
    field_name = name_input.get("name", "txtEntityName") if name_input else "txtEntityName"
    form_data[field_name] = name

    # Submit button
    btn = (
        soup.find("input", {"id": "btnEntitySearch"}) or
        soup.find("input", {"type": "submit"}) or
        soup.find("button", {"type": "submit"})
    )
    if btn and btn.get("name"):
        form_data[btn["name"]] = btn.get("value", "Search")

    resp2 = session.post(NVSOS_URL, data=form_data, timeout=20,
                         headers={"Referer": NVSOS_URL})
    soup2 = BeautifulSoup(resp2.text, "lxml")

    # Find results table
    results_tbl = (
        soup2.find("table", {"id": re.compile("grdEntity|Results", re.I)}) or
        soup2.find("table")
    )
    if not results_tbl:
        return None

    rows = results_tbl.find_all("tr")
    if len(rows) < 2:
        return None

    hdrs = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]

    # Pick best matching row
    best_row, best_score = None, 0
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        row_text = " ".join(c.get_text(strip=True) for c in cells)
        score = fuzz.token_sort_ratio(name.upper(), row_text.upper())
        if score > best_score:
            best_score, best_row = score, cells

    if not best_row or best_score < 40:
        return None

    entity: dict[str, str] = {}
    for i, cell in enumerate(best_row):
        h = hdrs[i] if i < len(hdrs) else f"COL{i}"
        entity[h] = cell.get_text(strip=True)

    # Follow detail link
    detail_link = None
    for cell in best_row:
        a = cell.find("a", href=True)
        if a:
            href = a["href"]
            detail_link = href if href.startswith("http") else urljoin(NVSOS_URL, href)
            break

    if detail_link:
        try:
            resp3 = session.get(detail_link, timeout=20, headers={"Referer": NVSOS_URL})
            soup3 = BeautifulSoup(resp3.text, "lxml")
            detail_text = soup3.get_text(" ", strip=True)

            def labeled(soup_obj, *labels):
                for lbl in labels:
                    el = soup_obj.find(string=re.compile(lbl, re.I))
                    if el:
                        nxt = el.find_parent().find_next_sibling()
                        if nxt:
                            return nxt.get_text(strip=True)[:200]
                    m = re.search(rf"(?i){lbl}\s*:?\s*(.{{1,200}}?)(?:\n|$)", detail_text)
                    if m:
                        return m.group(1).strip()
                return ""

            entity["registered_agent"] = labeled(soup3, "Registered Agent", "Agent Name")
            entity["officers"] = _sos_extract_officers(soup3, detail_text)
            entity["formation_date"] = labeled(soup3, "Formation Date", "Incorporation Date",
                                                "File Date", "Formed")
            entity["status"] = labeled(soup3, "Status", "Entity Status", "Standing")
            entity["detail_url"] = detail_link
        except Exception as exc:
            entity["detail_error"] = str(exc)[:100]

    entity["entity_name"] = name
    entity["match_score"] = best_score
    return entity


def _sos_extract_officers(soup: BeautifulSoup, text: str) -> str:
    names: list[str] = []

    for tbl in soup.find_all("table"):
        hdrs = [th.get_text(strip=True).upper() for th in tbl.find_all("th")]
        if any(h in " ".join(hdrs) for h in ["OFFICER", "MANAGER", "DIRECTOR", "TITLE", "NAME"]):
            for row in tbl.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if cells:
                    names.append(" | ".join(filter(None, cells)))
            break

    if not names:
        for pat in [
            r"(?:Officer|Manager|Director|President|Member)\s*:?\s*([A-Z][A-Za-z\s,\.]{5,60})",
            r"([A-Z][A-Z\s]{5,40}),\s*(?:President|Manager|Member|Director)",
        ]:
            names.extend(re.findall(pat, text)[:5])

    return "; ".join(dict.fromkeys(names))[:500]


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 4 — OPEN WEB OSINT
# ─────────────────────────────────────────────────────────────────────────────

def layer4_web_osint(entity_names: list, officer_map: dict) -> dict:
    print("\n" + "=" * 60)
    print(f"LAYER 4 — OPEN WEB OSINT  ({len(entity_names)} entities, capped 50)")
    print("=" * 60)

    results: dict[str, dict] = {}
    session = _http_session()

    for name in entity_names[:50]:
        print(f"  Web: {name[:50]}", end="", flush=True)

        contact: dict = {"phones": [], "emails": [], "websites": [], "snippets": []}

        queries = [
            f'"{name}" Las Vegas real estate investor',
            f'"{name}" Clark County deed',
        ]
        officers_str = officer_map.get(name, "")
        if officers_str:
            for officer in officers_str.split(";")[:2]:
                officer = officer.strip()
                if len(officer) > 5:
                    queries.append(f'"{officer}" Las Vegas real estate')

        for q in queries[:3]:
            try:
                d = _ddg_search(session, q)
                contact["phones"].extend(d["phones"])
                contact["emails"].extend(d["emails"])
                contact["websites"].extend(d["websites"])
                contact["snippets"].extend(d["snippets"][:2])
            except Exception:
                pass
            sleep(1.2)

        for k in ("phones", "emails", "websites"):
            contact[k] = list(dict.fromkeys(contact[k]))

        if any(contact[k] for k in ("phones", "emails", "websites")):
            results[name] = contact
            print(
                f" → ph:{len(contact['phones'])} "
                f"em:{len(contact['emails'])} "
                f"web:{len(contact['websites'])}"
            )
        else:
            print(" → none")

    print(f"\n  Layer 4: contact data for {len(results)} entities")
    return results


def _ddg_search(session: requests.Session, query: str) -> dict:
    result: dict = {"phones": [], "emails": [], "websites": [], "snippets": []}
    try:
        resp = session.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            timeout=15,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        soup = BeautifulSoup(resp.text, "lxml")

        for div in soup.find_all("div", class_=re.compile(r"result__body|result__snippet")):
            text = div.get_text(" ", strip=True)
            result["snippets"].append(text[:300])
            result["phones"].extend(extract_phones(text))
            result["emails"].extend(extract_emails(text))

        for a in soup.find_all("a", class_=re.compile(r"result__url|result__a")):
            href = a.get("href", "")
            if href.startswith("http"):
                result["websites"].append(href[:200])

        full = soup.get_text(" ")
        result["phones"].extend(extract_phones(full))
        result["emails"].extend(extract_emails(full))
    except Exception:
        pass
    return result


def _http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 5 — PROPSTREAM CSV
# ─────────────────────────────────────────────────────────────────────────────

def layer5_propstream() -> list:
    print("\n" + "=" * 60)
    print("LAYER 5 — PROPSTREAM CSV")
    print("=" * 60)

    records: list[dict] = []

    if not PROPSTREAM_DIR.exists():
        print(f"  {PROPSTREAM_DIR} not found — skipping")
        return records

    # Collect CSVs matching target ZIPs in filename, or all CSVs otherwise
    zip_csvs = []
    for z in TARGET_ZIPS:
        zip_csvs.extend(PROPSTREAM_DIR.glob(f"*{z}*"))
    zip_csvs = [f for f in zip_csvs if f.suffix.lower() == ".csv"]

    if not zip_csvs:
        zip_csvs = list(PROPSTREAM_DIR.glob("*.csv"))

    if not zip_csvs:
        print(f"  No CSVs in {PROPSTREAM_DIR}")
        return records

    print(f"  Found {len(zip_csvs)} file(s)")

    for csv_path in zip_csvs:
        print(f"  Processing {csv_path.name}")
        try:
            df = pd.read_csv(csv_path, low_memory=False)
            print(f"    {len(df)} rows | cols: {list(df.columns[:8])}")

            def fc(*names) -> str | None:
                for n in names:
                    for c in df.columns:
                        if n.upper() in c.upper():
                            return c
                return None

            owner_col = fc("Owner Name", "Owner", "Grantee")
            mail_col = fc("Mailing Address", "Mail Addr", "Owner Address", "Owner Mail")
            otype_col = fc("Owner Type", "Ownership Type", "Entity Type")
            equity_col = fc("Equity %", "Equity Pct", "Equity Percent", "% Equity", "Equity")
            sale_date_col = fc("Sale Date", "Last Sale Date", "Transfer Date")
            sale_price_col = fc("Sale Price", "Last Sale Price", "Transfer Amount")
            apn_col = fc("APN", "Parcel", "Tax ID", "Parcel Number")

            filtered = df.copy()

            if otype_col:
                mask = filtered[otype_col].astype(str).str.upper().str.contains(
                    r"LLC|CORP|TRUST|INC\b|L\.L\.C", na=False, regex=True
                )
                filtered = filtered[mask]

            if equity_col:
                filtered[equity_col] = pd.to_numeric(
                    filtered[equity_col].astype(str).str.replace(r"[%,\s]", "", regex=True),
                    errors="coerce",
                )
                filtered = filtered[filtered[equity_col] >= 95]

            print(f"    After filter: {len(filtered)} rows")

            for _, row in filtered.iterrows():
                owner = str(row[owner_col]).strip() if owner_col else ""
                mail = str(row[mail_col]).strip() if mail_col else ""
                sd = str(row[sale_date_col]).strip() if sale_date_col else ""
                sp = _parse_price(str(row[sale_price_col])) if sale_price_col else 0.0
                apn = str(row[apn_col]).strip() if apn_col else ""

                if owner and owner.lower() not in ("nan", "none", ""):
                    records.append({
                        "grantee_raw": owner,
                        "grantee_normalized": normalize_name(owner),
                        "mailing_address": "" if mail.lower() in ("nan", "none") else mail,
                        "record_date": "" if sd.lower() in ("nan", "none") else sd,
                        "sale_price": sp,
                        "instrument_num": "",
                        "grantor": "",
                        "apn": apn,
                        "source_layers": "L5",
                        "cash_flag": True,
                    })

        except Exception as exc:
            print(f"    Error: {exc}")

    # Show same-address clusters
    addr_map: dict[str, list[str]] = {}
    for r in records:
        m = r.get("mailing_address", "").strip()
        if m:
            addr_map.setdefault(m, []).append(r["grantee_raw"])
    clusters = {k: v for k, v in addr_map.items() if len(v) > 1}
    if clusters:
        print(f"\n  Same-address portfolio clusters ({len(clusters)}):")
        for addr, names in list(clusters.items())[:5]:
            print(f"    {addr[:60]}: {', '.join(set(names))[:80]}")

    print(f"\n  Layer 5: {len(records)} records")
    return records


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 6 — DEDUPLICATE AND SCORE
# ─────────────────────────────────────────────────────────────────────────────

def layer6_merge_and_score(
    l1: list,
    l2: list,
    l3_sos: dict,
    l4_web: dict,
    l5: list,
) -> list:
    print("\n" + "=" * 60)
    print("LAYER 6 — DEDUPLICATE + SCORE")
    print("=" * 60)

    all_recs = l1 + l2 + l5
    if not all_recs:
        print("  No records to process.")
        return []

    # Master buyer dict: normalized_name → aggregated entry
    buyer_map: dict[str, dict] = {}

    def _get_or_create(norm: str) -> dict:
        if norm not in buyer_map:
            buyer_map[norm] = {
                "grantee_raw": "",
                "grantee_normalized": norm,
                "alias_cluster": norm,
                "source_layers": set(),
                "record_dates": [],
                "sale_prices": [],
                "grantor": "",
                "instrument_nums": [],
                "cash_flag": False,
                "officer_names": "",
                "registered_agent": "",
                "phones": [],
                "emails": [],
                "websites": [],
                "mailing_address": "",
                "purchase_count": 0,
                "total_spend": 0.0,
                "local_flag": False,
                "proximity_flag": False,
                "buyer_status": "COLD",
            }
        return buyer_map[norm]

    # Ingest records
    for rec in all_recs:
        norm = rec.get("grantee_normalized", "").strip()
        if not norm:
            continue
        key = _fuzzy_find(norm, buyer_map, FUZZY_THRESHOLD) or norm
        entry = _get_or_create(key)

        if not entry["grantee_raw"]:
            entry["grantee_raw"] = rec.get("grantee_raw", "")

        src = rec.get("source_layers", "")
        if src:
            entry["source_layers"].add(src)

        dt = rec.get("record_date", "")
        if dt and dt.lower() not in ("nan", "none", ""):
            entry["record_dates"].append(dt)

        price = rec.get("sale_price", 0.0) or 0.0
        if price > 0:
            entry["sale_prices"].append(price)

        inst = rec.get("instrument_num", "").strip()
        if inst:
            entry["instrument_nums"].append(inst)

        if rec.get("cash_flag"):
            entry["cash_flag"] = True

        if rec.get("mailing_address") and not entry["mailing_address"]:
            mail = rec["mailing_address"]
            if mail.lower() not in ("nan", "none", ""):
                entry["mailing_address"] = mail

        if rec.get("grantor") and not entry["grantor"]:
            entry["grantor"] = rec["grantor"]

    # Enrich from SOS (Layer 3)
    for sos_name, sos_data in l3_sos.items():
        norm = normalize_name(sos_name)
        key = _fuzzy_find(norm, buyer_map, 80)
        if key:
            e = buyer_map[key]
            e["source_layers"].add("L3")
            if sos_data.get("officers"):
                e["officer_names"] = sos_data["officers"]
            if sos_data.get("registered_agent"):
                e["registered_agent"] = sos_data["registered_agent"]

    # Enrich from web OSINT (Layer 4)
    for web_name, web_data in l4_web.items():
        norm = normalize_name(web_name)
        key = _fuzzy_find(norm, buyer_map, 80)
        if key:
            e = buyer_map[key]
            e["source_layers"].add("L4")
            e["phones"].extend(web_data.get("phones", []))
            e["emails"].extend(web_data.get("emails", []))
            e["websites"].extend(web_data.get("websites", []))

    # Build alias clusters
    clusters = _build_clusters(list(buyer_map.keys()))

    # Score and finalise
    today = datetime.date.today()
    cutoff_12mo = today - datetime.timedelta(days=365)
    final: list[dict] = []

    for norm_key, e in buyer_map.items():
        e["purchase_count"] = len(e["record_dates"])
        e["total_spend"] = sum(e["sale_prices"])

        parsed_dates = [d for d in (_parse_date(s) for s in e["record_dates"]) if d]
        recent = sum(1 for d in parsed_dates if d >= cutoff_12mo)

        if recent >= 3:
            e["buyer_status"] = "ACTIVE"
        elif recent >= 1:
            e["buyer_status"] = "WARM"
        else:
            e["buyer_status"] = "COLD"

        mail = e["mailing_address"]
        e["local_flag"] = is_local_buyer(mail)
        e["proximity_flag"] = is_proximity_buyer(mail)

        for cluster_rep, members in clusters.items():
            if norm_key in members:
                e["alias_cluster"] = cluster_rep
                break

        final.append({
            "grantee_raw": e["grantee_raw"],
            "grantee_normalized": e["grantee_normalized"],
            "alias_cluster": e.get("alias_cluster", e["grantee_normalized"]),
            "source_layers": ",".join(sorted(e["source_layers"])),
            "record_date": "; ".join(sorted(set(e["record_dates"]))[:5]),
            "sale_price": e["sale_prices"][-1] if e["sale_prices"] else 0.0,
            "grantor": e["grantor"],
            "instrument_num": "; ".join(dict.fromkeys(e["instrument_nums"]))[:200],
            "cash_flag": e["cash_flag"],
            "officer_names": e["officer_names"],
            "registered_agent": e["registered_agent"],
            "phone": "; ".join(dict.fromkeys(e["phones"]))[:200],
            "email": "; ".join(dict.fromkeys(e["emails"]))[:200],
            "website": "; ".join(dict.fromkeys(e["websites"]))[:300],
            "mailing_address": e["mailing_address"],
            "buyer_status": e["buyer_status"],
            "purchase_count": e["purchase_count"],
            "total_spend": e["total_spend"],
            "local_flag": e["local_flag"],
            "proximity_flag": e["proximity_flag"],
        })

    final.sort(key=lambda r: r["purchase_count"], reverse=True)
    print(f"  Layer 6: {len(final)} unique buyers after merge")
    return final


def _fuzzy_find(norm: str, buyer_map: dict, threshold: int) -> str | None:
    if not buyer_map:
        return None
    if norm in buyer_map:
        return norm
    keys = list(buyer_map.keys())
    try:
        match, score = process.extractOne(norm, keys, scorer=fuzz.token_sort_ratio)
        return match if score >= threshold else None
    except Exception:
        return None


def _build_clusters(names: list) -> dict:
    clusters: dict[str, set] = {}
    assigned: set = set()
    for n in names:
        if n in assigned:
            continue
        group = {n}
        assigned.add(n)
        for other in names:
            if other not in assigned and fuzz.token_sort_ratio(n, other) >= FUZZY_THRESHOLD:
                group.add(other)
                assigned.add(other)
        clusters[n] = group
    return clusters


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def write_csv(records: list):
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"\n  CSV written → {OUTPUT_CSV}")


def print_summary(records: list):
    print("\n" + "=" * 60)
    print("CONSOLE SUMMARY")
    print("=" * 60)

    if not records:
        print("  No buyers found.")
        return

    print(f"\nTotal buyers found: {len(records)}")

    print("\nTop 15 by purchase count:")
    for i, r in enumerate(
        sorted(records, key=lambda x: x["purchase_count"], reverse=True)[:15], 1
    ):
        print(
            f"  {i:2}. {r['grantee_raw'][:48]:<50} "
            f"{r['purchase_count']:3}x  {r['buyer_status']:<6}  "
            f"[{r['source_layers']}]"
        )

    print("\nTop 10 by total spend:")
    for i, r in enumerate(
        sorted(records, key=lambda x: x["total_spend"], reverse=True)[:10], 1
    ):
        print(
            f"  {i:2}. {r['grantee_raw'][:48]:<50}  "
            f"${r['total_spend']:>14,.0f}"
        )

    local = [r for r in records if r["local_flag"]]
    print(f"\nLocal buyers (891xx mailing): {len(local)}")
    for r in local[:25]:
        print(f"  • {r['grantee_raw'][:55]}  →  {r['mailing_address'][:55]}")

    prox = [r for r in records if r["proximity_flag"]]
    print(f"\nProximity buyers (W Alexander Rd mailing): {len(prox)}")
    for r in prox:
        print(f"  • {r['grantee_raw'][:55]}  →  {r['mailing_address'][:55]}")

    high_conf = [r for r in records if len(r["source_layers"].split(",")) >= 3]
    print(f"\nHigh-confidence buyers (3+ source layers): {len(high_conf)}")
    for r in high_conf[:25]:
        print(f"  • [{r['source_layers']}]  {r['grantee_raw'][:55]}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Clark County Cash Buyer OSINT Agent")
    print(f"Date    : {datetime.date.today()}")
    print(f"Window  : {DATE_START} – {DATE_END}")
    print(f"Anchor  : {ANCHOR_ADDR}  APN {ANCHOR_APN}")
    print(f"ZIPs    : {', '.join(sorted(TARGET_ZIPS))}")
    print("=" * 60)

    # Layers 1 & 2 require Playwright
    l1_records: list[dict] = []
    l2_records: list[dict] = []
    with sync_playwright() as pw:
        l1_records = layer1_recorder(pw)
        l2_records = layer2_assessor(pw)

    # Collect entity names for SOS + web OSINT
    entity_set: set[str] = set()
    for r in l1_records + l2_records:
        raw = r.get("grantee_raw", "").strip()
        if raw and len(raw) > 3:
            if re.search(
                r"\b(LLC|INC|CORP|LTD|LP|TRUST|PROPERTIES|HOLDINGS|"
                r"CAPITAL|REALTY|INVESTMENTS|ACQUISITIONS|HOMES|PARTNERS)\b",
                raw.upper(),
            ):
                entity_set.add(raw)

    entity_list = sorted(entity_set)
    print(f"\nEntities queued for SOS / web: {len(entity_list)}")

    # Layer 3 — NV SOS
    l3_sos = layer3_nvsos(entity_list)

    # Layer 4 — Web OSINT
    officer_map = {n: d.get("officers", "") for n, d in l3_sos.items()}
    l4_web = layer4_web_osint(entity_list, officer_map)

    # Layer 5 — PropStream
    l5_records = layer5_propstream()

    # Layer 6 — Merge & score
    final = layer6_merge_and_score(l1_records, l2_records, l3_sos, l4_web, l5_records)

    write_csv(final)
    print_summary(final)

    print(f"\nDone — {len(final)} buyers → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
