"""
Ingest CSVs from data/buyer-activity/raw/.

For each file:
  • Detect format (propwire vs deed/export)
  • Map headers to canonical fields via header_map
  • Normalise and yield Transaction objects
  • Record why files were skipped in IgnoredFile objects
"""
from __future__ import annotations
import csv
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Allow running this file standalone from any cwd
sys.path.insert(0, str(Path(__file__).parent))
from header_map import build_column_map, detect_format  # noqa: E402

RAW_DIR = Path(__file__).parent / "raw"

_ENTITY_RE = re.compile(
    r"\b(LLC|Inc|Corp|LP|LLP|Trust|REIT|Properties|Holdings|Investments|"
    r"Homes|Builders|Development|Capital|Ventures|Partners|Group|Realty|"
    r"Fund|Assets|Acquisitions|Solutions|Enterprises|Industries)\b",
    re.IGNORECASE,
)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Transaction:
    source_file: str
    fmt: str                          # 'propwire' | 'deed' | 'unknown'
    buyer_name:      Optional[str] = None
    buyer_name_2:    Optional[str] = None
    buyer_entity:    Optional[str] = None
    seller_name:     Optional[str] = None
    property_address: Optional[str] = None
    city:            Optional[str] = None
    state:           Optional[str] = None
    zip:             Optional[str] = None
    county:          Optional[str] = None
    apn:             Optional[str] = None
    sale_date:       Optional[str] = None
    sale_price:      Optional[float] = None
    property_type:   Optional[str] = None
    financing_type:  Optional[str] = None
    lender_name:     Optional[str] = None
    loan_amount:     Optional[float] = None
    beds:            Optional[int] = None
    baths:           Optional[float] = None
    sqft:            Optional[int] = None
    year_built:      Optional[int] = None


@dataclass
class IgnoredFile:
    path: str
    reason: str


# ── Public entry point ────────────────────────────────────────────────────────

def load_raw_dir(
    raw_dir: Path = RAW_DIR,
) -> tuple[list[Transaction], list[IgnoredFile]]:
    """
    Scan *raw_dir* for CSV files and return (transactions, ignored_files).
    Non-CSV files, empty files, and files with no recognised buyer column are
    all captured in ignored_files with an explanation.
    """
    transactions: list[Transaction] = []
    ignored: list[IgnoredFile] = []

    if not raw_dir.exists():
        return transactions, ignored

    for entry in sorted(raw_dir.iterdir()):
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue  # hidden / private files silently skipped

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


# ── Per-file ingestion ────────────────────────────────────────────────────────

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

        canonical_targets = set(col_map.values())
        has_buyer_field = bool(
            canonical_targets & {"buyer_name", "buyer_name_2", "buyer_entity"}
        )
        if not has_buyer_field:
            cols = ", ".join(sorted(canonical_targets))
            return [], f"no buyer/grantee/owner column mapped (mapped: {cols})"

        rows = list(reader)
        if not rows:
            return [], "no data rows after header"

        transactions: list[Transaction] = []
        for row in rows:
            txn = _map_row(row, col_map, str(path), fmt)
            if txn is not None:
                transactions.append(txn)

        if not transactions:
            return [], "all rows lacked a usable buyer identifier"

        return transactions, None


def _map_row(
    row: dict[str, str],
    col_map: dict[str, str],
    source_file: str,
    fmt: str,
) -> Optional[Transaction]:
    # Collect non-empty canonical values
    canonical: dict[str, str] = {}
    for raw_col, canon in col_map.items():
        val = row.get(raw_col, "").strip()
        if val:
            canonical[canon] = val

    buyer_name   = canonical.get("buyer_name")
    buyer_entity = canonical.get("buyer_entity")

    # If buyer_name looks like an entity, promote it
    if not buyer_entity and buyer_name and _entity_re_match(buyer_name):
        buyer_entity = buyer_name
        buyer_name = None

    # Must have at least one buyer identifier
    if not buyer_name and not buyer_entity and not canonical.get("buyer_name_2"):
        return None

    return Transaction(
        source_file=source_file,
        fmt=fmt,
        buyer_name=buyer_name,
        buyer_name_2=canonical.get("buyer_name_2"),
        buyer_entity=buyer_entity,
        seller_name=canonical.get("seller_name"),
        property_address=canonical.get("property_address"),
        city=canonical.get("city"),
        state=canonical.get("state"),
        zip=_clean_zip(canonical.get("zip")),
        county=canonical.get("county"),
        apn=canonical.get("apn"),
        sale_date=canonical.get("sale_date"),
        sale_price=_to_dollars(canonical.get("sale_price")),
        property_type=canonical.get("property_type"),
        financing_type=canonical.get("financing_type"),
        lender_name=canonical.get("lender_name"),
        loan_amount=_to_dollars(canonical.get("loan_amount")),
        beds=_to_int(canonical.get("beds")),
        baths=_to_float(canonical.get("baths")),
        sqft=_to_int(canonical.get("sqft")),
        year_built=_to_int(canonical.get("year_built")),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _entity_re_match(name: str) -> bool:
    return bool(_ENTITY_RE.search(name))


def _clean_zip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = re.search(r"\b(\d{5})(?:-\d{4})?\b", raw)
    return m.group(1) if m else raw.strip()


def _to_dollars(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    clean = re.sub(r"[$,\s]", "", raw)
    try:
        return float(clean)
    except ValueError:
        return None


def _to_float(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _to_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    clean = re.sub(r"[,\s]", "", raw)
    try:
        return int(float(clean))
    except ValueError:
        return None
