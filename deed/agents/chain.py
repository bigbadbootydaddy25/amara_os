"""
CHAIN agent — Harrison County Clerk grantor/grantee index.
URL: https://harrison.countyclerk.us/online-records/

Primary path: Selenium via CloakBrowser (bypasses bot detection / login walls).
Fallback:     requests + BeautifulSoup (works if site allows plain HTTP).

Saves raw results to OUTPUT_DIR/CHAIN_RESULTS_11-409-19.json.
"""
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from deed.config import PARCEL_ID, COUNTY, HEADERS, TIMEOUT, NOTES_FILE, OUTPUT_DIR, keychain

log = logging.getLogger("CHAIN")

BASE       = "https://harrison.countyclerk.us/online-records"
JSON_OUT   = OUTPUT_DIR / f"CHAIN_RESULTS_{PARCEL_ID}.json"

# CloakBrowser location
CLOAK_BASE = Path("/Users/user/Downloads/neuron_ai_brain_mvp/CloakBrowser")
CLOAK_APP  = CLOAK_BASE / "CloakBrowser.app" / "Contents" / "MacOS" / "CloakBrowser"
CLOAK_BIN  = CLOAK_BASE / "CloakBrowser"   # flat binary fallback

# Selenium implicit wait (seconds)
WAIT = 12


@dataclass
class Instrument:
    seq:           int = 0
    inst_type:     str = ""
    grantor:       str = ""
    grantee:       str = ""
    book:          str = ""
    page:          str = ""
    date_recorded: str = ""
    date_instr:    str = ""
    description:   str = ""
    doc_url:       str = ""
    notes:         str = ""


# ══════════════════════════════════════════════════════════════════════════════
#  Public entry point
# ══════════════════════════════════════════════════════════════════════════════

def run() -> dict:
    log.info("CHAIN — loading manual seed | parcel %s", PARCEL_ID)

    # Load cached JSON if present (from a previous successful run)
    if JSON_OUT.exists():
        try:
            cached = json.loads(JSON_OUT.read_text())
            if cached.get("instruments"):
                log.info("Loaded %d instruments from cache: %s", len(cached["instruments"]), JSON_OUT)
                _log_instruments_from_dicts(cached["instruments"])
                return cached
        except Exception as e:
            log.warning("Cache read failed (%s) — loading seed", e)

    # Load hardcoded manual chain data directly — no scraping
    from deed.chain_seed import CHAIN_RESULT
    _log_instruments_from_dicts(CHAIN_RESULT["instruments"])
    log.info("Chain loaded: %d instruments (oldest 1874 → vesting 2010)", CHAIN_RESULT["count"])
    _save_json(CHAIN_RESULT)
    return CHAIN_RESULT


# ══════════════════════════════════════════════════════════════════════════════
#  CloakBrowser / Selenium path
# ══════════════════════════════════════════════════════════════════════════════

def _find_cloak_binary() -> Path | None:
    """Locate the CloakBrowser executable."""
    candidates = [
        CLOAK_APP,
        CLOAK_BIN,
        CLOAK_BASE / "CloakBrowser",
        CLOAK_BASE / "chromium",
        CLOAK_BASE / "chrome",
    ]
    # Also glob for any executable in the directory
    if CLOAK_BASE.exists():
        for f in CLOAK_BASE.rglob("CloakBrowser"):
            if f.is_file():
                candidates.insert(0, f)

    for c in candidates:
        if c.exists() and c.is_file():
            log.info("CloakBrowser binary: %s", c)
            return c

    log.warning("CloakBrowser not found under %s", CLOAK_BASE)
    return None


def _launch_cloak():
    """Return a Selenium WebDriver using CloakBrowser, or None if unavailable."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        log.warning("selenium not installed — run: pip3 install selenium")
        return None

    binary = _find_cloak_binary()
    if not binary:
        return None

    options = Options()
    options.binary_location = str(binary)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Look for chromedriver bundled with CloakBrowser or on PATH
    driver_path = _find_chromedriver()

    try:
        if driver_path:
            service = Service(executable_path=str(driver_path))
            driver  = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)

        driver.implicitly_wait(WAIT)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
        )
        log.info("CloakBrowser launched OK")
        return driver
    except Exception as e:
        log.warning("CloakBrowser launch failed: %s", e)
        return None


def _find_chromedriver() -> Path | None:
    """Find chromedriver — bundled with CloakBrowser or system PATH."""
    import shutil
    candidates = [
        CLOAK_BASE / "chromedriver",
        CLOAK_BASE / "chromedriver-mac-x64" / "chromedriver",
        CLOAK_BASE / "chromedriver-mac-arm64" / "chromedriver",
        CLOAK_BASE / "CloakBrowser.app" / "Contents" / "MacOS" / "chromedriver",
    ]
    if CLOAK_BASE.exists():
        for f in CLOAK_BASE.rglob("chromedriver"):
            if f.is_file():
                candidates.insert(0, f)

    for c in candidates:
        if c.exists():
            return c

    sys_driver = shutil.which("chromedriver")
    if sys_driver:
        return Path(sys_driver)

    return None


def _selenium_search(driver, instruments: list, errors: list) -> tuple[list, list]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    wait = WebDriverWait(driver, WAIT)

    # ── Navigate ──────────────────────────────────────────────────────────────
    log.info("Navigating to %s/", BASE)
    driver.get(f"{BASE}/")
    time.sleep(2)

    # Handle login wall if present
    _handle_login(driver, wait)

    # ── Search strategies ─────────────────────────────────────────────────────
    search_configs = [
        {"label": "parcel ID",      "fn": _fill_parcel_id},
        {"label": "district/map",   "fn": _fill_district_map},
        {"label": "grantor STRUNK", "fn": _fill_grantor_strunk},
    ]

    for cfg in search_configs:
        log.info("Selenium search: %s", cfg["label"])
        try:
            driver.get(f"{BASE}/")
            time.sleep(1.5)
            _handle_login(driver, wait)
            cfg["fn"](driver, wait)
            time.sleep(2)
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "lxml")
            found = _parse_results(soup, instruments)
            log.info("  → %d instruments", found)
            if found:
                break
        except TimeoutException:
            log.warning("  Timeout on search: %s", cfg["label"])
        except Exception as e:
            log.warning("  Search failed (%s): %s", cfg["label"], e)

    # ── If results found, try to get all pages ────────────────────────────────
    if instruments:
        _paginate(driver, instruments)

    return instruments, errors


def _handle_login(driver, wait) -> None:
    """Detect and handle a login page if present."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    src = driver.page_source.lower()
    if "login" not in src and "sign in" not in src and "username" not in src:
        return

    log.info("  Login page detected — attempting Keychain credentials")
    user = keychain("HarrisonCountyClerk", "username") or ""
    pwd  = keychain("HarrisonCountyClerk", "password") or ""

    if not user or not pwd:
        log.warning("  No credentials in Keychain for 'HarrisonCountyClerk'")
        log.warning("  Add: security add-generic-password -s HarrisonCountyClerk -a username -w <user>")
        log.warning("  Add: security add-generic-password -s HarrisonCountyClerk -a password -w <pass>")
        return

    try:
        from selenium.webdriver.common.by import By
        for sel in ["input[type='text']", "input[name*='user']", "input[id*='user']"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                el.clear(); el.send_keys(user)
                break
            except Exception:
                pass
        for sel in ["input[type='password']", "input[name*='pass']", "input[id*='pass']"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                el.clear(); el.send_keys(pwd)
                break
            except Exception:
                pass
        for sel in ["input[type='submit']", "button[type='submit']", "button"]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                btn.click()
                time.sleep(2)
                break
            except Exception:
                pass
        log.info("  Login submitted")
    except Exception as e:
        log.warning("  Login fill failed: %s", e)


def _fill_parcel_id(driver, wait) -> None:
    from selenium.webdriver.common.by import By
    for name in ["txtParcelID", "ParcelID", "parcelid", "Parcel"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR,
                                     f"input[name='{name}'],input[id='{name}']")
            el.clear()
            el.send_keys(PARCEL_ID)
            _submit(driver)
            return
        except Exception:
            pass
    # Generic — fill any input that looks like a parcel field
    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
    if inputs:
        inputs[0].clear()
        inputs[0].send_keys(PARCEL_ID)
        _submit(driver)


def _fill_district_map(driver, wait) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select

    # District dropdown
    for sel_id in ["ddlDistrict", "District", "district"]:
        try:
            sel = Select(driver.find_element(By.CSS_SELECTOR,
                                             f"select[name='{sel_id}'],select[id='{sel_id}']"))
            for opt in sel.options:
                if "11" in opt.get_attribute("value") or "elk" in opt.text.lower():
                    sel.select_by_value(opt.get_attribute("value"))
                    break
            break
        except Exception:
            pass

    # Map number
    for name in ["txtMapNum", "MapNum", "mapnum", "Map"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR,
                                     f"input[name='{name}'],input[id='{name}']")
            el.clear(); el.send_keys("409")
            break
        except Exception:
            pass

    # Parcel number
    for name in ["txtParcelNum", "ParcelNum", "parcelnum"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR,
                                     f"input[name='{name}'],input[id='{name}']")
            el.clear(); el.send_keys("19")
            break
        except Exception:
            pass

    _submit(driver)


def _fill_grantor_strunk(driver, wait) -> None:
    from selenium.webdriver.common.by import By

    for name in ["txtGrantorName", "GrantorName", "Grantor", "grantor"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR,
                                     f"input[name='{name}'],input[id='{name}']")
            el.clear(); el.send_keys("STRUNK")
            _submit(driver)
            return
        except Exception:
            pass


def _submit(driver) -> None:
    from selenium.webdriver.common.by import By

    for sel in ["input[value='Search']", "button[value='Search']",
                "input[type='submit']", "button[type='submit']"]:
        try:
            driver.find_element(By.CSS_SELECTOR, sel).click()
            return
        except Exception:
            pass
    # Last resort: submit the first form
    try:
        driver.find_element(By.TAG_NAME, "form").submit()
    except Exception:
        pass


def _paginate(driver, instruments: list) -> None:
    """Follow Next Page links to collect all result rows."""
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import NoSuchElementException

    page = 1
    while True:
        try:
            nxt = driver.find_element(By.PARTIAL_LINK_TEXT, "Next")
            nxt.click()
            time.sleep(1.5)
            soup = BeautifulSoup(driver.page_source, "lxml")
            added = _parse_results(soup, instruments)
            log.info("  Page %d: %d more instruments", page + 1, added)
            if not added:
                break
            page += 1
        except NoSuchElementException:
            break
        except Exception as e:
            log.warning("  Pagination stopped: %s", e)
            break


# ══════════════════════════════════════════════════════════════════════════════
#  Fallback: requests + BeautifulSoup
# ══════════════════════════════════════════════════════════════════════════════

def _requests_search(instruments: list, errors: list) -> tuple[list, list]:
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        r = session.get(f"{BASE}/", timeout=TIMEOUT)
        if r.status_code == 403:
            msg = "IDX returned 403 — site requires browser session (CloakBrowser)"
            log.error(msg)
            errors.append(msg)
            _note(msg)
            return instruments, errors
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
    except Exception as e:
        msg = f"IDX unreachable via requests: {e}"
        log.error(msg)
        errors.append(msg)
        _note(msg)
        return instruments, errors

    vs = _viewstate(soup)
    searches = [
        {**vs, "txtParcelID": PARCEL_ID,                "btnSearch": "Search"},
        {**vs, "txtParcelID": PARCEL_ID.replace("-",""), "btnSearch": "Search"},
        {**vs, "ddlDistrict": "11", "txtMapNum": "409", "txtParcelNum": "19",
               "btnSearch": "Search"},
        {**vs, "txtGrantorName": "STRUNK",               "btnSearch": "Search"},
    ]

    for i, payload in enumerate(searches, 1):
        log.info("  Requests search %d/%d", i, len(searches))
        try:
            r = session.post(f"{BASE}/", data=payload, timeout=TIMEOUT)
            r.raise_for_status()
            soup2 = BeautifulSoup(r.content, "lxml")
            found = _parse_results(soup2, instruments)
            if found:
                log.info("  → %d instruments", found)
                break
            log.info("  → 0 results")
        except Exception as e:
            log.warning("  Requests search %d failed: %s", i, e)
        time.sleep(1)

    return instruments, errors


# ══════════════════════════════════════════════════════════════════════════════
#  Shared parsing helpers
# ══════════════════════════════════════════════════════════════════════════════

def _viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
                 "__EVENTTARGET", "__EVENTARGUMENT"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_results(soup: BeautifulSoup, instruments: list) -> int:
    table = (soup.find("table", id=re.compile(r"result|grid|data", re.I))
             or soup.find("table"))
    if not table:
        return 0
    rows = table.find_all("tr")
    if len(rows) < 2:
        return 0
    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
    start = len(instruments)

    for seq, row in enumerate(rows[1:], start + 1):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not any(cells):
            continue
        inst = Instrument(seq=seq)
        for h, v in zip(headers, cells):
            if   "grantor"  in h:                       inst.grantor       = v
            elif "grantee"  in h:                       inst.grantee       = v
            elif "book"     in h:                       inst.book          = v
            elif "page"     in h:                       inst.page          = v
            elif "type"     in h or "inst" in h:        inst.inst_type     = v
            elif "record"   in h and "date" in h:       inst.date_recorded = v
            elif "date"     in h:                       inst.date_instr    = v
            elif "desc"     in h:                       inst.description   = v
        link = row.find("a", href=True)
        if link:
            href = link["href"]
            inst.doc_url = href if href.startswith("http") else f"{BASE}/{href.lstrip('/')}"
        if inst.grantor or inst.book:
            instruments.append(inst)

    return len(instruments) - start


def _extract_legal_desc(instruments: list) -> str:
    for inst in instruments:
        desc = inst.description or ""
        if any(kw in desc.upper() for kw in ["BEGINNING", "THENCE", "CHAIN", "BEARING", "POLE"]):
            return desc
    return ""


def _analyze_chain(instruments: list, gaps: list) -> None:
    instr_sorted = sorted(instruments, key=lambda i: i.date_recorded or i.date_instr or "")
    for i in range(len(instr_sorted) - 1):
        curr, nxt = instr_sorted[i], instr_sorted[i + 1]
        if curr.grantee and nxt.grantor:
            if curr.grantee.upper().strip() != nxt.grantor.upper().strip():
                gap = (
                    f"Break at {curr.seq}→{nxt.seq}: "
                    f"grantee '{curr.grantee}' ≠ grantor '{nxt.grantor}'"
                )
                gaps.append(gap)
                _note(f"⚠ GAP: {gap}")
                log.warning("GAP: %s", gap)


def _log_instruments_from_dicts(dicts: list) -> None:
    log.info("Chain of title — %d instruments:", len(dicts))
    for i in dicts:
        log.info("  [%03d] %-18s | %-35s → %-35s | BK %-8s PG %-6s | %s",
                 i.get("seq", 0), i.get("type", "UNKNOWN")[:18],
                 i.get("grantor", "—")[:35], i.get("grantee", "—")[:35],
                 i.get("book", "—"), i.get("page", "—"),
                 i.get("date_recorded", i.get("date_instr", "—")))
        _note(f"[{i.get('seq',0):03d}] {i.get('type','UNKNOWN'):<18} | "
              f"{i.get('grantor','—')} → {i.get('grantee','—')} | "
              f"BK {i.get('book','—')} PG {i.get('page','—')} | "
              f"{i.get('date_recorded', i.get('date_instr','—'))}")
        if i.get("notes"):
            log.info("        NOTE: %s", i["notes"])


def _log_instruments(instruments: list) -> None:
    log.info("Chain of title — %d instruments:", len(instruments))
    for i in instruments:
        log.info("  [%03d] %-18s | %s → %s | BK %-6s PG %-6s | %s",
                 i.seq, i.inst_type or "UNKNOWN",
                 i.grantor or "—", i.grantee or "—",
                 i.book or "—", i.page or "—",
                 i.date_recorded or i.date_instr or "—")
        _note(f"[{i.seq:03d}] {i.inst_type or 'UNKNOWN':<18} | "
              f"{i.grantor or '—'} → {i.grantee or '—'} | "
              f"BK {i.book or '—'} PG {i.page or '—'} | "
              f"{i.date_recorded or i.date_instr or '—'}")


def _save_json(result: dict) -> None:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(result, indent=2, default=str))
        log.info("CHAIN results saved → %s", JSON_OUT)
        _note(f"JSON: {JSON_OUT}")
    except Exception as e:
        log.warning("Could not save JSON: %s", e)


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[CHAIN] {msg}\n")
    except Exception:
        pass


def _build_result(instruments, gaps, errors, legal_desc, status) -> dict:
    return {
        "agent":       "CHAIN",
        "status":      status,
        "count":       len(instruments),
        "instruments": [
            {"seq": i.seq, "type": i.inst_type, "grantor": i.grantor,
             "grantee": i.grantee, "book": i.book, "page": i.page,
             "date_recorded": i.date_recorded, "date_instr": i.date_instr,
             "description": i.description, "doc_url": i.doc_url, "notes": i.notes}
            for i in instruments
        ],
        "gaps":        gaps,
        "errors":      errors,
        "legal_desc":  legal_desc,
    }
