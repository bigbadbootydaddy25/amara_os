"""
Match signal detectors for parcel↔buyer scoring.

Each detector receives a Parcel and a LoadedBuyerProfile and returns zero or
more MatchSignal objects. Weights here are canonical — the scorer sums them
per signal type (no double-counting).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

from models import LoadedBuyerProfile, MatchSignal, Parcel

# ---------------------------------------------------------------------------
# Signal type registry (used as keys in scorer weight maps)
# ---------------------------------------------------------------------------

# Geographic
SIG_ZIP_MATCH = "ZIP_MATCH"                       # parcel ZIP in buyer ZIP list

# Price
SIG_PRICE_FIT = "PRICE_FIT"                       # price within ±40% of buyer avg
SIG_PRICE_BELOW_AVG = "PRICE_BELOW_AVG"           # price below buyer avg (deal)

# Land use / property type
SIG_LAND_USE_ALIGNMENT = "LAND_USE_ALIGNMENT"     # land use suits buyer type
SIG_INFILL_OPPORTUNITY = "INFILL_OPPORTUNITY"     # vacant lot + infill-capable buyer

# Activity signals
SIG_RECENT_AREA_ACTIVITY = "RECENT_AREA_ACTIVITY" # buyer bought in this ZIP ≤365 days
SIG_NEARBY_BUILDER = "NEARBY_BUILDER_ACTIVITY"    # verified builder active in ZIP

# Buyer characteristics
SIG_ENTITY_TYPE = "ENTITY_TYPE_MATCH"             # LLC buyer for investment parcel
SIG_HIGH_BUILDER = "HIGH_BUILDER_SCORE"           # buyer builder_score ≥ 60
SIG_HIGH_INVESTOR = "HIGH_INVESTOR_SCORE"         # buyer investor_score ≥ 60
SIG_PERMIT_ALIGNMENT = "PERMIT_ALIGNMENT"         # builder with permits ↔ vacant lot

# Parcel characteristics
SIG_DISTRESSED_MATCH = "DISTRESSED_MATCH"         # distressed parcel + investor

# Canonical weights (scorer uses these, not per-signal weight fields)
BUYER_SIGNAL_WEIGHTS = {
    SIG_ZIP_MATCH: 25,
    SIG_PRICE_FIT: 20,
    SIG_PRICE_BELOW_AVG: 10,
    SIG_LAND_USE_ALIGNMENT: 20,
    SIG_INFILL_OPPORTUNITY: 20,
    SIG_RECENT_AREA_ACTIVITY: 15,
    SIG_NEARBY_BUILDER: 20,
    SIG_ENTITY_TYPE: 15,
    SIG_HIGH_BUILDER: 15,
    SIG_HIGH_INVESTOR: 15,
    SIG_PERMIT_ALIGNMENT: 15,
    SIG_DISTRESSED_MATCH: 10,
}

_VACANT_LAND_USES = {
    "VACANT", "UNIMPROVED", "RAW LAND", "LAND", "LOT",
    "UNDEVELOPED", "BARE LAND", "EMPTY LOT", "INFILL",
}

_BUILDER_SIGNAL_TYPES = {
    "BUILDER_KEYWORD", "INFILL_ACTIVITY", "PERMIT_ACTIVITY",
    "VACANT_LAND_CONCENTRATION",
}


# ---------------------------------------------------------------------------
# Record-level detectors (parcel × profile → signals)
# ---------------------------------------------------------------------------

def detect_zip_match(parcel: Parcel, profile: LoadedBuyerProfile) -> List[MatchSignal]:
    if parcel.zip_code and parcel.zip_code in profile.zip_codes:
        return [MatchSignal(
            signal_type=SIG_ZIP_MATCH,
            value=parcel.zip_code,
            weight=BUYER_SIGNAL_WEIGHTS[SIG_ZIP_MATCH],
            evidence=(
                f"Parcel ZIP {parcel.zip_code} matches buyer's active ZIP codes: "
                f"{', '.join(profile.zip_codes)}"
            ),
        )]
    return []


def detect_price_fit(parcel: Parcel, profile: LoadedBuyerProfile) -> List[MatchSignal]:
    price = parcel.effective_price
    if price <= 0 or profile.avg_price <= 0:
        return []
    lo, hi = profile.price_range
    signals: List[MatchSignal] = []
    if lo <= price <= hi:
        signals.append(MatchSignal(
            signal_type=SIG_PRICE_FIT,
            value=f"${price:,.0f}",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_PRICE_FIT],
            evidence=(
                f"Parcel price ${price:,.0f} is within buyer's historical "
                f"range ${lo:,.0f}–${hi:,.0f} (avg ${profile.avg_price:,.0f})"
            ),
        ))
    if price < profile.avg_price:
        signals.append(MatchSignal(
            signal_type=SIG_PRICE_BELOW_AVG,
            value=f"${price:,.0f}",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_PRICE_BELOW_AVG],
            evidence=(
                f"Parcel price ${price:,.0f} is below buyer's average "
                f"acquisition of ${profile.avg_price:,.0f}"
            ),
        ))
    return signals


def detect_land_use_alignment(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    is_vac = _is_vacant(parcel)
    # Vacant → builders; residential/improved → investors
    if is_vac and profile.is_verified_builder:
        return [MatchSignal(
            signal_type=SIG_LAND_USE_ALIGNMENT,
            value=parcel.land_use or "VACANT",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_LAND_USE_ALIGNMENT],
            evidence=(
                f"Vacant/unimproved parcel aligns with verified builder profile "
                f"'{profile.owner_name}'"
            ),
        )]
    if not is_vac and profile.is_possible_cash_buyer:
        return [MatchSignal(
            signal_type=SIG_LAND_USE_ALIGNMENT,
            value=parcel.land_use or "IMPROVED",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_LAND_USE_ALIGNMENT],
            evidence=(
                f"Improved parcel aligns with cash-buyer/investor profile "
                f"'{profile.owner_name}'"
            ),
        )]
    return []


def detect_infill_opportunity(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    """Vacant parcel + buyer has infill/builder signals."""
    if not _is_vacant(parcel):
        return []
    has_infill = bool(
        _BUILDER_SIGNAL_TYPES & set(profile.signal_types)
        or profile.builder_score >= 40
    )
    if has_infill:
        return [MatchSignal(
            signal_type=SIG_INFILL_OPPORTUNITY,
            value=f"builder_score={profile.builder_score}",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_INFILL_OPPORTUNITY],
            evidence=(
                f"Vacant infill opportunity for '{profile.owner_name}' "
                f"(builder score {profile.builder_score}/100)"
            ),
        )]
    return []


def detect_recent_area_activity(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    """Buyer purchased in the same ZIP within the last 365 days."""
    if parcel.zip_code not in profile.zip_codes:
        return []
    cutoff = date.today() - timedelta(days=365)
    for ds in profile.acquisition_dates:
        d = _parse_date(ds)
        if d and d >= cutoff:
            return [MatchSignal(
                signal_type=SIG_RECENT_AREA_ACTIVITY,
                value=ds,
                weight=BUYER_SIGNAL_WEIGHTS[SIG_RECENT_AREA_ACTIVITY],
                evidence=(
                    f"'{profile.owner_name}' purchased in ZIP {parcel.zip_code} "
                    f"on {ds} (within last 365 days)"
                ),
            )]
    return []


def detect_nearby_builder_activity(
    parcel: Parcel,
    all_profiles: List[LoadedBuyerProfile],
) -> List[MatchSignal]:
    """Detects whether any verified builder has activity in the parcel's ZIP."""
    if not parcel.zip_code:
        return []
    active = [
        p for p in all_profiles
        if p.is_verified_builder
        and parcel.zip_code in p.zip_codes
        and not p.is_quarantined
    ]
    if active:
        names = ", ".join(p.owner_name for p in active[:3])
        return [MatchSignal(
            signal_type=SIG_NEARBY_BUILDER,
            value=parcel.zip_code,
            weight=BUYER_SIGNAL_WEIGHTS[SIG_NEARBY_BUILDER],
            evidence=(
                f"Active builder(s) in ZIP {parcel.zip_code}: {names}"
            ),
        )]
    return []


def detect_entity_type_match(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    """LLC/entity buyer matched to an investment/non-homestead parcel."""
    is_entity = "LLC_COMPANY" in profile.signal_types
    if not is_entity:
        return []
    # Investment parcel: vacant, commercial, or mailing mismatch implied
    if _is_vacant(parcel) or parcel.land_use in {"COMMERCIAL", "MULTI-FAMILY", "INDUSTRIAL"}:
        return [MatchSignal(
            signal_type=SIG_ENTITY_TYPE,
            value="LLC_ENTITY",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_ENTITY_TYPE],
            evidence=(
                f"LLC/entity buyer '{profile.owner_name}' matched to "
                f"investment-grade parcel ({parcel.land_use or 'VACANT'})"
            ),
        )]
    return []


def detect_high_score(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    signals: List[MatchSignal] = []
    if profile.builder_score >= 60 and _is_vacant(parcel):
        signals.append(MatchSignal(
            signal_type=SIG_HIGH_BUILDER,
            value=str(profile.builder_score),
            weight=BUYER_SIGNAL_WEIGHTS[SIG_HIGH_BUILDER],
            evidence=(
                f"High builder confidence score {profile.builder_score}/100 "
                f"for vacant parcel at {parcel.address or parcel.parcel_id}"
            ),
        ))
    if profile.investor_score >= 60 and not _is_vacant(parcel):
        signals.append(MatchSignal(
            signal_type=SIG_HIGH_INVESTOR,
            value=str(profile.investor_score),
            weight=BUYER_SIGNAL_WEIGHTS[SIG_HIGH_INVESTOR],
            evidence=(
                f"High investor confidence score {profile.investor_score}/100 "
                f"for improved parcel at {parcel.address or parcel.parcel_id}"
            ),
        ))
    return signals


def detect_permit_alignment(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    """Builder with permit history matched to vacant parcel."""
    if not _is_vacant(parcel):
        return []
    if "PERMIT_ACTIVITY" in profile.signal_types or "INFILL_ACTIVITY" in profile.signal_types:
        return [MatchSignal(
            signal_type=SIG_PERMIT_ALIGNMENT,
            value="PERMIT_HISTORY",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_PERMIT_ALIGNMENT],
            evidence=(
                f"Builder '{profile.owner_name}' has permit history — "
                f"aligned with vacant parcel {parcel.parcel_id}"
            ),
        )]
    return []


def detect_distressed_match(
    parcel: Parcel, profile: LoadedBuyerProfile
) -> List[MatchSignal]:
    if parcel.distressed and profile.is_possible_cash_buyer:
        return [MatchSignal(
            signal_type=SIG_DISTRESSED_MATCH,
            value="DISTRESSED",
            weight=BUYER_SIGNAL_WEIGHTS[SIG_DISTRESSED_MATCH],
            evidence=(
                f"Distressed parcel {parcel.parcel_id} matched to "
                f"cash buyer '{profile.owner_name}'"
            ),
        )]
    return []


# ---------------------------------------------------------------------------
# Aggregate: run all detectors for one parcel × one profile
# ---------------------------------------------------------------------------

def detect_match_signals(
    parcel: Parcel,
    profile: LoadedBuyerProfile,
    all_profiles: List[LoadedBuyerProfile],
) -> List[MatchSignal]:
    signals: List[MatchSignal] = []
    signals += detect_zip_match(parcel, profile)
    signals += detect_price_fit(parcel, profile)
    signals += detect_land_use_alignment(parcel, profile)
    signals += detect_infill_opportunity(parcel, profile)
    signals += detect_recent_area_activity(parcel, profile)
    signals += detect_entity_type_match(parcel, profile)
    signals += detect_high_score(parcel, profile)
    signals += detect_permit_alignment(parcel, profile)
    signals += detect_distressed_match(parcel, profile)
    # Nearby builder activity is parcel-level, not profile-level — added once
    return signals


# ---------------------------------------------------------------------------
# Score computation (sums canonical weights, no duplicate signal types)
# ---------------------------------------------------------------------------

def compute_match_score(signals: List[MatchSignal]) -> int:
    seen: set = set()
    total = 0
    for sig in signals:
        if sig.signal_type not in seen:
            total += BUYER_SIGNAL_WEIGHTS.get(sig.signal_type, sig.weight)
            seen.add(sig.signal_type)
    return min(total, 100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_vacant(parcel: Parcel) -> bool:
    if parcel.is_vacant:
        return True
    for lu in _VACANT_LAND_USES:
        if lu in parcel.land_use:
            return True
    return False


def _parse_date(ds: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(ds, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


from typing import Optional  # noqa: E402 (keep at bottom to avoid circular)
