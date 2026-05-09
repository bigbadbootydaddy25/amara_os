"""
Deal Signal Finder Agent

Ingests public-record distress signals — trustee notices, code violations,
pre-foreclosure data, municipal liens, auction calendars — and produces
ranked deal opportunity profiles with full source evidence trails.

Accepted source types:
  trustee_sale_notice          — recorded trustee sale notice
  notice_of_trustee_sale       — official notice of trustee sale (NTS)
  notice_of_default            — notice of default (NOD), pre-foreclosure entry
  pre_foreclosure_list         — aggregated pre-foreclosure export
  substitute_trustee_record    — substitute trustee appointment
  auction_calendar             — scheduled public auction listing
  code_violation               — code enforcement violation record
  nuisance_violation           — nuisance / property-maintenance violation
  municipal_lien               — municipal or utility lien filing
  demolition_condemnation      — demolition order or condemnation notice

Rules:
  - Public records and user-provided files only.
  - No private account scraping, no automated contacting.
  - No fabricated trustee names or sale dates — every signal cites a source.
  - Raw signals are separated from verified opportunities.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Routing thresholds
# ---------------------------------------------------------------------------

VERIFIED_OPPORTUNITY  = 0.70  # distress_signal_confidence >= this
PROBABLE_OPPORTUNITY  = 0.45
WATCH_LIST_THRESHOLD  = 0.20
# Below WATCH_LIST_THRESHOLD → NOISE

# ---------------------------------------------------------------------------
# Minimum counts for "repeated" violations
# ---------------------------------------------------------------------------
_REPEATED_OPEN_MIN   = 3   # >= this many open violations → repeated
_REPEATED_TOTAL_MIN  = 3   # OR >= this total AND >= 2 open → repeated
_REPEATED_OPEN_ALT   = 2   # open count for the total-based alternate path

# Days-until-sale urgency bands
_URGENT_DAYS  = 30
_UPCOMING_DAYS = 90

# ---------------------------------------------------------------------------
# Signal weights (additive; capped at 1.0 after summation)
# ---------------------------------------------------------------------------
_WS_TRUSTEE_NOTICE      = 0.25  # confirmed trustee / auction notice
_WS_NOTICE_OF_DEFAULT   = 0.15  # NOD filed (pre-foreclosure pipeline)
_WS_SUBSTITUTE_TRUSTEE  = 0.08  # substitute trustee appointed
_WS_SALE_DATE           = 0.06  # confirmed future sale date present
_WS_SALE_URGENT_30D     = 0.15  # sale within 30 days
_WS_SALE_UPCOMING_90D   = 0.08  # sale within 31–90 days
_WS_PRE_POSTING         = 0.08  # NOD/pre-foreclosure before public posting
_WS_REPEATED_VIOLATIONS = 0.12  # 3+ open, or 2+ open with 3+ total
_WS_SEVERE_VIOLATION    = 0.10  # structural/fire/condemnation/imminent danger
_WS_MUNICIPAL_LIEN      = 0.08  # recorded municipal or utility lien
_WS_PROPERTY_MAINT      = 0.05  # nuisance/maintenance violation present
_WS_DEMOLITION          = 0.12  # demolition order or condemnation notice

# ---------------------------------------------------------------------------
# Violation type classification
# ---------------------------------------------------------------------------

_SEVERE_VIOLATION_TYPES: frozenset[str] = frozenset({
    "structural_deficiency",
    "structural_failure",
    "fire_hazard",
    "unsafe_structure",
    "unsafe_building",
    "condemnation",
    "imminent_danger",
    "demolition_order",
    "health_hazard",
    "electrical_hazard",
    "gas_leak",
    "collapse_risk",
    "uninhabitable",
})

_MAINTENANCE_VIOLATION_TYPES: frozenset[str] = frozenset({
    "exterior_maintenance",
    "debris_accumulation",
    "overgrown_vegetation",
    "broken_windows",
    "unsecured_building",
    "graffiti",
    "inoperable_vehicle",
    "garbage_accumulation",
    "property_neglect",
    "nuisance",
    "blight",
    "tall_grass",
    "junk_accumulation",
})

# ---------------------------------------------------------------------------
# Trustee name extraction patterns (applied to raw_text field)
# ---------------------------------------------------------------------------

_TRUSTEE_TEXT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Substitute trustee patterns (must be checked first)
    ("substitute", re.compile(
        r"[Ss]ubstitute\s+[Tt]rustee[:\s]+([A-Z][A-Za-z &.,'-]{2,70}?)(?:\s*,|\s*\n|$)",
        re.MULTILINE,
    )),
    ("substitute", re.compile(
        r"([A-Z][A-Za-z &.,'-]{2,70}?),?\s+as\s+[Ss]ubstitute\s+[Tt]rustee",
        re.MULTILINE,
    )),
    ("substitute", re.compile(
        r"[Aa]ppointed\s+[Ss]ubstitute\s+[Tt]rustee[:\s]+([A-Z][A-Za-z &.,'-]{2,70}?)(?:\s*,|\s*\n|$)",
        re.MULTILINE,
    )),
    # Regular trustee patterns
    ("trustee", re.compile(
        r"[Tt]rustee[:\s]+([A-Z][A-Za-z &.,'-]{2,70}?)(?:\s*,|\s*\n|$)",
        re.MULTILINE,
    )),
    ("trustee", re.compile(
        r"([A-Z][A-Za-z &.,'-]{2,70}?),?\s+as\s+[Tt]rustee",
        re.MULTILINE,
    )),
    ("trustee", re.compile(
        r"[Aa]ppointed\s+[Tt]rustee[:\s]+([A-Z][A-Za-z &.,'-]{2,70}?)(?:\s*,|\s*\n|$)",
        re.MULTILINE,
    )),
]

# Formats tried in order when parsing a sale_date string
_DATE_FORMATS: list[str] = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%y",
]

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    TRUSTEE_SALE_NOTICE       = "trustee_sale_notice"
    NOTICE_OF_TRUSTEE_SALE    = "notice_of_trustee_sale"
    NOTICE_OF_DEFAULT         = "notice_of_default"
    PRE_FORECLOSURE_LIST      = "pre_foreclosure_list"
    SUBSTITUTE_TRUSTEE_RECORD = "substitute_trustee_record"
    AUCTION_CALENDAR          = "auction_calendar"
    CODE_VIOLATION            = "code_violation"
    NUISANCE_VIOLATION        = "nuisance_violation"
    MUNICIPAL_LIEN            = "municipal_lien"
    DEMOLITION_CONDEMNATION   = "demolition_condemnation"


class DealType(str, Enum):
    VERIFIED_OPPORTUNITY  = "verified_opportunity"
    PROBABLE_OPPORTUNITY  = "probable_opportunity"
    WATCH_LIST            = "watch_list"
    NOISE                 = "noise"


# Source-type groupings for signal logic
_TRUSTEE_SOURCES: frozenset[SourceType] = frozenset({
    SourceType.TRUSTEE_SALE_NOTICE,
    SourceType.NOTICE_OF_TRUSTEE_SALE,
    SourceType.SUBSTITUTE_TRUSTEE_RECORD,
    SourceType.AUCTION_CALENDAR,
})

_PREFORECLOSURE_SOURCES: frozenset[SourceType] = frozenset({
    SourceType.NOTICE_OF_DEFAULT,
    SourceType.PRE_FORECLOSURE_LIST,
})

_VIOLATION_SOURCES: frozenset[SourceType] = frozenset({
    SourceType.CODE_VIOLATION,
    SourceType.NUISANCE_VIOLATION,
    SourceType.MUNICIPAL_LIEN,
    SourceType.DEMOLITION_CONDEMNATION,
})

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DealSignals:
    # Trustee / foreclosure signals
    trustee_notice_present:     bool = False
    substitute_trustee_present: bool = False
    trustee_name:               str | None = None
    substitute_trustee:         str | None = None
    trustee_firm:               str | None = None
    sale_date:                  str | None = None   # ISO date string
    sale_date_present:          bool = False
    days_until_sale:            int | None = None
    # Pre-foreclosure signals
    notice_of_default_present:  bool = False
    pre_posting_signal:         bool = False
    # Violation signals
    violation_count:            int = 0
    open_violation_count:       int = 0
    repeated_code_violations:   bool = False
    severe_violation_type:      bool = False
    severe_violation_types:     list[str] = field(default_factory=list)
    municipal_lien_present:     bool = False
    property_maintenance_signal: bool = False
    demolition_risk:            bool = False
    # Composite
    distress_signal_confidence: float = 0.0
    source_evidence:            list[str] = field(default_factory=list)


@dataclass
class DealProfile:
    property_key:   str
    parcel_id:      str | None
    address:        str | None
    owner_name:     str | None
    deal_type:      DealType
    deal_score:     float
    signals:        DealSignals
    evidence_flags: list[str]
    source_records: list[dict[str, Any]]
    source_types:   list[str]
    run_timestamp:  str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class DealReport:
    run_timestamp:          str
    total_records:          int
    total_properties:       int
    today:                  str                    # date used for urgency calc
    verified_opportunities: list[DealProfile]
    probable_opportunities: list[DealProfile]
    watch_list:             list[DealProfile]
    noise:                  list[DealProfile]


# Internal grouping helper
@dataclass
class _PropertyGroup:
    key:        str
    parcel_id:  str | None
    address:    str | None
    owner_name: str | None
    records:    list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _normalize_address(addr: str) -> str:
    """Normalise a street address for cross-source matching."""
    addr = unicodedata.normalize("NFKD", addr).encode("ascii", "ignore").decode()
    abbrevs = {
        r"\bst\.?\b": "street",
        r"\bave\.?\b": "avenue",
        r"\bdr\.?\b": "drive",
        r"\brd\.?\b": "road",
        r"\bblvd\.?\b": "boulevard",
        r"\bln\.?\b": "lane",
        r"\bct\.?\b": "court",
        r"\bpl\.?\b": "place",
        r"\bhwy\.?\b": "highway",
        r"\bpkwy\.?\b": "parkway",
        r"\bapt\.?\b": "apartment",
        r"\bste\.?\b": "suite",
    }
    addr_lower = addr.lower()
    for pat, rep in abbrevs.items():
        addr_lower = re.sub(pat, rep, addr_lower, flags=re.IGNORECASE)
    addr_lower = re.sub(r"[^\w\s]", " ", addr_lower)
    return re.sub(r"\s+", " ", addr_lower).strip()


def _normalize_name(name: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()


def _parse_sale_date(date_str: str | None) -> date | None:
    """Try multiple date formats; return None if none match."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_source_type(raw: str | None) -> SourceType | None:
    """Coerce a raw source_type string to SourceType, or None."""
    if not raw:
        return None
    try:
        return SourceType(raw.lower().strip())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Trustee text extraction
# ---------------------------------------------------------------------------


def _extract_trustee_from_text(
    text: str,
) -> tuple[str | None, str | None]:
    """
    Scan raw_text for trustee / substitute trustee names.

    Returns (trustee_name, substitute_trustee).  Substitute patterns
    take priority and are checked first.
    """
    trustee_name: str | None = None
    substitute_trustee: str | None = None

    for role, pat in _TRUSTEE_TEXT_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        name = m.group(1).strip().rstrip(".,")
        if not name:
            continue
        if role == "substitute" and substitute_trustee is None:
            substitute_trustee = name
        elif role == "trustee" and trustee_name is None:
            trustee_name = name

    return trustee_name, substitute_trustee


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------


def _extract_signals(group: _PropertyGroup, today: date) -> DealSignals:
    """
    Derive all DealSignals for a property group by examining every
    contributing source record.
    """
    sig = DealSignals()
    evidence: list[str] = []

    # Collect source types present in the group
    source_types_present: set[SourceType] = set()
    for rec in group.records:
        st = _parse_source_type(rec.get("source_type"))
        if st:
            source_types_present.add(st)

    has_trustee_source = bool(source_types_present & _TRUSTEE_SOURCES)
    has_preforeclosure  = bool(source_types_present & _PREFORECLOSURE_SOURCES)

    # ----------------------------------------------------------------
    # Pass 1 — trustee / foreclosure records
    # ----------------------------------------------------------------
    earliest_sale: date | None = None

    for rec in group.records:
        st = _parse_source_type(rec.get("source_type"))
        if st is None:
            continue
        src_name = str(rec.get("source_name", "") or "")
        src_url  = str(rec.get("source_url",  "") or "")

        # ---- Trustee notices ----
        if st in _TRUSTEE_SOURCES:
            sig.trustee_notice_present = True
            evidence.append(
                f"trustee notice source: {st.value}"
                + (f" [{src_name}]" if src_name else "")
            )

        if st == SourceType.SUBSTITUTE_TRUSTEE_RECORD:
            sig.substitute_trustee_present = True

        # Structured trustee fields
        trustee_name_raw = str(rec.get("trustee_name", "") or "").strip()
        if trustee_name_raw and sig.trustee_name is None:
            sig.trustee_name = trustee_name_raw
            evidence.append(f"trustee name: {trustee_name_raw}")

        sub_trustee_raw = str(rec.get("substitute_trustee", "") or "").strip()
        if sub_trustee_raw:
            sig.substitute_trustee_present = True
            if sig.substitute_trustee is None:
                sig.substitute_trustee = sub_trustee_raw
                evidence.append(f"substitute trustee: {sub_trustee_raw}")

        firm_raw = str(rec.get("trustee_firm", "") or "").strip()
        if firm_raw and sig.trustee_firm is None:
            sig.trustee_firm = firm_raw
            evidence.append(f"trustee firm: {firm_raw}")

        # Fall back to text extraction when structured fields are absent
        raw_text = str(rec.get("raw_text", "") or "")
        if raw_text and (not sig.trustee_name or not sig.substitute_trustee):
            txt_trustee, txt_sub = _extract_trustee_from_text(raw_text)
            if txt_trustee and not sig.trustee_name:
                sig.trustee_name = txt_trustee
                evidence.append(f"trustee name (from text): {txt_trustee}")
            if txt_sub:
                sig.substitute_trustee_present = True
                if not sig.substitute_trustee:
                    sig.substitute_trustee = txt_sub
                    evidence.append(f"substitute trustee (from text): {txt_sub}")

        # Sale date
        sale_date_parsed = _parse_sale_date(rec.get("sale_date"))
        if sale_date_parsed:
            if earliest_sale is None or sale_date_parsed < earliest_sale:
                earliest_sale = sale_date_parsed

        # Notice of default
        if st == SourceType.NOTICE_OF_DEFAULT:
            sig.notice_of_default_present = True
            evidence.append(
                f"notice of default"
                + (f" [{src_name}]" if src_name else "")
            )

        if st == SourceType.PRE_FORECLOSURE_LIST:
            evidence.append(
                f"pre-foreclosure list entry"
                + (f" [{src_name}]" if src_name else "")
            )

        if src_url:
            evidence.append(f"source url: {src_url}")

    # Resolve sale date signals
    if earliest_sale is not None:
        days = (earliest_sale - today).days
        sig.sale_date = earliest_sale.isoformat()
        if days >= 0:
            sig.sale_date_present = True
            sig.days_until_sale   = days
            evidence.append(
                f"sale date: {sig.sale_date} ({days} day(s) until sale)"
            )
        else:
            evidence.append(
                f"sale date: {sig.sale_date} (past — {abs(days)} day(s) ago)"
            )

    # Pre-posting: has pre-foreclosure source but NO public trustee/auction notice
    if has_preforeclosure and not has_trustee_source:
        sig.pre_posting_signal = True
        evidence.append(
            "pre-posting signal: pre-foreclosure recorded without "
            "public auction notice"
        )

    # ----------------------------------------------------------------
    # Pass 2 — violation records
    # ----------------------------------------------------------------
    violation_count  = 0
    open_count       = 0
    severe_types: list[str] = []

    for rec in group.records:
        st = _parse_source_type(rec.get("source_type"))
        if st is None:
            continue
        src_name = str(rec.get("source_name", "") or "")

        # Municipal lien
        if st == SourceType.MUNICIPAL_LIEN or bool(rec.get("municipal_lien")):
            sig.municipal_lien_present = True
            evidence.append(
                f"municipal lien recorded"
                + (f" [{src_name}]" if src_name else "")
            )

        # Demolition / condemnation
        if st == SourceType.DEMOLITION_CONDEMNATION:
            sig.demolition_risk = True
            sig.severe_violation_type = True
            v_type = str(rec.get("violation_type", "condemnation") or "condemnation")
            if v_type not in severe_types:
                severe_types.append(v_type)
            evidence.append(
                f"demolition/condemnation notice"
                + (f" [{src_name}]" if src_name else "")
            )

        # Code / nuisance violations
        if st in (SourceType.CODE_VIOLATION, SourceType.NUISANCE_VIOLATION):
            violation_count += 1
            status   = str(rec.get("violation_status", "") or "").lower()
            is_open  = status in ("open", "active", "pending", "outstanding", "")
            if is_open:
                open_count += 1

            v_type = str(rec.get("violation_type", "") or "").lower()
            is_severe = bool(rec.get("is_severe")) or (v_type in _SEVERE_VIOLATION_TYPES)
            if is_severe:
                sig.severe_violation_type = True
                if v_type and v_type not in severe_types:
                    severe_types.append(v_type)

            if v_type in _MAINTENANCE_VIOLATION_TYPES:
                sig.property_maintenance_signal = True

            viol_label = v_type or "violation"
            viol_status_str = status or "unknown"
            evidence.append(
                f"{'open ' if is_open else ''}violation: {viol_label} "
                f"(status={viol_status_str})"
                + (f" [{src_name}]" if src_name else "")
            )

    sig.violation_count      = violation_count
    sig.open_violation_count = open_count
    sig.severe_violation_types = severe_types

    # Repeated violations
    sig.repeated_code_violations = open_count >= _REPEATED_OPEN_MIN or (
        violation_count >= _REPEATED_TOTAL_MIN and open_count >= _REPEATED_OPEN_ALT
    )

    sig.source_evidence = evidence
    return sig


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _deal_score(sig: DealSignals) -> float:
    score = 0.0

    if sig.trustee_notice_present:
        score += _WS_TRUSTEE_NOTICE
    if sig.notice_of_default_present:
        score += _WS_NOTICE_OF_DEFAULT
    if sig.substitute_trustee_present:
        score += _WS_SUBSTITUTE_TRUSTEE
    if sig.pre_posting_signal:
        score += _WS_PRE_POSTING
    if sig.sale_date_present:
        score += _WS_SALE_DATE
        if sig.days_until_sale is not None:
            if sig.days_until_sale <= _URGENT_DAYS:
                score += _WS_SALE_URGENT_30D
            elif sig.days_until_sale <= _UPCOMING_DAYS:
                score += _WS_SALE_UPCOMING_90D
    if sig.repeated_code_violations:
        score += _WS_REPEATED_VIOLATIONS
    if sig.severe_violation_type:
        score += _WS_SEVERE_VIOLATION
    if sig.municipal_lien_present:
        score += _WS_MUNICIPAL_LIEN
    if sig.property_maintenance_signal:
        score += _WS_PROPERTY_MAINT
    if sig.demolition_risk:
        score += _WS_DEMOLITION

    return max(0.0, min(1.0, round(score, 4)))


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route(score: float) -> DealType:
    if score >= VERIFIED_OPPORTUNITY:
        return DealType.VERIFIED_OPPORTUNITY
    if score >= PROBABLE_OPPORTUNITY:
        return DealType.PROBABLE_OPPORTUNITY
    if score >= WATCH_LIST_THRESHOLD:
        return DealType.WATCH_LIST
    return DealType.NOISE


# ---------------------------------------------------------------------------
# Trustee entity collection
# ---------------------------------------------------------------------------


def _collect_trustee_entities(profiles: list[DealProfile]) -> list[dict[str, Any]]:
    """
    Aggregate unique trustee firm / name mentions across all profiles.
    Returns a list of entity dicts sorted by property_count descending.
    """
    entities: dict[str, dict[str, Any]] = {}

    for p in profiles:
        sig = p.signals
        # Determine the canonical key for this trustee
        key_name = _normalize_name(sig.trustee_firm or sig.trustee_name or "")
        if not key_name:
            continue

        if key_name not in entities:
            entities[key_name] = {
                "trustee_name":    sig.trustee_name,
                "substitute_trustee": sig.substitute_trustee,
                "trustee_firm":    sig.trustee_firm,
                "is_substitute":   sig.substitute_trustee_present,
                "property_count":  0,
                "parcel_ids":      [],
                "addresses":       [],
                "sale_dates":      [],
                "source_evidence": [],
            }

        ent = entities[key_name]
        ent["property_count"] += 1
        if p.parcel_id and p.parcel_id not in ent["parcel_ids"]:
            ent["parcel_ids"].append(p.parcel_id)
        if p.address and p.address not in ent["addresses"]:
            ent["addresses"].append(p.address)
        if sig.sale_date and sig.sale_date not in ent["sale_dates"]:
            ent["sale_dates"].append(sig.sale_date)
        ent["source_evidence"].extend(sig.source_evidence)
        if sig.substitute_trustee_present:
            ent["is_substitute"] = True

    result = sorted(entities.values(), key=lambda e: e["property_count"], reverse=True)
    # Deduplicate source evidence per entity
    for ent in result:
        seen: set[str] = set()
        deduped: list[str] = []
        for ev in ent["source_evidence"]:
            if ev not in seen:
                seen.add(ev)
                deduped.append(ev)
        ent["source_evidence"] = deduped
        if ent["sale_dates"]:
            ent["earliest_sale"] = min(ent["sale_dates"])
        else:
            ent["earliest_sale"] = None

    return result


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------


class DealSignalAgent:
    """
    Processes a batch of public-record distress signal records and
    produces five output documents with ranked deal opportunity profiles.

    Usage:
        agent = DealSignalAgent(reports_dir=Path("reports"))
        report = agent.run(records, today=date.today())
        agent.write_outputs(report)
    """

    def __init__(self, reports_dir: Path | None = None) -> None:
        self.reports_dir = reports_dir or Path(__file__).parent / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        records: list[dict[str, Any]],
        today: date | None = None,
    ) -> DealReport:
        """
        Process a list of raw distress-signal record dicts.

        Each record should carry at minimum:
            source_type   str   (one of the SourceType values)
            record_id     str
            parcel_id     str   (preferred grouping key)
            address       str   (fallback grouping key)

        Pass ``today`` to pin the current date for urgency calculations
        (useful for deterministic tests).
        """
        if today is None:
            today = date.today()

        groups = self._group_records(records)
        profiles: list[DealProfile] = []
        for group in groups.values():
            profiles.append(self._process_group(group, today))

        profiles.sort(key=lambda p: p.deal_score, reverse=True)

        verified  = [p for p in profiles if p.deal_type == DealType.VERIFIED_OPPORTUNITY]
        probable  = [p for p in profiles if p.deal_type == DealType.PROBABLE_OPPORTUNITY]
        watchlist = [p for p in profiles if p.deal_type == DealType.WATCH_LIST]
        noise     = [p for p in profiles if p.deal_type == DealType.NOISE]

        return DealReport(
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            total_records=len(records),
            total_properties=len(profiles),
            today=today.isoformat(),
            verified_opportunities=verified,
            probable_opportunities=probable,
            watch_list=watchlist,
            noise=noise,
        )

    def write_outputs(self, report: DealReport) -> None:
        """Write all five output documents to reports_dir."""
        self._write_trustee_signal_report(report)
        self._write_code_violation_report(report)
        self._write_trustee_entities(report)
        self._write_pre_foreclosure_signals(report)
        self._write_violation_matches(report)

    # ------------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------------

    def _group_records(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, _PropertyGroup]:
        groups: dict[str, _PropertyGroup] = {}

        for rec in records:
            parcel_id = str(rec.get("parcel_id", "") or "").strip()
            address   = str(rec.get("address",   "") or "").strip()
            record_id = str(rec.get("record_id", "") or "").strip()
            owner_name = str(rec.get("owner_name", "") or "").strip() or None

            if parcel_id:
                key = f"parcel:{parcel_id}"
            elif address:
                key = f"addr:{_normalize_address(address)}"
            else:
                key = f"rec:{record_id or id(rec)}"

            if key not in groups:
                groups[key] = _PropertyGroup(
                    key=key,
                    parcel_id=parcel_id or None,
                    address=address or None,
                    owner_name=owner_name,
                )
            else:
                # Use the first non-null owner name encountered
                if groups[key].owner_name is None and owner_name:
                    groups[key].owner_name = owner_name

            groups[key].records.append(rec)

        return groups

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _process_group(
        self,
        group: _PropertyGroup,
        today: date,
    ) -> DealProfile:
        sig   = _extract_signals(group, today)
        score = _deal_score(sig)
        sig.distress_signal_confidence = score
        dtype = _route(score)

        source_types = sorted({
            rec.get("source_type", "unknown")
            for rec in group.records
        })

        return DealProfile(
            property_key=group.key,
            parcel_id=group.parcel_id,
            address=group.address,
            owner_name=group.owner_name,
            deal_type=dtype,
            deal_score=score,
            signals=sig,
            evidence_flags=list(sig.source_evidence),
            source_records=group.records,
            source_types=source_types,
        )

    # ------------------------------------------------------------------
    # Output writers
    # ------------------------------------------------------------------

    def _write_trustee_signal_report(self, report: DealReport) -> None:
        all_profiles = (
            report.verified_opportunities
            + report.probable_opportunities
            + report.watch_list
            + report.noise
        )
        ts = report.run_timestamp

        lines = [
            "# TRUSTEE SIGNAL REPORT",
            "",
            f"_Generated: {ts} | Today: {report.today}_",
            "",
        ]

        trustee_profiles = [
            p for p in all_profiles if p.signals.trustee_notice_present
            or p.signals.notice_of_default_present
            or p.signals.pre_posting_signal
        ]

        lines += [
            f"## Summary",
            "",
            f"| Category | Count |",
            f"|----------|-------|",
            f"| Total properties analysed | {report.total_properties} |",
            f"| With trustee/auction notice | "
            f"{sum(1 for p in all_profiles if p.signals.trustee_notice_present)} |",
            f"| With notice of default | "
            f"{sum(1 for p in all_profiles if p.signals.notice_of_default_present)} |",
            f"| Pre-posting (before public auction) | "
            f"{sum(1 for p in all_profiles if p.signals.pre_posting_signal)} |",
            f"| With confirmed sale date | "
            f"{sum(1 for p in all_profiles if p.signals.sale_date_present)} |",
            f"| Sale within 30 days | "
            f"{sum(1 for p in all_profiles if p.signals.days_until_sale is not None and p.signals.days_until_sale <= _URGENT_DAYS)} |",
            "",
        ]

        if trustee_profiles:
            lines += ["## Trustee & Foreclosure Signals", ""]
            for p in trustee_profiles:
                sig = p.signals
                lines.append(f"### {p.address or p.parcel_id or p.property_key}")
                lines.append("")
                lines.append(f"- **Deal type**: {p.deal_type}")
                lines.append(f"- **Deal score**: {p.deal_score:.3f}")
                if sig.trustee_name:
                    lines.append(f"- **Trustee**: {sig.trustee_name}")
                if sig.substitute_trustee:
                    lines.append(f"- **Substitute trustee**: {sig.substitute_trustee}")
                if sig.trustee_firm:
                    lines.append(f"- **Trustee firm**: {sig.trustee_firm}")
                if sig.sale_date:
                    urgency = ""
                    if sig.days_until_sale is not None:
                        if sig.days_until_sale <= _URGENT_DAYS:
                            urgency = " ⚠ URGENT"
                        elif sig.days_until_sale <= _UPCOMING_DAYS:
                            urgency = " (upcoming)"
                    lines.append(f"- **Sale date**: {sig.sale_date}{urgency}")
                if sig.days_until_sale is not None:
                    lines.append(f"- **Days until sale**: {sig.days_until_sale}")
                if sig.pre_posting_signal:
                    lines.append(
                        "- **Pre-posting signal**: YES — pre-foreclosure detected "
                        "before public auction posting"
                    )
                if sig.notice_of_default_present:
                    lines.append("- **Notice of default**: filed")
                if p.parcel_id:
                    lines.append(f"- **Parcel**: `{p.parcel_id}`")
                if p.owner_name:
                    lines.append(f"- **Owner**: {p.owner_name}")
                if sig.source_evidence:
                    lines.append("- **Evidence**:")
                    for ev in sig.source_evidence:
                        lines.append(f"  - {ev}")
                lines.append("")
        else:
            lines += ["_No trustee or foreclosure signals found in this batch._", ""]

        self._write(self.reports_dir / "TRUSTEE_SIGNAL_REPORT.md", "\n".join(lines))

    def _write_code_violation_report(self, report: DealReport) -> None:
        all_profiles = (
            report.verified_opportunities
            + report.probable_opportunities
            + report.watch_list
            + report.noise
        )
        ts = report.run_timestamp

        lines = [
            "# CODE VIOLATION REPORT",
            "",
            f"_Generated: {ts}_",
            "",
            "## Summary",
            "",
            f"| Category | Count |",
            f"|----------|-------|",
            f"| Properties with any violation | "
            f"{sum(1 for p in all_profiles if p.signals.violation_count > 0)} |",
            f"| Properties with severe violation | "
            f"{sum(1 for p in all_profiles if p.signals.severe_violation_type)} |",
            f"| Properties with repeated violations | "
            f"{sum(1 for p in all_profiles if p.signals.repeated_code_violations)} |",
            f"| Properties with municipal lien | "
            f"{sum(1 for p in all_profiles if p.signals.municipal_lien_present)} |",
            f"| Properties with demolition risk | "
            f"{sum(1 for p in all_profiles if p.signals.demolition_risk)} |",
            "",
        ]

        violation_profiles = [
            p for p in all_profiles
            if p.signals.violation_count > 0
            or p.signals.municipal_lien_present
            or p.signals.demolition_risk
        ]

        if violation_profiles:
            lines += ["## Violation Detail", ""]
            for p in violation_profiles:
                sig = p.signals
                lines.append(f"### {p.address or p.parcel_id or p.property_key}")
                lines.append("")
                lines.append(f"- **Deal type**: {p.deal_type}")
                lines.append(f"- **Deal score**: {p.deal_score:.3f}")
                lines.append(f"- **Violations total**: {sig.violation_count}")
                lines.append(f"- **Open violations**: {sig.open_violation_count}")
                if sig.severe_violation_type:
                    types_str = ", ".join(sig.severe_violation_types) or "unspecified"
                    lines.append(f"- **Severe violation type(s)**: {types_str}")
                if sig.repeated_code_violations:
                    lines.append("- **Repeated violations**: YES")
                if sig.municipal_lien_present:
                    lines.append("- **Municipal lien**: recorded")
                if sig.demolition_risk:
                    lines.append("- **Demolition/condemnation risk**: YES")
                if sig.property_maintenance_signal:
                    lines.append("- **Property maintenance issues**: YES")
                if p.parcel_id:
                    lines.append(f"- **Parcel**: `{p.parcel_id}`")
                if p.owner_name:
                    lines.append(f"- **Owner**: {p.owner_name}")
                if sig.source_evidence:
                    lines.append("- **Evidence**:")
                    for ev in sig.source_evidence:
                        lines.append(f"  - {ev}")
                lines.append("")
        else:
            lines += ["_No violation records found in this batch._", ""]

        self._write(self.reports_dir / "CODE_VIOLATION_REPORT.md", "\n".join(lines))

    def _write_trustee_entities(self, report: DealReport) -> None:
        all_profiles = (
            report.verified_opportunities
            + report.probable_opportunities
            + report.watch_list
            + report.noise
        )
        entities = _collect_trustee_entities(all_profiles)
        payload = {
            "run_timestamp": report.run_timestamp,
            "today": report.today,
            "entity_count": len(entities),
            "entities": entities,
        }
        self._write(
            self.reports_dir / "TRUSTEE_ENTITIES.json",
            json.dumps(payload, indent=2),
        )

    def _write_pre_foreclosure_signals(self, report: DealReport) -> None:
        all_profiles = (
            report.verified_opportunities
            + report.probable_opportunities
            + report.watch_list
            + report.noise
        )
        pre_forc = [
            p for p in all_profiles
            if p.signals.pre_posting_signal or p.signals.notice_of_default_present
        ]

        signals_list = []
        for p in pre_forc:
            sig = p.signals
            signals_list.append({
                "property_key":  p.property_key,
                "parcel_id":     p.parcel_id,
                "address":       p.address,
                "owner_name":    p.owner_name,
                "deal_type":     p.deal_type,
                "deal_score":    p.deal_score,
                "pre_posting_signal":         sig.pre_posting_signal,
                "notice_of_default_present":  sig.notice_of_default_present,
                "trustee_notice_present":     sig.trustee_notice_present,
                "sale_date":                  sig.sale_date,
                "days_until_sale":            sig.days_until_sale,
                "source_types":               p.source_types,
                "evidence_flags":             p.evidence_flags,
            })

        payload = {
            "run_timestamp": report.run_timestamp,
            "today": report.today,
            "pre_foreclosure_count": len(signals_list),
            "signals": signals_list,
        }
        self._write(
            self.reports_dir / "PRE_FORECLOSURE_SIGNALS.json",
            json.dumps(payload, indent=2),
        )

    def _write_violation_matches(self, report: DealReport) -> None:
        """
        Violation matches: properties where BOTH trustee/foreclosure signals
        AND code violation signals are present — the highest-value overlap.
        """
        all_profiles = (
            report.verified_opportunities
            + report.probable_opportunities
            + report.watch_list
            + report.noise
        )

        matches = [
            p for p in all_profiles
            if (p.signals.trustee_notice_present or p.signals.notice_of_default_present)
            and (
                p.signals.repeated_code_violations
                or p.signals.severe_violation_type
                or p.signals.municipal_lien_present
                or p.signals.demolition_risk
            )
        ]

        match_list = []
        for p in matches:
            sig = p.signals
            match_list.append({
                "property_key":   p.property_key,
                "parcel_id":      p.parcel_id,
                "address":        p.address,
                "owner_name":     p.owner_name,
                "deal_type":      p.deal_type,
                "deal_score":     p.deal_score,
                "trustee_notice_present":     sig.trustee_notice_present,
                "notice_of_default_present":  sig.notice_of_default_present,
                "sale_date":                  sig.sale_date,
                "days_until_sale":            sig.days_until_sale,
                "violation_count":            sig.violation_count,
                "open_violation_count":       sig.open_violation_count,
                "repeated_code_violations":   sig.repeated_code_violations,
                "severe_violation_type":      sig.severe_violation_type,
                "severe_violation_types":     sig.severe_violation_types,
                "municipal_lien_present":     sig.municipal_lien_present,
                "demolition_risk":            sig.demolition_risk,
                "distress_signal_confidence": sig.distress_signal_confidence,
                "source_types":               p.source_types,
                "evidence_flags":             p.evidence_flags,
            })

        payload = {
            "run_timestamp":  report.run_timestamp,
            "today":          report.today,
            "match_count":    len(match_list),
            "matches":        match_list,
        }
        self._write(
            self.reports_dir / "VIOLATION_MATCHES.json",
            json.dumps(payload, indent=2),
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _load_records_from_path(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]
    records: list[dict[str, Any]] = []
    for json_file in sorted(path.glob("**/*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Skipping malformed JSON {json_file}: {exc}", file=sys.stderr)
    return records


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Deal Signal Finder — rank distress-signal records into deal opportunities"
    )
    parser.add_argument(
        "records",
        nargs="?",
        help="Path to a JSON file or directory of JSON files. Reads stdin if omitted.",
    )
    parser.add_argument(
        "--reports-dir", default=None,
        help="Output directory for reports (default: agents/deal-signal-finder/reports/)",
    )
    parser.add_argument(
        "--today", default=None,
        help="Override today's date for urgency calculations (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print summary to stdout; do not write report files.",
    )
    args = parser.parse_args(argv)

    today_date: date | None = None
    if args.today:
        today_date = _parse_sale_date(args.today)
        if today_date is None:
            print(f"[ERROR] Cannot parse --today value: {args.today}", file=sys.stderr)
            return 1

    if args.records:
        p = Path(args.records)
        if not p.exists():
            print(f"[ERROR] Path not found: {p}", file=sys.stderr)
            return 1
        raw_records = _load_records_from_path(p)
    else:
        try:
            raw_records = json.load(sys.stdin)
            if isinstance(raw_records, dict):
                raw_records = [raw_records]
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Failed to parse JSON from stdin: {exc}", file=sys.stderr)
            return 1

    reports_dir = (
        Path(args.reports_dir) if args.reports_dir
        else Path(__file__).parent / "reports"
    )
    agent = DealSignalAgent(reports_dir=reports_dir)
    report = agent.run(raw_records, today=today_date)

    print(f"\nDeal Signal Finder — {report.run_timestamp}")
    print(f"  Records processed       : {report.total_records}")
    print(f"  Properties found        : {report.total_properties}")
    print(f"  Verified opportunities  : {len(report.verified_opportunities)}")
    print(f"  Probable opportunities  : {len(report.probable_opportunities)}")
    print(f"  Watch list              : {len(report.watch_list)}")
    print(f"  Noise                   : {len(report.noise)}")

    if report.verified_opportunities:
        print("\nTop verified opportunities:")
        for p in report.verified_opportunities[:5]:
            print(
                f"  [{p.deal_score:.2f}] {p.address or p.parcel_id or p.property_key}"
            )

    if not args.dry_run:
        agent.write_outputs(report)
        print(f"\nReports written to: {reports_dir}/")

    n_actionable = len(report.verified_opportunities) + len(report.probable_opportunities)
    return 0 if n_actionable > 0 or report.total_records == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
