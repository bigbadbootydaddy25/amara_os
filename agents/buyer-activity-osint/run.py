#!/usr/bin/env python3
"""
Buyer Activity OSINT Agent

Scans CSV exports in data/buyer-activity/raw/, normalises headers from both
Propwire-style ("Buyer Name", "Sale Price") and deed/export-style
("grantee_name", "consideration_amount") formats, builds buyer activity
profiles, and writes structured reports.

Profiles are always built from whatever buyer/grantee/owner fields are present.
A match against known entity seeds (buyers/*.md) enriches a profile but is
never required.

Usage:
    python3 agents/buyer-activity-osint/run.py --workspace-root /path/to/ai-brain
    python3 agents/buyer-activity-osint/run.py --workspace-root . --dry-run
    python3 agents/buyer-activity-osint/run.py --workspace-root . --json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER MAP
# 130+ aliases covering Propwire title-case and deed/export snake_case headers.
# Keys are lowercase + whitespace-collapsed.  Values are canonical field names.
# ═══════════════════════════════════════════════════════════════════════════════

_RAW_MAP: dict[str, str] = {
    # ── buyer / grantee (primary) ─────────────────────────────────────────────
    "buyer name":                   "buyer_name",
    "buyer_name":                   "buyer_name",
    "buyer 1 name":                 "buyer_name",
    "buyer_1_name":                 "buyer_name",
    "buyer name 1":                 "buyer_name",
    "buyer1":                       "buyer_name",
    "grantee name":                 "buyer_name",
    "grantee_name":                 "buyer_name",
    "grantee full name":            "buyer_name",
    "grantee_full_name":            "buyer_name",
    "grantee 1":                    "buyer_name",
    "grantee_1":                    "buyer_name",
    "grantee":                      "buyer_name",
    "buyer":                        "buyer_name",
    "purchaser":                    "buyer_name",
    "owner name":                   "buyer_name",
    "owner_name":                   "buyer_name",
    "owner":                        "buyer_name",
    "owner 1":                      "buyer_name",
    "owner_1":                      "buyer_name",
    "mailing name":                 "buyer_name",
    # ── buyer / grantee (secondary) ───────────────────────────────────────────
    "buyer name 2":                 "buyer_name_2",
    "buyer_name_2":                 "buyer_name_2",
    "buyer 2 name":                 "buyer_name_2",
    "buyer_2_name":                 "buyer_name_2",
    "buyer2":                       "buyer_name_2",
    "grantee name 2":               "buyer_name_2",
    "grantee_name_2":               "buyer_name_2",
    "grantee 2":                    "buyer_name_2",
    "grantee_2":                    "buyer_name_2",
    "co-buyer":                     "buyer_name_2",
    "co buyer":                     "buyer_name_2",
    "owner 2":                      "buyer_name_2",
    "owner_2":                      "buyer_name_2",
    # ── buyer entity / company ────────────────────────────────────────────────
    "buyer company":                "buyer_entity",
    "buyer_company":                "buyer_entity",
    "buyer entity":                 "buyer_entity",
    "buyer_entity":                 "buyer_entity",
    "entity name":                  "buyer_entity",
    "entity_name":                  "buyer_entity",
    "company":                      "buyer_entity",
    "company name":                 "buyer_entity",
    "company_name":                 "buyer_entity",
    "organization":                 "buyer_entity",
    "owner entity":                 "buyer_entity",
    "owner_entity":                 "buyer_entity",
    # ── seller / grantor ──────────────────────────────────────────────────────
    "grantor name":                 "seller_name",
    "grantor_name":                 "seller_name",
    "seller name":                  "seller_name",
    "seller_name":                  "seller_name",
    "seller":                       "seller_name",
    "grantor":                      "seller_name",
    # ── property address ──────────────────────────────────────────────────────
    "property address":             "property_address",
    "property_address":             "property_address",
    "address":                      "property_address",
    "site address":                 "property_address",
    "situs address":                "property_address",
    "situs_address":                "property_address",
    "mailing address":              "property_address",
    "street address":               "property_address",
    "street_address":               "property_address",
    "city":                         "city",
    "property city":                "city",
    "property_city":                "city",
    "situs city":                   "city",
    "situs_city":                   "city",
    "state":                        "state",
    "property state":               "state",
    "property_state":               "state",
    "situs state":                  "state",
    "situs_state":                  "state",
    "zip":                          "zip",
    "zip code":                     "zip",
    "zip_code":                     "zip",
    "postal code":                  "zip",
    "postal_code":                  "zip",
    "property zip":                 "zip",
    "property_zip":                 "zip",
    "situs zip":                    "zip",
    "situs_zip":                    "zip",
    "county":                       "county",
    "property county":              "county",
    "property_county":              "county",
    # ── APN ──────────────────────────────────────────────────────────────────
    "apn":                          "apn",
    "parcel number":                "apn",
    "parcel_number":                "apn",
    "parcel id":                    "apn",
    "parcel_id":                    "apn",
    "assessor parcel number":       "apn",
    "assessor_parcel_number":       "apn",
    "tax id":                       "apn",
    "tax_id":                       "apn",
    "folio":                        "apn",
    "folio number":                 "apn",
    "folio_number":                 "apn",
    "account number":               "apn",
    "account_number":               "apn",
    # ── sale date ─────────────────────────────────────────────────────────────
    "sale date":                    "sale_date",
    "sale_date":                    "sale_date",
    "recording date":               "sale_date",
    "recording_date":               "sale_date",
    "deed date":                    "sale_date",
    "deed_date":                    "sale_date",
    "transfer date":                "sale_date",
    "transfer_date":                "sale_date",
    "close date":                   "sale_date",
    "close_date":                   "sale_date",
    "closing date":                 "sale_date",
    "closing_date":                 "sale_date",
    "document date":                "sale_date",
    "document_date":                "sale_date",
    "last sale date":               "sale_date",
    "last_sale_date":               "sale_date",
    "sold date":                    "sale_date",
    "sold_date":                    "sale_date",
    # ── sale price ────────────────────────────────────────────────────────────
    "sale price":                   "sale_price",
    "sale_price":                   "sale_price",
    "sales price":                  "sale_price",
    "sales_price":                  "sale_price",
    "consideration amount":         "sale_price",
    "consideration_amount":         "sale_price",
    "purchase price":               "sale_price",
    "purchase_price":               "sale_price",
    "sold price":                   "sale_price",
    "sold_price":                   "sale_price",
    "transfer amount":              "sale_price",
    "transfer_amount":              "sale_price",
    "deed amount":                  "sale_price",
    "deed_amount":                  "sale_price",
    # ── property type ─────────────────────────────────────────────────────────
    "property type":                "property_type",
    "property_type":                "property_type",
    "type":                         "property_type",
    "use type":                     "property_type",
    "use_type":                     "property_type",
    "land use":                     "property_type",
    "land_use":                     "property_type",
    "use code":                     "property_type",
    "use_code":                     "property_type",
    "property class":               "property_type",
    "property_class":               "property_type",
    "property use":                 "property_type",
    "property_use":                 "property_type",
    "improvement type":             "property_type",
    "improvement_type":             "property_type",
    # ── financing type ────────────────────────────────────────────────────────
    "financing type":               "financing_type",
    "financing_type":               "financing_type",
    "loan type":                    "financing_type",
    "loan_type":                    "financing_type",
    "deed type":                    "financing_type",
    "deed_type":                    "financing_type",
    "transaction type":             "financing_type",
    "transaction_type":             "financing_type",
    "funding type":                 "financing_type",
    "funding_type":                 "financing_type",
    "instrument type":              "financing_type",
    "instrument_type":              "financing_type",
    # ── lender / loan ─────────────────────────────────────────────────────────
    "lender name":                  "lender_name",
    "lender_name":                  "lender_name",
    "lender":                       "lender_name",
    "mortgage company":             "lender_name",
    "mortgage_company":             "lender_name",
    "bank":                         "lender_name",
    "bank name":                    "lender_name",
    "bank_name":                    "lender_name",
    "mortgagee":                    "lender_name",
    "loan amount":                  "loan_amount",
    "loan_amount":                  "loan_amount",
    "mortgage amount":              "loan_amount",
    "mortgage_amount":              "loan_amount",
    "loan balance":                 "loan_amount",
    "loan_balance":                 "loan_amount",
    "open mortgage":                "loan_amount",
    "open_mortgage":                "loan_amount",
    # ── property details ──────────────────────────────────────────────────────
    "beds":                         "beds",
    "bedrooms":                     "beds",
    "bd":                           "beds",
    "bed":                          "beds",
    "# beds":                       "beds",
    "# bedrooms":                   "beds",
    "baths":                        "baths",
    "bathrooms":                    "baths",
    "ba":                           "baths",
    "bath":                         "baths",
    "# baths":                      "baths",
    "total baths":                  "baths",
    "total_baths":                  "baths",
    "sqft":                         "sqft",
    "sq ft":                        "sqft",
    "square feet":                  "sqft",
    "square_feet":                  "sqft",
    "living area":                  "sqft",
    "living_area":                  "sqft",
    "building size":                "sqft",
    "building_size":                "sqft",
    "heated area":                  "sqft",
    "heated_area":                  "sqft",
    "gross area":                   "sqft",
    "gross_area":                   "sqft",
    "year built":                   "year_built",
    "year_built":                   "year_built",
    "built":                        "year_built",
    "yr built":                     "year_built",
    "yr_built":                     "year_built",
    "year constructed":             "year_built",
    "year_constructed":             "year_built",
}

# ─── date parsing ────────────────────────────────────────────────────────────

_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%Y%m%d",
    "%B %d, %Y",
    "%b %d, %Y",
)


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


_ENTITY_RE = re.compile(
    r"\b(LLC|Inc|Corp|LP|LLP|Trust|REIT|Properties|Holdings|Investments|"
    r"Homes|Builders|Development|Capital|Ventures|Partners|Group|Realty|"
    r"Fund|Assets|Acquisitions|Solutions|Enterprises|Industries)\b",
    re.IGNORECASE,
)

BUYER_FIELDS = frozenset({"buyer_name", "buyer_name_2", "buyer_entity"})


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER NORMALISATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_key(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower())


def build_column_map(headers: list[str]) -> dict[str, str]:
    """Map raw CSV headers → canonical field names (first-write wins)."""
    result: dict[str, str] = {}
    seen: set[str] = set()
    for h in headers:
        canon = _RAW_MAP.get(_norm_key(h))
        if canon and canon not in seen:
            result[h] = canon
            seen.add(canon)
    return result


def detect_format(headers: list[str]) -> str:
    snake = sum(1 for h in headers if "_" in h and h == h.lower())
    spaced = sum(1 for h in headers if " " in h)
    if snake > spaced:
        return "deed"
    if spaced > 0:
        return "propwire"
    return "unknown"


def unmapped_headers(headers: list[str]) -> list[str]:
    mapped = set(build_column_map(headers))
    return [h for h in headers if h not in mapped]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Transaction:
    source_file: str
    fmt: str
    buyer_name:       Optional[str] = None
    buyer_name_2:     Optional[str] = None
    buyer_entity:     Optional[str] = None
    seller_name:      Optional[str] = None
    property_address: Optional[str] = None
    city:             Optional[str] = None
    state:            Optional[str] = None
    zip:              Optional[str] = None
    county:           Optional[str] = None
    apn:              Optional[str] = None
    sale_date:        Optional[str] = None
    sale_price:       Optional[float] = None
    property_type:    Optional[str] = None
    financing_type:   Optional[str] = None
    lender_name:      Optional[str] = None
    loan_amount:      Optional[float] = None
    beds:             Optional[int] = None
    baths:            Optional[float] = None
    sqft:             Optional[int] = None
    year_built:       Optional[int] = None


@dataclass
class IgnoredFile:
    path: str
    reason: str


@dataclass
class BuyerSeed:
    buyer_id: str
    buyer_name: str
    entity_name: Optional[str] = None
    status: str = "unknown"
    zip_codes: list[str] = field(default_factory=list)


@dataclass
class BuyerActivityProfile:
    buyer_key:        str
    display_name:     str
    entity_name:      Optional[str]
    individual_name:  Optional[str]
    seed_id:          Optional[str]
    seed_status:      Optional[str]
    transaction_count: int
    zip_codes:        list[str]
    property_types:   list[str]
    financing_types:  list[str]
    price_min:        Optional[float]
    price_max:        Optional[float]
    price_avg:        Optional[float]
    most_recent_sale: Optional[str]
    earliest_sale:    Optional[str]
    source_files:     list[str]
    # ── purchase history (populated by _make_profile) ─────────────────────
    total_purchase_count:          int   = 0
    recent_purchase_count_30d:     int   = 0
    recent_purchase_count_90d:     int   = 0
    recent_purchase_count_180d:    int   = 0
    recent_purchase_count_365d:    int   = 0
    last_purchase_date:            Optional[str]  = None
    days_since_last_purchase:      Optional[int]  = None
    first_purchase_date:           Optional[str]  = None
    purchase_velocity_score:       float = 0.0
    multi_purchase_buyer:          bool  = False
    repeat_market_buyer:           bool  = False
    purchase_markets:              list[str] = field(default_factory=list)
    purchase_zip_codes:            list[str] = field(default_factory=list)
    purchase_property_types:       list[str] = field(default_factory=list)
    purchase_timing_confidence:    str   = "low"   # high | medium | low
    recent_purchase_evidence:      list[dict] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# CSV INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

def load_raw_dir(raw_dir: Path) -> tuple[list[Transaction], list[IgnoredFile]]:
    transactions: list[Transaction] = []
    ignored: list[IgnoredFile] = []

    if not raw_dir.exists():
        return transactions, ignored

    for entry in sorted(raw_dir.iterdir()):
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        if entry.suffix.lower() != ".csv":
            ignored.append(IgnoredFile(
                path=str(entry),
                reason=f"not a CSV (suffix: {entry.suffix!r})",
            ))
            continue
        try:
            txns, skip_reason = _ingest_file(entry)
        except Exception as exc:
            ignored.append(IgnoredFile(path=str(entry), reason=f"parse error: {exc}"))
            continue
        if skip_reason:
            ignored.append(IgnoredFile(path=str(entry), reason=skip_reason))
        else:
            transactions.extend(txns)

    return transactions, ignored


def _ingest_file(path: Path) -> tuple[list[Transaction], Optional[str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return [], "empty file or missing header row"

        headers = list(reader.fieldnames)
        col_map = build_column_map(headers)
        fmt = detect_format(headers)

        if not col_map:
            sample = ", ".join(f'"{h}"' for h in headers[:6])
            return [], f"no recognised headers (found: {sample})"

        if not (set(col_map.values()) & BUYER_FIELDS):
            cols = ", ".join(sorted(set(col_map.values())))
            return [], f"no buyer/grantee/owner column mapped (mapped: {cols})"

        rows = list(reader)
        if not rows:
            return [], "no data rows after header"

        transactions = [t for r in rows if (t := _map_row(r, col_map, str(path), fmt))]
        if not transactions:
            return [], "all rows lacked a usable buyer identifier"

        return transactions, None


def _map_row(
    row: dict[str, str],
    col_map: dict[str, str],
    source_file: str,
    fmt: str,
) -> Optional[Transaction]:
    canon: dict[str, str] = {
        c: v
        for raw_col, c in col_map.items()
        if (v := row.get(raw_col, "").strip())
    }

    buyer_name   = canon.get("buyer_name")
    buyer_entity = canon.get("buyer_entity")

    # Promote entity-looking names from buyer_name
    if not buyer_entity and buyer_name and _ENTITY_RE.search(buyer_name):
        buyer_entity = buyer_name
        buyer_name = None

    if not buyer_name and not buyer_entity and not canon.get("buyer_name_2"):
        return None

    return Transaction(
        source_file=source_file,
        fmt=fmt,
        buyer_name=buyer_name,
        buyer_name_2=canon.get("buyer_name_2"),
        buyer_entity=buyer_entity,
        seller_name=canon.get("seller_name"),
        property_address=canon.get("property_address"),
        city=canon.get("city"),
        state=canon.get("state"),
        zip=_clean_zip(canon.get("zip")),
        county=canon.get("county"),
        apn=canon.get("apn"),
        sale_date=canon.get("sale_date"),
        sale_price=_to_float(canon.get("sale_price")),
        property_type=canon.get("property_type"),
        financing_type=canon.get("financing_type"),
        lender_name=canon.get("lender_name"),
        loan_amount=_to_float(canon.get("loan_amount")),
        beds=_to_int(canon.get("beds")),
        baths=_to_float(canon.get("baths")),
        sqft=_to_int(canon.get("sqft")),
        year_built=_to_int(canon.get("year_built")),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEED LOADING  (buyers/BUY-*.md)
# ═══════════════════════════════════════════════════════════════════════════════

def load_seeds(buyers_dir: Path) -> list[BuyerSeed]:
    if not buyers_dir.exists():
        return []
    seeds = []
    for md in sorted(buyers_dir.glob("BUY-*.md")):
        seed = _parse_buyer_md(md)
        if seed:
            seeds.append(seed)
    return seeds


def _parse_buyer_md(path: Path) -> Optional[BuyerSeed]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    name_m   = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    buyer_name = name_m.group(1).strip() if name_m else path.stem

    entity_m = re.search(r"##\s+Entity\s*\n+([^\n]+)", text)
    entity_name = entity_m.group(1).strip() if entity_m else None
    if entity_name and entity_name.lower() in ("llc or individual", "n/a", ""):
        entity_name = None

    id_m    = re.search(r"\*\*ID:\*\*\s*(BUY-\d+)", text)
    buyer_id = id_m.group(1) if id_m else path.stem

    status_m = re.search(r"\*\*Status:\*\*\s*(\w+)", text)
    status   = status_m.group(1).lower() if status_m else "unknown"

    zip_m = re.search(r"##\s+ZIP Codes\s*\n([\s\S]+?)(?=\n##|\Z)", text)
    zip_codes = re.findall(r"\b(\d{5})\b", zip_m.group(1)) if zip_m else []

    return BuyerSeed(buyer_id=buyer_id, buyer_name=buyer_name,
                     entity_name=entity_name, status=status, zip_codes=zip_codes)


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match_seed(
    buyer_entity: Optional[str],
    buyer_name: Optional[str],
    seeds: list[BuyerSeed],
) -> Optional[BuyerSeed]:
    for candidate in filter(None, [buyer_entity, buyer_name]):
        norm = _norm_name(candidate)
        for seed in seeds:
            if seed.entity_name and _norm_name(seed.entity_name) == norm:
                return seed
            if _norm_name(seed.buyer_name) == norm:
                return seed
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

def _buyer_key(txn: Transaction) -> Optional[str]:
    raw = txn.buyer_entity or txn.buyer_name or ""
    return re.sub(r"[^a-z0-9]", "", raw.lower()) or None


def _most_common(items: list[str]) -> Optional[str]:
    return max(set(items), key=items.count) if items else None


def build_profiles(
    transactions: list[Transaction],
    seeds: list[BuyerSeed],
    ref_date: Optional[date] = None,
) -> list[BuyerActivityProfile]:
    grouped: dict[str, list[Transaction]] = {}
    for txn in transactions:
        key = _buyer_key(txn)
        if key:
            grouped.setdefault(key, []).append(txn)

    today = ref_date or date.today()
    profiles = [_make_profile(k, txns, seeds, today) for k, txns in grouped.items()]
    profiles.sort(key=lambda p: (p.recent_purchase_count_90d, p.total_purchase_count), reverse=True)
    return profiles


def _make_profile(
    key: str,
    txns: list[Transaction],
    seeds: list[BuyerSeed],
    ref_date: date,
) -> BuyerActivityProfile:
    entities    = [t.buyer_entity for t in txns if t.buyer_entity]
    individuals = [t.buyer_name   for t in txns if t.buyer_name]

    entity_name     = _most_common(entities)
    individual_name = _most_common(individuals)
    display_name    = entity_name or individual_name or key

    seed   = match_seed(entity_name, individual_name, seeds)
    prices = [t.sale_price for t in txns if t.sale_price is not None]
    raw_dates = sorted(d for t in txns if (d := t.sale_date))

    # ── parse dates ────────────────────────────────────────────────────────
    parsed: list[tuple[date, Transaction]] = []
    for txn in txns:
        d = _parse_date(txn.sale_date)
        if d:
            parsed.append((d, txn))
    parsed.sort(key=lambda x: x[0])

    dated_count = len(parsed)
    total       = len(txns)
    if dated_count == 0:
        timing_confidence = "low"
    elif dated_count == total:
        timing_confidence = "high"
    else:
        timing_confidence = "medium"

    # ── windowed counts ────────────────────────────────────────────────────
    def _count_within(days: int) -> int:
        return sum(1 for d, _ in parsed if (ref_date - d).days <= days)

    cnt_30  = _count_within(30)
    cnt_90  = _count_within(90)
    cnt_180 = _count_within(180)
    cnt_365 = _count_within(365)

    last_date  = parsed[-1][0] if parsed else None
    first_date = parsed[0][0]  if parsed else None
    days_since = (ref_date - last_date).days if last_date else None

    # ── velocity score 0–100 ───────────────────────────────────────────────
    # Rate = purchases per 30 days over active window; 5/month → 100
    if dated_count == 0:
        velocity = 0.0
    elif dated_count == 1:
        velocity = 10.0
    else:
        active_days = max(1, (last_date - first_date).days)
        rate_per_30 = (dated_count / active_days) * 30
        velocity = min(100.0, round(rate_per_30 * 20, 1))

    # ── flags ──────────────────────────────────────────────────────────────
    multi_purchase  = total >= 2
    zip_set         = sorted({t.zip  for t in txns if t.zip})
    market_set      = sorted({t.city for t in txns if t.city})
    repeat_market   = len(zip_set) >= 2 or len(market_set) >= 2
    prop_type_set   = sorted({t.property_type for t in txns if t.property_type})

    # ── recent evidence (last 180 days, most recent first) ────────────────
    recent_evidence = []
    for d, txn in reversed(parsed):
        if (ref_date - d).days > 180:
            break
        addr_parts = [p for p in [
            txn.property_address,
            txn.city,
            txn.state,
            txn.zip,
        ] if p]
        evidence = {
            "date":          d.isoformat(),
            "address":       ", ".join(addr_parts) if addr_parts else None,
            "sale_price":    txn.sale_price,
            "financing_type": txn.financing_type,
            "property_type": txn.property_type,
            "source_file":   Path(txn.source_file).name,
        }
        recent_evidence.append(evidence)

    return BuyerActivityProfile(
        buyer_key=key,
        display_name=display_name,
        entity_name=entity_name,
        individual_name=individual_name,
        seed_id=seed.buyer_id if seed else None,
        seed_status=seed.status if seed else None,
        transaction_count=total,
        zip_codes=zip_set,
        property_types=prop_type_set,
        financing_types=sorted({t.financing_type for t in txns if t.financing_type}),
        price_min=min(prices) if prices else None,
        price_max=max(prices) if prices else None,
        price_avg=round(sum(prices) / len(prices), 2) if prices else None,
        most_recent_sale=raw_dates[-1] if raw_dates else None,
        earliest_sale=raw_dates[0] if raw_dates else None,
        source_files=sorted({t.source_file for t in txns}),
        # purchase history
        total_purchase_count=total,
        recent_purchase_count_30d=cnt_30,
        recent_purchase_count_90d=cnt_90,
        recent_purchase_count_180d=cnt_180,
        recent_purchase_count_365d=cnt_365,
        last_purchase_date=last_date.isoformat() if last_date else None,
        days_since_last_purchase=days_since,
        first_purchase_date=first_date.isoformat() if first_date else None,
        purchase_velocity_score=velocity,
        multi_purchase_buyer=multi_purchase,
        repeat_market_buyer=repeat_market,
        purchase_markets=market_set,
        purchase_zip_codes=zip_set,
        purchase_property_types=prop_type_set,
        purchase_timing_confidence=timing_confidence,
        recent_purchase_evidence=recent_evidence,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT WRITERS
# ═══════════════════════════════════════════════════════════════════════════════

def write_reports(
    transactions: list[Transaction],
    profiles: list[BuyerActivityProfile],
    ignored: list[IgnoredFile],
    reports_dir: Path,
    workspace_root: Path,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    _write_buyer_profiles_md(profiles, reports_dir, ts)
    _write_ignored_files_md(ignored, reports_dir, ts, workspace_root)
    _write_activity_summary_json(transactions, profiles, ignored, reports_dir, ts)
    _write_recent_buyers_json(profiles, reports_dir, ts)
    _write_multi_purchase_buyers_json(profiles, reports_dir, ts)
    _write_buyer_purchase_history_md(profiles, reports_dir, ts)


def _write_buyer_profiles_md(
    profiles: list[BuyerActivityProfile],
    reports_dir: Path,
    ts: str,
) -> None:
    lines = [
        "# BUYER_ACTIVITY_PROFILES",
        "",
        f"_Generated: {ts}_",
        f"_Profiles: {len(profiles)}_",
        "",
    ]
    if not profiles:
        lines.append("> No buyer profiles produced in this run.\n")
    else:
        for p in profiles:
            seed_tag = f"[{p.seed_id} · {p.seed_status}]" if p.seed_id else "[new]"
            lines += [
                f"## {p.display_name}",
                "",
                f"- **Seed**: {seed_tag}",
                f"- **Transactions**: {p.transaction_count}",
            ]
            if p.zip_codes:
                lines.append(f"- **ZIP codes**: {', '.join(p.zip_codes)}")
            if p.property_types:
                lines.append(f"- **Property types**: {', '.join(p.property_types)}")
            if p.financing_types:
                lines.append(f"- **Financing**: {', '.join(p.financing_types)}")
            if p.price_avg is not None:
                lines.append(
                    f"- **Price range**: ${p.price_min:,.0f} – ${p.price_max:,.0f}"
                    f"  (avg ${p.price_avg:,.0f})"
                )
            if p.most_recent_sale:
                lines.append(f"- **Most recent sale**: {p.most_recent_sale}")
            if p.earliest_sale and p.earliest_sale != p.most_recent_sale:
                lines.append(f"- **Earliest sale**: {p.earliest_sale}")
            # purchase history
            lines.append(f"- **Total purchases**: {p.total_purchase_count}")
            conf = p.purchase_timing_confidence
            lines.append(f"- **Purchase timing confidence**: {conf}")
            if p.days_since_last_purchase is not None:
                lines.append(f"- **Days since last purchase**: {p.days_since_last_purchase}")
            if p.purchase_velocity_score > 0:
                lines.append(f"- **Purchase velocity score**: {p.purchase_velocity_score}")
            lines.append(f"- **Multi-purchase buyer**: {p.multi_purchase_buyer}")
            lines.append(f"- **Repeat market buyer**: {p.repeat_market_buyer}")
            counts = (
                f"30d={p.recent_purchase_count_30d}  "
                f"90d={p.recent_purchase_count_90d}  "
                f"180d={p.recent_purchase_count_180d}  "
                f"365d={p.recent_purchase_count_365d}"
            )
            lines.append(f"- **Recent purchases**: {counts}")
            if p.purchase_markets:
                lines.append(f"- **Purchase markets**: {', '.join(p.purchase_markets)}")
            if p.recent_purchase_evidence:
                lines.append("- **Recent evidence**:")
                for ev in p.recent_purchase_evidence[:5]:
                    price_str = f"${ev['sale_price']:,.0f}" if ev.get("sale_price") else "n/a"
                    addr_str  = ev.get("address") or "n/a"
                    lines.append(f"  - {ev['date']}  {addr_str}  {price_str}  ({ev['source_file']})")
            lines.append("")

    (reports_dir / "BUYER_ACTIVITY_PROFILES.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _write_ignored_files_md(
    ignored: list[IgnoredFile],
    reports_dir: Path,
    ts: str,
    workspace_root: Path,
) -> None:
    lines = [
        "# IGNORED_FILES",
        "",
        f"_Generated: {ts}_",
        f"_Files skipped: {len(ignored)}_",
        "",
    ]
    if not ignored:
        lines.append("> No files were ignored in this run.\n")
    else:
        lines += [
            "| File | Reason |",
            "|------|--------|",
        ]
        for ign in ignored:
            try:
                display = Path(ign.path).relative_to(workspace_root)
            except ValueError:
                display = Path(ign.path).name
            lines.append(f"| `{display}` | {ign.reason} |")
        lines.append("")

    (reports_dir / "IGNORED_FILES.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _profile_to_dict(p: BuyerActivityProfile) -> dict:
    return {
        "buyer_key":                   p.buyer_key,
        "display_name":                p.display_name,
        "entity_name":                 p.entity_name,
        "individual_name":             p.individual_name,
        "seed_id":                     p.seed_id,
        "seed_status":                 p.seed_status,
        "transaction_count":           p.transaction_count,
        "zip_codes":                   p.zip_codes,
        "property_types":              p.property_types,
        "financing_types":             p.financing_types,
        "price_min":                   p.price_min,
        "price_max":                   p.price_max,
        "price_avg":                   p.price_avg,
        "most_recent_sale":            p.most_recent_sale,
        "earliest_sale":               p.earliest_sale,
        "source_files":                [Path(f).name for f in p.source_files],
        # purchase history
        "total_purchase_count":        p.total_purchase_count,
        "recent_purchase_count_30d":   p.recent_purchase_count_30d,
        "recent_purchase_count_90d":   p.recent_purchase_count_90d,
        "recent_purchase_count_180d":  p.recent_purchase_count_180d,
        "recent_purchase_count_365d":  p.recent_purchase_count_365d,
        "last_purchase_date":          p.last_purchase_date,
        "days_since_last_purchase":    p.days_since_last_purchase,
        "first_purchase_date":         p.first_purchase_date,
        "purchase_velocity_score":     p.purchase_velocity_score,
        "multi_purchase_buyer":        p.multi_purchase_buyer,
        "repeat_market_buyer":         p.repeat_market_buyer,
        "purchase_markets":            p.purchase_markets,
        "purchase_zip_codes":          p.purchase_zip_codes,
        "purchase_property_types":     p.purchase_property_types,
        "purchase_timing_confidence":  p.purchase_timing_confidence,
        "recent_purchase_evidence":    p.recent_purchase_evidence,
    }


def _write_recent_buyers_json(
    profiles: list[BuyerActivityProfile],
    reports_dir: Path,
    ts: str,
) -> None:
    recent = [p for p in profiles if p.recent_purchase_count_90d >= 1]
    recent.sort(key=lambda p: (p.recent_purchase_count_90d, p.purchase_velocity_score), reverse=True)
    payload = {
        "run_timestamp": ts,
        "total_recent_buyers": len(recent),
        "window_days": 90,
        "buyers": [_profile_to_dict(p) for p in recent],
    }
    (reports_dir / "RECENT_BUYERS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def _write_multi_purchase_buyers_json(
    profiles: list[BuyerActivityProfile],
    reports_dir: Path,
    ts: str,
) -> None:
    multi = [p for p in profiles if p.multi_purchase_buyer]
    multi.sort(key=lambda p: (p.total_purchase_count, p.purchase_velocity_score), reverse=True)
    payload = {
        "run_timestamp": ts,
        "total_multi_purchase_buyers": len(multi),
        "buyers": [_profile_to_dict(p) for p in multi],
    }
    (reports_dir / "MULTI_PURCHASE_BUYERS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def _write_buyer_purchase_history_md(
    profiles: list[BuyerActivityProfile],
    reports_dir: Path,
    ts: str,
) -> None:
    lines = [
        "# BUYER_PURCHASE_HISTORY",
        "",
        f"_Generated: {ts}_",
        f"_Profiles: {len(profiles)}_",
        "",
        "Ranked by recency (most 90-day purchases first).",
        "",
    ]
    for p in profiles:
        seed_tag = f"[{p.seed_id}·{p.seed_status}]" if p.seed_id else "[new]"
        lines += [
            f"## {p.display_name}  {seed_tag}",
            "",
            f"| Field | Value |",
            f"|---|---|",
            f"| Total purchases | {p.total_purchase_count} |",
            f"| First purchase | {p.first_purchase_date or 'unknown'} |",
            f"| Last purchase | {p.last_purchase_date or 'unknown'} |",
            f"| Days since last purchase | {p.days_since_last_purchase if p.days_since_last_purchase is not None else 'unknown'} |",
            f"| Purchases (30d / 90d / 180d / 365d) | {p.recent_purchase_count_30d} / {p.recent_purchase_count_90d} / {p.recent_purchase_count_180d} / {p.recent_purchase_count_365d} |",
            f"| Purchase velocity score | {p.purchase_velocity_score} |",
            f"| Multi-purchase buyer | {p.multi_purchase_buyer} |",
            f"| Repeat market buyer | {p.repeat_market_buyer} |",
            f"| Purchase timing confidence | {p.purchase_timing_confidence} |",
        ]
        if p.purchase_markets:
            lines.append(f"| Markets | {', '.join(p.purchase_markets)} |")
        if p.purchase_zip_codes:
            lines.append(f"| ZIP codes | {', '.join(p.purchase_zip_codes)} |")
        if p.purchase_property_types:
            lines.append(f"| Property types | {', '.join(p.purchase_property_types)} |")
        if p.price_avg is not None:
            lines.append(
                f"| Price range | ${p.price_min:,.0f} – ${p.price_max:,.0f}"
                f" (avg ${p.price_avg:,.0f}) |"
            )
        lines.append("")
        if p.recent_purchase_evidence:
            lines.append("**Recent purchase evidence:**")
            lines.append("")
            lines.append("| Date | Address | Price | Financing | Source |")
            lines.append("|---|---|---|---|---|")
            for ev in p.recent_purchase_evidence:
                price_str = f"${ev['sale_price']:,.0f}" if ev.get("sale_price") else "n/a"
                lines.append(
                    f"| {ev['date']} "
                    f"| {ev.get('address') or 'n/a'} "
                    f"| {price_str} "
                    f"| {ev.get('financing_type') or 'n/a'} "
                    f"| {ev['source_file']} |"
                )
            lines.append("")
        lines.append("")

    (reports_dir / "BUYER_PURCHASE_HISTORY.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _write_activity_summary_json(
    transactions: list[Transaction],
    profiles: list[BuyerActivityProfile],
    ignored: list[IgnoredFile],
    reports_dir: Path,
    ts: str,
) -> None:
    payload = {
        "run_timestamp": ts,
        "eligible_transaction_count": len(transactions),
        "buyer_profiles": [_profile_to_dict(p) for p in profiles],
        "ignored_files": [
            {"file": Path(i.path).name, "reason": i.reason}
            for i in ignored
        ],
    }
    (reports_dir / "ACTIVITY_SUMMARY.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE COERCIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _to_float(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(re.sub(r"[$,\s]", "", raw))
    except ValueError:
        return None


def _to_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    try:
        return int(float(re.sub(r"[,\s]", "", raw)))
    except ValueError:
        return None


def _clean_zip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = re.search(r"\b(\d{5})(?:-\d{4})?\b", raw)
    return m.group(1) if m else raw.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Buyer Activity OSINT — scan CSVs, map headers, build buyer profiles"
    )
    parser.add_argument(
        "--workspace-root",
        default=".",
        help="Root of the ai-brain workspace (default: current directory). "
             "CSVs are read from <root>/data/buyer-activity/raw/ and "
             "seeds from <root>/buyers/.",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Override the CSV input directory (default: <workspace-root>/data/buyer-activity/raw/)",
    )
    parser.add_argument(
        "--buyers-dir",
        default=None,
        help="Override the buyers seed directory (default: <workspace-root>/buyers/)",
    )
    parser.add_argument(
        "--reports-dir",
        default=None,
        help="Override the reports output directory "
             "(default: agents/buyer-activity-osint/reports/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary to stdout without writing report files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Print full JSON output to stdout in addition to the summary.",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace_root).expanduser().resolve()
    raw_dir   = Path(args.raw_dir).resolve()    if args.raw_dir    else workspace / "data" / "buyer-activity" / "raw"
    buyers_dir = Path(args.buyers_dir).resolve() if args.buyers_dir else workspace / "buyers"
    reports_dir = (
        Path(args.reports_dir).resolve()
        if args.reports_dir
        else Path(__file__).parent / "reports"
    )

    _banner("buyer-activity-osint")

    # ── 1. Seeds ──────────────────────────────────────────────────────────────
    seeds = load_seeds(buyers_dir)
    print(f"  workspace root:          {workspace}")
    print(f"  entity seeds:            {len(seeds) if seeds else 'none — buyers/ not found'}")

    # ── 2. Ingest ─────────────────────────────────────────────────────────────
    transactions, ignored = load_raw_dir(raw_dir)
    csv_count = sum(1 for f in raw_dir.iterdir() if f.suffix.lower() == ".csv") if raw_dir.exists() else 0
    print(f"  raw directory:           {raw_dir}")
    print(f"  CSV files scanned:       {csv_count}")
    print(f"  transactions ingested:   {len(transactions)}")

    # ── 3. Profiles ───────────────────────────────────────────────────────────
    profiles = build_profiles(transactions, seeds)

    # ── 4. Summary ────────────────────────────────────────────────────────────
    print()
    print(f"eligible_transaction_count: {len(transactions)}")
    print(f"buyer_profiles:             {len(profiles)}")

    if profiles:
        _section("Buyer profiles")
        for p in profiles:
            seed_tag  = f"[{p.seed_id}·{p.seed_status}]" if p.seed_id else "[new]"
            price_str = (
                f"  avg ${p.price_avg:>9,.0f}"
                f"  range ${p.price_min:,.0f}–${p.price_max:,.0f}"
            ) if p.price_avg else ""
            flags = []
            if p.multi_purchase_buyer:
                flags.append("multi-purchase")
            if p.repeat_market_buyer:
                flags.append("repeat-market")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            zip_str = ", ".join(p.zip_codes[:4]) + ("…" if len(p.zip_codes) > 4 else "")
            print(f"  {seed_tag:<22} {p.display_name:<38} {p.transaction_count:>3} txn(s){price_str}{flag_str}")
            if p.days_since_last_purchase is not None:
                vel = f"velocity={p.purchase_velocity_score}"
                win = (
                    f"30d={p.recent_purchase_count_30d}"
                    f" 90d={p.recent_purchase_count_90d}"
                    f" 180d={p.recent_purchase_count_180d}"
                    f" 365d={p.recent_purchase_count_365d}"
                )
                print(f"    {'':22} Last purchase {p.days_since_last_purchase}d ago  {vel}  {win}")
            if zip_str:
                print(f"    {'':22} ZIPs: {zip_str}")
            if p.property_types:
                print(f"    {'':22} Types: {', '.join(p.property_types)}")
            if p.financing_types:
                print(f"    {'':22} Financing: {', '.join(p.financing_types)}")

    # ── 5. Ignored files ──────────────────────────────────────────────────────
    _section(f"Ignored files ({len(ignored)})" if ignored else "Ignored files")
    if ignored:
        for ign in ignored:
            try:
                display = Path(ign.path).relative_to(workspace)
            except ValueError:
                display = Path(ign.path).name
            print(f"  {str(display):<45} {ign.reason}")
    else:
        print("  none")

    # ── 6. JSON stdout ────────────────────────────────────────────────────────
    if args.json_out:
        payload = {
            "eligible_transaction_count": len(transactions),
            "buyer_profiles": [
                {k: v for k, v in vars(p).items() if k != "source_files"}
                | {"source_files": [Path(f).name for f in p.source_files]}
                for p in profiles
            ],
            "ignored_files": [{"file": Path(i.path).name, "reason": i.reason} for i in ignored],
        }
        print("\n" + json.dumps(payload, indent=2, default=str))

    # ── 7. Write reports ──────────────────────────────────────────────────────
    if not args.dry_run:
        write_reports(transactions, profiles, ignored, reports_dir, workspace)
        print(f"\nReports written to: {reports_dir}/")
        print(f"  • BUYER_ACTIVITY_PROFILES.md")
        print(f"  • IGNORED_FILES.md")
        print(f"  • ACTIVITY_SUMMARY.json")
        print(f"  • RECENT_BUYERS.json")
        print(f"  • MULTI_PURCHASE_BUYERS.json")
        print(f"  • BUYER_PURCHASE_HISTORY.md")

    return 0


def _banner(title: str) -> None:
    bar = "━" * (len(title) + 4)
    print(f"\n{bar}\n  {title}\n{bar}\n")


def _section(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 52 - len(title))}")


if __name__ == "__main__":
    sys.exit(main())
