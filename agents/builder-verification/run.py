"""
Builder Verification Agent

Converts raw owner/buyer records into ranked builder and cash-buyer
intelligence profiles. Evidence-based only — no fabricated buyers,
no inferred intent beyond what the signals directly support.

Input records describe individual parcel ownership/sale events.
The agent scores each record on two independent axes (builder
confidence, investor/cash-buyer confidence), routes to a buyer
type, and emits five output documents.

Optional `research` key per record unlocks source-backed scoring
boosts and entity intelligence via SOS, website, business profiles,
social profiles, and county records.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

BUILDER_THRESHOLD = 0.65      # builder_confidence >= this → VERIFIED_BUILDER
INVESTOR_THRESHOLD = 0.50     # investor_confidence >= this → POSSIBLE_CASH_BUYER
REPEAT_BUYER_MIN = 3          # prior_acquisitions >= this → REPEAT_BUYER fallback

# Permit counts
_PERMIT_FULL = 3              # >= this → full permit credit
_PERMIT_PARTIAL = 1           # >= this → partial permit credit

# Nearby-parcel counts
_NEARBY_FULL = 3
_NEARBY_PARTIAL = 2

# Acquisition counts
_ACQ_FULL = 4                 # >= this → full repeat credit (both axes)
_ACQ_PARTIAL = 2              # >= this → partial repeat credit

# Days threshold for purchase clustering
_CLUSTER_DAYS = 90

# ---------------------------------------------------------------------------
# Builder confidence weights  (must sum to 1.0)
# ---------------------------------------------------------------------------
_WB_KEYWORDS = 0.30   # builder/construction keywords in owner name
_WB_PERMITS  = 0.25   # permit / build activity
_WB_ENTITY   = 0.15   # LLC / Corp / Inc entity
_WB_REPEAT   = 0.15   # repeat acquisitions pattern
_WB_NEARBY   = 0.15   # multiple nearby parcels (infill concentration)

# ---------------------------------------------------------------------------
# Investor / cash-buyer confidence weights  (must sum to 1.0)
# ---------------------------------------------------------------------------
_WI_REPEAT   = 0.25   # repeat acquisitions
_WI_ENTITY   = 0.20   # LLC / Corp / Trust entity
_WI_MISMATCH = 0.20   # mailing address ≠ parcel address
_WI_VACANT   = 0.20   # vacant-land ownership
_WI_CLUSTER  = 0.15   # recent purchase clustering

# ---------------------------------------------------------------------------
# Research boost constants
# ---------------------------------------------------------------------------
_WR_SOS_ACTIVE           = 0.05   # active SOS registration confirms entity
_WR_CONSTRUCTION_PROFILE = 0.12   # BBB/Houzz listing with contractor category
_WR_WEBSITE_CONSTRUCTION = 0.06   # website explicitly mentions construction
_WR_COUNTY_PERMIT_HEAVY  = 0.04   # county permit count >= 5
_WR_CORROBORATION_3PLUS  = 0.03   # 3+ independent source types agree

_MAX_BUILDER_BOOST  = 0.20        # additive cap on research builder boost
_MAX_INVESTOR_BOOST = 0.15        # additive cap on research investor boost

# County permit count that triggers heavy-permit boost
_COUNTY_PERMIT_HEAVY_MIN = 5
# County deed count that triggers investor activity boost
_COUNTY_DEED_HEAVY_MIN = 5

# ---------------------------------------------------------------------------
# Keyword / entity patterns
# ---------------------------------------------------------------------------

_BUILDER_KEYWORD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bconstruct(ion|s|ed|ing)?\b",
        r"\bbuild(er|ers|ing|s)?\b",
        r"\bdevelop(er|ers|ment|ing|s)?\b",
        r"\bhome\s*build(er|ers|ing)?\b",
        r"\binfill\b",
        r"\bcontractor\b",
        r"\bremodel(ing|s)?\b",
        r"\brenovati(on|ons|ng)\b",
        r"\bgeneral\s+contractor\b",
        r"\bcustom\s+home\b",
    ]
]

_COMPANY_ENTITY_PATTERN = re.compile(
    r"\b(llc|l\.l\.c\.?|inc\.?|corp\.?|co\.?|ltd\.?|lp|l\.p\.?|"
    r"pllc|pc|plc|company|companies|enterprises|group|holdings|"
    r"ventures|partners|partnership|associates|trust|foundation)\b",
    re.IGNORECASE,
)

# These entity keywords suggest investor/holding structures more than builders
_INVESTOR_ENTITY_KEYWORDS = re.compile(
    r"\b(holding|holdings|capital|investment|invest|asset|assets|"
    r"acquisition|acquisitions|fund|equity|properties|realty|trust)\b",
    re.IGNORECASE,
)

# Business profile categories that confirm construction activity
_CONSTRUCTION_CATEGORIES: frozenset[str] = frozenset({
    "general contractor",
    "home builder",
    "contractor",
    "builder",
    "construction",
    "remodeling",
    "renovation",
    "custom home",
})


# ---------------------------------------------------------------------------
# Source types and reliability
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    SECRETARY_OF_STATE = "secretary_of_state"
    WEBSITE            = "website"
    BUSINESS_PROFILE   = "business_profile"
    SOCIAL_PROFILE     = "social_profile"
    COUNTY_RECORDS     = "county_records"


# Reliability weight per source type (0.0–1.0)
_SOURCE_RELIABILITY: dict[SourceType, float] = {
    SourceType.SECRETARY_OF_STATE: 0.97,
    SourceType.COUNTY_RECORDS:     0.95,
    SourceType.BUSINESS_PROFILE:   0.82,
    SourceType.WEBSITE:            0.72,
    SourceType.SOCIAL_PROFILE:     0.55,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class BuyerType(str, Enum):
    VERIFIED_BUILDER    = "verified_builder"
    POSSIBLE_CASH_BUYER = "possible_cash_buyer"
    REPEAT_BUYER        = "repeat_buyer"
    QUARANTINED         = "quarantined"
    WEAK_RECORD         = "weak_record"


@dataclass
class SourceCitation:
    source_type: SourceType
    name: str
    url: str | None = None
    reliability: float = 0.0


@dataclass
class ResearchEvidence:
    sources: list[SourceCitation] = field(default_factory=list)
    # SOS signals
    sos_registered: bool = False
    sos_active: bool = False
    sos_legal_name: str | None = None
    sos_state: str | None = None
    # Website signals
    website_url: str | None = None
    website_construction: bool = False
    # Business profile signals
    construction_profile_platforms: list[str] = field(default_factory=list)
    # County record signals
    county_deed_count: int = 0
    county_permit_count: int = 0
    county_source_name: str | None = None

    @property
    def source_count(self) -> int:
        """Number of distinct SourceType values present in sources."""
        return len({s.source_type for s in self.sources})


@dataclass
class BuyerSignals:
    is_company_owned: bool = False
    entity_type_detected: str | None = None
    has_builder_keywords: bool = False
    builder_keyword_matches: list[str] = field(default_factory=list)
    permit_count: int = 0
    has_permit_activity: bool = False
    nearby_parcel_count: int = 0
    prior_acquisitions: int = 0
    batch_acquisition_count: int = 0     # occurrences of this owner in current batch
    owns_vacant_land: bool = False
    mailing_address_mismatch: bool = False
    has_purchase_cluster: bool = False
    purchase_cluster_days: int | None = None
    source_evidence: list[str] = field(default_factory=list)
    research_evidence: ResearchEvidence | None = None


@dataclass
class BuyerProfile:
    record_id: str
    owner_name: str
    parcel_id: str
    buyer_type: BuyerType
    builder_confidence: float
    investor_confidence: float
    signals: BuyerSignals
    evidence_flags: list[str]
    weak_reasons: list[str] = field(default_factory=list)
    parcel_address: str | None = None
    mailing_address: str | None = None
    sale_price: float | None = None
    sale_date: str | None = None
    source_file: str | None = None
    entity_matches: list[str] = field(default_factory=list)
    research_confidence: float = 0.0
    run_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class VerificationReport:
    run_timestamp: str
    total_processed: int
    verified_builders: list[BuyerProfile]
    possible_cash_buyers: list[BuyerProfile]
    repeat_buyers: list[BuyerProfile]
    quarantined: list[BuyerProfile]
    weak_records: list[BuyerProfile]


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------


def _normalize_owner(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for grouping."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()


def _detect_builder_keywords(name: str) -> list[str]:
    matches: list[str] = []
    for pat in _BUILDER_KEYWORD_PATTERNS:
        found = pat.findall(name)
        if found:
            # Record the full match text rather than capture groups
            for m in pat.finditer(name):
                matches.append(m.group(0).lower())
    return list(dict.fromkeys(matches))  # deduplicate, preserve order


def _detect_entity(name: str) -> str | None:
    """Return the matched entity suffix/keyword, or None."""
    m = _COMPANY_ENTITY_PATTERN.search(name)
    return m.group(0).upper() if m else None


def _addresses_mismatch(parcel_addr: str | None, mailing_addr: str | None) -> bool:
    """True when both addresses are present and meaningfully different."""
    if not parcel_addr or not mailing_addr:
        return False
    def _norm(a: str) -> str:
        return re.sub(r"\s+", " ", a.lower().strip())
    return _norm(parcel_addr) != _norm(mailing_addr)


def _extract_research_evidence(record: dict[str, Any]) -> ResearchEvidence | None:
    """
    Parse the optional ``research`` dict from a raw record.

    Supported keys: secretary_of_state, website, business_profiles,
    social_profiles, county_records.

    Returns None when the record has no research data or when no
    parseable sources are found.
    """
    research = record.get("research")
    if not research or not isinstance(research, dict):
        return None

    ev = ResearchEvidence()

    # Secretary of State ------------------------------------------------
    sos = research.get("secretary_of_state")
    if sos and isinstance(sos, dict):
        ev.sos_registered = bool(sos.get("registered", False))
        status = str(sos.get("status", "") or "").lower()
        ev.sos_active = ev.sos_registered and status == "active"
        legal_name = sos.get("legal_name")
        if legal_name:
            ev.sos_legal_name = str(legal_name)
        state = sos.get("state")
        if state:
            ev.sos_state = str(state)
        url = sos.get("source_url")
        name = sos.get("source_name", "Secretary of State")
        ev.sources.append(SourceCitation(
            source_type=SourceType.SECRETARY_OF_STATE,
            name=str(name),
            url=str(url) if url else None,
            reliability=_SOURCE_RELIABILITY[SourceType.SECRETARY_OF_STATE],
        ))

    # Website -----------------------------------------------------------
    website = research.get("website")
    if website and isinstance(website, dict):
        ev.website_url = website.get("url")
        ev.website_construction = bool(website.get("mentions_construction", False))
        ev.sources.append(SourceCitation(
            source_type=SourceType.WEBSITE,
            name=str(ev.website_url or "website"),
            url=ev.website_url,
            reliability=_SOURCE_RELIABILITY[SourceType.WEBSITE],
        ))

    # Business profiles -------------------------------------------------
    profiles = research.get("business_profiles", [])
    if profiles and isinstance(profiles, list):
        for prof in profiles:
            if not isinstance(prof, dict):
                continue
            platform = str(prof.get("platform", "unknown"))
            categories: list[str] = prof.get("categories") or []
            is_construction = any(
                c.lower() in _CONSTRUCTION_CATEGORIES for c in categories
            )
            if is_construction:
                ev.construction_profile_platforms.append(platform)
            ev.sources.append(SourceCitation(
                source_type=SourceType.BUSINESS_PROFILE,
                name=platform,
                url=prof.get("url"),
                reliability=_SOURCE_RELIABILITY[SourceType.BUSINESS_PROFILE],
            ))

    # Social profiles ---------------------------------------------------
    socials = research.get("social_profiles", [])
    if socials and isinstance(socials, list):
        for social in socials:
            if not isinstance(social, dict):
                continue
            platform = str(social.get("platform", "unknown"))
            ev.sources.append(SourceCitation(
                source_type=SourceType.SOCIAL_PROFILE,
                name=platform,
                url=social.get("url"),
                reliability=_SOURCE_RELIABILITY[SourceType.SOCIAL_PROFILE],
            ))

    # County records ----------------------------------------------------
    county = research.get("county_records")
    if county and isinstance(county, dict):
        ev.county_deed_count = int(county.get("deed_count", 0) or 0)
        ev.county_permit_count = int(county.get("permit_count", 0) or 0)
        ev.county_source_name = county.get("source_name")
        url = county.get("source_url")
        ev.sources.append(SourceCitation(
            source_type=SourceType.COUNTY_RECORDS,
            name=str(ev.county_source_name or "County Records"),
            url=str(url) if url else None,
            reliability=_SOURCE_RELIABILITY[SourceType.COUNTY_RECORDS],
        ))

    return ev if ev.sources else None


def _research_confidence(ev: ResearchEvidence) -> float:
    """
    Aggregate reliability score for a set of research sources (0.0–1.0).

    Computed as the average reliability across distinct source types,
    plus a small corroboration bonus for 2+ types agreeing.
    """
    if not ev.sources:
        return 0.0
    # One reliability value per distinct source type (highest wins ties)
    type_reliability: dict[SourceType, float] = {}
    for s in ev.sources:
        if s.source_type not in type_reliability or s.reliability > type_reliability[s.source_type]:
            type_reliability[s.source_type] = s.reliability
    avg = sum(type_reliability.values()) / len(type_reliability)
    corroboration = min(0.10, (len(type_reliability) - 1) * 0.05)
    return min(1.0, round(avg + corroboration, 4))


def _research_builder_boost(ev: ResearchEvidence) -> float:
    """
    Additive builder confidence boost derived from external research.
    Capped at _MAX_BUILDER_BOOST (0.20).
    """
    boost = 0.0
    if ev.sos_active:
        boost += _WR_SOS_ACTIVE
    if ev.construction_profile_platforms:
        boost += _WR_CONSTRUCTION_PROFILE
    if ev.website_construction:
        boost += _WR_WEBSITE_CONSTRUCTION
    if ev.county_permit_count >= _COUNTY_PERMIT_HEAVY_MIN:
        boost += _WR_COUNTY_PERMIT_HEAVY
    if ev.source_count >= 3:
        boost += _WR_CORROBORATION_3PLUS
    return min(_MAX_BUILDER_BOOST, round(boost, 4))


def _research_investor_boost(ev: ResearchEvidence) -> float:
    """
    Additive investor confidence boost derived from external research.
    Capped at _MAX_INVESTOR_BOOST (0.15).
    """
    boost = 0.0
    if ev.sos_active:
        boost += 0.05   # active entity confirms organised buyer
    if ev.county_deed_count >= _COUNTY_DEED_HEAVY_MIN:
        boost += 0.06   # high deed activity → active acquisitor
    if ev.source_count >= 3:
        boost += 0.04   # well-documented entity
    return min(_MAX_INVESTOR_BOOST, round(boost, 4))


def _extract_signals(
    record: dict[str, Any],
    batch_counts: dict[str, int],
) -> BuyerSignals:
    """
    Extract all measurable signals from a raw record dict.

    Expected keys (all optional except record_id/owner_name/parcel_id):
      owner_name            str
      parcel_address        str
      mailing_address       str
      land_use              str   ("vacant", "residential", "commercial", …)
      permit_count          int
      entity_type           str   ("LLC", "CORP", "TRUST", "INDIVIDUAL", …)
      nearby_parcel_count   int
      prior_acquisitions    int   (pre-computed from upstream data pipeline)
      purchase_cluster_days int   (days between this and most recent prior purchase)
      source_file           str
      research              dict  (optional — enables research-backed scoring)
    """
    sig = BuyerSignals()
    owner: str = str(record.get("owner_name", "") or "")
    parcel_addr: str | None = record.get("parcel_address")
    mailing_addr: str | None = record.get("mailing_address")

    # --- Entity / company ---
    declared_type: str = str(record.get("entity_type", "") or "").upper()
    detected_entity = _detect_entity(owner)
    is_company = declared_type in ("LLC", "CORP", "INC", "TRUST", "LP", "LLP", "PLLC") or (
        detected_entity is not None
    )
    sig.is_company_owned = is_company
    sig.entity_type_detected = declared_type if declared_type else detected_entity

    if is_company:
        label = sig.entity_type_detected or "company"
        sig.source_evidence.append(f"company entity: {owner} ({label})")

    # --- Builder keywords ---
    kw_matches = _detect_builder_keywords(owner)
    sig.has_builder_keywords = bool(kw_matches)
    sig.builder_keyword_matches = kw_matches
    if kw_matches:
        sig.source_evidence.append(
            f"builder keyword(s) in owner name: {', '.join(kw_matches)}"
        )

    # --- Permits ---
    permit_count: int = int(record.get("permit_count", 0) or 0)
    sig.permit_count = permit_count
    sig.has_permit_activity = permit_count >= _PERMIT_PARTIAL
    if permit_count > 0:
        sig.source_evidence.append(f"permit activity: {permit_count} permit(s) on record")

    # --- Nearby parcels ---
    nearby: int = int(record.get("nearby_parcel_count", 0) or 0)
    sig.nearby_parcel_count = nearby
    if nearby > 0:
        sig.source_evidence.append(f"nearby parcel concentration: {nearby} parcel(s)")

    # --- Prior acquisitions (pre-computed) ---
    prior: int = int(record.get("prior_acquisitions", 0) or 0)
    sig.prior_acquisitions = prior
    if prior >= _ACQ_PARTIAL:
        sig.source_evidence.append(f"prior acquisitions (upstream): {prior}")

    # --- Batch-level repeat detection ---
    norm_key = _normalize_owner(owner)
    batch_count = batch_counts.get(norm_key, 1)
    sig.batch_acquisition_count = batch_count
    if batch_count > 1:
        sig.source_evidence.append(
            f"appears {batch_count}× in current batch (same owner)"
        )

    # Merge batch count into effective repeat signal
    effective_acquisitions = max(prior, batch_count)
    sig.prior_acquisitions = effective_acquisitions

    # --- Vacant land ---
    land_use: str = str(record.get("land_use", "") or "").lower()
    sig.owns_vacant_land = "vacant" in land_use
    if sig.owns_vacant_land:
        sig.source_evidence.append(f"vacant land ownership: land_use={land_use!r}")

    # --- Mailing address mismatch ---
    sig.mailing_address_mismatch = _addresses_mismatch(parcel_addr, mailing_addr)
    if sig.mailing_address_mismatch:
        sig.source_evidence.append(
            f"mailing address mismatch: parcel={parcel_addr!r}, "
            f"mailing={mailing_addr!r}"
        )

    # --- Purchase clustering ---
    cluster_days = record.get("purchase_cluster_days")
    if cluster_days is not None:
        try:
            cluster_days = int(cluster_days)
            sig.purchase_cluster_days = cluster_days
            sig.has_purchase_cluster = cluster_days <= _CLUSTER_DAYS
            if sig.has_purchase_cluster:
                sig.source_evidence.append(
                    f"purchase cluster: {cluster_days} days since prior purchase"
                )
        except (TypeError, ValueError):
            pass

    # --- Source file ---
    src = record.get("source_file")
    if src:
        sig.source_evidence.append(f"source: {src}")

    # --- Research evidence (optional) ---
    sig.research_evidence = _extract_research_evidence(record)
    if sig.research_evidence is not None:
        rc = _research_confidence(sig.research_evidence)
        ev = sig.research_evidence
        parts: list[str] = []
        if ev.sos_active:
            parts.append(f"SOS active ({ev.sos_state or 'unknown state'})")
        if ev.construction_profile_platforms:
            parts.append(
                f"construction profiles: {', '.join(ev.construction_profile_platforms)}"
            )
        if ev.website_construction:
            parts.append("website mentions construction")
        if ev.county_permit_count:
            parts.append(f"county permits: {ev.county_permit_count}")
        if parts:
            sig.source_evidence.append(
                f"research evidence ({rc:.2f} confidence): {'; '.join(parts)}"
            )

    return sig


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _builder_score(sig: BuyerSignals) -> float:
    score = 0.0

    # Keywords (0–0.30)
    if sig.has_builder_keywords:
        score += _WB_KEYWORDS

    # Permits (0–0.25)
    if sig.permit_count >= _PERMIT_FULL:
        score += _WB_PERMITS
    elif sig.permit_count >= _PERMIT_PARTIAL:
        score += _WB_PERMITS * 0.45

    # Entity type (0–0.15)
    if sig.is_company_owned:
        score += _WB_ENTITY

    # Repeat acquisitions (0–0.15)
    if sig.prior_acquisitions >= _ACQ_FULL:
        score += _WB_REPEAT
    elif sig.prior_acquisitions >= _ACQ_PARTIAL:
        score += _WB_REPEAT * 0.45

    # Nearby parcels / infill concentration (0–0.15)
    if sig.nearby_parcel_count >= _NEARBY_FULL:
        score += _WB_NEARBY
    elif sig.nearby_parcel_count >= _NEARBY_PARTIAL:
        score += _WB_NEARBY * 0.45

    # Research boost (additive, capped separately)
    if sig.research_evidence is not None:
        score += _research_builder_boost(sig.research_evidence)

    return max(0.0, min(1.0, round(score, 4)))


def _investor_score(sig: BuyerSignals) -> float:
    score = 0.0

    # Repeat acquisitions (0–0.25)
    if sig.prior_acquisitions >= _ACQ_FULL:
        score += _WI_REPEAT
    elif sig.prior_acquisitions >= _ACQ_PARTIAL:
        score += _WI_REPEAT * 0.48

    # Entity type — investor-flavoured entities score higher (0–0.20)
    if sig.is_company_owned:
        if sig.entity_type_detected and _INVESTOR_ENTITY_KEYWORDS.search(
            sig.entity_type_detected
        ):
            score += _WI_ENTITY  # holding/capital/trust → full
        else:
            score += _WI_ENTITY * 0.75  # generic LLC/Corp → partial

    # Mailing address mismatch (0–0.20)
    if sig.mailing_address_mismatch:
        score += _WI_MISMATCH

    # Vacant land ownership (0–0.20)
    if sig.owns_vacant_land:
        score += _WI_VACANT

    # Purchase clustering (0–0.15)
    if sig.has_purchase_cluster:
        score += _WI_CLUSTER

    # Research boost (additive, capped separately)
    if sig.research_evidence is not None:
        score += _research_investor_boost(sig.research_evidence)

    return max(0.0, min(1.0, round(score, 4)))


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route(
    record: dict[str, Any],
    sig: BuyerSignals,
    b_score: float,
    i_score: float,
) -> tuple[BuyerType, list[str], list[str]]:
    """
    Return (buyer_type, evidence_flags, weak_reasons).

    Priority order:
    1. Missing required fields → WEAK_RECORD
    2. builder_confidence >= BUILDER_THRESHOLD → VERIFIED_BUILDER
    3. investor_confidence >= INVESTOR_THRESHOLD → POSSIBLE_CASH_BUYER
    4. prior_acquisitions >= REPEAT_BUYER_MIN → REPEAT_BUYER
    5. Otherwise → QUARANTINED
    """
    evidence: list[str] = list(sig.source_evidence)
    weak: list[str] = []

    # 1. Required field validation
    missing = [
        f for f in ("record_id", "owner_name", "parcel_id")
        if not str(record.get(f, "") or "").strip()
    ]
    if missing:
        weak.append(f"missing required field(s): {', '.join(missing)}")
        return BuyerType.WEAK_RECORD, evidence, weak

    # 2. Verified builder
    if b_score >= BUILDER_THRESHOLD:
        evidence.append(f"builder confidence {b_score:.3f} ≥ threshold {BUILDER_THRESHOLD}")
        return BuyerType.VERIFIED_BUILDER, evidence, weak

    # 3. Possible cash buyer
    if i_score >= INVESTOR_THRESHOLD:
        evidence.append(
            f"investor confidence {i_score:.3f} ≥ threshold {INVESTOR_THRESHOLD}"
        )
        return BuyerType.POSSIBLE_CASH_BUYER, evidence, weak

    # 4. Repeat buyer fallback
    if sig.prior_acquisitions >= REPEAT_BUYER_MIN:
        evidence.append(
            f"repeat buyer: {sig.prior_acquisitions} acquisition(s), "
            f"below builder ({b_score:.3f}) and investor ({i_score:.3f}) thresholds"
        )
        return BuyerType.REPEAT_BUYER, evidence, weak

    # 5. Quarantine — insufficient signals
    weak.append(
        f"builder confidence {b_score:.3f} below {BUILDER_THRESHOLD}, "
        f"investor confidence {i_score:.3f} below {INVESTOR_THRESHOLD}, "
        f"acquisitions {sig.prior_acquisitions} below {REPEAT_BUYER_MIN}"
    )
    return BuyerType.QUARANTINED, evidence, weak


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------


class BuilderVerificationAgent:
    """
    Processes a batch of raw owner/buyer records and produces five
    output documents with evidence-backed confidence profiles.

    Usage:
        agent = BuilderVerificationAgent(reports_dir=Path("reports"))
        report = agent.run(records)
        agent.write_outputs(report)
    """

    def __init__(self, reports_dir: Path | None = None) -> None:
        self.reports_dir = reports_dir or Path(__file__).parent / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, records: list[dict[str, Any]]) -> VerificationReport:
        """
        Process a list of raw record dicts.

        Required keys per record:
            record_id     str
            owner_name    str
            parcel_id     str

        All other keys are optional and scored when present.
        """
        # Pre-compute batch-level owner frequency for cross-record repeat detection
        batch_counts: dict[str, int] = {}
        for r in records:
            key = _normalize_owner(str(r.get("owner_name", "") or ""))
            batch_counts[key] = batch_counts.get(key, 0) + 1

        # Build entity index from SOS legal names across the batch
        entity_index: dict[str, str] = {}  # normalized → canonical legal name
        for r in records:
            research = r.get("research")
            if not research or not isinstance(research, dict):
                continue
            sos = research.get("secretary_of_state")
            if sos and isinstance(sos, dict) and sos.get("registered") and sos.get("legal_name"):
                legal_name = str(sos["legal_name"])
                norm = _normalize_owner(legal_name)
                entity_index[norm] = legal_name

        profiles: list[BuyerProfile] = []
        for raw in records:
            profiles.append(self._process_record(raw, batch_counts, entity_index))

        builders    = [p for p in profiles if p.buyer_type == BuyerType.VERIFIED_BUILDER]
        cash_buyers = [p for p in profiles if p.buyer_type == BuyerType.POSSIBLE_CASH_BUYER]
        repeats     = [p for p in profiles if p.buyer_type == BuyerType.REPEAT_BUYER]
        quarantined = [p for p in profiles if p.buyer_type == BuyerType.QUARANTINED]
        weak        = [p for p in profiles if p.buyer_type == BuyerType.WEAK_RECORD]

        # Sort by confidence descending within each bucket
        builders.sort(key=lambda p: p.builder_confidence, reverse=True)
        cash_buyers.sort(key=lambda p: p.investor_confidence, reverse=True)
        repeats.sort(key=lambda p: p.signals.prior_acquisitions, reverse=True)

        return VerificationReport(
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            total_processed=len(profiles),
            verified_builders=builders,
            possible_cash_buyers=cash_buyers,
            repeat_buyers=repeats,
            quarantined=quarantined,
            weak_records=weak,
        )

    def write_outputs(self, report: VerificationReport) -> None:
        """Write all five output documents to reports_dir."""
        self._write_verified_builders(report)
        self._write_possible_cash_buyers(report)
        self._write_buyer_activity_report(report)
        self._write_buyer_confidence_scores(report)
        self._write_entity_intelligence_report(report)

    # ------------------------------------------------------------------
    # Record processing
    # ------------------------------------------------------------------

    def _process_record(
        self,
        raw: dict[str, Any],
        batch_counts: dict[str, int],
        entity_index: dict[str, str],
    ) -> BuyerProfile:
        record_id  = str(raw.get("record_id", "") or "")
        owner_name = str(raw.get("owner_name", "") or "")
        parcel_id  = str(raw.get("parcel_id", "") or "")

        sig = _extract_signals(raw, batch_counts)
        b_score = _builder_score(sig)
        i_score = _investor_score(sig)
        buyer_type, evidence_flags, weak_reasons = _route(raw, sig, b_score, i_score)

        sale_price_raw = raw.get("sale_price")
        sale_price: float | None = None
        if sale_price_raw is not None:
            try:
                sale_price = float(sale_price_raw)
            except (TypeError, ValueError):
                pass

        # Entity matching: check owner name and SOS legal name against entity index
        entity_matches: list[str] = []
        norm_owner = _normalize_owner(owner_name)
        if norm_owner in entity_index:
            legal = entity_index[norm_owner]
            if legal not in entity_matches:
                entity_matches.append(legal)
        if sig.research_evidence and sig.research_evidence.sos_legal_name:
            norm_legal = _normalize_owner(sig.research_evidence.sos_legal_name)
            for idx_norm, idx_legal in entity_index.items():
                if idx_norm in (norm_legal, norm_owner):
                    if idx_legal not in entity_matches:
                        entity_matches.append(idx_legal)

        research_confidence = (
            _research_confidence(sig.research_evidence)
            if sig.research_evidence is not None
            else 0.0
        )

        return BuyerProfile(
            record_id=record_id,
            owner_name=owner_name,
            parcel_id=parcel_id,
            buyer_type=buyer_type,
            builder_confidence=b_score,
            investor_confidence=i_score,
            signals=sig,
            evidence_flags=evidence_flags,
            weak_reasons=weak_reasons,
            parcel_address=raw.get("parcel_address"),
            mailing_address=raw.get("mailing_address"),
            sale_price=sale_price,
            sale_date=raw.get("sale_date"),
            source_file=raw.get("source_file"),
            entity_matches=entity_matches,
            research_confidence=research_confidence,
        )

    # ------------------------------------------------------------------
    # Output writers
    # ------------------------------------------------------------------

    def _write_verified_builders(self, report: VerificationReport) -> None:
        payload = [_profile_to_dict(p) for p in report.verified_builders]
        self._write(
            self.reports_dir / "VERIFIED_BUILDERS.json",
            json.dumps(payload, indent=2),
        )

    def _write_possible_cash_buyers(self, report: VerificationReport) -> None:
        payload = [_profile_to_dict(p) for p in report.possible_cash_buyers]
        self._write(
            self.reports_dir / "POSSIBLE_CASH_BUYERS.json",
            json.dumps(payload, indent=2),
        )

    def _write_buyer_activity_report(self, report: VerificationReport) -> None:
        ts = report.run_timestamp
        total = report.total_processed
        n_b  = len(report.verified_builders)
        n_cb = len(report.possible_cash_buyers)
        n_r  = len(report.repeat_buyers)
        n_q  = len(report.quarantined)
        n_w  = len(report.weak_records)

        lines = [
            "# BUYER_ACTIVITY_REPORT",
            "",
            f"_Generated: {ts}_",
            "",
            "## Summary",
            "",
            f"| Category | Count |",
            f"|----------|-------|",
            f"| Total processed | {total} |",
            f"| Verified builders | {n_b} |",
            f"| Possible cash buyers | {n_cb} |",
            f"| Repeat buyers | {n_r} |",
            f"| Quarantined (weak signals) | {n_q} |",
            f"| Weak records (missing data) | {n_w} |",
            "",
        ]

        if report.verified_builders:
            lines += ["## Verified Builders", ""]
            for p in report.verified_builders:
                lines += _profile_md_block(p, show_builder=True)

        if report.possible_cash_buyers:
            lines += ["## Possible Cash Buyers", ""]
            for p in report.possible_cash_buyers:
                lines += _profile_md_block(p, show_builder=False)

        if report.repeat_buyers:
            lines += ["## Repeat Buyers", ""]
            for p in report.repeat_buyers:
                lines += [
                    f"### {p.owner_name}",
                    "",
                    f"- **Record ID**: `{p.record_id}`",
                    f"- **Acquisitions**: {p.signals.prior_acquisitions}",
                    f"- **Builder confidence**: {p.builder_confidence:.3f}",
                    f"- **Investor confidence**: {p.investor_confidence:.3f}",
                    "",
                ]

        if report.quarantined:
            lines += [
                "## Quarantined Records",
                "",
                "_Insufficient signals to classify. Review upstream data quality._",
                "",
            ]
            for p in report.quarantined:
                reasons = "; ".join(p.weak_reasons) or "below all thresholds"
                lines.append(
                    f"- `{p.record_id}` **{p.owner_name}** — {reasons}"
                )
            lines.append("")

        if report.weak_records:
            lines += [
                "## Weak Records (Missing Required Fields)",
                "",
                "_These records are missing required fields and cannot be scored._",
                "",
            ]
            for p in report.weak_records:
                reasons = "; ".join(p.weak_reasons) or "see record"
                lines.append(f"- `{p.record_id or '(no id)'}` — {reasons}")
            lines.append("")

        self._write(
            self.reports_dir / "BUYER_ACTIVITY_REPORT.md",
            "\n".join(lines),
        )

    def _write_buyer_confidence_scores(self, report: VerificationReport) -> None:
        all_profiles = (
            report.verified_builders
            + report.possible_cash_buyers
            + report.repeat_buyers
            + report.quarantined
            + report.weak_records
        )

        payload = {
            "run_timestamp": report.run_timestamp,
            "thresholds": {
                "builder": BUILDER_THRESHOLD,
                "investor": INVESTOR_THRESHOLD,
                "repeat_buyer_min_acquisitions": REPEAT_BUYER_MIN,
            },
            "counts": {
                "total": report.total_processed,
                "verified_builders": len(report.verified_builders),
                "possible_cash_buyers": len(report.possible_cash_buyers),
                "repeat_buyers": len(report.repeat_buyers),
                "quarantined": len(report.quarantined),
                "weak_records": len(report.weak_records),
            },
            "scores": [
                {
                    "record_id": p.record_id,
                    "owner_name": p.owner_name,
                    "parcel_id": p.parcel_id,
                    "buyer_type": p.buyer_type,
                    "builder_confidence": p.builder_confidence,
                    "investor_confidence": p.investor_confidence,
                    "research_confidence": p.research_confidence,
                    "entity_matches": p.entity_matches,
                    "signals": {
                        "is_company_owned": p.signals.is_company_owned,
                        "entity_type_detected": p.signals.entity_type_detected,
                        "has_builder_keywords": p.signals.has_builder_keywords,
                        "builder_keyword_matches": p.signals.builder_keyword_matches,
                        "permit_count": p.signals.permit_count,
                        "nearby_parcel_count": p.signals.nearby_parcel_count,
                        "prior_acquisitions": p.signals.prior_acquisitions,
                        "owns_vacant_land": p.signals.owns_vacant_land,
                        "mailing_address_mismatch": p.signals.mailing_address_mismatch,
                        "has_purchase_cluster": p.signals.has_purchase_cluster,
                        "purchase_cluster_days": p.signals.purchase_cluster_days,
                    },
                    "evidence_flags": p.evidence_flags,
                    "weak_reasons": p.weak_reasons,
                }
                for p in all_profiles
            ],
        }

        self._write(
            self.reports_dir / "BUYER_CONFIDENCE_SCORES.json",
            json.dumps(payload, indent=2),
        )

    def _write_entity_intelligence_report(self, report: VerificationReport) -> None:
        all_profiles = (
            report.verified_builders
            + report.possible_cash_buyers
            + report.repeat_buyers
            + report.quarantined
            + report.weak_records
        )

        # Collect profiles that have research evidence
        researched = [p for p in all_profiles if p.signals.research_evidence is not None]
        ts = report.run_timestamp

        lines = [
            "# ENTITY INTELLIGENCE REPORT",
            "",
            f"_Generated: {ts}_",
            "",
        ]

        if not researched:
            lines += [
                "_No research-backed entity records in this batch._",
                "",
            ]
            self._write(
                self.reports_dir / "ENTITY_INTELLIGENCE_REPORT.md",
                "\n".join(lines),
            )
            return

        lines += [
            f"## Entities with Research Evidence ({len(researched)} record(s))",
            "",
        ]

        for p in researched:
            ev = p.signals.research_evidence
            assert ev is not None
            b_boost = _research_builder_boost(ev)
            i_boost = _research_investor_boost(ev)
            rc = p.research_confidence

            lines += [f"### {p.owner_name}", ""]
            lines.append(f"- **Record ID**: `{p.record_id}`")
            lines.append(f"- **Parcel**: `{p.parcel_id}`")
            lines.append(f"- **Buyer type**: {p.buyer_type}")
            lines.append(
                f"- **Builder confidence**: {p.builder_confidence:.3f} "
                f"(research boost: +{b_boost:.3f})"
            )
            lines.append(
                f"- **Investor confidence**: {p.investor_confidence:.3f} "
                f"(research boost: +{i_boost:.3f})"
            )
            lines.append(f"- **Research confidence**: {rc:.3f}")
            if p.entity_matches:
                lines.append(
                    f"- **Entity matches**: {', '.join(p.entity_matches)}"
                )

            if ev.sos_legal_name:
                lines.append(
                    f"- **SOS legal name**: {ev.sos_legal_name} "
                    f"({ev.sos_state or 'unknown'}) — "
                    f"{'active' if ev.sos_active else 'registered/inactive'}"
                )

            if ev.construction_profile_platforms:
                lines.append(
                    f"- **Construction profiles**: "
                    f"{', '.join(ev.construction_profile_platforms)}"
                )

            if ev.website_construction and ev.website_url:
                lines.append(f"- **Website (construction)**: {ev.website_url}")

            if ev.county_deed_count or ev.county_permit_count:
                lines.append(
                    f"- **County records** ({ev.county_source_name or 'unknown'}): "
                    f"deeds={ev.county_deed_count}, permits={ev.county_permit_count}"
                )

            lines += ["", "**Sources:**", ""]
            for src in ev.sources:
                url_str = f" — {src.url}" if src.url else ""
                lines.append(
                    f"  - [{src.source_type}] {src.name} "
                    f"(reliability: {src.reliability:.2f}){url_str}"
                )

            lines.append("")

        self._write(
            self.reports_dir / "ENTITY_INTELLIGENCE_REPORT.md",
            "\n".join(lines),
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _profile_to_dict(p: BuyerProfile) -> dict[str, Any]:
    ev = p.signals.research_evidence
    research_dict: dict[str, Any] | None = None
    if ev is not None:
        research_dict = {
            "sos_active": ev.sos_active,
            "sos_legal_name": ev.sos_legal_name,
            "sos_state": ev.sos_state,
            "website_construction": ev.website_construction,
            "construction_profile_platforms": ev.construction_profile_platforms,
            "county_deed_count": ev.county_deed_count,
            "county_permit_count": ev.county_permit_count,
            "source_count": ev.source_count,
            "sources": [
                {
                    "source_type": s.source_type,
                    "name": s.name,
                    "url": s.url,
                    "reliability": s.reliability,
                }
                for s in ev.sources
            ],
        }

    return {
        "record_id": p.record_id,
        "owner_name": p.owner_name,
        "parcel_id": p.parcel_id,
        "buyer_type": p.buyer_type,
        "builder_confidence": p.builder_confidence,
        "investor_confidence": p.investor_confidence,
        "research_confidence": p.research_confidence,
        "entity_matches": p.entity_matches,
        "parcel_address": p.parcel_address,
        "mailing_address": p.mailing_address,
        "sale_price": p.sale_price,
        "sale_date": p.sale_date,
        "source_file": p.source_file,
        "signals": {
            "is_company_owned": p.signals.is_company_owned,
            "entity_type_detected": p.signals.entity_type_detected,
            "has_builder_keywords": p.signals.has_builder_keywords,
            "builder_keyword_matches": p.signals.builder_keyword_matches,
            "permit_count": p.signals.permit_count,
            "nearby_parcel_count": p.signals.nearby_parcel_count,
            "prior_acquisitions": p.signals.prior_acquisitions,
            "owns_vacant_land": p.signals.owns_vacant_land,
            "mailing_address_mismatch": p.signals.mailing_address_mismatch,
            "has_purchase_cluster": p.signals.has_purchase_cluster,
            "purchase_cluster_days": p.signals.purchase_cluster_days,
        },
        "research_evidence": research_dict,
        "evidence_flags": p.evidence_flags,
        "run_timestamp": p.run_timestamp,
    }


def _profile_md_block(p: BuyerProfile, *, show_builder: bool) -> list[str]:
    conf_label = "Builder confidence" if show_builder else "Investor confidence"
    conf_val = p.builder_confidence if show_builder else p.investor_confidence
    lines = [
        f"### {p.owner_name}",
        "",
        f"- **Record ID**: `{p.record_id}`",
        f"- **Parcel**: `{p.parcel_id}`",
        f"- **{conf_label}**: {conf_val:.3f}",
    ]
    if not show_builder:
        lines.append(f"- **Builder confidence**: {p.builder_confidence:.3f}")
    if p.research_confidence > 0:
        lines.append(f"- **Research confidence**: {p.research_confidence:.3f}")
    if p.entity_matches:
        lines.append(f"- **Entity matches**: {', '.join(p.entity_matches)}")
    if p.parcel_address:
        lines.append(f"- **Parcel address**: {p.parcel_address}")
    if p.sale_price is not None:
        lines.append(f"- **Sale price**: ${p.sale_price:,.0f}")
    if p.sale_date:
        lines.append(f"- **Sale date**: {p.sale_date}")
    if p.evidence_flags:
        lines.append("- **Evidence**:")
        for flag in p.evidence_flags:
            lines.append(f"  - {flag}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# CLI entry point
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
            print(
                f"[WARN] Skipping malformed JSON {json_file}: {exc}",
                file=sys.stderr,
            )
    return records


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Builder Verification Agent — convert owner records into buyer intelligence profiles"
    )
    parser.add_argument(
        "records",
        nargs="?",
        help=(
            "Path to a JSON file (list of records) or a directory of JSON files. "
            "If omitted, reads from stdin."
        ),
    )
    parser.add_argument(
        "--reports-dir",
        default=None,
        help="Directory to write output reports (default: agents/builder-verification/reports/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary to stdout without writing files.",
    )
    args = parser.parse_args(argv)

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
        Path(args.reports_dir)
        if args.reports_dir
        else Path(__file__).parent / "reports"
    )

    agent = BuilderVerificationAgent(reports_dir=reports_dir)
    report = agent.run(raw_records)

    print(f"\nBuilder Verification Agent — {report.run_timestamp}")
    print(f"  Processed         : {report.total_processed}")
    print(f"  Verified builders : {len(report.verified_builders)}")
    print(f"  Cash buyers       : {len(report.possible_cash_buyers)}")
    print(f"  Repeat buyers     : {len(report.repeat_buyers)}")
    print(f"  Quarantined       : {len(report.quarantined)}")
    print(f"  Weak records      : {len(report.weak_records)}")

    if report.verified_builders:
        print("\nTop builders:")
        for p in report.verified_builders[:5]:
            print(
                f"  [{p.builder_confidence:.2f}] {p.owner_name} "
                f"(parcel {p.parcel_id})"
            )

    if not args.dry_run:
        agent.write_outputs(report)
        print(f"\nReports written to: {reports_dir}/")

    n_actionable = (
        len(report.verified_builders) + len(report.possible_cash_buyers)
    )
    return 0 if n_actionable > 0 or report.total_processed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
