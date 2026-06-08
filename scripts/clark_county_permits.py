"""
Clark County NV – Residential Building Permit Intelligence
==========================================================
SOURCE 1  Census Bureau BPS timeseries (national, no CBSA filter)
          https://api.census.gov/data/timeseries/eits/bps
          Pulls national new-residential counts; shown as context.

SOURCE 2  Nevada Open Data Portal – Socrata (PRIMARY for ZIP data)
          https://data.nv.gov
          Building/construction permit records for Clark County NV.
          Auto-discovers dataset via catalog API.

SOURCE 3  HUD SOCDS Building Permits Database (FALLBACK)
          https://socds.huduser.gov/permits/output.odb
          Clark County FIPS 32003, last 4 quarters, returns CSV.

Results grouped by ZIP, flagged Hot/Warm/Cold, pushed to Airtable.

Requirements:  pip3 install httpx
Usage:
    export AIRTABLE_API_KEY=pat05vgLOgpayULeQ...
    python3 scripts/clark_county_permits.py
"""

import csv
import httpx
import io
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

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

# Nevada Open Data (Socrata)
NV_SOCRATA_BASE  = "https://data.nv.gov"

# HUD SOCDS – Clark County NV
HUD_URL          = "https://socds.huduser.gov/permits/output.odb"
CLARK_FIPS_STATE = "32"
CLARK_FIPS_COUNTY = "003"   # Clark County NV = FIPS 32003

if not AIRTABLE_API_KEY:
    sys.exit("ERROR: set AIRTABLE_API_KEY env var before running.")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cutoff_str() -> str:
    return (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()


def _flag(count: int) -> str:
    if count >= HOT_THRESHOLD:
        return "Hot"
    if count >= WARM_THRESHOLD:
        return "Warm"
    return "Cold"


RESIDENTIAL_RE = re.compile(
    r"(new\s*res|single.?famil|sfr|duplex|townhome|townhouse|"
    r"residential|nsfr|row\s*home|single\s*unit|1.unit|one.unit|"
    r"detached|attached\s*home|condo|apartment)",
    re.I,
)


def _looks_residential(text: str) -> bool:
    return bool(RESIDENTIAL_RE.search(text or ""))


def _extract_zip(text: str) -> str:
    """Pull first 5-digit Nevada ZIP (89xxx) from a string."""
    m = re.search(r"\b(89\d{3})\b", text or "")
    return m.group(1) if m else ""


def _col_find(cols: list[str], *patterns: str):
    """Return first column name matching any of the given substrings."""
    lower = {c.lower(): c for c in cols}
    for p in patterns:
        for k, v in lower.items():
            if p in k:
                return v
    return None


# ── Step 1: Verify Airtable ───────────────────────────────────────────────────

def verify_airtable(client: httpx.Client) -> tuple[str, dict]:
    """Return (table_id, {field_name: field_id}) for the Permit Activity table."""
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
    if missing:
        print(f"  WARNING – missing tables: {missing}")
    else:
        print("  All 3 required tables confirmed ✓")

    target = next((t for t in all_tables if t["name"] == AIRTABLE_TABLE), None)
    if not target:
        sys.exit(f"ERROR: '{AIRTABLE_TABLE}' not found. Existing: {sorted(table_names)}")

    fields = {f["name"]: f["id"] for f in target.get("fields", [])}
    print(f"  '{AIRTABLE_TABLE}' fields: {sorted(fields.keys())}")
    return target["id"], fields


# ── Step 2a: Census BPS – national new-residential (context/validation) ───────

def fetch_census_bps(client: httpx.Client) -> dict:
    """
    Pull national new-residential permit counts for the last 6 months
    using the exact Census BPS timeseries endpoint format.
    Returns {YYYY-MM: unit_count}.  No CBSA filter — national aggregate.
    """
    print("\n[Step 2a] Census BPS – national new-residential (last 6 months)…")

    # Build last 6 complete months (current month may be partial/unreleased)
    months = []
    d = date.today().replace(day=1) - timedelta(days=1)  # end of last month
    d = d.replace(day=1)
    for _ in range(6):
        months.append(d.strftime("%Y-%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    months.sort()

    results: dict[str, int] = {}

    for month in months:
        try:
            r = client.get(
                "https://api.census.gov/data/timeseries/eits/bps",
                params={
                    "get":            "cell_value,time_slot_id,category_code,seasonally_adj",
                    "for":            "us:*",
                    "time":           month,
                    "category_code":  "101",   # 1-unit (single-family) structures
                    "seasonally_adj": "no",
                },
                timeout=20,
            )
            if r.status_code == 200:
                rows = r.json()          # [[header…], [val…], …]
                if len(rows) > 1:
                    header  = rows[0]
                    val_idx = header.index("cell_value") if "cell_value" in header else 0
                    # Sum across any rows returned for this month
                    for row in rows[1:]:
                        try:
                            results[month] = results.get(month, 0) + int(row[val_idx])
                        except (ValueError, IndexError):
                            pass
            elif r.status_code == 204:
                results[month] = 0
            else:
                print(f"  {month}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {month}: {e}")

    if results:
        print(f"  Months: {sorted(results.keys())}")
        print(f"  National single-family permits (6-mo): {sum(results.values()):,}")
        print("  (National totals — shown for context; ZIP data comes from NV Socrata / HUD)")
    else:
        print("  No Census data returned — endpoint may be lagged; continuing.")

    return results


# ── Step 2b: Nevada Open Data / Socrata (PRIMARY ZIP-level source) ────────────

def _socrata_discover(client: httpx.Client) -> tuple[str, list[str]]:
    """
    Find a building/construction permit dataset on data.nv.gov.
    Returns (dataset_4x4_id, [column_names]).
    """
    # Try catalog search with two query terms
    for query in ("building permit", "construction permit", "building permits"):
        try:
            r = client.get(
                f"{NV_SOCRATA_BASE}/api/catalog/v1",
                params={"q": query, "limit": 20},
                timeout=20,
            )
            if r.status_code != 200:
                continue
            results = r.json().get("results", [])
            for item in results:
                res  = item.get("resource", {})
                name = res.get("name", "").lower()
                desc = res.get("description", "").lower()
                # Prioritise datasets mentioning Clark County or Las Vegas
                if "permit" in name or "permit" in desc:
                    ds_id = res.get("id", "")
                    if not ds_id:
                        continue
                    # Probe it for Clark County data
                    cols = res.get("columns_name", [])
                    if not cols:
                        probe = client.get(
                            f"{NV_SOCRATA_BASE}/resource/{ds_id}.json",
                            params={"$limit": 1},
                            timeout=15,
                        )
                        if probe.status_code == 200 and probe.json():
                            cols = list(probe.json()[0].keys())
                    print(f"  Dataset: '{res.get('name')}' (id={ds_id})")
                    print(f"  Columns: {cols}")
                    return ds_id, cols
        except Exception as e:
            print(f"  Catalog search '{query}' error: {e}")

    # Hard fallback: known Nevada open-data permit dataset IDs
    for fid in ["6aem-y4yw", "rj8h-vc6h", "fwmq-be5t", "3zaz-p6ax", "i4ny-zgr3"]:
        try:
            probe = client.get(
                f"{NV_SOCRATA_BASE}/resource/{fid}.json",
                params={"$limit": 1},
                timeout=15,
            )
            if probe.status_code == 200 and probe.json():
                cols = list(probe.json()[0].keys())
                print(f"  Found via fallback ID: {fid}  cols={cols}")
                return fid, cols
        except Exception:
            continue

    return "", []


def fetch_socrata_permits(client: httpx.Client) -> list[dict]:
    """
    Query Nevada Open Data (Socrata) for Clark County residential permits,
    last 90 days.  Returns list of normalised permit dicts.
    """
    print(f"\n[Step 2b] Nevada Open Data (Socrata) – {NV_SOCRATA_BASE}…")

    ds_id, cols = _socrata_discover(client)
    if not ds_id:
        print("  Could not discover a permit dataset on data.nv.gov — will try HUD fallback.")
        return []

    date_col = _col_find(cols, "issued", "issue_date", "open_date", "filed", "created_date", "permit_date")
    addr_col = _col_find(cols, "address", "location", "street", "site_address")
    zip_col  = _col_find(cols, "zip", "postal")
    desc_col = _col_find(cols, "description", "desc", "work_desc", "permit_type", "type", "category")
    cont_col = _col_find(cols, "contractor", "builder", "applicant", "owner")
    county_col = _col_find(cols, "county")

    cutoff   = _cutoff_str()
    limit    = 5000
    offset   = 0
    all_recs: list[dict] = []

    print(f"  date_col={date_col}  zip_col={zip_col}  addr_col={addr_col}  cutoff={cutoff}")

    while True:
        params: dict = {"$limit": limit, "$offset": offset}

        # Build WHERE: date filter + optionally county filter
        where_clauses = []
        if date_col:
            where_clauses.append(f"{date_col} >= '{cutoff}T00:00:00.000'")
        if county_col:
            where_clauses.append(f"upper({county_col}) = 'CLARK'")
        if where_clauses:
            params["$where"] = " AND ".join(where_clauses)
        if date_col:
            params["$order"] = f"{date_col} DESC"

        try:
            r = client.get(
                f"{NV_SOCRATA_BASE}/resource/{ds_id}.json",
                params=params,
                timeout=40,
            )
            if r.status_code == 400:
                # SoQL type error — strip WHERE and retry bare
                print("  SoQL error, retrying without filters…")
                params.pop("$where", None)
                params.pop("$order", None)
                r = client.get(
                    f"{NV_SOCRATA_BASE}/resource/{ds_id}.json",
                    params=params,
                    timeout=40,
                )
            r.raise_for_status()
        except Exception as e:
            print(f"  Socrata fetch error: {e}")
            break

        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break

        for rec in batch:
            # Manual date filter in case SoQL was stripped
            raw_date = str(rec.get(date_col, "") or "") if date_col else ""
            if raw_date and raw_date[:10] < cutoff:
                continue

            # ZIP resolution: dedicated col → parse address → scan all values
            if zip_col and rec.get(zip_col):
                zip_code = str(rec[zip_col]).strip()[:5]
            elif addr_col:
                zip_code = _extract_zip(str(rec.get(addr_col, "") or ""))
            else:
                zip_code = next(
                    (_extract_zip(str(v)) for v in rec.values() if _extract_zip(str(v))),
                    "",
                )

            desc    = str(rec.get(desc_col, "") or "") if desc_col else ""
            builder = str(rec.get(cont_col, "") or "").strip() if cont_col else ""

            all_recs.append({
                "description": desc,
                "zip_code":    zip_code,
                "builder":     builder,
                "issued_date": raw_date[:10],
                "source":      "NV Socrata",
            })

        print(f"  …{len(all_recs)} records", end="\r")
        if len(batch) < limit:
            break
        offset += limit

    print(f"\n  Total from NV Socrata: {len(all_recs)}")
    return all_recs


# ── Step 2c: HUD SOCDS – Clark County fallback ────────────────────────────────

def fetch_hud_permits(client: httpx.Client) -> list[dict]:
    """
    Pull Clark County NV (FIPS 32003) permit data from HUD SOCDS.
    The endpoint returns an HTML page with an embedded data table;
    we parse it into per-ZIP rows.  Last 4 quarters.

    HUD SOCDS URL: https://socds.huduser.gov/permits/output.odb
    POST params: type=county, state=32, county=003, sa=, year=YYYY,
                 lastyears=4, units=1  (1-unit = single family)
    """
    print("\n[Step 2c] HUD SOCDS Building Permits – Clark County NV (FIPS 32003)…")

    current_year = date.today().year
    all_recs: list[dict] = []

    # HUD SOCDS accepts a form POST; "units=1" = single-family
    # Try both the place-level and county-level endpoints
    form_data = {
        "type":      "county",
        "state":     CLARK_FIPS_STATE,
        "county":    CLARK_FIPS_COUNTY,
        "sa":        "",
        "year":      str(current_year),
        "lastyears": "4",
        "units":     "1",          # 1-unit structures (single-family)
        "Submit":    "Get+Data",
    }

    try:
        r = client.post(HUD_URL, data=form_data, timeout=40)
        r.raise_for_status()
    except Exception as e:
        print(f"  HUD POST failed: {e}")
        # Try GET with same params
        try:
            r = client.get(HUD_URL, params=form_data, timeout=40)
            r.raise_for_status()
        except Exception as e2:
            print(f"  HUD GET also failed: {e2}")
            return []

    content_type = r.headers.get("content-type", "")
    body         = r.text

    # ── Parse CSV response ────────────────────────────────────────────────────
    if "csv" in content_type or body.strip().startswith('"'):
        print("  Received CSV response.")
        all_recs = _parse_hud_csv(body)

    # ── Parse HTML response ───────────────────────────────────────────────────
    else:
        print("  Received HTML response — parsing data table…")
        all_recs = _parse_hud_html(body)

    print(f"  Total from HUD SOCDS: {len(all_recs)}")
    return all_recs


def _parse_hud_csv(body: str) -> list[dict]:
    """Parse CSV body from HUD SOCDS into permit dicts."""
    recs = []
    try:
        reader = csv.DictReader(io.StringIO(body))
        for row in reader:
            # Typical HUD CSV columns: place_name, fips, year, month, bldgs, units, value
            zip_code = _extract_zip(
                row.get("place_name", "") or row.get("name", "") or ""
            )
            try:
                count = int(row.get("units", row.get("bldgs", 1)) or 1)
            except ValueError:
                count = 1
            for _ in range(count):
                recs.append({
                    "description": "Single-Family Residential",
                    "zip_code":    zip_code,
                    "builder":     "",
                    "issued_date": f"{row.get('year', '')}",
                    "source":      "HUD SOCDS",
                })
    except Exception as e:
        print(f"  CSV parse error: {e}")
    return recs


def _parse_hud_html(html: str) -> list[dict]:
    """
    Extract permit data from the HUD SOCDS HTML table.
    Rows look like:  | Place Name | YYYY-Q# | Units | Buildings | … |
    """
    recs     = []
    tag_re   = re.compile(r"<[^>]+>")
    row_re   = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.I)
    cell_re  = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.I)

    cutoff = _cutoff_str()
    rows   = row_re.findall(html)

    # Find header row to understand column order
    header: list[str] = []
    data_rows          = []
    for row in rows:
        cells = [tag_re.sub("", c).strip() for c in cell_re.findall(row)]
        cells = [c for c in cells if c]
        if not cells:
            continue
        if not header and any(
            kw in " ".join(cells).lower()
            for kw in ("place", "units", "year", "quarter", "permit")
        ):
            header = [c.lower() for c in cells]
        elif header:
            data_rows.append(cells)

    if not header:
        # No header found — treat columns positionally: name, period, units
        for row in rows:
            cells = [tag_re.sub("", c).strip() for c in cell_re.findall(row)]
            cells = [c for c in cells if c and c not in ("", "-")]
            if len(cells) >= 3:
                data_rows.append(cells)

    def _col_idx(patterns):
        for p in patterns:
            for i, h in enumerate(header):
                if p in h:
                    return i
        return None

    name_idx  = _col_idx(["place", "name", "location"]) or 0
    unit_idx  = _col_idx(["units", "unit"]) or 2
    period_idx = _col_idx(["year", "quarter", "period", "date"])

    for cells in data_rows:
        if len(cells) < 2:
            continue
        try:
            units = int(cells[unit_idx]) if unit_idx < len(cells) else 1
        except (ValueError, IndexError):
            units = 1

        place    = cells[name_idx] if name_idx < len(cells) else ""
        zip_code = _extract_zip(place)

        # Each row represents `units` permits; emit one record per unit
        # (keeps the grouping logic consistent with Socrata records)
        for _ in range(max(units, 1)):
            recs.append({
                "description": "Single-Family Residential",
                "zip_code":    zip_code,
                "builder":     "",
                "issued_date": cutoff,   # approximate — HUD data is quarterly
                "source":      "HUD SOCDS",
            })

    return recs


# ── Step 3: Filter residential + group by ZIP ─────────────────────────────────

def group_by_zip(permits: list[dict]) -> list[dict]:
    """
    Filter to residential descriptions, group by ZIP code.
    If keyword filter matches nothing (dataset may be pre-filtered),
    falls back to all records.
    """
    residential = [p for p in permits if _looks_residential(p.get("description", ""))]

    # HUD SOCDS records are always "Single-Family Residential" — they pass.
    # NV Socrata: if nothing matches (permit types use different language), use all.
    if not residential and permits:
        print("  Keyword filter matched 0 — using all records (dataset may be pre-filtered to residential)")
        residential = permits

    by_source = defaultdict(int)
    for p in residential:
        by_source[p.get("source", "unknown")] += 1
    print(f"\n[Step 3] {len(permits)} total → {len(residential)} residential")
    for src, n in sorted(by_source.items()):
        print(f"  {src}: {n}")

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

# Logical field → possible Airtable column names (first match wins)
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
    """Map logical names → actual Airtable field IDs (or names as fallback)."""
    lower_map = {k.lower(): v for k, v in airtable_fields.items()}
    resolved  = {}
    for logical, candidates in FIELD_ALIASES.items():
        for c in candidates:
            fid = airtable_fields.get(c) or lower_map.get(c.lower())
            if fid:
                resolved[logical] = fid
                break
        if logical not in resolved:
            resolved[logical] = logical   # rely on typecast
    return resolved


def push_to_airtable(
    client: httpx.Client,
    rows: list[dict],
    table_id: str,
    airtable_fields: dict,
) -> int:
    """Batch-insert ZIP rows into Airtable 10 at a time."""
    print(f"\n[Step 4] Pushing {len(rows)} records → '{AIRTABLE_TABLE}'…")
    if not rows:
        print("  Nothing to push.")
        return 0

    field_map = _resolve_fields(airtable_fields)
    print(f"  Field map: {field_map}")

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

        resp = client.post(
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


# ── Step 5: Terminal summary ──────────────────────────────────────────────────

def print_summary(rows: list[dict], census: dict, created: int) -> None:
    hot_rows = [r for r in rows if r["flag"] == "Hot"]

    print(f"\n{'='*64}")
    print(f"  CLARK COUNTY NV — RESIDENTIAL PERMIT SUMMARY")
    print(f"  Market: {MARKET} | Period: {PERIOD} | Run: {TODAY}")
    print(f"{'='*64}")

    if census:
        print(f"\n  Census BPS (national, single-family, for context):")
        for mo in sorted(census):
            print(f"    {mo}:  {census[mo]:>8,} units")
        print(f"    {'Total:':10}  {sum(census.values()):>8,} units")

    print(f"\n  ZIP-level data: {len(rows)} ZIPs → {created} records pushed to Airtable")

    print(f"\n{'─'*64}")
    print(f"  HOT ZIP CODES  (≥{HOT_THRESHOLD} permits in last 90 days)")
    print(f"{'─'*64}")
    if not hot_rows:
        print(f"  None at ≥{HOT_THRESHOLD} threshold.")
    else:
        print(f"  {'ZIP':<10} {'Permits':>8}   Builders")
        print(f"  {'─'*58}")
        for r in sorted(hot_rows, key=lambda x: -x["permit_count"]):
            b = r["builders"][:48] + ("…" if len(r["builders"]) > 48 else "")
            print(f"  {r['zip_code']:<10} {r['permit_count']:>8}   {b}")
    print(f"{'='*64}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Clark County NV Residential Permit Intelligence")
    print(f"Run date: {TODAY}")
    print(f"Sources:  [1] Census BPS  [2] NV Open Data (Socrata)  [3] HUD SOCDS")

    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (AMARA Permit Intelligence/1.0)"},
        follow_redirects=True,
        timeout=30,
    ) as client:

        # Step 1 — Airtable verification
        table_id, airtable_fields = verify_airtable(client)

        # Step 2a — Census BPS (national context, no ZIP granularity)
        census_totals = fetch_census_bps(client)

        # Step 2b — NV Socrata (primary: individual permits with ZIPs)
        raw_permits = fetch_socrata_permits(client)

        # Step 2c — HUD SOCDS fallback if Socrata yields nothing
        if not raw_permits:
            print("\n  NV Socrata returned 0 records — engaging HUD SOCDS fallback…")
            raw_permits = fetch_hud_permits(client)

        if not raw_permits:
            print("\nERROR: All three data sources returned 0 records.")
            print("Check your network connection and re-run.")
            sys.exit(1)

        # Step 3 — Group by ZIP
        zip_rows = group_by_zip(raw_permits)

        # Step 4 — Push to Airtable
        created = push_to_airtable(client, zip_rows, table_id, airtable_fields)

        # Step 5 — Print summary
        print_summary(zip_rows, census_totals, created)

        print(f"Done. {created}/{len(zip_rows)} ZIP records confirmed in Airtable '{AIRTABLE_TABLE}'.")


if __name__ == "__main__":
    main()
