"""
AMARA Auto Matcher — Stage 7: Distress + Motivation Scoring

Scores each lead on how motivated the seller is likely to be.
Higher distress score = more motivated seller = more likely to accept MAO.

SFR signals:  DOM, price drops, distressed keywords, bad photos, vacancy/probate/estate
Land signals: dead paper, ghost streets, plat/phase gap, builder adjacency, ownership weakness
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from system.lead_intake import PropertyLead, Classification


# ─── Keyword Signal Tables ────────────────────────────────────────────────────

VACANCY_KEYWORDS = frozenset({
    "vacant", "empty", "unoccupied", "no occupants", "utilities off",
    "winterized", "boarded", "board up", "abandoned",
})

INHERITED_KEYWORDS = frozenset({
    "inherited", "inheritance", "heir", "heirs", "trust sale",
    "living trust", "beneficiary", "out of state heir",
})

PROBATE_KEYWORDS = frozenset({
    "probate", "court approval", "court confirmation", "estate sale",
    "administrator", "executor", "personal representative",
})

ESTATE_KEYWORDS = frozenset({
    "estate", "estate of", "deceased", "passed away", "family estate",
    "selling family home",
})

FINANCIAL_DISTRESS_KEYWORDS = frozenset({
    "foreclosure", "pre-foreclosure", "nod", "notice of default",
    "bank owned", "reo", "short sale", "tax lien", "tax delinquent",
    "behind on payments", "lis pendens", "bankruptcy",
})

MOTIVATED_SELLER_KEYWORDS = frozenset({
    "motivated", "must sell", "needs to sell", "priced to sell",
    "bring all offers", "all offers considered", "price reduced",
    "will negotiate", "flexible", "make an offer",
})

# Land-specific
DEAD_PAPER_KEYWORDS = frozenset({
    "recorded subdivision", "platted", "lot and block",
    "old subdivision", "never developed", "dormant",
})

GHOST_STREET_KEYWORDS = frozenset({
    "ghost street", "paper street", "platted street", "unimproved street",
    "mapped road", "dedicated road never built",
})

OWNERSHIP_WEAKNESS_KEYWORDS = frozenset({
    "out of state owner", "absentee", "tax delinquent", "delinquent taxes",
    "clouded title", "heir property", "undivided interest",
})

# Aggregate all SFR keyword sets for fast lookup
_ALL_SFR_KEYWORD_SETS = [
    VACANCY_KEYWORDS, INHERITED_KEYWORDS, PROBATE_KEYWORDS,
    ESTATE_KEYWORDS, FINANCIAL_DISTRESS_KEYWORDS, MOTIVATED_SELLER_KEYWORDS,
]


# ─── DOM Thresholds ───────────────────────────────────────────────────────────

def _dom_score(dom: int) -> float:
    """Score days on market. Longer = more motivated. Returns 0.0–1.0."""
    if dom <= 14:   return 0.0
    if dom <= 30:   return 0.15
    if dom <= 60:   return 0.35
    if dom <= 90:   return 0.55
    if dom <= 120:  return 0.75
    return 1.0


def _price_drop_score(drops: int) -> float:
    """Score price reductions. More drops = more motivated. Returns 0.0–1.0."""
    if drops == 0:  return 0.0
    if drops == 1:  return 0.30
    if drops == 2:  return 0.60
    return 1.0


def _keyword_score(description: str, keyword_sets: list[frozenset]) -> float:
    """
    Count distinct keyword categories matched. Each category = +0.20, capped at 1.0.
    """
    desc_lower = description.lower()
    hits = sum(
        1 for kw_set in keyword_sets
        if any(kw in desc_lower for kw in kw_set)
    )
    return min(hits * 0.20, 1.0)


# ─── Distress Score Dataclasses ───────────────────────────────────────────────

@dataclass
class SFRDistressScore:
    property_id:           str
    dom_score:             float = 0.0
    price_drop_score:      float = 0.0
    keyword_score:         float = 0.0
    bad_photos_score:      float = 0.0
    vacancy_signal:        bool  = False
    inherited_signal:      bool  = False
    probate_signal:        bool  = False
    estate_signal:         bool  = False
    financial_distress:    bool  = False
    motivated_seller:      bool  = False
    total_distress_score:  float = 0.0
    signal_summary:        list[str] = field(default_factory=list)

    def grade(self) -> str:
        if self.total_distress_score >= 0.70: return "HIGH"
        if self.total_distress_score >= 0.40: return "MEDIUM"
        return "LOW"


@dataclass
class LandDistressScore:
    property_id:           str
    dead_paper_signal:     bool  = False
    ghost_street_signal:   bool  = False
    plat_phase_gap:        bool  = False
    builder_adjacency:     bool  = False
    ownership_weakness:    bool  = False
    total_distress_score:  float = 0.0
    signal_summary:        list[str] = field(default_factory=list)

    def grade(self) -> str:
        if self.total_distress_score >= 0.70: return "HIGH"
        if self.total_distress_score >= 0.40: return "MEDIUM"
        return "LOW"


# ─── Scoring Functions ────────────────────────────────────────────────────────

def score_sfr_distress(lead: PropertyLead) -> SFRDistressScore:
    """
    Stage 7 (SFR): Score distress and motivation signals.
    Inputs: DOM, price drops, keywords, bad photos flag, vacancy/probate signals.
    """
    desc = (lead.description or "").lower()
    signals = []

    dom_s   = _dom_score(lead.dom)
    drop_s  = _price_drop_score(lead.price_drops)
    kw_s    = _keyword_score(lead.description or "", _ALL_SFR_KEYWORD_SETS)
    photo_s = 0.30 if lead.bad_photos_flag else 0.0

    vacancy    = any(kw in desc for kw in VACANCY_KEYWORDS)
    inherited  = any(kw in desc for kw in INHERITED_KEYWORDS)
    probate    = any(kw in desc for kw in PROBATE_KEYWORDS)
    estate     = any(kw in desc for kw in ESTATE_KEYWORDS)
    financial  = any(kw in desc for kw in FINANCIAL_DISTRESS_KEYWORDS)
    motivated  = any(kw in desc for kw in MOTIVATED_SELLER_KEYWORDS)

    if dom_s > 0:      signals.append(f"DOM {lead.dom}d (+{dom_s:.0%})")
    if drop_s > 0:     signals.append(f"{lead.price_drops} price drop(s) (+{drop_s:.0%})")
    if kw_s > 0:       signals.append(f"distress keywords (+{kw_s:.0%})")
    if photo_s > 0:    signals.append("bad photos flagged (+0.30)")
    if vacancy:        signals.append("VACANT")
    if inherited:      signals.append("INHERITED")
    if probate:        signals.append("PROBATE")
    if estate:         signals.append("ESTATE")
    if financial:      signals.append("FINANCIAL DISTRESS")
    if motivated:      signals.append("MOTIVATED SELLER LANGUAGE")

    # Weighted average of scored components; boolean signals add flat bonus
    boolean_bonus = sum([vacancy, inherited, probate, estate, financial, motivated]) * 0.10
    raw = (dom_s * 0.30) + (drop_s * 0.25) + (kw_s * 0.25) + (photo_s * 0.20) + boolean_bonus
    total = min(raw, 1.0)

    return SFRDistressScore(
        property_id          = lead.property_id,
        dom_score            = dom_s,
        price_drop_score     = drop_s,
        keyword_score        = kw_s,
        bad_photos_score     = photo_s,
        vacancy_signal       = vacancy,
        inherited_signal     = inherited,
        probate_signal       = probate,
        estate_signal        = estate,
        financial_distress   = financial,
        motivated_seller     = motivated,
        total_distress_score = round(total, 3),
        signal_summary       = signals,
    )


def score_land_distress(lead: PropertyLead) -> LandDistressScore:
    """
    Stage 7 (Land): Score dead paper and subdivision decay signals.
    """
    desc    = (lead.description or "").lower()
    kws     = set(lead.keywords or [])
    signals = []

    dead_paper   = bool(kws & DEAD_PAPER_KEYWORDS) or any(kw in desc for kw in DEAD_PAPER_KEYWORDS)
    ghost_street = any(kw in desc for kw in GHOST_STREET_KEYWORDS)
    plat_gap     = any(kw in desc for kw in ("plat", "phase", "never developed", "dormant"))
    builder_adj  = any(kw in desc for kw in ("adjacent to builder", "next to subdivision", "bordering new homes"))
    own_weak     = any(kw in desc for kw in OWNERSHIP_WEAKNESS_KEYWORDS)

    if dead_paper:   signals.append("DEAD PAPER signal")
    if ghost_street: signals.append("GHOST STREET signal")
    if plat_gap:     signals.append("PLAT/PHASE GAP")
    if builder_adj:  signals.append("BUILDER ADJACENCY")
    if own_weak:     signals.append("OWNERSHIP WEAKNESS")

    # Each land signal = 0.20, capped at 1.0
    signal_count = sum([dead_paper, ghost_street, plat_gap, builder_adj, own_weak])
    total        = min(signal_count * 0.20, 1.0)

    return LandDistressScore(
        property_id          = lead.property_id,
        dead_paper_signal    = dead_paper,
        ghost_street_signal  = ghost_street,
        plat_phase_gap       = plat_gap,
        builder_adjacency    = builder_adj,
        ownership_weakness   = own_weak,
        total_distress_score = round(total, 3),
        signal_summary       = signals,
    )


def score_distress(lead: PropertyLead) -> SFRDistressScore | LandDistressScore:
    """Dispatch to correct scorer based on lead type."""
    if lead.is_land():
        return score_land_distress(lead)
    return score_sfr_distress(lead)
