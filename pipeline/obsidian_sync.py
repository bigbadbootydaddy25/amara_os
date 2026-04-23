"""
Obsidian vault sync — generates and updates all markdown notes from pipeline data.

Vault structure:
  /vault/Properties/     — one note per property
  /vault/CashBuyers/     — one note per buyer
  /vault/ZIPs/           — one note per ZIP code
  /vault/Counties/       — one note per county
  /vault/DistressFlags/  — one note per flag type
  /vault/Reports/        — generated report summaries
  /vault/DailyRunLogs/   — one note per pipeline run
  /vault/Dashboard.md    — Dataview query dashboard

All notes use [[wiki links]], YAML frontmatter, and consistent tags
so Obsidian graph view, tag search, and Dataview queries work out of the box.

Run standalone:
    cd /home/user/amara_os/pipeline
    python obsidian_sync.py

Called automatically by pipeline.py after each full run.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

VAULT_DIR   = Path(__file__).parent.parent / "vault"
CLEAN_DIR   = Path(__file__).parent / "data" / "clean"
REPORTS_DIR = Path(__file__).parent / "reports"

# Ensure vault subdirectories exist
for sub in ["Properties", "CashBuyers", "ZIPs", "Counties", "DistressFlags", "Reports", "DailyRunLogs"]:
    (VAULT_DIR / sub).mkdir(parents=True, exist_ok=True)

# ── YAML frontmatter helper ────────────────────────────────────────────────

def _yaml_val(v: Any) -> str:
    """Format a value for YAML frontmatter."""
    if v is None or str(v) in ("", "nan", "None"):
        return '""'
    s = str(v).replace('"', "'")
    if any(c in s for c in ":[]{},#|>&*?!%@`"):
        return f'"{s}"'
    return s


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {_yaml_val(item)}")
        else:
            lines.append(f"{k}: {_yaml_val(v)}")
    lines.append("---")
    return "\n".join(lines)


def _safe_filename(text: str) -> str:
    """Convert any string to a safe filename."""
    text = re.sub(r'[<>:"/\\|?*]', "-", str(text))
    text = re.sub(r"\s+", "-", text).strip("-")
    return text[:120]  # filesystem limit safety


def _wiki(text: str, path: str = "") -> str:
    """Format a wiki link: [[path/name|display]] or [[name]]."""
    if not text or str(text) in ("", "nan", "None"):
        return ""
    safe = _safe_filename(text)
    if path:
        return f"[[{path}/{safe}|{text}]]"
    return f"[[{safe}|{text}]]"


# ── Distress flag notes ────────────────────────────────────────────────────

FLAG_DESCRIPTIONS = {
    "preforeclosure":  "Property has a Lis Pendens / pre-foreclosure filing recorded with the county clerk.",
    "tax_delinquent":  "Owner has unpaid property taxes on file with the county tax assessor.",
    "code_violation":  "Active code enforcement / blight violation on file with the city.",
    "probate":         "Property is part of a probate estate filing.",
    "dom90":           "Listed on MLS for 90+ days without selling.",
    "nod":             "Notice of Default filed — first step in foreclosure process.",
    "bankruptcy":      "Debtor (owner) has an active Chapter 7 or Chapter 13 bankruptcy filing.",
    "vacant_land":     "Parcel is vacant / unimproved residential land (no structures).",
    "ghost_plat":      "Platted subdivision with no building permits issued in 3+ years.",
    "absentee_owner":  "Owner's mailing address differs from the property address.",
    "cash_buyer":      "Property was purchased with cash (no corresponding mortgage recorded).",
}

def generate_distress_flag_notes():
    for flag, description in FLAG_DESCRIPTIONS.items():
        note_path = VAULT_DIR / "DistressFlags" / f"{flag}.md"
        fm = _frontmatter({
            "type":        flag,
            "category":    "DistressFlag",
            "tags":        [flag, "distress-flag"],
        })
        content = f"""{fm}

# {flag.replace('_', ' ').title()}

{description}

## Properties with this flag

```dataview
TABLE address, zip_code, distress_score, owner_name
FROM "Properties"
WHERE contains(distress_flags, "{flag}")
SORT distress_score DESC
```
"""
        note_path.write_text(content, encoding="utf-8")


# ── Property notes ─────────────────────────────────────────────────────────

def generate_property_notes(df: pd.DataFrame, matches_df: pd.DataFrame):
    """Generate one markdown note per property."""
    count = 0

    # Index matches by property address+zip for fast lookup
    match_index: dict[str, list[dict]] = {}
    if not matches_df.empty:
        for _, m in matches_df.iterrows():
            key = f"{m.get('property_address','')}_{m.get('property_zip','')}"
            match_index.setdefault(key, []).append(m.to_dict())

    for _, row in df.iterrows():
        address   = str(row.get("address", "")).strip()
        zip_code  = str(row.get("zip_code", "")).strip()
        city      = str(row.get("city", ""))
        state     = str(row.get("state", ""))
        county    = str(row.get("county", ""))
        owner     = str(row.get("owner_name", ""))
        score     = row.get("distress_score", 0)
        is_hp     = str(row.get("is_high_priority", "")).lower() == "true"
        source    = str(row.get("source", ""))
        flags_raw = str(row.get("distress_flags", ""))
        flags     = [f.strip() for f in flags_raw.split("|") if f.strip()]
        scrape_dt = str(row.get("scrape_date", ""))

        if not address or not zip_code:
            continue

        filename  = _safe_filename(f"{address}-{zip_code}")
        note_path = VAULT_DIR / "Properties" / f"{filename}.md"

        # Get matched buyers
        match_key  = f"{address}_{zip_code}"
        prop_matches = sorted(
            match_index.get(match_key, []),
            key=lambda x: float(x.get("match_score", 0)),
            reverse=True,
        )[:5]

        buyer_links = "\n".join(
            f"- {_wiki(m.get('buyer_name',''), 'CashBuyers')} "
            f"(score: {m.get('match_score','')}, type: {m.get('buyer_type','')})"
            for m in prop_matches
            if m.get("buyer_name")
        ) or "_No matches found_"

        flag_links = "\n".join(
            f"- {_wiki(f, 'DistressFlags')}"
            for f in flags
        ) or "_None_"

        tag_list = ["property"] + [f"flag-{f}" for f in flags]
        if is_hp:
            tag_list.append("high-priority")
        if int(score or 0) >= 7:
            tag_list.append("critical")

        fm = _frontmatter({
            "address":        address,
            "zip_code":       zip_code,
            "city":           city,
            "state":          state,
            "county":         county,
            "owner_name":     owner,
            "distress_score": score,
            "distress_flags": flags,
            "is_high_priority": is_hp,
            "source":         source,
            "scrape_date":    scrape_dt,
            "tags":           tag_list,
        })

        content = f"""{fm}

# {address}

> **ZIP:** {_wiki(zip_code, 'ZIPs')} | **County:** {_wiki(county, 'Counties')} | **State:** {state}

## Distress Profile

| Field | Value |
|-------|-------|
| Distress Score | **{score} / 10** |
| High Priority | {'✅ YES' if is_hp else 'No'} |
| Owner | {owner} |
| Source | {source} |
| Scraped | {scrape_dt} |

## Distress Flags

{flag_links}

## Matched Cash Buyers

{buyer_links}

## Source Data

```
{flags_raw}
```

---
_Note auto-generated by pipeline on {scrape_dt}_
"""
        note_path.write_text(content, encoding="utf-8")
        count += 1

    print(f"  Property notes: {count} written")


# ── Cash buyer notes ───────────────────────────────────────────────────────

def generate_buyer_notes(df: pd.DataFrame, matches_df: pd.DataFrame):
    """Generate one markdown note per cash buyer."""
    buyers = df[df["distress_type"].str.lower().str.contains("cash_buyer", na=False)].copy()
    if buyers.empty:
        print("  Cash buyer notes: 0 (no buyer records)")
        return

    # Build purchase history per buyer
    history: dict[str, list[dict]] = {}
    for _, row in buyers.iterrows():
        name = str(row.get("owner_name", "")).strip()
        if not name:
            continue
        history.setdefault(name, []).append(row.to_dict())

    # Index matches by buyer name
    buyer_match_index: dict[str, list[dict]] = {}
    if not matches_df.empty:
        for _, m in matches_df.iterrows():
            bname = str(m.get("buyer_name", "")).strip()
            if bname:
                buyer_match_index.setdefault(bname, []).append(m.to_dict())

    count = 0
    for buyer_name, purchases in history.items():
        filename  = _safe_filename(buyer_name)
        note_path = VAULT_DIR / "CashBuyers" / f"{filename}.md"

        # Derive buyer type from raw_data
        buyer_type = "entity_buyer"
        for p in purchases:
            raw = {}
            try:
                raw = json.loads(p.get("raw_data", "{}"))
            except (ValueError, TypeError):
                pass
            if raw.get("buyer_type"):
                buyer_type = raw["buyer_type"]
                break

        zips_active = sorted({str(p.get("zip_code","")) for p in purchases if p.get("zip_code")})
        zip_links   = " ".join(_wiki(z, "ZIPs") for z in zips_active)

        last_purchase = max(
            (str(p.get("filing_date","")) for p in purchases),
            default="",
        )

        matched_props = buyer_match_index.get(buyer_name, [])
        prop_links = "\n".join(
            f"- {_wiki(m.get('property_address',''), 'Properties')} "
            f"({m.get('property_zip','')}, score: {m.get('match_score','')})"
            for m in sorted(matched_props, key=lambda x: float(x.get("match_score",0)), reverse=True)[:10]
        ) or "_None_"

        # Purchase history table
        history_rows = "\n".join(
            f"| {p.get('filing_date','')} | {p.get('address','')} | {p.get('zip_code','')} | {p.get('amount_owed','')} |"
            for p in sorted(purchases, key=lambda x: x.get("filing_date",""), reverse=True)[:20]
        )

        tag_list = ["cashbuyer", buyer_type]
        if len(purchases) >= 3:
            tag_list.append("repeat-buyer")

        fm = _frontmatter({
            "buyer_name":          buyer_name,
            "buyer_type":          buyer_type,
            "purchase_count":      len(purchases),
            "last_purchase_date":  last_purchase,
            "active_zips":         zips_active,
            "tags":                tag_list,
        })

        content = f"""{fm}

# {buyer_name}

> **Type:** {buyer_type} | **Purchases:** {len(purchases)} | **Last Active:** {last_purchase}

## Active ZIPs

{zip_links}

## Matched Properties

{prop_links}

## Purchase History

| Date | Address | ZIP | Amount |
|------|---------|-----|--------|
{history_rows}

---
_Note auto-generated by pipeline_
"""
        note_path.write_text(content, encoding="utf-8")
        count += 1

    print(f"  Cash buyer notes: {count} written")


# ── ZIP notes ──────────────────────────────────────────────────────────────

def generate_zip_notes(df: pd.DataFrame):
    """Generate one note per ZIP code with property and buyer summaries."""
    from config import ZIP_COUNTY_MAP

    count = 0
    for zip_code in df["zip_code"].unique():
        if not zip_code or str(zip_code) in ("", "nan"):
            continue
        zip_df   = df[df["zip_code"] == zip_code]
        info     = ZIP_COUNTY_MAP.get(str(zip_code), {})
        city     = info.get("city", "")
        state    = info.get("state", "")
        county   = info.get("county", "")

        prop_count = len(zip_df[zip_df["distress_type"] != "cash_buyer"])
        buyer_count= len(zip_df[zip_df["distress_type"].str.lower().str.contains("cash_buyer", na=False)])

        top5 = (
            zip_df[zip_df["distress_type"] != "cash_buyer"]
            .assign(ds=lambda x: pd.to_numeric(x["distress_score"], errors="coerce").fillna(0))
            .nlargest(5, "ds")
        )
        top5_links = "\n".join(
            f"- {_wiki(row['address'], 'Properties')} (score: {row.get('distress_score','')})"
            for _, row in top5.iterrows()
        ) or "_None_"

        # Buyer type breakdown
        buyers_df = zip_df[zip_df["distress_type"].str.lower().str.contains("cash_buyer", na=False)]
        buyer_types: dict[str, int] = {}
        for _, r in buyers_df.iterrows():
            raw = {}
            try:
                raw = json.loads(r.get("raw_data", "{}"))
            except (ValueError, TypeError):
                pass
            bt = raw.get("buyer_type", "unknown")
            buyer_types[bt] = buyer_types.get(bt, 0) + 1
        buyer_breakdown = "\n".join(f"  - {bt}: {cnt}" for bt, cnt in sorted(buyer_types.items()))

        flag_counts: dict[str, int] = {}
        for _, r in zip_df.iterrows():
            for f in str(r.get("distress_flags","")).split("|"):
                f = f.strip()
                if f:
                    flag_counts[f] = flag_counts.get(f, 0) + 1

        tags = ["zip", state.lower() if state else "unknown", city.lower().replace(" ", "-") if city else "unknown"]
        fm = _frontmatter({
            "zip_code":             zip_code,
            "city":                 city,
            "state":                state,
            "county":               county,
            "total_distressed":     prop_count,
            "total_cash_buyers":    buyer_count,
            "tags":                 tags,
        })

        content = f"""{fm}

# ZIP {zip_code} — {city}, {state}

> **County:** {_wiki(county, 'Counties')} | **State:** {state}

## Summary

| Metric | Count |
|--------|-------|
| Distressed Properties | {prop_count} |
| Active Cash Buyers | {buyer_count} |

## Distress Flag Breakdown

{chr(10).join(f'- **{_wiki(f, "DistressFlags")}**: {c}' for f, c in sorted(flag_counts.items(), key=lambda x: -x[1]))}

## Buyer Type Breakdown

{buyer_breakdown or "_No buyer data_"}

## Top 5 Highest Distress Properties

{top5_links}

## All Properties

```dataview
TABLE address, distress_score, distress_flags, owner_name
FROM "Properties"
WHERE zip_code = "{zip_code}"
SORT distress_score DESC
```

## All Cash Buyers

```dataview
TABLE buyer_name, buyer_type, purchase_count
FROM "CashBuyers"
WHERE contains(active_zips, "{zip_code}")
SORT purchase_count DESC
```

---
_Note auto-generated by pipeline_
"""
        note_path = VAULT_DIR / "ZIPs" / f"{zip_code}.md"
        note_path.write_text(content, encoding="utf-8")
        count += 1

    print(f"  ZIP notes: {count} written")


# ── County notes ───────────────────────────────────────────────────────────

def generate_county_notes(df: pd.DataFrame):
    from config import ZIP_COUNTY_MAP

    counties: dict[tuple, list[str]] = {}
    for zip_code in df["zip_code"].unique():
        info = ZIP_COUNTY_MAP.get(str(zip_code), {})
        key  = (info.get("county",""), info.get("state",""))
        counties.setdefault(key, []).append(zip_code)

    count = 0
    for (county_name, state), zips in counties.items():
        if not county_name:
            continue
        county_df = df[df["zip_code"].isin(zips)]
        zip_links = " ".join(_wiki(z, "ZIPs") for z in sorted(zips))
        prop_count = len(county_df[county_df["distress_type"] != "cash_buyer"])

        fm = _frontmatter({
            "county":    county_name,
            "state":     state,
            "zip_codes": sorted(zips),
            "tags":      ["county", state.lower() if state else "unknown"],
        })
        content = f"""{fm}

# {county_name} County, {state}

## Target ZIPs

{zip_links}

## Stats

| Metric | Value |
|--------|-------|
| Target ZIPs | {len(zips)} |
| Distressed Properties | {prop_count} |

## All ZIPs in County

```dataview
TABLE city, total_distressed, total_cash_buyers
FROM "ZIPs"
WHERE county = "{county_name}" AND state = "{state}"
SORT total_distressed DESC
```

---
_Note auto-generated by pipeline_
"""
        filename  = _safe_filename(f"{county_name}-{state}")
        note_path = VAULT_DIR / "Counties" / f"{filename}.md"
        note_path.write_text(content, encoding="utf-8")
        count += 1

    print(f"  County notes: {count} written")


# ── Daily run log note ─────────────────────────────────────────────────────

def generate_run_log_note(
    run_date: str,
    new_props: int,
    new_buyers: int,
    new_matches: int,
    errors: list[str],
):
    note_path = VAULT_DIR / "DailyRunLogs" / f"{run_date}-run.md"
    fm = _frontmatter({
        "date":        run_date,
        "new_props":   new_props,
        "new_buyers":  new_buyers,
        "new_matches": new_matches,
        "tags":        ["runlog", "daily"],
    })
    error_list = "\n".join(f"- {e}" for e in errors) if errors else "_None_"
    content = f"""{fm}

# Pipeline Run — {run_date}

## Summary

| Metric | Count |
|--------|-------|
| New Properties Found | {new_props} |
| New Cash Buyers Found | {new_buyers} |
| New Matches Made | {new_matches} |

## Errors / Failed Scrapers

{error_list}

## Links

- [[Dashboard]]
- [[../Reports/latest-summary]]
"""
    note_path.write_text(content, encoding="utf-8")
    print(f"  Run log note: {note_path.name}")


# ── Dashboard.md ───────────────────────────────────────────────────────────

def generate_dashboard():
    content = """---
title: Real Estate OSINT Dashboard
tags: [dashboard]
---

# Real Estate OSINT Dashboard

## High Priority Properties (score > 7)

```dataview
TABLE address, zip_code, distress_score, distress_flags, owner_name
FROM "Properties"
WHERE distress_score > 7
SORT distress_score DESC
LIMIT 50
```

## Cash Buyers with 3+ Purchases

```dataview
TABLE buyer_name, buyer_type, purchase_count, last_purchase_date
FROM "CashBuyers"
WHERE purchase_count >= 3
SORT purchase_count DESC
```

## Ghost Subdivisions

```dataview
TABLE address, zip_code, owner_name
FROM "Properties"
WHERE contains(distress_flags, "ghost_plat")
SORT zip_code ASC
```

## Pre-Foreclosures Filed in Last 30 Days

```dataview
TABLE address, zip_code, filing_date, owner_name
FROM "Properties"
WHERE contains(distress_flags, "preforeclosure")
SORT filing_date DESC
LIMIT 100
```

## Top ZIPs by Distressed Property Count

```dataview
TABLE zip_code, city, state, total_distressed, total_cash_buyers
FROM "ZIPs"
SORT total_distressed DESC
LIMIT 20
```

## Infill Lots Matched to Builders

```dataview
TABLE property_address, property_zip, buyer_name, buyer_type, match_score
FROM "Reports"
WHERE contains(file.name, "matches") AND buyer_type = "builder"
SORT match_score DESC
LIMIT 30
```

## Recent Pipeline Runs

```dataview
TABLE date, new_props, new_buyers, new_matches
FROM "DailyRunLogs"
SORT date DESC
LIMIT 7
```

---
_Dashboard powered by Obsidian Dataview plugin_
"""
    (VAULT_DIR / "Dashboard.md").write_text(content, encoding="utf-8")
    print("  Dashboard.md written")


# ── Report notes ───────────────────────────────────────────────────────────

def generate_report_notes():
    """Copy CSVs to vault/Reports as markdown summary notes."""
    for csv_file in sorted(REPORTS_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(csv_file, nrows=100, dtype=str)
            if df.empty:
                continue
            md_table = df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.head(20).to_string()
            note_path = VAULT_DIR / "Reports" / f"{csv_file.stem}.md"
            fm = _frontmatter({"report": csv_file.stem, "tags": ["report"], "generated": datetime.now().strftime("%Y-%m-%d")})
            note_path.write_text(f"{fm}\n\n# {csv_file.stem.replace('_',' ').title()}\n\n{md_table}\n", encoding="utf-8")
        except Exception as exc:
            print(f"  Warning: could not generate report note for {csv_file.name}: {exc}")
    print("  Report notes written")


# ── Main entry point ───────────────────────────────────────────────────────

def sync_vault(
    run_date: str | None = None,
    new_props: int = 0,
    new_buyers: int = 0,
    new_matches: int = 0,
    errors: list[str] | None = None,
):
    """
    Full vault sync. Called by pipeline.py after every run.
    Also callable standalone for testing.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*50}")
    print(f"Syncing Obsidian vault — {run_date}")
    print(f"{'='*50}")

    # Load data
    props_file   = CLEAN_DIR / "properties_clean.csv"
    matches_file = CLEAN_DIR / "matches.csv"

    if not props_file.exists():
        print("No clean properties file found. Run data_cleaner.py first.")
        return

    df       = pd.read_csv(props_file, dtype=str)
    df["zip_code"] = df["zip_code"].astype(str).str.strip()
    matches  = pd.read_csv(matches_file, dtype=str) if matches_file.exists() else pd.DataFrame()

    # Generate all note types
    generate_distress_flag_notes()
    generate_property_notes(df, matches)
    generate_buyer_notes(df, matches)
    generate_zip_notes(df)
    generate_county_notes(df)
    generate_run_log_note(run_date, new_props, new_buyers, new_matches, errors or [])
    generate_dashboard()
    generate_report_notes()

    print(f"\nVault sync complete → {VAULT_DIR}/")


if __name__ == "__main__":
    sync_vault()
