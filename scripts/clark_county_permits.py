"""
Clark County NV – New Residential Building Permit Scraper
Pulls permits from the Accela public portal using raw HTTP only (no browser/Playwright).
Groups by ZIP, flags activity level, pushes results to Airtable.

Requirements: pip install httpx
Usage:        python clark_county_permits.py
"""

import httpx
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta, datetime

# ── Config ────────────────────────────────────────────────────────────────────
# Set these env vars before running:
#   export AIRTABLE_API_KEY=pat05vgLOgpayULeQ...
#   export AIRTABLE_BASE_ID=appGtDvO4grC0iv4V
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appGtDvO4grC0iv4V")

if not AIRTABLE_API_KEY:
    sys.exit("ERROR: Set the AIRTABLE_API_KEY environment variable before running.")
TABLE_NAME       = "Permit Activity"
MARKET           = "Las Vegas NV"
PERIOD           = "Last 90 Days"
TODAY            = date.today().isoformat()

# Accela public portal for Clark County NV
# Endpoint: Citizen Access / Open Data API (no auth required)
ACCELA_BASE      = "https://aca3.accela.com/clarkcountynv"
ACCELA_SEARCH    = f"{ACCELA_BASE}/Cap/CapHome.aspx"

LOOKBACK_DAYS    = 90
HOT_THRESHOLD    = 10
WARM_THRESHOLD   = 5

# ── Step 1: Verify Airtable connection ────────────────────────────────────────

def verify_airtable(client: httpx.Client) -> dict:
    """Verify base exists and return table name → table-id mapping."""
    print("\n[Step 1] Verifying Airtable connection…")
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

    r = client.get(
        f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()

    tables = {t["name"]: t["id"] for t in r.json().get("tables", [])}
    expected = {"Permit Feeds", "Permit Activity", "Acquisition Targets"}
    found    = set(tables.keys())
    missing  = expected - found

    print(f"  Base:   AMARA Permit Intelligence ({AIRTABLE_BASE_ID})")
    print(f"  Tables: {sorted(found)}")

    if missing:
        print(f"  WARNING – missing tables: {missing}")
    else:
        print("  All 3 required tables confirmed.")

    return tables


# ── Step 2: Pull permits from Accela (raw HTTP) ───────────────────────────────

def _get_session_tokens(client: httpx.Client) -> dict:
    """
    Fetch the Accela search page and extract ASP.NET session tokens
    (__VIEWSTATE, __EVENTVALIDATION, etc.) needed for the POST.
    """
    r = client.get(
        ACCELA_SEARCH,
        params={"module": "Building", "TabName": "BuildingPermits"},
        timeout=30,
        follow_redirects=True,
    )
    r.raise_for_status()
    html = r.text

    tokens = {}
    for field in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
                  "__RequestVerificationToken"):
        m = re.search(
            rf'<input[^>]+name="{re.escape(field)}"[^>]+value="([^"]*)"',
            html,
        )
        if m:
            tokens[field] = m.group(1)
    return tokens


def _build_date_range() -> tuple[str, str]:
    end   = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    fmt   = lambda d: d.strftime("%m/%d/%Y")
    return fmt(start), fmt(end)


def fetch_permits(client: httpx.Client) -> list[dict]:
    """
    Query the Accela Citizen Access portal for NEW RESIDENTIAL building
    permits filed in Clark County NV in the last 90 days.

    Accela exposes two interfaces we can try without login:
      1. The HTML form search (ASP.NET postback) – primary
      2. The Accela Open Data / REST endpoint (if enabled) – fallback

    Returns a list of permit dicts with keys:
        permit_number, filed_date, description, builder, address, zip_code
    """
    print("\n[Step 2] Pulling permits from Accela public portal…")
    start_date, end_date = _build_date_range()
    print(f"  Date range: {start_date} → {end_date}")

    permits = []

    # ── Attempt A: Accela REST / Open Data API (no auth, if available) ────────
    # Some Accela deployments expose /api/v4/records
    try:
        permits = _fetch_via_rest(client, start_date, end_date)
        if permits:
            print(f"  REST API returned {len(permits)} permits.")
            return permits
    except Exception as exc:
        print(f"  REST API unavailable ({exc}), falling back to form search…")

    # ── Attempt B: ASP.NET form POST ──────────────────────────────────────────
    try:
        permits = _fetch_via_form(client, start_date, end_date)
        if permits:
            print(f"  Form search returned {len(permits)} permits.")
            return permits
    except Exception as exc:
        print(f"  Form search failed ({exc}).")

    print("  WARNING: No permits retrieved. Returning empty list.")
    return permits


def _fetch_via_rest(client: httpx.Client, start_date: str, end_date: str) -> list[dict]:
    """
    Accela Open Data REST API pattern used by many county deployments.
    Endpoint: GET /api/v4/records
    """
    base_url = "https://apis.accela.com/v4/records"
    params = {
        "agency":      "CLARKCOUNTYNV",
        "type":        "Building/Building Permit/NA/NA",
        "status":      "Issued",
        "openedDateFrom": start_date,
        "openedDateTo":   end_date,
        "limit":       1000,
        "offset":      0,
        "lang":        "en",
    }
    permits = []
    while True:
        r = client.get(base_url, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        data = r.json()
        records = data.get("result", [])
        for rec in records:
            permits.append(_normalize_rest_record(rec))
        if len(records) < params["limit"]:
            break
        params["offset"] += params["limit"]
    return permits


def _normalize_rest_record(rec: dict) -> dict:
    addr   = rec.get("addresses", [{}])[0]
    zip_   = addr.get("postalCode", "").strip()[:5]
    desc   = rec.get("type", {}).get("text", "")
    return {
        "permit_number": rec.get("id", ""),
        "filed_date":    rec.get("openedDate", "")[:10],
        "description":   desc,
        "builder":       rec.get("applicant", {}).get("fullName", ""),
        "address":       f"{addr.get('streetStart','')} {addr.get('streetName','')}".strip(),
        "zip_code":      zip_,
    }


def _fetch_via_form(client: httpx.Client, start_date: str, end_date: str) -> list[dict]:
    """
    POST to the Accela Citizen Access ASP.NET search form.
    Parses the HTML results table.
    """
    tokens = _get_session_tokens(client)

    # Build the search POST payload
    payload = {
        "__EVENTTARGET":   "ctl00$PlaceHolderMain$btnNewSearch",
        "__EVENTARGUMENT": "",
        "ctl00$PlaceHolderMain$generalSearchForm$ddlGSPermitType": "Building Permit",
        "ctl00$PlaceHolderMain$generalSearchForm$txtGSStartDate":  start_date,
        "ctl00$PlaceHolderMain$generalSearchForm$txtGSEndDate":    end_date,
        "ctl00$PlaceHolderMain$generalSearchForm$txtGSPermitNumber": "",
        "ctl00$PlaceHolderMain$generalSearchForm$txtGSProjectName":  "",
        **tokens,
    }

    r = client.post(
        ACCELA_SEARCH,
        data=payload,
        timeout=60,
        follow_redirects=True,
    )
    r.raise_for_status()
    return _parse_results_table(r.text)


def _parse_results_table(html: str) -> list[dict]:
    """Extract permit rows from the Accela search results HTML table."""
    permits = []
    # Find all rows in the results grid
    row_pattern = re.compile(
        r'<tr[^>]*class="[^"]*ACA_TabRow[^"]*"[^>]*>(.*?)</tr>',
        re.DOTALL | re.IGNORECASE,
    )
    cell_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
    tag_pattern  = re.compile(r'<[^>]+>')

    for row_m in row_pattern.finditer(html):
        cells = [
            tag_pattern.sub("", c.group(1)).strip()
            for c in cell_pattern.finditer(row_m.group(1))
        ]
        if len(cells) < 4:
            continue
        # Typical columns: Permit #, Type, Project Name, Address, Filed Date, Status
        permit = {
            "permit_number": cells[0] if len(cells) > 0 else "",
            "description":   cells[1] if len(cells) > 1 else "",
            "address":       cells[3] if len(cells) > 3 else "",
            "filed_date":    cells[4] if len(cells) > 4 else "",
            "builder":       "",
            "zip_code":      _extract_zip(cells[3] if len(cells) > 3 else ""),
        }
        permits.append(permit)

    return permits


def _extract_zip(address: str) -> str:
    m = re.search(r'\b(8[89]\d{3}|89\d{3})\b', address)
    return m.group(1) if m else ""


# ── Step 3: Filter NEW RESIDENTIAL, group by ZIP ──────────────────────────────

def filter_residential(permits: list[dict]) -> list[dict]:
    """Keep only permits that look like new residential construction."""
    keywords = re.compile(
        r'(new\s+res|single.?family|sfr|duplex|townhome|townhouse|residential|nsfr)',
        re.IGNORECASE,
    )
    if not permits:
        return permits
    filtered = [p for p in permits if keywords.search(p.get("description", ""))]
    print(f"\n[Step 3] {len(permits)} total → {len(filtered)} residential after filter")
    return filtered


def group_by_zip(permits: list[dict]) -> list[dict]:
    """
    Group permits by ZIP code.
    Returns list of dicts ready for Airtable insertion.
    """
    zip_map: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "builders": set()
    })
    for p in permits:
        z = p.get("zip_code", "").strip()
        if not z:
            z = "UNKNOWN"
        zip_map[z]["count"] += 1
        if p.get("builder"):
            zip_map[z]["builders"].add(p["builder"])

    results = []
    for zip_code, info in sorted(zip_map.items(), key=lambda x: -x[1]["count"]):
        count = info["count"]
        if count >= HOT_THRESHOLD:
            flag = "Hot"
        elif count >= WARM_THRESHOLD:
            flag = "Warm"
        else:
            flag = "Cold"

        results.append({
            "zip_code":     zip_code,
            "permit_count": count,
            "builders":     ", ".join(sorted(info["builders"])) or "N/A",
            "flag":         flag,
        })

    print(f"  Grouped into {len(results)} ZIP codes")
    return results


# ── Step 4: Push to Airtable ──────────────────────────────────────────────────

def _get_table_fields(client: httpx.Client) -> dict:
    """Return field name → field id mapping for Permit Activity table."""
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    r = client.get(
        f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    for t in r.json().get("tables", []):
        if t["name"] == TABLE_NAME:
            return {f["name"]: f["id"] for f in t.get("fields", [])}
    return {}


def push_to_airtable(client: httpx.Client, zip_results: list[dict], table_id: str) -> int:
    """Batch-insert all ZIP records into Airtable. Returns count of records created."""
    print(f"\n[Step 4] Pushing {len(zip_results)} records to Airtable…")

    if not zip_results:
        print("  Nothing to push.")
        return 0

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type":  "application/json",
    }

    # Airtable allows 10 records per request
    BATCH = 10
    created = 0

    for i in range(0, len(zip_results), BATCH):
        batch = zip_results[i : i + BATCH]
        records = []
        for row in batch:
            records.append({
                "fields": {
                    "ZIP Code":     row["zip_code"],
                    "Market":       MARKET,
                    "Permit Count": row["permit_count"],
                    "Period":       PERIOD,
                    "Builder Names": row["builders"],
                    "Pull Date":    TODAY,
                    "Flag":         row["flag"],
                }
            })
        payload = {"records": records, "typecast": True}

        r = client.post(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}",
            headers=headers,
            content=json.dumps(payload),
            timeout=30,
        )

        if r.status_code in (200, 201):
            batch_created = len(r.json().get("records", []))
            created += batch_created
            print(f"  Batch {i // BATCH + 1}: {batch_created} records written")
        else:
            print(f"  Batch {i // BATCH + 1} ERROR {r.status_code}: {r.text[:200]}")

    return created


# ── Step 5: Print Hot ZIPs ────────────────────────────────────────────────────

def print_hot_zips(zip_results: list[dict]) -> None:
    hot = [z for z in zip_results if z["flag"] == "Hot"]
    print(f"\n{'='*60}")
    print(f"  HOT ZIP CODES — {MARKET} (Last 90 Days)")
    print(f"{'='*60}")
    if not hot:
        print("  No Hot ZIPs found (< {HOT_THRESHOLD} permits threshold).")
    else:
        print(f"  {'ZIP Code':<12} {'Permits':>8}   Builders")
        print(f"  {'-'*55}")
        for z in sorted(hot, key=lambda x: -x["permit_count"]):
            builders = z["builders"]
            if len(builders) > 50:
                builders = builders[:47] + "…"
            print(f"  {z['zip_code']:<12} {z['permit_count']:>8}   {builders}")
    print(f"{'='*60}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Clark County NV Residential Permit Intelligence")
    print(f"Run date: {TODAY}")

    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (AMARA Permit Intelligence)"},
        follow_redirects=True,
    ) as client:

        # Step 1 – Verify Airtable
        tables = verify_airtable(client)
        permit_activity_id = tables.get(TABLE_NAME)
        if not permit_activity_id:
            raise RuntimeError(f"Table '{TABLE_NAME}' not found in base.")

        # Step 2 – Fetch permits
        raw_permits = fetch_permits(client)

        # Step 3 – Filter residential, group by ZIP
        residential = filter_residential(raw_permits)
        zip_results  = group_by_zip(residential)

        # Print summary before push
        warm = sum(1 for z in zip_results if z["flag"] == "Warm")
        hot  = sum(1 for z in zip_results if z["flag"] == "Hot")
        cold = sum(1 for z in zip_results if z["flag"] == "Cold")
        print(f"\n  ZIP summary → Hot: {hot}  Warm: {warm}  Cold: {cold}")

        # Step 4 – Push to Airtable
        created = push_to_airtable(client, zip_results, permit_activity_id)
        print(f"\n  Total records landed in Airtable: {created}")

        # Step 5 – Print Hot ZIPs
        print_hot_zips(zip_results)

        print(f"Done. {created}/{len(zip_results)} records confirmed in '{TABLE_NAME}'.")


if __name__ == "__main__":
    main()
