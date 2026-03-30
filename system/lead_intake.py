"""
AMARA Auto Matcher — Stage 1: Lead Intake + Stage 2: Property Classification

Stage 1: Normalizes incoming leads from any source into a standard PropertyLead.
Stage 2: Classifies each lead into a processing path before any math runs.
"""

from __future__ import annotations

import csv
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ─── Property Types ───────────────────────────────────────────────────────────

class PropertyType:
    SFR        = "SFR"
    MFR        = "MFR"
    LAND       = "land"
    COMMERCIAL = "commercial"
    MOBILE     = "mobile"
    UNKNOWN    = "unknown"


# ─── Classification Outcomes ──────────────────────────────────────────────────

class Classification:
    SFR_WHOLESALE   = "sfr_wholesale"
    RENTAL_HEDGE    = "rental_hedge"
    INFILL_LOT      = "infill_lot"
    LAND_SUBDIVISION= "land_subdivision"
    DEAD_PAPER      = "dead_paper"
    REJECT          = "reject"


# ─── Lead Sources ─────────────────────────────────────────────────────────────

class LeadSource:
    ZILLOW     = "zillow"
    XLEADS     = "xleads"
    PROPSTREAM = "propstream"
    PROPELIO   = "propelio"
    CSV        = "csv"
    MANUAL     = "manual"


# ─── Stage 1: Property Lead ───────────────────────────────────────────────────

@dataclass
class PropertyLead:
    """Normalized incoming lead — output of Stage 1."""
    property_id:   str
    source:        str
    address:       str
    city:          str
    state:         str
    zip_code:      str
    county_name:   str        = ""
    parcel_id:     str        = ""
    property_type: str        = PropertyType.UNKNOWN
    beds:          float      = 0
    baths:         float      = 0
    sqft:          int        = 0
    lot_size:      float      = 0       # acres
    year_built:    int        = 0
    list_price:    float      = 0
    dom:           int        = 0
    price_drops:   int        = 0
    keywords:      list[str]  = field(default_factory=list)
    description:   str        = ""
    has_photos:    bool       = False
    bad_photos_flag: bool     = False
    created_at:    str        = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def price_per_sqft(self) -> float:
        if self.sqft and self.list_price:
            return self.list_price / self.sqft
        return 0.0

    def is_land(self) -> bool:
        return self.property_type in (PropertyType.LAND,) or (
            self.sqft == 0 and self.lot_size > 0.5
        )

    def summary(self) -> str:
        return (
            f"{self.property_id} | {self.address}, {self.city} {self.state} {self.zip_code} | "
            f"{self.property_type} | ${self.list_price:,.0f} | "
            f"{self.beds}bd/{self.baths}ba {self.sqft:,}sqft | DOM:{self.dom}"
        )


# ─── Stage 2: Property Classification ─────────────────────────────────────────

@dataclass
class ClassificationResult:
    property_id:          str
    classification:       str
    dead_paper_candidate: bool   = False
    hedge_fund_fit:       bool   = False
    infill_candidate:     bool   = False
    reject_reason:        str    = ""
    notes:                str    = ""

    def is_workable(self) -> bool:
        return self.classification != Classification.REJECT


# Keyword lists for classification signals
_DISTRESS_KEYWORDS = {
    "probate", "estate", "inherited", "heir", "trust", "deceased",
    "divorce", "foreclosure", "pre-foreclosure", "tax lien", "tax delinquent",
    "motivated", "must sell", "as-is", "as is", "fixer", "handyman",
    "vacant", "abandoned", "cash only", "investor special", "tlc",
    "price reduced", "reduced", "bring all offers",
}

_DEAD_PAPER_KEYWORDS = {
    "plat", "platted", "recorded subdivision", "ghost street", "phase",
    "lot and block", "unimproved", "raw land", "acreage",
    "developer", "development opportunity", "entitled", "entitlement",
    "zoned residential", "zoned r-1", "zoned r-2",
}

_REJECT_SIGNALS = {
    "condo", "townhome", "townhouse", "co-op", "hoa fee",
    "age restricted", "55+", "leasehold",
}

_HIGH_EQUITY_RENTAL_SIGNALS = {
    "tenant occupied", "currently rented", "leased", "rental income",
    "cash flow", "cap rate", "noi",
}


def _extract_keywords(description: str) -> list[str]:
    """Pull known signal keywords from a property description."""
    found = []
    desc_lower = description.lower()
    for kw in (_DISTRESS_KEYWORDS | _DEAD_PAPER_KEYWORDS | _HIGH_EQUITY_RENTAL_SIGNALS):
        if kw in desc_lower:
            found.append(kw)
    return found


def classify_property(lead: PropertyLead) -> ClassificationResult:
    """
    Stage 2: Determine processing path for an incoming lead.

    Classification priority:
    1. reject          — signals that make the deal non-viable for wholesale
    2. dead_paper      — land subdivision / ghost streets / plat gaps
    3. land_subdivision— raw land / large lot / development
    4. infill_lot      — small urban lot with builder demand
    5. rental_hedge    — fits buy-and-hold buy box signals
    6. sfr_wholesale   — default SFR path
    """
    desc_lower = (lead.description or "").lower()
    kw_set     = set(lead.keywords or []) | {kw for kw in _extract_keywords(lead.description or "")}
    notes_parts = []

    # ── Hard rejects ──────────────────────────────────────────────────────────
    for signal in _REJECT_SIGNALS:
        if signal in desc_lower:
            return ClassificationResult(
                property_id=lead.property_id,
                classification=Classification.REJECT,
                reject_reason=f"Reject signal found: '{signal}'",
            )

    if lead.property_type in (PropertyType.COMMERCIAL, PropertyType.MOBILE):
        return ClassificationResult(
            property_id=lead.property_id,
            classification=Classification.REJECT,
            reject_reason=f"Property type '{lead.property_type}' outside wholesale scope",
        )

    if lead.list_price <= 0:
        return ClassificationResult(
            property_id=lead.property_id,
            classification=Classification.REJECT,
            reject_reason="No list price — cannot underwrite",
        )

    # ── Dead paper / land subdivision ─────────────────────────────────────────
    dead_paper_hit = bool(kw_set & _DEAD_PAPER_KEYWORDS)
    is_land_type   = lead.property_type == PropertyType.LAND or lead.is_land()

    ghost_street  = any(k in desc_lower for k in ("ghost street", "platted streets", "recorded plat"))
    plat_gap      = any(k in desc_lower for k in ("phase", "plat", "lot and block"))
    builder_adj   = any(k in desc_lower for k in ("adjacent to", "next to builder", "near subdivision"))

    if dead_paper_hit or (is_land_type and plat_gap):
        notes_parts.append("Dead paper / platted subdivision signals detected")
        return ClassificationResult(
            property_id=lead.property_id,
            classification=Classification.DEAD_PAPER,
            dead_paper_candidate=True,
            notes="; ".join(notes_parts),
        )

    if is_land_type or lead.lot_size >= 2.0:
        if lead.lot_size <= 0.5 and lead.sqft == 0:
            infill = True
            notes_parts.append(f"Small urban lot ({lead.lot_size} acres) — infill candidate")
            return ClassificationResult(
                property_id=lead.property_id,
                classification=Classification.INFILL_LOT,
                infill_candidate=True,
                notes="; ".join(notes_parts),
            )
        notes_parts.append(f"Land / large lot ({lead.lot_size} acres)")
        return ClassificationResult(
            property_id=lead.property_id,
            classification=Classification.LAND_SUBDIVISION,
            notes="; ".join(notes_parts),
        )

    # ── Rental / hedge ────────────────────────────────────────────────────────
    rental_signals = kw_set & _HIGH_EQUITY_RENTAL_SIGNALS
    if rental_signals:
        notes_parts.append(f"Rental signals: {', '.join(rental_signals)}")
        return ClassificationResult(
            property_id=lead.property_id,
            classification=Classification.RENTAL_HEDGE,
            hedge_fund_fit=True,
            notes="; ".join(notes_parts),
        )

    # ── Default: SFR wholesale ─────────────────────────────────────────────────
    if lead.property_type in (PropertyType.SFR, PropertyType.MFR, PropertyType.UNKNOWN):
        return ClassificationResult(
            property_id=lead.property_id,
            classification=Classification.SFR_WHOLESALE,
            notes="; ".join(notes_parts) or "Standard SFR wholesale path",
        )

    return ClassificationResult(
        property_id=lead.property_id,
        classification=Classification.REJECT,
        reject_reason=f"No classification path matched for type '{lead.property_type}'",
    )


# ─── CSV Ingestion ────────────────────────────────────────────────────────────

# Flexible column name mapping for various export formats
_CSV_FIELD_MAP = {
    "address":       ["address", "property address", "street address", "addr"],
    "city":          ["city"],
    "state":         ["state", "st"],
    "zip_code":      ["zip", "zip code", "zipcode", "postal code"],
    "county_name":   ["county", "county name"],
    "parcel_id":     ["apn", "parcel id", "parcel", "assessor parcel"],
    "property_type": ["property type", "type", "asset type"],
    "beds":          ["beds", "bedrooms", "br"],
    "baths":         ["baths", "bathrooms", "ba"],
    "sqft":          ["sqft", "sq ft", "square feet", "living area", "size"],
    "lot_size":      ["lot size", "lot acres", "acreage", "acres"],
    "year_built":    ["year built", "yr built", "built"],
    "list_price":    ["list price", "price", "asking price", "listing price"],
    "dom":           ["dom", "days on market", "days listed"],
    "price_drops":   ["price drops", "price reductions", "reductions"],
    "description":   ["description", "remarks", "public remarks", "notes"],
}


def _resolve_csv_column(header: str, field_map: dict[str, list[str]]) -> str | None:
    h = header.lower().strip()
    for field_name, aliases in field_map.items():
        if h in aliases:
            return field_name
    return None


def _safe_float(val: str) -> float:
    try:
        return float(re.sub(r"[^\d.]", "", val or "0") or 0)
    except ValueError:
        return 0.0


def _safe_int(val: str) -> int:
    try:
        return int(re.sub(r"[^\d]", "", val or "0") or 0)
    except ValueError:
        return 0


def ingest_from_csv(
    csv_path: str | Path,
    source: str = LeadSource.CSV,
) -> list[PropertyLead]:
    """
    Stage 1: Ingest leads from a CSV export (Zillow, XLeads, PropStream, etc.).
    Flexible column mapping handles varied export formats.
    """
    leads = []
    path  = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader     = csv.DictReader(f)
        col_lookup = {}
        for header in (reader.fieldnames or []):
            mapped = _resolve_csv_column(header, _CSV_FIELD_MAP)
            if mapped:
                col_lookup[mapped] = header  # field_name → actual csv column

        for row in reader:
            def get(field: str, default: str = "") -> str:
                col = col_lookup.get(field)
                return row.get(col, default).strip() if col else default

            address  = get("address")
            zip_code = re.sub(r"[^\d]", "", get("zip_code"))[:5]
            if not address or not zip_code:
                continue  # skip rows without address + ZIP

            description = get("description")
            keywords    = _extract_keywords(description)

            lead = PropertyLead(
                property_id   = f"PROP-{uuid.uuid4().hex[:8].upper()}",
                source        = source,
                address       = address,
                city          = get("city"),
                state         = get("state"),
                zip_code      = zip_code,
                county_name   = get("county_name"),
                parcel_id     = get("parcel_id"),
                property_type = get("property_type") or PropertyType.SFR,
                beds          = _safe_float(get("beds")),
                baths         = _safe_float(get("baths")),
                sqft          = _safe_int(get("sqft")),
                lot_size      = _safe_float(get("lot_size")),
                year_built    = _safe_int(get("year_built")),
                list_price    = _safe_float(get("list_price")),
                dom           = _safe_int(get("dom")),
                price_drops   = _safe_int(get("price_drops")),
                keywords      = keywords,
                description   = description,
                has_photos    = True,  # assume photos unless flagged
            )
            leads.append(lead)

    return leads


def ingest_manual(
    address: str,
    zip_code: str,
    city: str,
    state: str,
    list_price: float,
    property_type: str      = PropertyType.SFR,
    beds: float             = 0,
    baths: float            = 0,
    sqft: int               = 0,
    lot_size: float         = 0,
    year_built: int         = 0,
    dom: int                = 0,
    description: str        = "",
    source: str             = LeadSource.MANUAL,
) -> PropertyLead:
    """Stage 1: Create a single lead from manual entry."""
    keywords = _extract_keywords(description)
    return PropertyLead(
        property_id   = f"PROP-{uuid.uuid4().hex[:8].upper()}",
        source        = source,
        address       = address,
        city          = city,
        state         = state,
        zip_code      = zip_code[:5],
        property_type = property_type,
        beds          = beds,
        baths         = baths,
        sqft          = sqft,
        lot_size      = lot_size,
        year_built    = year_built,
        list_price    = list_price,
        dom           = dom,
        keywords      = keywords,
        description   = description,
        has_photos    = False,
    )
