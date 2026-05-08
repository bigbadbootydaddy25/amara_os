"""
Matching engine: scores every (parcel, buyer) combination and returns
ranked ParcelMatch lists.

Buyer matching  — all non-quarantined profiles (investors + builders)
Builder matching — verified builders only, restricted to vacant/infill parcels
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from models import LoadedBuyerProfile, Parcel, ParcelMatch, ParcelOpportunity
from match_signals import (
    compute_match_score,
    detect_match_signals,
    detect_nearby_builder_activity,
    _is_vacant,
)

# Minimum score to surface a match
MIN_BUYER_SCORE = 20
MIN_BUILDER_SCORE = 25

# How many matches to keep per parcel
TOP_N = 5


# ---------------------------------------------------------------------------
# Core match computation
# ---------------------------------------------------------------------------

def _match_parcel_to_profile(
    parcel: Parcel,
    profile: LoadedBuyerProfile,
    all_profiles: List[LoadedBuyerProfile],
    match_type: str,
) -> ParcelMatch:
    signals = detect_match_signals(parcel, profile, all_profiles)
    score = compute_match_score(signals)
    return ParcelMatch(
        parcel_id=parcel.parcel_id,
        buyer_name=profile.owner_name,
        match_score=score,
        match_type=match_type,
        signals=signals,
    )


def _classify_match_type(profile: LoadedBuyerProfile) -> str:
    if profile.is_verified_builder:
        return "BUILDER"
    if profile.is_possible_cash_buyer:
        return "CASH_BUYER"
    return "INVESTOR"


# ---------------------------------------------------------------------------
# Buyer matching (investors / cash buyers)
# ---------------------------------------------------------------------------

def match_buyers(
    parcel: Parcel,
    profiles: List[LoadedBuyerProfile],
) -> List[ParcelMatch]:
    """
    Score parcel against all non-quarantined investor/cash-buyer profiles.
    Returns top-N by score, filtered to >= MIN_BUYER_SCORE.
    """
    eligible = [
        p for p in profiles
        if not p.is_quarantined and p.is_possible_cash_buyer
    ]
    matches: List[ParcelMatch] = []
    for profile in eligible:
        m = _match_parcel_to_profile(
            parcel, profile, profiles, _classify_match_type(profile)
        )
        if m.match_score >= MIN_BUYER_SCORE:
            matches.append(m)

    return sorted(matches, key=lambda m: m.match_score, reverse=True)[:TOP_N]


# ---------------------------------------------------------------------------
# Builder matching (verified builders, infill/vacant focus)
# ---------------------------------------------------------------------------

def match_builders(
    parcel: Parcel,
    profiles: List[LoadedBuyerProfile],
) -> List[ParcelMatch]:
    """
    Score parcel against verified builder profiles.
    Considers all parcels but weights vacant/infill heavily.
    Returns top-N by score, filtered to >= MIN_BUILDER_SCORE.
    """
    builders = [
        p for p in profiles
        if not p.is_quarantined and p.is_verified_builder
    ]

    # Inject nearby-builder-activity signal into each builder match
    nearby_sigs = detect_nearby_builder_activity(parcel, profiles)

    matches: List[ParcelMatch] = []
    for profile in builders:
        m = _match_parcel_to_profile(parcel, profile, profiles, "BUILDER")
        # Attach parcel-level nearby activity signals (avoid duplicate types)
        existing_types = {s.signal_type for s in m.signals}
        for sig in nearby_sigs:
            if sig.signal_type not in existing_types:
                m.signals.append(sig)
                existing_types.add(sig.signal_type)
        # Recompute score after adding nearby signals
        from match_signals import compute_match_score as _cs
        m = ParcelMatch(
            parcel_id=m.parcel_id,
            buyer_name=m.buyer_name,
            match_score=_cs(m.signals),
            match_type=m.match_type,
            signals=m.signals,
        )
        if m.match_score >= MIN_BUILDER_SCORE:
            matches.append(m)

    return sorted(matches, key=lambda m: m.match_score, reverse=True)[:TOP_N]


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def generate_match_summary(match: ParcelMatch, parcel: Parcel) -> str:
    sig_types = list({s.signal_type for s in match.signals})
    parts = [
        f"{match.match_type} match score {match.match_score}/100 for "
        f"'{match.buyer_name}'.",
        f"Parcel {parcel.parcel_id} at {parcel.address or 'N/A'}.",
        f"Active signals: {', '.join(sig_types)}." if sig_types else "",
    ]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Full opportunity builder
# ---------------------------------------------------------------------------

def build_parcel_opportunities(
    parcels: List[Parcel],
    profiles: List[LoadedBuyerProfile],
) -> List[ParcelOpportunity]:
    """
    Runs both buyer and builder matching for every parcel.
    Populates ParcelOpportunity objects (without disposition — that's added
    later by disposition.py).
    """
    opportunities: List[ParcelOpportunity] = []
    for parcel in parcels:
        buyer_matches = match_buyers(parcel, profiles)
        builder_matches = match_builders(parcel, profiles)

        # Attach summaries
        for m in buyer_matches + builder_matches:
            m.summary = generate_match_summary(m, parcel)

        opp = ParcelOpportunity(
            parcel=parcel,
            top_buyer_matches=buyer_matches,
            top_builder_matches=builder_matches,
        )
        opportunities.append(opp)

    return opportunities
