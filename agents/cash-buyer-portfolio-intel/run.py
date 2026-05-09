#!/usr/bin/env python3
"""
Cash Buyer Portfolio Intelligence Agent

Ingests PropStream/Propwire portfolio exports, linked-properties exports,
ownership-graph output, buyer-activity output, manual CSVs, and text/screenshot
notes to build evidence-backed portfolio profiles for each cash buyer.

Every numeric field requires a source record.  No values are fabricated.
Manual extraction from screenshot notes is permitted when the source path is
recorded in source_evidence.

Usage:
    python3 agents/cash-buyer-portfolio-intel/run.py --workspace-root /path/to/ai-brain
    python3 agents/cash-buyer-portfolio-intel/run.py --workspace-root . --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# ENCODING-RESILIENT CSV READER  (same waterfall as ownership-graph)
# ═══════════════════════════════════════════════════════════════════════════════

ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


@dataclass
class FileResult:
    path: str
    encoding_used: Optional[str] = None
    rows: list[dict] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None


def read_csv_rows(path: Path) -> FileResult:
    for enc in ENCODINGS:
        try:
            with open(path, newline="", encoding=enc, errors="strict") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            return FileResult(path=str(path), encoding_used=enc, rows=rows)
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            return FileResult(
                path=str(path),
                skipped=True,
                skip_reason=f"parse error ({type(exc).__name__}): {exc}",
            )
    return FileResult(
        path=str(path),
        skipped=True,
        skip_reason=f"could not decode with any of: {', '.join(ENCODINGS)}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER MAP
# Covers PropStream title-case, Propwire mixed-case, and manual snake_case.
# Keys: lowercase + whitespace-collapsed.  Values: canonical field names.
# ═══════════════════════════════════════════════════════════════════════════════

_RAW_MAP: dict[str, str] = {
    # ── owner / buyer name ────────────────────────────────────────────────────
    "owner name":                   "owner_name",
    "owner_name":                   "owner_name",
    "owner":                        "owner_name",
    "owner 1":                      "owner_name",
    "owner_1":                      "owner_name",
    "buyer name":                   "owner_name",
    "buyer_name":                   "owner_name",
    "buyer":                        "owner_name",
    "grantee":                      "owner_name",
    "grantee name":                 "owner_name",
    "grantee_name":                 "owner_name",
    "mailing name":                 "owner_name",
    "investor name":                "owner_name",
    "investor_name":                "owner_name",
    "entity name":                  "owner_name",
    "entity_name":                  "owner_name",
    "company name":                 "owner_name",
    "company_name":                 "owner_name",
    # ── property address ──────────────────────────────────────────────────────
    "property address":             "property_address",
    "property_address":             "property_address",
    "address":                      "property_address",
    "situs address":                "property_address",
    "situs_address":                "property_address",
    "street address":               "property_address",
    "street_address":               "property_address",
    "mailing address":              "property_address",
    "mailing_address":              "property_address",
    # ── location ──────────────────────────────────────────────────────────────
    "city":                         "city",
    "property city":                "city",
    "property_city":                "city",
    "situs city":                   "city",
    "state":                        "state",
    "property state":               "state",
    "property_state":               "state",
    "situs state":                  "state",
    "zip":                          "zip",
    "zip code":                     "zip",
    "zip_code":                     "zip",
    "property zip":                 "zip",
    "property_zip":                 "zip",
    "situs zip":                    "zip",
    "postal code":                  "zip",
    "county":                       "county",
    "property county":              "county",
    "property_county":              "county",
    "situs county":                 "county",
    # ── parcel / apn ──────────────────────────────────────────────────────────
    "apn":                          "apn",
    "parcel number":                "apn",
    "parcel_number":                "apn",
    "parcel id":                    "apn",
    "parcel_id":                    "apn",
    "account number":               "apn",
    "account_number":               "apn",
    "tax id":                       "apn",
    "tax_id":                       "apn",
    # ── estimated value (AVM) ─────────────────────────────────────────────────
    "estimated value":              "estimated_value",
    "estimated_value":              "estimated_value",
    "estimated market value":       "estimated_value",
    "estimated_market_value":       "estimated_value",
    "avm":                          "estimated_value",
    "avm value":                    "estimated_value",
    "avm_value":                    "estimated_value",
    "market value":                 "estimated_value",
    "market_value":                 "estimated_value",
    "assessed value":               "estimated_value",
    "assessed_value":               "estimated_value",
    "zillow estimate":              "estimated_value",
    "zestimate":                    "estimated_value",
    "current value":                "estimated_value",
    "current_value":                "estimated_value",
    # ── open loan / mortgage balance ──────────────────────────────────────────
    "open loan balance":            "open_loan_balance",
    "open_loan_balance":            "open_loan_balance",
    "loan balance":                 "open_loan_balance",
    "loan_balance":                 "open_loan_balance",
    "open mortgage":                "open_loan_balance",
    "open_mortgage":                "open_loan_balance",
    "total open mortgage":          "open_loan_balance",
    "total_open_mortgage":          "open_loan_balance",
    "mortgage balance":             "open_loan_balance",
    "mortgage_balance":             "open_loan_balance",
    "liens":                        "open_loan_balance",
    "total liens":                  "open_loan_balance",
    "total_liens":                  "open_loan_balance",
    "outstanding balance":          "open_loan_balance",
    "outstanding_balance":          "open_loan_balance",
    # ── equity ────────────────────────────────────────────────────────────────
    "equity":                       "equity",
    "estimated equity":             "equity",
    "estimated_equity":             "equity",
    "equity amount":                "equity",
    "equity_amount":                "equity",
    "net equity":                   "equity",
    "net_equity":                   "equity",
    "equity %":                     "equity_pct",
    "equity percent":               "equity_pct",
    "equity_pct":                   "equity_pct",
    "equity ratio":                 "equity_pct",
    "equity_ratio":                 "equity_pct",
    "ltv":                          "ltv",
    "loan to value":                "ltv",
    "loan_to_value":                "ltv",
    # ── sale / transaction ────────────────────────────────────────────────────
    "last sale price":              "last_sale_price",
    "last_sale_price":              "last_sale_price",
    "last sale amount":             "last_sale_price",
    "last_sale_amount":             "last_sale_price",
    "sale price":                   "last_sale_price",
    "sale_price":                   "last_sale_price",
    "purchase price":               "last_sale_price",
    "purchase_price":               "last_sale_price",
    "consideration amount":         "last_sale_price",
    "consideration_amount":         "last_sale_price",
    "last sale date":               "last_sale_date",
    "last_sale_date":               "last_sale_date",
    "sale date":                    "last_sale_date",
    "sale_date":                    "last_sale_date",
    "recording date":               "last_sale_date",
    "recording_date":               "last_sale_date",
    "deed date":                    "last_sale_date",
    "deed_date":                    "last_sale_date",
    "purchase date":                "last_sale_date",
    "purchase_date":                "last_sale_date",
    # ── days on market ────────────────────────────────────────────────────────
    "days on market":               "dom",
    "days_on_market":               "dom",
    "dom":                          "dom",
    "avg dom":                      "dom",
    "average dom":                  "dom",
    # ── property type ─────────────────────────────────────────────────────────
    "property type":                "property_type",
    "property_type":                "property_type",
    "land use":                     "property_type",
    "land_use":                     "property_type",
    "property class":               "property_type",
    "property_class":               "property_type",
    "use code":                     "property_type",
    "use_code":                     "property_type",
    # ── occupancy ─────────────────────────────────────────────────────────────
    "occupancy":                    "occupancy",
    "occupancy status":             "occupancy",
    "occupancy_status":             "occupancy",
    "occupancy type":               "occupancy",
    "occupancy_type":               "occupancy",
    "owner occupied":               "occupancy",
    "owner_occupied":               "occupancy",
    # ── purchase method / financing ───────────────────────────────────────────
    "purchase method":              "purchase_method",
    "purchase_method":              "purchase_method",
    "financing type":               "purchase_method",
    "financing_type":               "purchase_method",
    "deed type":                    "purchase_method",
    "deed_type":                    "purchase_method",
    "transaction type":             "purchase_method",
    "transaction_type":             "purchase_method",
    "loan type":                    "purchase_method",
    "loan_type":                    "purchase_method",
    "instrument type":              "purchase_method",
    "instrument_type":              "purchase_method",
    # ── linked properties count ───────────────────────────────────────────────
    "linked properties":            "linked_properties_count",
    "linked_properties":            "linked_properties_count",
    "linked properties count":      "linked_properties_count",
    "linked_properties_count":      "linked_properties_count",
    "portfolio count":              "linked_properties_count",
    "portfolio_count":              "linked_properties_count",
    "properties owned":             "linked_properties_count",
    "properties_owned":             "linked_properties_count",
    "total properties":             "linked_properties_count",
    "total_properties":             "linked_properties_count",
    "property count":               "linked_properties_count",
    "property_count":               "linked_properties_count",
}

# ─── entity-name detector ─────────────────────────────────────────────────────

_ENTITY_RE = re.compile(
    r"\b(LLC|Inc|Corp|LP|LLP|Trust|REIT|Properties|Holdings|Investments|"
    r"Homes|Builders|Development|Capital|Ventures|Partners|Group|Realty|"
    r"Fund|Assets|Acquisitions|Enterprises|Equity|Solutions|Strategies|"
    r"Associates|Management|Services|Funding|Lending|Mortgage)\b",
    re.IGNORECASE,
)

# ─── purchase-method signal detectors ────────────────────────────────────────

_CASH_RE       = re.compile(r"\bcash\b", re.I)
_CONV_RE       = re.compile(r"\b(conv|conventional)\b", re.I)
_HARD_MONEY_RE = re.compile(r"\bhard.?money\b", re.I)
_FHA_RE        = re.compile(r"\bfha\b", re.I)
_VA_RE         = re.compile(r"\bva\b", re.I)
_SFR_RE        = re.compile(r"\b(sfr|single.?fam|residential)\b", re.I)
_MFR_RE        = re.compile(r"\b(mfr|multi.?fam|duplex|triplex|quadplex|apartment)\b", re.I)
_LAND_RE       = re.compile(r"\b(land|lot|vacant|infill)\b", re.I)
_COMM_RE       = re.compile(r"\b(commercial|retail|office|industrial|warehouse)\b", re.I)
_DISTRESS_RE   = re.compile(r"\b(foreclos\w*|reo|hud|tax.?lien|short.?sale|auction)\b", re.I)

# ─── note extraction patterns ─────────────────────────────────────────────────

_NOTE_PATTERNS: list[tuple[str, str]] = [
    (r"estimated[\s_]?value[:\s]+\$?([\d,]+)", "estimated_value"),
    (r"(?:market|avm)[\s_]?value[:\s]+\$?([\d,]+)", "estimated_value"),
    (r"open[\s_]?(?:loan|mortgage)[\s_]?(?:balance)?[:\s]+\$?([\d,]+)", "open_loan_balance"),
    (r"(?:loan|mortgage)[\s_]?balance[:\s]+\$?([\d,]+)", "open_loan_balance"),
    (r"equity[:\s]+\$?([\d,]+)", "equity"),
    (r"equity[\s_]?(?:ratio|pct|%)[:\s]+([\d.]+)%?", "equity_pct"),
    (r"(?:last[\s_]?)?sale[\s_]?price[:\s]+\$?([\d,]+)", "last_sale_price"),
    (r"purchase[\s_]?price[:\s]+\$?([\d,]+)", "last_sale_price"),
    (r"(?:properties[\s_]?owned|property[\s_]?count|linked[\s_]?properties)[:\s]+(\d+)", "linked_properties_count"),
    (r"(?:portfolio[\s_]?count|total[\s_]?properties)[:\s]+(\d+)", "linked_properties_count"),
    (r"(?:last[\s_]?)?(?:sale|purchase)[\s_]?date[:\s]+([\d/\-]+)", "last_sale_date"),
    (r"counties?[:\s]+([A-Za-z ,]+?)(?:\n|$)", "county"),
    (r"purchase[\s_]?method[:\s]+([A-Za-z ]+?)(?:\n|$)", "purchase_method"),
    (r"occupancy[:\s]+([A-Za-z ]+?)(?:\n|$)", "occupancy"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PropertyRecord:
    """One row from a portfolio or linked-properties CSV."""
    source_file: str
    source_type: str            # "portfolio_export" | "linked_properties" | "manual_csv" | "note"
    owner_name:         Optional[str]
    property_address:   Optional[str]
    city:               Optional[str]
    state:              Optional[str]
    zip:                Optional[str]
    county:             Optional[str]
    apn:                Optional[str]
    estimated_value:    Optional[float]
    open_loan_balance:  Optional[float]
    equity:             Optional[float]
    equity_pct:         Optional[float]     # 0–100 or 0–1, normalised on ingest
    ltv:                Optional[float]
    last_sale_price:    Optional[float]
    last_sale_date:     Optional[str]
    dom:                Optional[float]
    property_type:      Optional[str]
    occupancy:          Optional[str]
    purchase_method:    Optional[str]
    linked_properties_count: Optional[int]


@dataclass
class ManualNote:
    """Extracted key-values from a text or markdown note file."""
    source_file: str
    screenshot_paths: list[str]
    owner_name:         Optional[str]
    estimated_value:    Optional[float]
    open_loan_balance:  Optional[float]
    equity:             Optional[float]
    equity_pct:         Optional[float]
    last_sale_price:    Optional[float]
    last_sale_date:     Optional[str]
    linked_properties_count: Optional[int]
    county:             Optional[str]
    purchase_method:    Optional[str]
    occupancy:          Optional[str]
    raw_text:           str = ""


@dataclass
class CashBuyerPortfolio:
    """Aggregated intelligence profile for one cash buyer / entity."""
    buyer_key: str
    display_name: str
    buyer_name:   Optional[str]
    entity_name:  Optional[str]

    # ── portfolio composition ─────────────────────────────────────────────────
    properties_owned_count:     int            = 0
    linked_properties_count:    int            = 0
    total_open_loan_balance:    Optional[float] = None
    total_estimated_value:      Optional[float] = None
    total_portfolio_equity:     Optional[float] = None
    equity_ratio:               Optional[float] = None
    average_sale_price:         Optional[float] = None
    average_dom:                Optional[float] = None
    purchase_method:            list[str]      = field(default_factory=list)
    counties_active:            list[str]      = field(default_factory=list)
    zip_codes_active:           list[str]      = field(default_factory=list)
    property_types_owned:       list[str]      = field(default_factory=list)
    occupancy_mix:              dict[str, int] = field(default_factory=dict)
    ownership_length_summary:   Optional[str]  = None
    recent_purchase_count:      int            = 0
    last_purchase_date:         Optional[str]  = None
    portfolio_addresses:        list[str]      = field(default_factory=list)
    source_evidence:            list[dict]     = field(default_factory=list)

    # ── scores ────────────────────────────────────────────────────────────────
    confidence_score:      float = 0.0
    liquidity_score:       float = 0.0
    buying_capacity_score: float = 0.0
    leverage_risk_score:   float = 0.0
    activity_score:        float = 0.0
    asset_match_score:     float = 0.0
    dispo_priority_score:  float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_key(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower())


def _buyer_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower()) if name else ""


def _to_float(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(re.sub(r"[$,%\s,]", "", raw))
    except (ValueError, TypeError):
        return None


def _to_int(raw: Optional[str]) -> Optional[int]:
    v = _to_float(raw)
    return int(v) if v is not None else None


def _clean_zip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = re.search(r"\b(\d{5})\b", raw)
    return m.group(1) if m else None


def _norm_equity_pct(raw_pct: Optional[float]) -> Optional[float]:
    """Normalise equity_pct to 0–1 range regardless of whether source used 0–100 or 0–1."""
    if raw_pct is None:
        return None
    return raw_pct / 100.0 if raw_pct > 1.0 else raw_pct


_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y%m%d",
    "%B %d, %Y", "%b %d, %Y",
)


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _build_col_map(headers: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    seen: set[str] = set()
    for h in headers:
        canon = _RAW_MAP.get(_norm_key(h))
        if canon and canon not in seen:
            result[h] = canon
            seen.add(canon)
    return result


def _most_common(items: list[str]) -> Optional[str]:
    return max(set(items), key=items.count) if items else None


# ═══════════════════════════════════════════════════════════════════════════════
# CSV INGESTION  (portfolio exports + linked-properties exports + manual CSVs)
# ═══════════════════════════════════════════════════════════════════════════════

def _row_to_record(row: dict, col_map: dict[str, str],
                   source_file: str, source_type: str) -> Optional[PropertyRecord]:
    canon: dict[str, str] = {}
    for raw_col, c in col_map.items():
        v = row.get(raw_col, "").strip()
        if v:
            canon.setdefault(c, v)

    owner = canon.get("owner_name", "").strip()
    if not owner:
        return None

    # Equity pct: normalise to 0–1
    raw_epct = _to_float(canon.get("equity_pct"))
    epct     = _norm_equity_pct(raw_epct)

    return PropertyRecord(
        source_file=source_file,
        source_type=source_type,
        owner_name=owner,
        property_address=canon.get("property_address"),
        city=canon.get("city"),
        state=canon.get("state"),
        zip=_clean_zip(canon.get("zip")),
        county=canon.get("county"),
        apn=canon.get("apn"),
        estimated_value=_to_float(canon.get("estimated_value")),
        open_loan_balance=_to_float(canon.get("open_loan_balance")),
        equity=_to_float(canon.get("equity")),
        equity_pct=epct,
        ltv=_to_float(canon.get("ltv")),
        last_sale_price=_to_float(canon.get("last_sale_price")),
        last_sale_date=canon.get("last_sale_date"),
        dom=_to_float(canon.get("dom")),
        property_type=canon.get("property_type"),
        occupancy=canon.get("occupancy"),
        purchase_method=canon.get("purchase_method"),
        linked_properties_count=_to_int(canon.get("linked_properties_count")),
    )


def ingest_csv_dir(
    raw_dir: Path,
    source_type: str = "portfolio_export",
) -> tuple[list[PropertyRecord], list[FileResult]]:
    records: list[PropertyRecord] = []
    skipped: list[FileResult]     = []

    if not raw_dir.exists():
        return records, skipped

    for entry in sorted(raw_dir.iterdir()):
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        if entry.suffix.lower() != ".csv":
            skipped.append(FileResult(
                path=str(entry), skipped=True,
                skip_reason=f"not a CSV (suffix: {entry.suffix!r})",
            ))
            continue

        result = read_csv_rows(entry)
        if result.skipped:
            skipped.append(result)
            continue
        if not result.rows:
            continue

        col_map = _build_col_map(list(result.rows[0].keys()))
        if not col_map:
            skipped.append(FileResult(
                path=str(entry), skipped=True,
                skip_reason="no recognised portfolio headers",
            ))
            continue

        for row in result.rows:
            rec = _row_to_record(row, col_map, str(entry), source_type)
            if rec:
                records.append(rec)

    return records, skipped


# ═══════════════════════════════════════════════════════════════════════════════
# NOTE / SCREENSHOT INGESTION  (manual text extractions)
# ═══════════════════════════════════════════════════════════════════════════════

_SCREENSHOT_RE = re.compile(
    r"(?:screenshot|image|img|photo|capture)[:\s]+([^\n]+\.(?:png|jpg|jpeg|webp|heic|pdf))",
    re.I,
)
_OWNER_NOTE_RE = re.compile(
    r"(?:owner|buyer|entity|investor|company)[:\s]+([^\n]+)",
    re.I,
)


def _extract_float_from_note(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    raw = m.group(1).replace(",", "").replace("$", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_str_from_note(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else None


def parse_note_file(path: Path) -> Optional[ManualNote]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    owner_m = _OWNER_NOTE_RE.search(text)
    owner   = owner_m.group(1).strip() if owner_m else None
    if not owner:
        return None

    screenshots = _SCREENSHOT_RE.findall(text)

    def _flt(pattern: str) -> Optional[float]:
        return _extract_float_from_note(text, pattern)

    def _str(pattern: str) -> Optional[str]:
        return _extract_str_from_note(text, pattern)

    raw_epct = _flt(r"equity[\s_]?(?:ratio|pct|%)[:\s]+([\d.]+)%?")
    epct     = _norm_equity_pct(raw_epct)

    return ManualNote(
        source_file=str(path),
        screenshot_paths=[s.strip() for s in screenshots],
        owner_name=owner,
        estimated_value=_flt(r"estimated[\s_]?value[:\s]+\$?([\d,]+)") or
                        _flt(r"(?:market|avm)[\s_]?value[:\s]+\$?([\d,]+)"),
        open_loan_balance=_flt(r"open[\s_]?(?:loan|mortgage)[\s_]?(?:balance)?[:\s]+\$?([\d,]+)") or
                          _flt(r"(?:loan|mortgage)[\s_]?balance[:\s]+\$?([\d,]+)"),
        equity=_flt(r"equity[:\s]+\$?([\d,]+)"),
        equity_pct=epct,
        last_sale_price=_flt(r"(?:last[\s_]?)?(?:sale|purchase)[\s_]?price[:\s]+\$?([\d,]+)"),
        last_sale_date=_str(r"(?:last[\s_]?)?(?:sale|purchase)[\s_]?date[:\s]+([\d/\-]+)"),
        linked_properties_count=_to_int(
            _str(r"(?:properties[\s_]?owned|property[\s_]?count|linked[\s_]?properties|"
                 r"portfolio[\s_]?count|total[\s_]?properties)[:\s]+(\d+)")
        ),
        county=_str(r"counties?[:\s]+([A-Za-z ,]+?)(?:\n|$)"),
        purchase_method=_str(r"purchase[\s_]?method[:\s]+([A-Za-z ]+?)(?:\n|$)"),
        occupancy=_str(r"occupancy[:\s]+([A-Za-z ]+?)(?:\n|$)"),
        raw_text=text,
    )


def ingest_notes_dir(notes_dir: Path) -> list[ManualNote]:
    notes: list[ManualNote] = []
    if not notes_dir.exists():
        return notes
    for entry in sorted(notes_dir.iterdir()):
        if entry.suffix.lower() not in (".txt", ".md", ".note"):
            continue
        note = parse_note_file(entry)
        if note:
            notes.append(note)
    return notes


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY SUMMARY LOADER  (buyer-activity-osint/reports/ACTIVITY_SUMMARY.json)
# ═══════════════════════════════════════════════════════════════════════════════

def load_activity_summary(reports_dir: Path) -> dict[str, dict]:
    """Return {buyer_key: profile_dict} from ACTIVITY_SUMMARY.json."""
    path = reports_dir / "ACTIVITY_SUMMARY.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result: dict[str, dict] = {}
        for profile in data.get("buyer_profiles", []):
            key = profile.get("buyer_key", "")
            if key:
                result[key] = profile
        return result
    except (json.JSONDecodeError, OSError):
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# OWNERSHIP GRAPH LOADER  (ownership-graph/reports/OWNERSHIP_GRAPH.json)
# ═══════════════════════════════════════════════════════════════════════════════

def load_ownership_graph(reports_dir: Path) -> dict[str, dict]:
    """Return {owner_key: owner_dict} from OWNERSHIP_GRAPH.json."""
    path = reports_dir / "OWNERSHIP_GRAPH.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {o["owner_key"]: o for o in data.get("owners", []) if "owner_key" in o}
    except (json.JSONDecodeError, OSError):
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def _is_entity(name: str) -> bool:
    return bool(_ENTITY_RE.search(name))


def build_portfolios(
    records:  list[PropertyRecord],
    notes:    list[ManualNote],
    activity: dict[str, dict],
    graph:    dict[str, dict],
    ref_date: Optional[date] = None,
) -> list[CashBuyerPortfolio]:
    today = ref_date or date.today()

    # ── group property records by buyer_key ──────────────────────────────────
    groups: dict[str, list[PropertyRecord]] = {}
    for rec in records:
        key = _buyer_key(rec.owner_name or "")
        if key:
            groups.setdefault(key, []).append(rec)

    # ── also register buyers seen only in notes ───────────────────────────────
    note_by_key: dict[str, list[ManualNote]] = {}
    for note in notes:
        key = _buyer_key(note.owner_name or "")
        if key:
            note_by_key.setdefault(key, []).append(note)
            groups.setdefault(key, [])   # ensure key exists

    # ── also register buyers seen only in activity / graph ───────────────────
    for key in list(activity.keys()) + list(graph.keys()):
        groups.setdefault(key, [])

    portfolios: list[CashBuyerPortfolio] = []
    for key, recs in groups.items():
        p = _make_portfolio(
            key, recs,
            note_by_key.get(key, []),
            activity.get(key, {}),
            graph.get(key, {}),
            today,
        )
        portfolios.append(p)

    portfolios.sort(key=lambda p: p.dispo_priority_score, reverse=True)
    return portfolios


def _make_portfolio(
    key:      str,
    recs:     list[PropertyRecord],
    notes:    list[ManualNote],
    act:      dict,
    grph:     dict,
    ref_date: date,
) -> CashBuyerPortfolio:
    # ── name resolution ───────────────────────────────────────────────────────
    all_names: list[str] = []
    for r in recs:
        if r.owner_name:
            all_names.append(r.owner_name)
    for n in notes:
        if n.owner_name:
            all_names.append(n.owner_name)
    if act:
        if act.get("entity_name"):
            all_names.insert(0, act["entity_name"])
        elif act.get("display_name"):
            all_names.insert(0, act["display_name"])
    if grph:
        if grph.get("display_name"):
            all_names.insert(0, grph["display_name"])

    display_name = _most_common(all_names) or key
    entity_names = [n for n in all_names if _is_entity(n)]
    individual_names = [n for n in all_names if not _is_entity(n)]
    entity_name   = _most_common(entity_names)
    buyer_name    = _most_common(individual_names)
    display_name  = entity_name or buyer_name or display_name

    # ── addresses ─────────────────────────────────────────────────────────────
    addresses: list[str] = []
    for r in recs:
        if r.property_address:
            parts = [p for p in [r.property_address, r.city, r.state, r.zip] if p]
            addresses.append(", ".join(parts))
    if grph:
        for prop in grph.get("properties", []):
            if prop.get("address"):
                parts = [p for p in [prop["address"], prop.get("city"),
                                     prop.get("state"), prop.get("zip")] if p]
                addresses.append(", ".join(parts))
    addresses = list(dict.fromkeys(addresses))  # dedupe preserving order

    # ── properties_owned_count ────────────────────────────────────────────────
    # Best source: the max of actual record count, linked_properties field, graph count
    linked_from_recs = max(
        (r.linked_properties_count for r in recs if r.linked_properties_count),
        default=0,
    )
    linked_from_notes = max(
        (n.linked_properties_count for n in notes if n.linked_properties_count),
        default=0,
    )
    graph_count     = grph.get("property_count", 0) or 0
    direct_count    = len(addresses)
    linked_count    = max(linked_from_recs, linked_from_notes, graph_count)
    owned_count     = max(direct_count, linked_count)

    # ── financial aggregates ──────────────────────────────────────────────────
    # Prefer summed per-property values; fall back to single note values.
    est_values  = [r.estimated_value  for r in recs if r.estimated_value]
    loan_bals   = [r.open_loan_balance for r in recs if r.open_loan_balance]
    equities    = [r.equity           for r in recs if r.equity]
    sale_prices = [r.last_sale_price  for r in recs if r.last_sale_price]
    doms        = [r.dom              for r in recs if r.dom is not None]

    # Supplement with note values when CSV data is absent
    if not est_values:
        est_values  = [n.estimated_value  for n in notes if n.estimated_value]
    if not loan_bals:
        loan_bals   = [n.open_loan_balance for n in notes if n.open_loan_balance]
    if not equities:
        equities    = [n.equity           for n in notes if n.equity]
    if not sale_prices:
        sale_prices = [n.last_sale_price  for n in notes if n.last_sale_price]

    total_value  = sum(est_values)  if est_values  else None
    total_loans  = sum(loan_bals)   if loan_bals   else None
    total_equity_calc = None
    if total_value is not None and total_loans is not None:
        total_equity_calc = total_value - total_loans
    elif equities:
        total_equity_calc = sum(equities)

    # Equity ratio
    equity_ratio: Optional[float] = None
    if total_value and total_value > 0 and total_equity_calc is not None:
        equity_ratio = round(total_equity_calc / total_value, 4)
    else:
        # Use direct equity_pct fields (normalised 0–1)
        pct_vals = [r.equity_pct for r in recs if r.equity_pct is not None]
        if not pct_vals:
            pct_vals = [n.equity_pct for n in notes if n.equity_pct is not None]
        if pct_vals:
            equity_ratio = round(sum(pct_vals) / len(pct_vals), 4)

    avg_sale = round(sum(sale_prices) / len(sale_prices), 2) if sale_prices else None
    avg_dom  = round(sum(doms) / len(doms), 1) if doms else None

    # ── geographic / categorical sets ────────────────────────────────────────
    counties: list[str] = sorted({r.county for r in recs if r.county})
    if not counties:
        counties = sorted({n.county for n in notes if n.county})
    if grph:
        for p in grph.get("properties", []):
            if p.get("county") and p["county"] not in counties:
                counties.append(p["county"])

    zip_codes: list[str] = sorted({r.zip for r in recs if r.zip})
    if grph:
        for p in grph.get("properties", []):
            z = _clean_zip(p.get("zip"))
            if z and z not in zip_codes:
                zip_codes.append(z)

    prop_types: list[str] = sorted({r.property_type for r in recs if r.property_type})
    all_ptypes_str = " ".join(prop_types)

    purchase_methods: list[str] = sorted({r.purchase_method for r in recs if r.purchase_method})
    if not purchase_methods:
        purchase_methods = sorted({n.purchase_method for n in notes if n.purchase_method})
    all_pm_str = " ".join(purchase_methods)

    occupancy_mix: dict[str, int] = {}
    for r in recs:
        if r.occupancy:
            occ = r.occupancy.strip().lower()
            occupancy_mix[occ] = occupancy_mix.get(occ, 0) + 1

    # ── dates ─────────────────────────────────────────────────────────────────
    all_dates: list[date] = []
    for r in recs:
        d = _parse_date(r.last_sale_date)
        if d:
            all_dates.append(d)
    for n in notes:
        d = _parse_date(n.last_sale_date)
        if d:
            all_dates.append(d)
    all_dates.sort()

    last_purchase_date = all_dates[-1].isoformat() if all_dates else None

    # Enrich from activity profile
    recent_purchase_count = 0
    days_since: Optional[int] = None
    if act:
        recent_purchase_count = act.get("recent_purchase_count_90d", 0) or 0
        if not last_purchase_date and act.get("last_purchase_date"):
            last_purchase_date = act["last_purchase_date"]
    if last_purchase_date:
        d = _parse_date(last_purchase_date)
        if d:
            days_since = (ref_date - d).days

    # ── ownership length summary ──────────────────────────────────────────────
    if all_dates:
        span_days = (all_dates[-1] - all_dates[0]).days if len(all_dates) > 1 else 0
        if span_days == 0:
            ownership_length_summary = "single observed transaction"
        elif span_days < 365:
            ownership_length_summary = f"active ~{span_days}d"
        else:
            years = round(span_days / 365, 1)
            ownership_length_summary = f"active ~{years}yr"
    else:
        ownership_length_summary = None

    # ── source evidence list ──────────────────────────────────────────────────
    evidence: list[dict] = []
    for r in recs:
        evidence.append({
            "source_file": Path(r.source_file).name,
            "source_type": r.source_type,
            "address":     r.property_address,
            "estimated_value":   r.estimated_value,
            "open_loan_balance": r.open_loan_balance,
            "last_sale_price":   r.last_sale_price,
            "last_sale_date":    r.last_sale_date,
        })
    for n in notes:
        evidence.append({
            "source_file":       Path(n.source_file).name,
            "source_type":       "manual_note",
            "screenshot_paths":  n.screenshot_paths,
            "estimated_value":   n.estimated_value,
            "open_loan_balance": n.open_loan_balance,
            "last_sale_price":   n.last_sale_price,
            "last_sale_date":    n.last_sale_date,
        })
    if act:
        for ev in act.get("recent_purchase_evidence", []):
            evidence.append({"source_type": "activity_osint", **ev})
    if grph:
        evidence.append({
            "source_type":   "ownership_graph",
            "source_file":   ", ".join(grph.get("source_files", [])),
            "property_count": grph.get("property_count"),
        })

    # ── scoring ───────────────────────────────────────────────────────────────
    confidence = _score_confidence(
        est_values, loan_bals, all_dates, evidence, notes
    )
    liquidity  = _score_liquidity(equity_ratio, all_pm_str)
    capacity   = _score_buying_capacity(
        owned_count, equity_ratio, total_equity_calc,
        avg_sale, act,
    )
    leverage   = _score_leverage_risk(equity_ratio, total_value, total_loans)
    activity_s = _score_activity(act, days_since, recent_purchase_count)
    asset_match = _score_asset_match(all_ptypes_str, all_pm_str)
    dispo      = _score_dispo_priority(liquidity, activity_s, asset_match, capacity, confidence)

    return CashBuyerPortfolio(
        buyer_key=key,
        display_name=display_name,
        buyer_name=buyer_name,
        entity_name=entity_name,
        properties_owned_count=owned_count,
        linked_properties_count=linked_count,
        total_open_loan_balance=round(total_loans, 2) if total_loans else None,
        total_estimated_value=round(total_value, 2) if total_value else None,
        total_portfolio_equity=round(total_equity_calc, 2) if total_equity_calc else None,
        equity_ratio=equity_ratio,
        average_sale_price=avg_sale,
        average_dom=avg_dom,
        purchase_method=purchase_methods,
        counties_active=counties,
        zip_codes_active=zip_codes,
        property_types_owned=prop_types,
        occupancy_mix=occupancy_mix,
        ownership_length_summary=ownership_length_summary,
        recent_purchase_count=recent_purchase_count,
        last_purchase_date=last_purchase_date,
        portfolio_addresses=addresses,
        source_evidence=evidence,
        confidence_score=confidence,
        liquidity_score=liquidity,
        buying_capacity_score=capacity,
        leverage_risk_score=leverage,
        activity_score=activity_s,
        asset_match_score=asset_match,
        dispo_priority_score=dispo,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _score_confidence(
    est_values:  list[float],
    loan_bals:   list[float],
    dated_txns:  list[date],
    evidence:    list[dict],
    notes:       list[ManualNote],
) -> float:
    score = 0.0
    if est_values:   score += 25.0
    if loan_bals:    score += 20.0
    if dated_txns:   score += 15.0
    # Evidence sources: +10 per unique source type up to 20
    src_types = {e.get("source_type") for e in evidence}
    score += min(20.0, len(src_types) * 10.0)
    # Has property addresses: +10
    if any(e.get("address") for e in evidence):
        score += 10.0
    # Note-only penalty: −15 if no CSV records at all, only notes
    if notes and not est_values and not loan_bals:
        score -= 15.0
    return min(100.0, round(max(0.0, score), 1))


def _score_liquidity(equity_ratio: Optional[float], pm_str: str) -> float:
    """High equity + cash purchases = high liquidity."""
    if equity_ratio is None:
        base = 20.0
    elif equity_ratio >= 0.90:
        base = 95.0
    elif equity_ratio >= 0.80:
        base = 85.0
    elif equity_ratio >= 0.60:
        base = 65.0
    elif equity_ratio >= 0.40:
        base = 45.0
    elif equity_ratio >= 0.20:
        base = 28.0
    else:
        base = 10.0

    bonus = 0.0
    if _CASH_RE.search(pm_str):
        bonus += 10.0
    if not pm_str.strip():
        bonus += 5.0      # no loan record at all = likely cash
    return min(100.0, round(base + bonus, 1))


def _score_buying_capacity(
    owned_count:        int,
    equity_ratio:       Optional[float],
    total_equity:       Optional[float],
    avg_sale_price:     Optional[float],
    act:                dict,
) -> float:
    score = 0.0
    # Portfolio size signal (up to 30)
    score += min(30.0, owned_count * 2.0)
    # Equity available as down-payment pool (up to 40)
    if total_equity and total_equity > 0:
        # $50k per deal → how many deals can they fund?
        capacity_units = total_equity / 50_000
        score += min(40.0, capacity_units * 5.0)
    elif equity_ratio is not None:
        score += equity_ratio * 25.0
    # Activity-based velocity (up to 20)
    if act:
        vel = act.get("purchase_velocity_score", 0.0) or 0.0
        score += vel * 0.20
    # SFR repeat buyer boost (up to 10)
    if act and act.get("multi_purchase_buyer"):
        score += 10.0
    return min(100.0, round(score, 1))


def _score_leverage_risk(
    equity_ratio:  Optional[float],
    total_value:   Optional[float],
    total_loans:   Optional[float],
) -> float:
    """Higher score = more leveraged = higher risk."""
    if equity_ratio is not None:
        ltv = 1.0 - equity_ratio
        return round(min(100.0, max(0.0, ltv * 100.0)), 1)
    if total_value and total_value > 0 and total_loans is not None:
        ltv = total_loans / total_value
        return round(min(100.0, max(0.0, ltv * 100.0)), 1)
    # Unknown leverage = moderate risk assumed
    return 50.0


def _score_activity(
    act:           dict,
    days_since:    Optional[int],
    recent_count:  int,
) -> float:
    """Pull directly from acquisition_heat_score when available."""
    if act and act.get("acquisition_heat_score") is not None:
        return min(100.0, round(float(act["acquisition_heat_score"]), 1))
    # Fallback: build from days_since + recent_count
    if days_since is None:
        recency = 0.0
    elif days_since <= 30:
        recency = 100.0
    elif days_since <= 90:
        recency = 80.0
    elif days_since <= 180:
        recency = 55.0
    elif days_since <= 365:
        recency = 30.0
    else:
        years_over = (days_since - 365) / 365
        recency = max(0.0, 15.0 - years_over * 15.0)

    volume = min(30.0, recent_count * 15.0)
    return round(min(100.0, 0.60 * recency + 0.40 * volume), 1)


def _score_asset_match(ptypes_str: str, pm_str: str) -> float:
    """How closely the buyer's portfolio matches SFR/cash deal targets."""
    score = 0.0
    if _SFR_RE.search(ptypes_str):   score += 35.0
    if _CASH_RE.search(pm_str):      score += 25.0
    if _DISTRESS_RE.search(ptypes_str + " " + pm_str): score += 20.0
    if _LAND_RE.search(ptypes_str):  score += 10.0
    if _MFR_RE.search(ptypes_str):   score += 5.0
    if _HARD_MONEY_RE.search(pm_str): score += 5.0
    # Penalise purely commercial portfolios
    if _COMM_RE.search(ptypes_str) and not _SFR_RE.search(ptypes_str):
        score -= 15.0
    return min(100.0, round(max(0.0, score), 1))


def _score_dispo_priority(
    liquidity:   float,
    activity:    float,
    asset_match: float,
    capacity:    float,
    confidence:  float,
) -> float:
    """
    35% activity (recent acquisition behaviour)
    + 30% liquidity (equity/cash available)
    + 20% asset match (SFR/cash/distress fit)
    + 10% buying capacity (portfolio size + equity pool)
    + 5%  confidence (evidence quality gate)
    """
    raw = (
        0.35 * activity
        + 0.30 * liquidity
        + 0.20 * asset_match
        + 0.10 * capacity
        + 0.05 * confidence
    )
    return min(100.0, round(raw, 1))


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT WRITERS
# ═══════════════════════════════════════════════════════════════════════════════

def _portfolio_to_dict(p: CashBuyerPortfolio) -> dict:
    return {
        "buyer_key":                  p.buyer_key,
        "display_name":               p.display_name,
        "buyer_name":                 p.buyer_name,
        "entity_name":                p.entity_name,
        "properties_owned_count":     p.properties_owned_count,
        "linked_properties_count":    p.linked_properties_count,
        "total_open_loan_balance":    p.total_open_loan_balance,
        "total_estimated_value":      p.total_estimated_value,
        "total_portfolio_equity":     p.total_portfolio_equity,
        "equity_ratio":               p.equity_ratio,
        "average_sale_price":         p.average_sale_price,
        "average_dom":                p.average_dom,
        "purchase_method":            p.purchase_method,
        "counties_active":            p.counties_active,
        "zip_codes_active":           p.zip_codes_active,
        "property_types_owned":       p.property_types_owned,
        "occupancy_mix":              p.occupancy_mix,
        "ownership_length_summary":   p.ownership_length_summary,
        "recent_purchase_count":      p.recent_purchase_count,
        "last_purchase_date":         p.last_purchase_date,
        "portfolio_addresses":        p.portfolio_addresses,
        "source_evidence":            p.source_evidence,
        "confidence_score":           p.confidence_score,
        "liquidity_score":            p.liquidity_score,
        "buying_capacity_score":      p.buying_capacity_score,
        "leverage_risk_score":        p.leverage_risk_score,
        "activity_score":             p.activity_score,
        "asset_match_score":          p.asset_match_score,
        "dispo_priority_score":       p.dispo_priority_score,
    }


def write_reports(
    portfolios:   list[CashBuyerPortfolio],
    skipped:      list[FileResult],
    reports_dir:  Path,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    portfolios = sorted(portfolios, key=lambda p: p.dispo_priority_score, reverse=True)

    _write_cash_buyer_portfolios_json(portfolios, skipped, reports_dir, ts)
    _write_high_capacity_buyers_json(portfolios, reports_dir, ts)
    _write_leveraged_buyers_json(portfolios, reports_dir, ts)
    _write_dispo_targets_md(portfolios, reports_dir, ts)
    _write_portfolio_report_md(portfolios, skipped, reports_dir, ts)


def _write_cash_buyer_portfolios_json(
    portfolios: list[CashBuyerPortfolio],
    skipped:    list[FileResult],
    reports_dir: Path,
    ts: str,
) -> None:
    payload = {
        "run_timestamp":    ts,
        "portfolio_count":  len(portfolios),
        "portfolios":       [_portfolio_to_dict(p) for p in portfolios],
        "skipped_files":    [
            {"file": Path(r.path).name, "reason": r.skip_reason}
            for r in skipped
        ],
    }
    (reports_dir / "CASH_BUYER_PORTFOLIOS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def _write_high_capacity_buyers_json(
    portfolios: list[CashBuyerPortfolio],
    reports_dir: Path,
    ts: str,
) -> None:
    high = [
        _portfolio_to_dict(p) for p in portfolios
        if p.liquidity_score >= 60.0 and p.buying_capacity_score >= 40.0
    ]
    payload = {
        "run_timestamp": ts,
        "count":         len(high),
        "criteria":      "liquidity_score >= 60 AND buying_capacity_score >= 40",
        "buyers":        high,
    }
    (reports_dir / "HIGH_CAPACITY_BUYERS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def _write_leveraged_buyers_json(
    portfolios: list[CashBuyerPortfolio],
    reports_dir: Path,
    ts: str,
) -> None:
    leveraged = [
        _portfolio_to_dict(p) for p in portfolios
        if p.leverage_risk_score >= 60.0
    ]
    payload = {
        "run_timestamp": ts,
        "count":         len(leveraged),
        "criteria":      "leverage_risk_score >= 60",
        "note":          "High leverage = more motivated sellers / equity-light buyers",
        "buyers":        leveraged,
    }
    (reports_dir / "LEVERAGED_BUYERS.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


def _fmt_money(v: Optional[float]) -> str:
    return f"${v:,.0f}" if v is not None else "—"


def _fmt_pct(v: Optional[float]) -> str:
    return f"{v * 100:.1f}%" if v is not None else "—"


def _write_dispo_targets_md(
    portfolios: list[CashBuyerPortfolio],
    reports_dir: Path,
    ts: str,
) -> None:
    top = [p for p in portfolios if p.dispo_priority_score >= 40.0][:30]
    lines = [
        "# DISPO_TARGETS",
        "",
        f"_Generated: {ts}_",
        f"_Showing top {len(top)} buyers by dispo_priority_score (≥40)_",
        "",
        "Scoring formula: 35% activity + 30% liquidity + 20% asset match + "
        "10% buying capacity + 5% confidence",
        "",
    ]
    if not top:
        lines.append("> No buyers meet the dispo priority threshold (≥40).\n")
    else:
        for rank, p in enumerate(top, 1):
            lines += [
                f"## {rank}. {p.display_name}",
                "",
                f"| Metric | Value |",
                f"|---|---|",
                f"| **Dispo Priority Score** | **{p.dispo_priority_score}** |",
                f"| Activity Score           | {p.activity_score} |",
                f"| Liquidity Score          | {p.liquidity_score} |",
                f"| Asset Match Score        | {p.asset_match_score} |",
                f"| Buying Capacity Score    | {p.buying_capacity_score} |",
                f"| Leverage Risk Score      | {p.leverage_risk_score} |",
                f"| Confidence Score         | {p.confidence_score} |",
                f"| Properties Owned         | {p.properties_owned_count} |",
                f"| Total Est. Value         | {_fmt_money(p.total_estimated_value)} |",
                f"| Total Portfolio Equity   | {_fmt_money(p.total_portfolio_equity)} |",
                f"| Equity Ratio             | {_fmt_pct(p.equity_ratio)} |",
                f"| Last Purchase            | {p.last_purchase_date or '—'} |",
                f"| Recent Purchases (90d)   | {p.recent_purchase_count} |",
                f"| Purchase Methods         | {', '.join(p.purchase_method) or '—'} |",
                f"| Counties Active          | {', '.join(p.counties_active) or '—'} |",
                f"| ZIP Codes                | {', '.join(p.zip_codes_active) or '—'} |",
                f"| Property Types           | {', '.join(p.property_types_owned) or '—'} |",
                "",
            ]
            if p.portfolio_addresses:
                lines.append("**Portfolio Addresses (sample):**")
                for addr in p.portfolio_addresses[:5]:
                    lines.append(f"- {addr}")
                if len(p.portfolio_addresses) > 5:
                    lines.append(f"- _(+{len(p.portfolio_addresses) - 5} more)_")
                lines.append("")

            if p.source_evidence:
                lines.append("**Source Evidence:**")
                for ev in p.source_evidence[:4]:
                    src = ev.get("source_file") or ev.get("source_type", "?")
                    lines.append(f"- `{src}`")
                if len(p.source_evidence) > 4:
                    lines.append(f"- _(+{len(p.source_evidence) - 4} more)_")
                lines.append("")

    (reports_dir / "DISPO_TARGETS.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _write_portfolio_report_md(
    portfolios: list[CashBuyerPortfolio],
    skipped:    list[FileResult],
    reports_dir: Path,
    ts: str,
) -> None:
    lines = [
        "# CASH_BUYER_PORTFOLIO_REPORT",
        "",
        f"_Generated: {ts}_",
        f"_Portfolios: {len(portfolios)}_",
        "",
        "## Summary",
        "",
    ]

    # Summary table
    hot = sum(1 for p in portfolios if p.activity_score >= 60)
    high_liq = sum(1 for p in portfolios if p.liquidity_score >= 60)
    high_lev = sum(1 for p in portfolios if p.leverage_risk_score >= 60)
    high_cap = sum(1 for p in portfolios if p.buying_capacity_score >= 40)
    lines += [
        "| Category | Count |",
        "|---|---|",
        f"| Total portfolios tracked | {len(portfolios)} |",
        f"| Active buyers (activity ≥ 60) | {hot} |",
        f"| High liquidity (liquidity ≥ 60) | {high_liq} |",
        f"| High leverage (risk ≥ 60) | {high_lev} |",
        f"| High capacity (capacity ≥ 40) | {high_cap} |",
        "",
    ]

    # Skipped files
    lines += ["## Skipped Files", ""]
    if skipped:
        lines += ["| File | Reason |", "|---|---|"]
        for r in skipped:
            lines.append(f"| `{Path(r.path).name}` | {r.skip_reason} |")
    else:
        lines.append("> No files skipped.")
    lines.append("")

    # Per-portfolio detail
    lines += ["## Portfolio Detail", ""]
    for p in portfolios:
        lines += [
            f"### {p.display_name}",
            "",
            f"- **Dispo Priority**: {p.dispo_priority_score}  "
            f"| **Activity**: {p.activity_score}  "
            f"| **Liquidity**: {p.liquidity_score}  "
            f"| **Asset Match**: {p.asset_match_score}",
        ]
        if p.entity_name:
            lines.append(f"- **Entity**: {p.entity_name}")
        if p.buyer_name:
            lines.append(f"- **Individual**: {p.buyer_name}")
        lines += [
            f"- **Properties owned**: {p.properties_owned_count}  "
            f"(linked: {p.linked_properties_count})",
        ]
        if p.total_estimated_value is not None:
            lines.append(
                f"- **Total est. value**: {_fmt_money(p.total_estimated_value)}  "
                f"| **Equity**: {_fmt_money(p.total_portfolio_equity)}  "
                f"({_fmt_pct(p.equity_ratio)})"
            )
        if p.total_open_loan_balance is not None:
            lines.append(f"- **Open loan balance**: {_fmt_money(p.total_open_loan_balance)}")
        if p.average_sale_price is not None:
            lines.append(f"- **Avg sale price**: {_fmt_money(p.average_sale_price)}")
        if p.average_dom is not None:
            lines.append(f"- **Avg DOM**: {p.average_dom}")
        if p.last_purchase_date:
            lines.append(
                f"- **Last purchase**: {p.last_purchase_date}  "
                f"(recent 90d: {p.recent_purchase_count})"
            )
        if p.purchase_method:
            lines.append(f"- **Purchase methods**: {', '.join(p.purchase_method)}")
        if p.counties_active:
            lines.append(f"- **Counties**: {', '.join(p.counties_active)}")
        if p.zip_codes_active:
            lines.append(f"- **ZIP codes**: {', '.join(p.zip_codes_active)}")
        if p.property_types_owned:
            lines.append(f"- **Property types**: {', '.join(p.property_types_owned)}")
        if p.occupancy_mix:
            occ_str = ", ".join(f"{k}: {v}" for k, v in p.occupancy_mix.items())
            lines.append(f"- **Occupancy mix**: {occ_str}")
        if p.ownership_length_summary:
            lines.append(f"- **Ownership span**: {p.ownership_length_summary}")
        if p.confidence_score < 40:
            lines.append(f"- **⚠ Confidence**: {p.confidence_score} (low — limited source data)")
        else:
            lines.append(f"- **Confidence**: {p.confidence_score}")
        if p.source_evidence:
            src_names = sorted({
                ev.get("source_file") or ev.get("source_type", "?")
                for ev in p.source_evidence
            })
            lines.append(f"- **Sources**: {', '.join(src_names[:6])}")
        lines.append("")

    (reports_dir / "CASH_BUYER_PORTFOLIO_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cash Buyer Portfolio Intel — builds evidence-backed portfolio profiles"
    )
    parser.add_argument("--workspace-root", default=".",
                        help="Workspace root containing data/ and agents/")
    parser.add_argument("--portfolio-dir", default=None,
                        help="Override portfolio CSV input directory")
    parser.add_argument("--linked-dir", default=None,
                        help="Override linked-properties CSV input directory")
    parser.add_argument("--notes-dir", default=None,
                        help="Override manual notes directory")
    parser.add_argument("--reports-dir", default=None,
                        help="Override reports output directory")
    parser.add_argument("--activity-reports", default=None,
                        help="Path to buyer-activity-osint reports directory")
    parser.add_argument("--graph-reports", default=None,
                        help="Path to ownership-graph reports directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without writing files")
    args = parser.parse_args(argv)

    workspace    = Path(args.workspace_root).expanduser().resolve()
    portfolio_dir = (Path(args.portfolio_dir).resolve() if args.portfolio_dir
                     else workspace / "data" / "portfolio-intel" / "raw")
    linked_dir   = (Path(args.linked_dir).resolve() if args.linked_dir
                    else workspace / "data" / "portfolio-intel" / "linked")
    notes_dir    = (Path(args.notes_dir).resolve() if args.notes_dir
                    else workspace / "data" / "portfolio-intel" / "notes")
    reports_dir  = (Path(args.reports_dir).resolve() if args.reports_dir
                    else Path(__file__).parent / "reports")
    activity_rpt = (Path(args.activity_reports).resolve() if args.activity_reports
                    else workspace / "agents" / "buyer-activity-osint" / "reports")
    graph_rpt    = (Path(args.graph_reports).resolve() if args.graph_reports
                    else workspace / "agents" / "ownership-graph" / "reports")

    print(f"\n{'━'*34}\n  cash-buyer-portfolio-intel\n{'━'*34}\n")
    print(f"  workspace:     {workspace}")
    print(f"  portfolio dir: {portfolio_dir}")
    print(f"  linked dir:    {linked_dir}")
    print(f"  notes dir:     {notes_dir}")

    # ── ingest ──────────────────────────────────────────────────────────────
    records, skipped1 = ingest_csv_dir(portfolio_dir, source_type="portfolio_export")
    linked_recs, skipped2 = ingest_csv_dir(linked_dir, source_type="linked_properties")
    all_records = records + linked_recs
    all_skipped = skipped1 + skipped2

    notes = ingest_notes_dir(notes_dir)
    activity = load_activity_summary(activity_rpt)
    graph    = load_ownership_graph(graph_rpt)

    print(f"  Portfolio rows:   {len(records)}")
    print(f"  Linked rows:      {len(linked_recs)}")
    print(f"  Notes:            {len(notes)}")
    print(f"  Activity profiles:{len(activity)}")
    print(f"  Graph owners:     {len(graph)}")
    print(f"  Skipped files:    {len(all_skipped)}")

    # ── build ────────────────────────────────────────────────────────────────
    portfolios = build_portfolios(all_records, notes, activity, graph)

    print(f"  Portfolios:       {len(portfolios)}")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return 0

    # ── write ────────────────────────────────────────────────────────────────
    write_reports(portfolios, all_skipped, reports_dir)
    print(f"\n  Reports written to: {reports_dir}/")
    for fname in [
        "CASH_BUYER_PORTFOLIOS.json",
        "HIGH_CAPACITY_BUYERS.json",
        "LEVERAGED_BUYERS.json",
        "DISPO_TARGETS.md",
        "CASH_BUYER_PORTFOLIO_REPORT.md",
    ]:
        fpath = reports_dir / fname
        size = fpath.stat().st_size if fpath.exists() else 0
        print(f"    ✓  {fname}  ({size} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
