"""
AMARA OS — Zillow Distress Hunting Engine

Structured workflow for finding distressed properties on Zillow.
Builds search criteria from buyer buy boxes and ZIP corridors,
scores resulting properties for distress signals, and feeds
qualified leads into the Auto Matcher pipeline.

This is a data-preparation and scoring layer — it does NOT
call Zillow's API directly. It structures the search parameters
a user or integration would execute, then scores whatever
CSV/export is returned.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from system.config import (
    VAULT_BUYERS, VAULT_ZIP_CORRIDORS,
    ACTIVITY_HOT, ACTIVITY_WARM, ACTIVITY_COLD,
)
from system.lead_intake import PropertyLead, ingest_from_csv
from system.distress_scorer import score_sfr_distress, SFRDistressScore
from system.vault import list_vault, read_vault_file, write_vault_file, append_observation


# ─── Search Criteria ──────────────────────────────────────────────────────────

@dataclass
class ZillowSearchCriteria:
    """
    Structured search parameters for a Zillow distress hunt.
    Maps directly to Zillow's filter UI and URL parameters.
    """
    label:          str               # e.g. "Houston North — BUY-0001 hunt"
    zip_codes:      list[str]
    min_price:      float = 0
    max_price:      float = 0         # 0 = no max
    min_beds:       int   = 0
    max_beds:       int   = 0         # 0 = no max
    min_sqft:       int   = 0
    max_sqft:       int   = 0         # 0 = no max
    min_year_built: int   = 0         # 0 = no filter
    max_year_built: int   = 0         # 0 = no filter
    min_dom:        int   = 30        # days on market — focus on stale listings
    property_type:  str   = "houses"  # houses / all / land

    # Distress filters — guide the manual search or filter logic
    price_reduced:  bool  = True      # show price-reduced listings
    for_sale_by_owner: bool = False
    foreclosure:    bool  = False     # bank-owned / foreclosure filter

    def to_search_string(self) -> str:
        """Generate a readable search configuration."""
        lines = [
            f"SEARCH: {self.label}",
            f"  ZIPs: {', '.join(self.zip_codes)}",
            f"  Type: {self.property_type}",
        ]
        if self.min_price or self.max_price:
            p_range = f"${self.min_price:,.0f}" if self.min_price else "$0"
            p_range += f" – ${self.max_price:,.0f}" if self.max_price else "+"
            lines.append(f"  Price: {p_range}")
        if self.min_beds:
            lines.append(f"  Beds: {self.min_beds}+")
        if self.min_dom:
            lines.append(f"  DOM: {self.min_dom}+ days")
        if self.price_reduced:
            lines.append("  Filter: Price Reduced")
        return "\n".join(lines)

    def to_url_params(self) -> dict[str, str]:
        """
        Return a dict of query parameters for constructing a Zillow search URL.
        The caller is responsible for composing the final URL.
        These follow Zillow's standard filter param naming conventions.
        """
        params: dict[str, str] = {}
        if self.min_price > 0:
            params["price_min"] = str(int(self.min_price))
        if self.max_price > 0:
            params["price_max"] = str(int(self.max_price))
        if self.min_beds > 0:
            params["beds_min"] = str(self.min_beds)
        if self.max_beds > 0:
            params["beds_max"] = str(self.max_beds)
        if self.min_sqft > 0:
            params["sqft_min"] = str(self.min_sqft)
        if self.max_sqft > 0:
            params["sqft_max"] = str(self.max_sqft)
        if self.min_dom > 0:
            params["days_on_zillow_min"] = str(self.min_dom)
        if self.price_reduced:
            params["price_reduction"] = "1"
        params["status_type"]  = "ForSale"
        params["home_type"]    = self.property_type
        return params


# ─── Hunt Session ─────────────────────────────────────────────────────────────

@dataclass
class HuntSession:
    """
    Represents one Zillow distress hunting session.
    Tracks criteria, properties found, and pipeline-ready leads.
    """
    session_id:    str = field(default_factory=lambda: f"HUNT-{uuid.uuid4().hex[:6].upper()}")
    created_at:    str = field(default_factory=lambda: date.today().isoformat())
    criteria:      list[ZillowSearchCriteria] = field(default_factory=list)
    raw_count:     int  = 0       # total listings returned from Zillow
    scored_count:  int  = 0       # listings scored after distress filter
    qualified:     int  = 0       # passed distress threshold
    rejected:      int  = 0       # below threshold
    leads:         list[PropertyLead] = field(default_factory=list)
    top_scores:    list[tuple[float, str]] = field(default_factory=list)  # (score, address)

    def summary(self) -> str:
        return (
            f"[{self.session_id}] Hunt Session — {self.created_at}\n"
            f"  Criteria sets: {len(self.criteria)}\n"
            f"  Raw: {self.raw_count} | Scored: {self.scored_count} | "
            f"Qualified: {self.qualified} | Rejected: {self.rejected}\n"
            f"  Top Leads:\n" +
            "\n".join(f"    {score:.2f} — {addr}" for score, addr in self.top_scores[:5])
        )


# ─── Distress Filter ──────────────────────────────────────────────────────────

# Minimum distress score to pass into the pipeline
DISTRESS_THRESHOLD = 0.30

# Keywords that trigger an automatic pull regardless of DOM
HIGH_PRIORITY_KEYWORDS = {
    "estate sale", "probate", "inherited", "fire damage", "flood",
    "as-is", "investor special", "motivated", "must sell", "foreclosure",
    "bank owned", "reo", "hoa liens", "tax lien", "price reduced",
    "vacant", "abandoned", "fixer", "teardown",
}


def _extract_keywords(description: str) -> list[str]:
    if not description:
        return []
    desc_lower = description.lower()
    found = []
    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw in desc_lower:
            found.append(kw)
    return found


def _is_high_priority(lead: PropertyLead) -> bool:
    """Return True if lead has any high-priority distress signal."""
    kws = {k.lower() for k in lead.keywords}
    return bool(kws & HIGH_PRIORITY_KEYWORDS)


# ─── Build Search Criteria from Buyer Vault ───────────────────────────────────

def build_search_criteria_from_buyer(
    buyer_id:   str,
    zip_codes:  list[str],
    max_price:  float,
    min_price:  float = 0,
    min_beds:   int   = 0,
    min_dom:    int   = 30,
) -> ZillowSearchCriteria:
    """
    Generate a Zillow search criteria object from a buyer's buy box.
    Use price + 15% as max to capture slightly overpriced deals.
    """
    label = f"Buyer {buyer_id} — {len(zip_codes)} ZIPs"
    return ZillowSearchCriteria(
        label      = label,
        zip_codes  = zip_codes,
        min_price  = min_price,
        max_price  = max_price * 1.15 if max_price else 0,
        min_beds   = min_beds,
        min_dom    = min_dom,
        price_reduced = True,
    )


def build_search_criteria_for_zip(
    zip_code:   str,
    min_price:  float = 0,
    max_price:  float = 0,
    label:      str   = "",
) -> ZillowSearchCriteria:
    """Build a broad ZIP-level search — used for corridor hunting."""
    return ZillowSearchCriteria(
        label      = label or f"ZIP {zip_code} corridor hunt",
        zip_codes  = [zip_code],
        min_price  = min_price,
        max_price  = max_price,
        min_dom    = 20,
        price_reduced = True,
    )


# ─── Score Leads from Export ──────────────────────────────────────────────────

@dataclass
class ScoredLead:
    lead:           PropertyLead
    distress:       SFRDistressScore
    distress_score: float
    is_high_priority: bool
    passed:         bool


def score_leads(
    leads:     list[PropertyLead],
    threshold: float = DISTRESS_THRESHOLD,
) -> list[ScoredLead]:
    """
    Score a list of leads for distress signals.
    Returns all leads with scores; filter `passed=True` for pipeline-ready leads.
    """
    results = []
    for lead in leads:
        distress  = score_sfr_distress(lead)
        hi_pri    = _is_high_priority(lead)
        score     = distress.total_distress_score

        # High-priority keywords auto-pass regardless of score
        passed = score >= threshold or hi_pri

        results.append(ScoredLead(
            lead             = lead,
            distress         = distress,
            distress_score   = round(score, 3),
            is_high_priority = hi_pri,
            passed           = passed,
        ))

    # Sort: high-priority first, then by score descending
    results.sort(key=lambda x: (0 if x.is_high_priority else 1, -x.distress_score))
    return results


# ─── Process Zillow CSV Export ────────────────────────────────────────────────

def process_zillow_export(
    csv_path:   str,
    session_id: str | None = None,
    threshold:  float = DISTRESS_THRESHOLD,
) -> HuntSession:
    """
    Process a Zillow CSV export:
    1. Ingest leads from CSV
    2. Score each lead for distress signals
    3. Return HuntSession with qualified leads ready for auto_matcher

    The CSV should have columns compatible with lead_intake.ingest_from_csv().
    Zillow exports typically include: address, price, beds, baths, sqft, DOM, description.
    """
    session = HuntSession()
    if session_id:
        session.session_id = session_id

    # Stage 1: Ingest
    leads = ingest_from_csv(csv_path, source="zillow")
    session.raw_count = len(leads)

    if not leads:
        return session

    # Stage 2: Score
    scored = score_leads(leads, threshold)
    session.scored_count = len(scored)

    # Stage 3: Filter
    passed = [s for s in scored if s.passed]
    failed = [s for s in scored if not s.passed]

    session.qualified = len(passed)
    session.rejected  = len(failed)
    session.leads     = [s.lead for s in passed]
    session.top_scores = [
        (s.distress_score, s.lead.address)
        for s in passed[:10]
    ]

    return session


# ─── Hunt Workflow ────────────────────────────────────────────────────────────

def run_distress_hunt(
    criteria_list:    list[ZillowSearchCriteria],
    csv_paths:        list[str],   # one per criteria set, in same order
    log_observation:  bool = True,
) -> HuntSession:
    """
    Full distress hunt workflow:
    1. Show search criteria
    2. Process CSV exports for each criteria set
    3. Merge and rank all leads
    4. Log observation to vault
    Returns combined HuntSession.
    """
    session = HuntSession(criteria=criteria_list)

    all_scored: list[ScoredLead] = []

    for criteria, csv_path in zip(criteria_list, csv_paths):
        leads = ingest_from_csv(csv_path, source="zillow")
        session.raw_count += len(leads)
        scored = score_leads(leads, DISTRESS_THRESHOLD)
        all_scored.extend(scored)

    # Deduplicate by address
    seen: set[str] = set()
    unique: list[ScoredLead] = []
    for s in all_scored:
        key = s.lead.address.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    unique.sort(key=lambda x: (0 if x.is_high_priority else 1, -x.distress_score))

    passed = [s for s in unique if s.passed]
    failed = [s for s in unique if not s.passed]

    session.scored_count = len(unique)
    session.qualified    = len(passed)
    session.rejected     = len(failed)
    session.leads        = [s.lead for s in passed]
    session.top_scores   = [(s.distress_score, s.lead.address) for s in passed[:10]]

    if log_observation and passed:
        _log_hunt_observation(session)

    return session


def _log_hunt_observation(session: HuntSession) -> None:
    """Auto-log a Zillow hunt observation to the vault."""
    today   = date.today().isoformat()
    market  = "Multi-ZIP" if session.criteria else "Unknown"
    if session.criteria:
        all_zips = []
        for c in session.criteria:
            all_zips.extend(c.zip_codes)
        market = ", ".join(sorted(set(all_zips))[:6])

    insight = (
        f"Zillow distress hunt returned {session.qualified} qualified leads "
        f"from {session.raw_count} listings across {market}."
    )

    top_lead_lines = "\n".join(
        f"- Score {score:.2f}: {addr}"
        for score, addr in session.top_scores[:5]
    )

    content = f"""# Zillow Hunt — {session.session_id}

## Market
{market}

## Insight
{insight}

## Top Distress Leads
{top_lead_lines}

## Impact
{session.qualified} leads routed to Auto Matcher pipeline for buyer matching and underwriting.

## Action
Run `python amara.py match csv` on qualified leads. Verify buyer match before sending any offer.

---

- **Session:** {session.session_id}
- **Date:** {today}
- **Raw:** {session.raw_count} | **Qualified:** {session.qualified} | **Rejected:** {session.rejected}
"""
    append_observation(content, topic=f"Zillow_Hunt_{session.session_id}")


def print_hunt_summary(session: HuntSession) -> None:
    print(f"\n{'═' * 60}")
    print(f"ZILLOW DISTRESS HUNT — {session.session_id}")
    print(f"{'─' * 60}")
    print(f"  Raw listings:  {session.raw_count}")
    print(f"  Scored:        {session.scored_count}")
    print(f"  Qualified:     {session.qualified}")
    print(f"  Rejected:      {session.rejected}")
    if session.top_scores:
        print(f"\n  TOP LEADS:")
        for score, addr in session.top_scores:
            print(f"    {score:.2f} — {addr}")
    print(f"{'═' * 60}\n")
