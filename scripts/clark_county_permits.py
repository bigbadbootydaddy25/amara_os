"""
Clark County NV – Residential Building Permit Scraper (Playwright)
==================================================================
Drives the Accela Citizen Access portal at aca.clarkcountynv.gov.
No login required — uses the public permit search.

Filters: Building Permits, New Residential, last 90 days.
Groups by ZIP, flags Hot/Warm/Cold, pushes to Airtable.

Requirements:
    pip3 install playwright httpx
    playwright install chromium

Usage:
    export AIRTABLE_API_KEY=pat05vgLOgpayULeQ...
    python3 scripts/clark_county_permits.py
"""

import asyncio
import httpx
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

# ── Config ────────────────────────────────────────────────────────────────────

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = "appGtDvO4grC0iv4V"
AIRTABLE_TABLE   = "Permit Activity"
MARKET           = "Las Vegas NV"
PERIOD           = "Last 90 Days"
TODAY            = date.today().isoformat()
LOOKBACK_DAYS    = 90
HOT_THRESHOLD    = 10
WARM_THRESHOLD   = 5

PORTAL_URL = "https://aca.clarkcountynv.gov/CitizenAccess/Cap/CapHome.aspx?module=Building&TabName=Building"

if not AIRTABLE_API_KEY:
    sys.exit("ERROR: set AIRTABLE_API_KEY env var before running.")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _flag(count: int) -> str:
    if count >= HOT_THRESHOLD:
        return "Hot"
    if count >= WARM_THRESHOLD:
        return "Warm"
    return "Cold"


RESIDENTIAL_RE = re.compile(
    r"(new\s*res|single.?famil|sfr|duplex|townhome|townhouse|"
    r"residential|nsfr|detached|1.unit|one.unit|r-1|r1\b)",
    re.I,
)


def _looks_residential(text: str) -> bool:
    return bool(RESIDENTIAL_RE.search(text or ""))


def _extract_zip(text: str) -> str:
    m = re.search(r"\b(89\d{3})\b", text or "")
    return m.group(1) if m else ""


def _date_range() -> tuple[str, str]:
    end   = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    fmt   = lambda d: d.strftime("%m/%d/%Y")
    return fmt(start), fmt(end)


# ── Step 1: Verify Airtable ───────────────────────────────────────────────────

def verify_airtable(client: httpx.Client) -> tuple[str, dict]:
    print("\n[Step 1] Verifying Airtable connection…")
    r = client.get(
        f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
        headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}"},
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"Airtable auth failed {r.status_code}: {r.text[:300]}")

    all_tables  = r.json().get("tables", [])
    table_names = {t["name"] for t in all_tables}
    expected    = {"Permit Feeds", "Permit Activity", "Acquisition Targets"}
    missing     = expected - table_names

    print(f"  Base:   AMARA Permit Intelligence ({AIRTABLE_BASE_ID})")
    print(f"  Tables: {sorted(table_names)}")
    print("  All 3 required tables confirmed ✓" if not missing
          else f"  WARNING – missing: {missing}")

    target = next((t for t in all_tables if t["name"] == AIRTABLE_TABLE), None)
    if not target:
        sys.exit(f"ERROR: '{AIRTABLE_TABLE}' not found in base.")

    fields = {f["name"]: f["id"] for f in target.get("fields", [])}
    print(f"  '{AIRTABLE_TABLE}' fields: {sorted(fields.keys())}")
    return target["id"], fields


# ── Step 2: Playwright scrape ─────────────────────────────────────────────────

async def scrape_permits() -> list[dict]:
    start_date, end_date = _date_range()
    print(f"\n[Step 2] Playwright → aca.clarkcountynv.gov")
    print(f"  Date range: {start_date} → {end_date}")

    permits: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx     = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        try:
            # ── 2.1  Load search page ─────────────────────────────────────────
            print("  Loading portal…")
            await page.goto(PORTAL_URL, wait_until="networkidle", timeout=60_000)
            await page.wait_for_timeout(1500)

            # ── 2.2  Fill search form ─────────────────────────────────────────
            print("  Filling search form…")

            # Permit type: try a dropdown or text field
            for sel in [
                "select[id*='PermitType'], select[id*='permitType'], select[name*='PermitType']",
                "#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType",
            ]:
                if await page.locator(sel).count() > 0:
                    await page.locator(sel).first.select_option(
                        label=re.compile(r"building permit", re.I)
                    )
                    break

            # Start date
            for sel in [
                "#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
                "input[id*='StartDate'], input[id*='startDate'], input[name*='StartDate']",
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.fill(start_date)
                    break

            # End date
            for sel in [
                "#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
                "input[id*='EndDate'], input[id*='endDate'], input[name*='EndDate']",
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.fill(end_date)
                    break

            # ── 2.3  Submit search ────────────────────────────────────────────
            print("  Submitting search…")
            for sel in [
                "#ctl00_PlaceHolderMain_btnNewSearch",
                "input[id*='btnNewSearch'], input[value*='Search'], button[id*='Search']",
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.click()
                    break

            await page.wait_for_load_state("networkidle", timeout=30_000)
            await page.wait_for_timeout(1500)

            # ── 2.4  Paginate and extract ─────────────────────────────────────
            page_num = 1
            while True:
                print(f"  Parsing results page {page_num}…")
                new_permits = await _extract_page(page)
                permits.extend(new_permits)
                print(f"    {len(new_permits)} permits found (total: {len(permits)})")

                # Look for a "Next" pagination link
                next_sel = (
                    "a[id*='lbtnNext'], "
                    "a:has-text('Next'), "
                    "a[title='Next page'], "
                    ".aca_pagination a:last-child"
                )
                next_link = page.locator(next_sel).first
                if await next_link.count() == 0:
                    break
                # Check it isn't disabled
                classes = await next_link.get_attribute("class") or ""
                if "disabled" in classes.lower():
                    break
                await next_link.click()
                await page.wait_for_load_state("networkidle", timeout=20_000)
                await page.wait_for_timeout(1000)
                page_num += 1

        except PWTimeout as e:
            print(f"  Timeout: {e}")
        except Exception as e:
            print(f"  Error: {e}")
            # Dump a screenshot for debugging
            try:
                await page.screenshot(path="/tmp/clark_county_debug.png", full_page=True)
                print("  Debug screenshot saved to /tmp/clark_county_debug.png")
            except Exception:
                pass
        finally:
            await browser.close()

    print(f"  Total permits scraped: {len(permits)}")
    return permits


async def _extract_page(page: Page) -> list[dict]:
    """
    Extract all permit rows from the current results page.
    Accela renders results in a table with class ACA_Grid_Caption or similar.
    """
    permits: list[dict] = []

    # Wait for results table
    try:
        await page.wait_for_selector(
            "table.ACA_Grid_Caption, table[id*='GridView'], .aca_grid table",
            timeout=10_000,
        )
    except PWTimeout:
        # No results table — check for "no records" message
        body = await page.inner_text("body")
        if re.search(r"no record|0 record|no result", body, re.I):
            print("    (no results on this page)")
        return permits

    # Extract rows
    rows = await page.query_selector_all(
        "table.ACA_Grid_Caption tr, table[id*='GridView'] tr, .aca_grid table tr"
    )

    header: list[str] = []
    for row in rows:
        cells = await row.query_selector_all("th, td")
        texts = [
            (await c.inner_text()).strip().replace("\n", " ")
            for c in cells
        ]
        texts = [t for t in texts if t]
        if not texts:
            continue

        # Detect header row
        if not header and any(
            kw in " ".join(texts).lower()
            for kw in ("permit", "type", "address", "status", "date")
        ):
            header = [t.lower() for t in texts]
            continue

        if not header or len(texts) < 2:
            continue

        row_dict = dict(zip(header, texts))

        # Map to normalised fields
        permit_num  = _first(row_dict, "permit #", "permit number", "permit no", "record number", "permit")
        description = _first(row_dict, "description", "type", "permit type", "work type")
        address     = _first(row_dict, "address", "project address", "location")
        filed_date  = _first(row_dict, "filed date", "date filed", "open date", "issue date", "date")
        status      = _first(row_dict, "status")
        contractor  = _first(row_dict, "contractor", "applicant", "owner", "builder")

        zip_code = _extract_zip(address or "")

        # If no ZIP in address, try clicking through to detail page
        if not zip_code and address:
            zip_code = _extract_zip(str(row_dict))

        permits.append({
            "permit_number": permit_num or "",
            "description":   description or "",
            "address":       address or "",
            "filed_date":    filed_date or "",
            "status":        status or "",
            "builder":       contractor or "",
            "zip_code":      zip_code,
        })

    return permits


def _first(d: dict, *keys: str) -> str:
    """Return the first dict value whose key contains any of the given substrings."""
    for k, v in d.items():
        for key in keys:
            if key in k:
                return v
    return ""


# ── Step 3: Filter residential + group by ZIP ─────────────────────────────────

def group_by_zip(permits: list[dict]) -> list[dict]:
    residential = [p for p in permits if _looks_residential(p.get("description", ""))]

    if not residential and permits:
        print("  Keyword filter matched 0 — using all records (portal may pre-filter to building permits)")
        residential = permits

    print(f"\n[Step 3] {len(permits)} scraped → {len(residential)} residential")

    zip_map: dict[str, dict] = defaultdict(lambda: {"count": 0, "builders": set()})
    for p in residential:
        z = p.get("zip_code", "").strip() or "UNKNOWN"
        zip_map[z]["count"] += 1
        b = p.get("builder", "").strip()
        if b:
            zip_map[z]["builders"].add(b)

    rows = []
    for z, info in sorted(zip_map.items(), key=lambda x: -x[1]["count"]):
        count = info["count"]
        rows.append({
            "zip_code":     z,
            "permit_count": count,
            "builders":     ", ".join(sorted(info["builders"])) or "N/A",
            "flag":         _flag(count),
        })

    hot  = sum(1 for r in rows if r["flag"] == "Hot")
    warm = sum(1 for r in rows if r["flag"] == "Warm")
    cold = sum(1 for r in rows if r["flag"] == "Cold")
    print(f"  → {len(rows)} ZIPs   Hot: {hot}  Warm: {warm}  Cold: {cold}")
    return rows


# ── Step 4: Push to Airtable ──────────────────────────────────────────────────

FIELD_ALIASES = {
    "ZIP Code":      ["ZIP Code", "Zip Code", "ZIP", "Zip"],
    "Market":        ["Market", "Market Name", "Region"],
    "Permit Count":  ["Permit Count", "Count", "Number of Permits"],
    "Period":        ["Period", "Time Period", "Date Range"],
    "Builder Names": ["Builder Names", "Builders", "Builder", "Contractor"],
    "Pull Date":     ["Pull Date", "Date Pulled", "Run Date", "Date"],
    "Flag":          ["Flag", "Activity Flag", "Heat Flag", "Status"],
}


def _resolve_fields(airtable_fields: dict) -> dict:
    lower_map = {k.lower(): v for k, v in airtable_fields.items()}
    resolved  = {}
    for logical, candidates in FIELD_ALIASES.items():
        for c in candidates:
            fid = airtable_fields.get(c) or lower_map.get(c.lower())
            if fid:
                resolved[logical] = fid
                break
        if logical not in resolved:
            resolved[logical] = logical
    return resolved


def push_to_airtable(
    client: httpx.Client,
    rows: list[dict],
    table_id: str,
    airtable_fields: dict,
) -> int:
    print(f"\n[Step 4] Pushing {len(rows)} records → '{AIRTABLE_TABLE}'…")
    if not rows:
        print("  Nothing to push.")
        return 0

    field_map  = _resolve_fields(airtable_fields)
    at_headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type":  "application/json",
    }

    def _record(row: dict) -> dict:
        return {"fields": {
            field_map["ZIP Code"]:      row["zip_code"],
            field_map["Market"]:        MARKET,
            field_map["Permit Count"]:  row["permit_count"],
            field_map["Period"]:        PERIOD,
            field_map["Builder Names"]: row["builders"],
            field_map["Pull Date"]:     TODAY,
            field_map["Flag"]:          row["flag"],
        }}

    BATCH   = 10
    created = 0

    for i in range(0, len(rows), BATCH):
        batch   = rows[i : i + BATCH]
        payload = {"records": [_record(r) for r in batch], "typecast": True}
        resp    = client.post(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}",
            headers=at_headers,
            content=json.dumps(payload),
            timeout=30,
        )
        n = i // BATCH + 1
        if resp.status_code in (200, 201):
            written  = len(resp.json().get("records", []))
            created += written
            print(f"  Batch {n}: {written} records written ✓")
        else:
            print(f"  Batch {n} FAILED {resp.status_code}: {resp.text[:300]}")

    return created


# ── Step 5: Summary ───────────────────────────────────────────────────────────

def print_summary(rows: list[dict], created: int) -> None:
    hot_rows = [r for r in rows if r["flag"] == "Hot"]

    print(f"\n{'='*64}")
    print(f"  CLARK COUNTY NV — RESIDENTIAL PERMIT SUMMARY")
    print(f"  Source: aca.clarkcountynv.gov  |  Run: {TODAY}")
    print(f"  Period: {PERIOD}  |  Airtable records: {created}/{len(rows)}")
    print(f"{'='*64}")
    print(f"\n  HOT ZIP CODES  (≥{HOT_THRESHOLD} permits)")
    print(f"  {'─'*58}")

    if not hot_rows:
        print(f"  None at ≥{HOT_THRESHOLD} threshold.")
    else:
        print(f"  {'ZIP':<10} {'Permits':>8}   Builders")
        print(f"  {'─'*55}")
        for r in sorted(hot_rows, key=lambda x: -x["permit_count"]):
            b = r["builders"][:46] + ("…" if len(r["builders"]) > 46 else "")
            print(f"  {r['zip_code']:<10} {r['permit_count']:>8}   {b}")

    print(f"{'='*64}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

async def _async_main() -> None:
    print("Clark County NV Residential Permit Intelligence (Playwright)")
    print(f"Run date: {TODAY}  |  Portal: aca.clarkcountynv.gov")

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        table_id, airtable_fields = verify_airtable(client)
        raw_permits               = await scrape_permits()

        if not raw_permits:
            print("\nERROR: No permits scraped.")
            print("Check /tmp/clark_county_debug.png for a screenshot of what the browser saw.")
            sys.exit(1)

        zip_rows = group_by_zip(raw_permits)
        created  = push_to_airtable(client, zip_rows, table_id, airtable_fields)
        print_summary(zip_rows, created)
        print(f"Done. {created}/{len(zip_rows)} ZIP records confirmed in Airtable '{AIRTABLE_TABLE}'.")


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
