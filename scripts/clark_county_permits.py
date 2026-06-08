"""
Clark County NV – Residential Building Permit Intelligence
==========================================================
SOURCE 1  Census Bureau Building Permits Survey (BPS)
          https://api.census.gov/data/timeseries/eits/bps
          Metro-level aggregate counts for Las Vegas CBSA 29820.
          No auth required.

SOURCE 2  Clark County NV Open Data (Socrata)
          https://opendata.clarkcountynv.gov
          Individual permit records with addresses/ZIPs.
          No auth required.

Results are grouped by ZIP, flagged Hot/Warm/Cold, and pushed
to Airtable base appGtDvO4grC0iv4V → "Permit Activity" table.

Requirements:  pip3 install httpx
Usage:
    export AIRTABLE_API_KEY=pat05vgLOgpayULeQ...
    python3 scripts/clark_county_permits.py
"""

import httpx
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta, datetime

# ── Config ────────────────────────────────────────────────────────────────────

AIRTABLE_API_KEY  = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID  = "appGtDvO4grC0iv4V"
AIRTABLE_TABLE    = "Permit Activity"
MARKET            = "Las Vegas NV"
PERIOD            = "Last 90 Days"
TODAY             = date.today().isoformat()
LOOKBACK_DAYS     = 90
HOT_THRESHOLD     = 10
WARM_THRESHOLD    = 5

# Census BPS – Las Vegas-Henderson-Paradise CBSA code
LV_CBSA           = "29820"

# Clark County Socrata base URL
SOCRATA_BASE      = "https://opendata.clarkcountynv.gov"

if not AIRTABLE_API_KEY:
    sys.exit("ERROR: set AIRTABLE_API_KEY env var before running.")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cutoff_str() -> str:
    """ISO date string 90 days ago, for SoQL $where clauses."""
    return (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()


def _flag(count: int) -> str:
    if count >= HOT_THRESHOLD:
        return "Hot"
    if count >= WARM_THRESHOLD:
        return "Warm"
    return "Cold"


RESIDENTIAL_RE = re.compile(
    r"(new\s*res|single.?family|sfr|duplex|townhome|townhouse|"
    r"residential|nsfr|row\s*home|single\s*unit|1.unit|one.unit)",
    re.I,
)


def _looks_residential(text: str) -> bool:
    return bool(RESIDENTIAL_RE.search(text or ""))


def _extract_zip(text: str) -> str:
    """Pull first 89xxx ZIP from an address string."""
    m = re.search(r"\b(89\d{3})\b", text or "")
    return m.group(1) if m else ""


# ── Step 1: Verify Airtable connection ───────────────────────────────────────

def verify_airtable(client: httpx.Client) -> tuple[str, dict]:
    """
    Return (table_id, {field_name: field_id}) for the Permit Activity table.
    Confirms all 3 expected tables exist.
    """
    print("\n[Step 1] Verifying Airtable connection…")
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    r = client.get(
        f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
        headers=headers,
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
        print(f"  WARNING – tables not found: {missing}")
    else:
        print("  All 3 required tables confirmed ✓")

    target = next((t for t in all_tables if t["name"] == AIRTABLE_TABLE), None)
    if not target:
        sys.exit(f"ERROR: '{AIRTABLE_TABLE}' table not found. Existing: {sorted(table_names)}")

    fields = {f["name"]: f["id"] for f in target.get("fields", [])}
    print(f"  '{AIRTABLE_TABLE}' fields: {sorted(fields.keys())}")
    return target["id"], fields


# ── Step 2a: Census BPS – metro-level aggregate ───────────────────────────────

def fetch_census_bps(client: httpx.Client) -> dict:
    """
    Pull last 6 months of new residential housing unit counts for
    Las Vegas CBSA 29820 from the Census BPS timeseries API.

    Returns {YYYY-MM: unit_count} for informational / validation use.
    NOTE: This API is aggregate (metro-wide) — no ZIP breakdown.
    """
    print("\n[Step 2a] Census BPS – Las Vegas metro (CBSA 29820)…")

    # Build list of YYYY-MM strings for the last 6 months
    months = []
    d = date.today().replace(day=1)
    for _ in range(6):
        months.append(d.strftime("%Y-%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    months.sort()

    results = {}

    for month in months:
        try:
            r = client.get(
                "https://api.census.gov/data/timeseries/eits/bps",
                params={
                    "get":           "cell_value,time_slot_name,category_code,geo_level_code",
                    "for":           f"metropolitan statistical area/micropolitan statistical area:{LV_CBSA}",
                    "time":          month,
                    "category_code": "101",          # 1-unit structures (single family)
                    "seasonally_adj": "no",
                },
                timeout=20,
            )
            if r.status_code == 200:
                rows = r.json()
                # rows[0] = header, rows[1:] = data
                if len(rows) > 1:
                    header = rows[0]
                    val_idx = header.index("cell_value") if "cell_value" in header else 0
                    for row in rows[1:]:
                        try:
                            results[month] = int(row[val_idx])
                        except (ValueError, IndexError):
                            pass
            elif r.status_code == 204:
                results[month] = 0
            else:
                print(f"  {month}: HTTP {r.status_code} – skipping")
        except Exception as e:
            print(f"  {month}: error ({e}) – skipping")

    if results:
        total = sum(results.values())
        print(f"  Months retrieved: {sorted(results.keys())}")
        print(f"  Metro single-family permits (6-month total): {total:,}")
    else:
        print("  Census BPS returned no data for this CBSA/period.")
        print("  (API may not support CBSA-level for this dataset — Socrata is primary source)")

    return results


# ── Step 2b: Clark County Socrata – permit-level with ZIPs ────────────────────

def _discover_dataset(client: httpx.Client) -> tuple[str, list[str]]:
    """
    Query the Socrata catalog API to find the building permits dataset.
    Returns (dataset_id, [column_names]).
    """
    r = client.get(
        f"{SOCRATA_BASE}/api/catalog/v1",
        params={"q": "building permit", "limit": 10},
        timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results", [])

    for item in results:
        res = item.get("resource", {})
        name = res.get("name", "").lower()
        if "permit" in name and "building" in name:
            ds_id = res.get("id", "")
            cols  = res.get("columns_name", [])
            print(f"  Dataset found: '{res['name']}' (id: {ds_id})")
            print(f"  Columns: {cols}")
            return ds_id, cols

    # Fallback: try known Clark County dataset IDs
    # (pulled from data.clarkcountynv.gov historical catalog)
    for candidate_id in ["umsv-bh2e", "mhh6-69yb", "e8vz-7xrw", "yvtm-qbxn"]:
        try:
            probe = client.get(
                f"{SOCRATA_BASE}/resource/{candidate_id}.json",
                params={"$limit": 1},
                timeout=15,
            )
            if probe.status_code == 200 and probe.json():
                cols = list(probe.json()[0].keys())
                print(f"  Dataset found via fallback ID: {candidate_id}")
                print(f"  Columns: {cols}")
                return candidate_id, cols
        except Exception:
            continue

    return "", []


def _pick_columns(cols: list[str]) -> dict:
    """
    Map logical field names to actual column names by fuzzy match.
    Returns {role: actual_column_name}.
    """
    col_lower = {c.lower(): c for c in cols}

    def find(patterns):
        for p in patterns:
            for k, v in col_lower.items():
                if p in k:
                    return v
        return None

    return {
        "permit_type":   find(["permit_type", "type", "work_type", "category"]),
        "description":   find(["description", "desc", "work_desc", "scope"]),
        "issued_date":   find(["issued", "issue_date", "open_date", "filed", "created"]),
        "address":       find(["address", "location", "street"]),
        "zip":           find(["zip", "postal"]),
        "contractor":    find(["contractor", "builder", "applicant", "owner"]),
        "status":        find(["status", "permit_status"]),
    }


def fetch_socrata_permits(client: httpx.Client) -> list[dict]:
    """
    Pull individual building permit records from Clark County open data.
    Filters to residential permits in the last 90 days.
    Returns list of normalized dicts with zip_code, builder, description, etc.
    """
    print("\n[Step 2b] Clark County Open Data (Socrata) – individual permits…")

    dataset_id, cols = _discover_dataset(client)
    if not dataset_id:
        print("  ERROR: Could not discover building permits dataset.")
        return []

    col_map   = _pick_columns(cols)
    cutoff    = _cutoff_str()
    date_col  = col_map.get("issued_date") or "issued_date"
    limit     = 5000
    offset    = 0
    all_recs  = []

    # Prefer ZIP column from dataset; fall back to parsing address
    zip_col  = col_map.get("zip")
    addr_col = col_map.get("address")
    desc_col = col_map.get("description") or col_map.get("permit_type") or ""
    cont_col = col_map.get("contractor")

    print(f"  Querying /{dataset_id}.json  (cutoff: {cutoff})")

    while True:
        params: dict = {
            "$limit":  limit,
            "$offset": offset,
            "$order":  f"{date_col} DESC",
        }
        # SoQL date filter — handle both ISO string and floating timestamp columns
        params["$where"] = f"{date_col} >= '{cutoff}T00:00:00.000'"

        try:
            r = client.get(
                f"{SOCRATA_BASE}/resource/{dataset_id}.json",
                params=params,
                timeout=30,
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Retry without time filter if column type mismatch
            if e.response.status_code == 400 and offset == 0:
                print(f"  Date filter failed, retrying without it…")
                params.pop("$where", None)
                r = client.get(
                    f"{SOCRATA_BASE}/resource/{dataset_id}.json",
                    params=params,
                    timeout=30,
                )
                r.raise_for_status()
            else:
                raise

        batch = r.json()
        if not batch:
            break

        for rec in batch:
            # Date filter (manual if SoQL failed or column is a string)
            raw_date = rec.get(date_col, "")
            if raw_date:
                try:
                    rec_date = raw_date[:10]  # YYYY-MM-DD
                    if rec_date < cutoff:
                        continue
                except Exception:
                    pass

            desc = str(rec.get(desc_col, "") or "")

            # ZIP: prefer dedicated column, else parse address
            if zip_col and rec.get(zip_col):
                zip_code = str(rec[zip_col]).strip()[:5]
            elif addr_col:
                zip_code = _extract_zip(str(rec.get(addr_col, "")))
            else:
                # Last resort: search all string values
                zip_code = ""
                for v in rec.values():
                    z = _extract_zip(str(v))
                    if z:
                        zip_code = z
                        break

            builder = str(rec.get(cont_col, "") or "") if cont_col else ""

            all_recs.append({
                "description": desc,
                "zip_code":    zip_code,
                "builder":     builder.strip(),
                "issued_date": raw_date[:10] if raw_date else "",
            })

        print(f"  Fetched {len(all_recs)} records so far…", end="\r")
        if len(batch) < limit:
            break
        offset += limit

    print(f"\n  Total records from Socrata: {len(all_recs)}")
    return all_recs


# ── Step 3: Filter residential + group by ZIP ─────────────────────────────────

def group_by_zip(permits: list[dict]) -> list[dict]:
    """Filter to residential, group by ZIP, return sorted result rows."""
    residential = [p for p in permits if _looks_residential(p.get("description", ""))]

    # If filter yields nothing (dataset may already be pre-filtered to residential),
    # use all records rather than returning empty.
    if not residential and permits:
        print("  Residential keyword filter matched 0 — using all records (dataset may be pre-filtered)")
        residential = permits

    print(f"\n[Step 3] {len(permits)} total → {len(residential)} residential")

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
    print(f"  Grouped → {len(rows)} ZIPs   Hot: {hot}  Warm: {warm}  Cold: {cold}")
    return rows


# ── Step 4: Push to Airtable ──────────────────────────────────────────────────

# Map our logical names → possible Airtable field names (first match wins)
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
    """
    Map our logical field names to actual Airtable field IDs.
    Returns {our_name: field_id_or_name_to_use}.
    Uses field IDs when available; falls back to field names with typecast.
    """
    resolved = {}
    lower_map = {k.lower(): v for k, v in airtable_fields.items()}

    for logical, candidates in FIELD_ALIASES.items():
        for candidate in candidates:
            field_id = airtable_fields.get(candidate) or lower_map.get(candidate.lower())
            if field_id:
                resolved[logical] = field_id
                break
        if logical not in resolved:
            # No match found — use the logical name and rely on typecast
            resolved[logical] = logical

    return resolved


def push_to_airtable(
    client: httpx.Client,
    rows: list[dict],
    table_id: str,
    airtable_fields: dict,
) -> int:
    """Batch-insert ZIP rows into Airtable. Returns count of records created."""
    print(f"\n[Step 4] Pushing {len(rows)} records → '{AIRTABLE_TABLE}'…")
    if not rows:
        print("  Nothing to push.")
        return 0

    field_map = _resolve_fields(airtable_fields)
    print(f"  Field mapping: {field_map}")

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type":  "application/json",
    }

    def _make_fields(row: dict) -> dict:
        return {
            field_map["ZIP Code"]:      row["zip_code"],
            field_map["Market"]:        MARKET,
            field_map["Permit Count"]:  row["permit_count"],
            field_map["Period"]:        PERIOD,
            field_map["Builder Names"]: row["builders"],
            field_map["Pull Date"]:     TODAY,
            field_map["Flag"]:          row["flag"],
        }

    BATCH   = 10
    created = 0

    for i in range(0, len(rows), BATCH):
        batch   = rows[i : i + BATCH]
        records = [{"fields": _make_fields(r)} for r in batch]
        payload = {"records": records, "typecast": True}

        r = client.post(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}",
            headers=headers,
            content=json.dumps(payload),
            timeout=30,
        )

        batch_num = i // BATCH + 1
        if r.status_code in (200, 201):
            n        = len(r.json().get("records", []))
            created += n
            print(f"  Batch {batch_num}: {n} records written ✓")
        else:
            print(f"  Batch {batch_num} FAILED {r.status_code}: {r.text[:300]}")

    return created


# ── Step 5: Terminal summary ──────────────────────────────────────────────────

def print_summary(rows: list[dict], census_totals: dict, created: int) -> None:
    hot_rows = [r for r in rows if r["flag"] == "Hot"]

    print(f"\n{'='*62}")
    print(f"  CLARK COUNTY NV — RESIDENTIAL PERMIT SUMMARY")
    print(f"  Market: {MARKET} | Period: {PERIOD}")
    print(f"{'='*62}")

    if census_totals:
        print(f"\n  Census BPS (metro aggregate, single-family):")
        for month in sorted(census_totals):
            print(f"    {month}:  {census_totals[month]:>6,} units")
        print(f"    {'Total:':10}  {sum(census_totals.values()):>6,} units")

    print(f"\n  Socrata (individual permits → {len(rows)} ZIPs pulled)")
    print(f"  Airtable records written: {created}/{len(rows)}")

    print(f"\n{'─'*62}")
    print(f"  HOT ZIP CODES  (≥{HOT_THRESHOLD} permits)")
    print(f"{'─'*62}")

    if not hot_rows:
        print(f"  None found at ≥{HOT_THRESHOLD} permit threshold.")
    else:
        print(f"  {'ZIP':<10} {'Permits':>8}   Top Builders")
        print(f"  {'─'*55}")
        for r in sorted(hot_rows, key=lambda x: -x["permit_count"]):
            builders = r["builders"]
            if len(builders) > 46:
                builders = builders[:43] + "…"
            print(f"  {r['zip_code']:<10} {r['permit_count']:>8}   {builders}")

    print(f"{'='*62}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Clark County NV Residential Permit Intelligence")
    print(f"Run date: {TODAY}")
    print(f"Sources:  Census BPS (CBSA {LV_CBSA}) + Clark County Open Data (Socrata)")

    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (AMARA Permit Intelligence/1.0)"},
        follow_redirects=True,
        timeout=30,
    ) as client:

        # Step 1 – Airtable verification
        table_id, airtable_fields = verify_airtable(client)

        # Step 2a – Census BPS (aggregate metro totals)
        census_totals = fetch_census_bps(client)

        # Step 2b – Socrata (individual permits with ZIP codes)
        raw_permits = fetch_socrata_permits(client)

        if not raw_permits:
            print("\nWARNING: No permit data retrieved from either source.")
            print("Check network, dataset availability, or try again later.")
            sys.exit(1)

        # Step 3 – Group by ZIP
        zip_rows = group_by_zip(raw_permits)

        # Step 4 – Push to Airtable
        created = push_to_airtable(client, zip_rows, table_id, airtable_fields)

        # Step 5 – Print summary
        print_summary(zip_rows, census_totals, created)

        print(f"Done. {created} records confirmed in Airtable '{AIRTABLE_TABLE}'.")


if __name__ == "__main__":
    main()
