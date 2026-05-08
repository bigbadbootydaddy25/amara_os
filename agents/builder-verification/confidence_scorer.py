"""
Confidence scoring engine.

Builder score and investor score are computed independently from the signals
attached to a BuyerProfile. Scores are capped at 100.

Signal weights are intentionally kept in signals.py (each DetectedSignal
carries its own weight). This module sums them by category and applies
profile-level adjustments.
"""
from __future__ import annotations

from typing import Dict

from models import BuyerProfile

# ---------------------------------------------------------------------------
# Signal → score category mapping
# ---------------------------------------------------------------------------

# Signals that contribute to the BUILDER score
_BUILDER_SIGNAL_WEIGHTS: Dict[str, int] = {
    "LLC_COMPANY": 15,
    "BUILDER_KEYWORD": 20,
    "VACANT_LAND": 15,
    "PERMIT_ACTIVITY": 25,
    "MULTIPLE_NEARBY_PARCELS": 20,
    "VACANT_LAND_CONCENTRATION": 20,
    "INFILL_ACTIVITY": 25,
    "REPEAT_ACQUISITIONS": 10,
    "RECENT_PURCHASE_CLUSTERING": 10,
}

# Signals that contribute to the INVESTOR / cash-buyer score
_INVESTOR_SIGNAL_WEIGHTS: Dict[str, int] = {
    "LLC_COMPANY": 20,
    "INVESTOR_KEYWORD": 15,
    "MAILING_MISMATCH": 20,
    "REPEAT_ACQUISITIONS": 25,
    "MULTIPLE_NEARBY_PARCELS": 15,
    "RECENT_PURCHASE_CLUSTERING": 15,
    "ROUND_SALE_PRICE": 5,
    "VACANT_LAND": 5,
    "VACANT_LAND_CONCENTRATION": 10,
}

_MAX_SCORE = 100


def compute_scores(profile: BuyerProfile) -> None:
    """
    Populates profile.builder_score and profile.investor_score in-place.

    Uses the canonical weights defined above (signal's own .weight field is
    used as a tiebreaker / evidence record, but the category weights here
    govern scoring so each signal type contributes only once per profile).
    """
    seen_builder: set = set()
    seen_investor: set = set()
    builder_total = 0
    investor_total = 0

    for sig in profile.signals:
        stype = sig.signal_type

        if stype in _BUILDER_SIGNAL_WEIGHTS and stype not in seen_builder:
            builder_total += _BUILDER_SIGNAL_WEIGHTS[stype]
            seen_builder.add(stype)

        if stype in _INVESTOR_SIGNAL_WEIGHTS and stype not in seen_investor:
            investor_total += _INVESTOR_SIGNAL_WEIGHTS[stype]
            seen_investor.add(stype)

    # Bonus: more than 1 parcel type of each boosts confidence
    if profile.parcel_count >= 5:
        builder_total += 5
        investor_total += 5
    elif profile.parcel_count >= 3:
        builder_total += 3
        investor_total += 3

    profile.builder_score = min(builder_total, _MAX_SCORE)
    profile.investor_score = min(investor_total, _MAX_SCORE)


def score_all_profiles(profiles: Dict[str, BuyerProfile]) -> None:
    """Scores every profile in the dict in-place."""
    for profile in profiles.values():
        compute_scores(profile)
