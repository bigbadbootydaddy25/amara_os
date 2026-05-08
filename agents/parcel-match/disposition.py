"""
Disposition path identification.

Analyzes parcel attributes and match results to surface the most likely
exit strategies for each opportunity. Each path carries a confidence score
and a list of evidence strings.

Paths (mutually non-exclusive — a parcel may support multiple):
  INFILL_BUILD          — vacant lot + active builder nearby
  WHOLESALE_TO_INVESTOR — distressed or below-market + cash buyer available
  REHAB_FLIP            — distressed + ARV spread + investor match
  HOLD_FOR_DEVELOPMENT  — large acreage, no immediate buyer fit
  RETAIL_LISTING        — improved residential, no strong entity match
"""
from __future__ import annotations

from typing import List

from models import DispositionPath, LoadedBuyerProfile, Parcel, ParcelMatch, ParcelOpportunity

_VACANT_LAND_USES = {
    "VACANT", "UNIMPROVED", "RAW LAND", "LAND", "LOT",
    "UNDEVELOPED", "BARE LAND", "EMPTY LOT", "INFILL",
}

_MIN_ARV_SPREAD = 1.20   # ARV must be ≥ 120% of price to flag REHAB_FLIP
_LARGE_ACREAGE = 1.0     # acres threshold for HOLD_FOR_DEVELOPMENT
_WHOLESALE_DOM = 90      # days-on-market threshold suggesting motivated seller


# ---------------------------------------------------------------------------
# Individual path detectors
# ---------------------------------------------------------------------------

def _infill_build(
    parcel: Parcel,
    builder_matches: List[ParcelMatch],
) -> DispositionPath | None:
    if not _is_vacant(parcel):
        return None
    confidence = 0
    evidence: List[str] = []
    recommended: List[str] = []

    evidence.append(f"Parcel is vacant/unimproved (land use: {parcel.land_use or 'N/A'})")
    confidence += 30

    if builder_matches:
        best = builder_matches[0]
        confidence += min(best.match_score // 2, 40)
        evidence.append(
            f"Top builder match: '{best.buyer_name}' "
            f"(score {best.match_score}/100)"
        )
        recommended = [m.buyer_name for m in builder_matches[:3]]

    if parcel.permit_count > 0:
        confidence += 10
        evidence.append(f"Existing permit activity ({parcel.permit_count} permit(s))")

    if parcel.acres > 0 and parcel.acres <= 2.0:
        confidence += 10
        evidence.append(
            f"Parcel size {parcel.acres:.2f} acres — typical infill lot"
        )

    return DispositionPath(
        path_type="INFILL_BUILD",
        confidence=min(confidence, 100),
        evidence=evidence,
        recommended_buyers=recommended,
    )


def _wholesale_to_investor(
    parcel: Parcel,
    buyer_matches: List[ParcelMatch],
) -> DispositionPath | None:
    confidence = 0
    evidence: List[str] = []
    recommended: List[str] = []

    if parcel.distressed:
        confidence += 25
        evidence.append("Parcel is flagged as distressed")

    if parcel.days_on_market >= _WHOLESALE_DOM:
        confidence += 15
        evidence.append(
            f"Parcel has been on market {parcel.days_on_market} days "
            f"(≥{_WHOLESALE_DOM} — motivated seller indicator)"
        )

    cash_buyers = [m for m in buyer_matches if m.match_type == "CASH_BUYER"]
    if cash_buyers:
        best = cash_buyers[0]
        confidence += min(best.match_score // 3, 30)
        evidence.append(
            f"Cash buyer available: '{best.buyer_name}' "
            f"(investor score {best.match_score}/100)"
        )
        recommended = [m.buyer_name for m in cash_buyers[:3]]

    if parcel.effective_price > 0 and parcel.arv > parcel.effective_price:
        spread_pct = (parcel.arv / parcel.effective_price - 1) * 100
        confidence += 10
        evidence.append(
            f"ARV ${parcel.arv:,.0f} vs price ${parcel.effective_price:,.0f} "
            f"({spread_pct:.0f}% spread)"
        )

    if confidence < 15:
        return None
    return DispositionPath(
        path_type="WHOLESALE_TO_INVESTOR",
        confidence=min(confidence, 100),
        evidence=evidence,
        recommended_buyers=recommended,
    )


def _rehab_flip(
    parcel: Parcel,
    buyer_matches: List[ParcelMatch],
) -> DispositionPath | None:
    if not parcel.distressed:
        return None
    price = parcel.effective_price
    if price <= 0 or parcel.arv <= 0:
        return None
    if parcel.arv < price * _MIN_ARV_SPREAD:
        return None

    spread_pct = (parcel.arv / price - 1) * 100
    confidence = 30
    evidence = [
        f"Distressed parcel with ARV spread: ${parcel.arv:,.0f} / "
        f"${price:,.0f} = {spread_pct:.0f}% upside"
    ]
    recommended: List[str] = []

    investor_matches = [m for m in buyer_matches if m.match_type in {"CASH_BUYER", "INVESTOR"}]
    if investor_matches:
        best = investor_matches[0]
        confidence += min(best.match_score // 2, 40)
        evidence.append(
            f"Investor match: '{best.buyer_name}' (score {best.match_score}/100)"
        )
        recommended = [m.buyer_name for m in investor_matches[:3]]

    if parcel.days_on_market >= _WHOLESALE_DOM:
        confidence += 10
        evidence.append(f"{parcel.days_on_market} days on market")

    return DispositionPath(
        path_type="REHAB_FLIP",
        confidence=min(confidence, 100),
        evidence=evidence,
        recommended_buyers=recommended,
    )


def _hold_for_development(
    parcel: Parcel,
    builder_matches: List[ParcelMatch],
    buyer_matches: List[ParcelMatch],
) -> DispositionPath | None:
    if not _is_vacant(parcel):
        return None
    if parcel.acres < _LARGE_ACREAGE:
        return None

    confidence = 25
    evidence = [
        f"Large vacant parcel: {parcel.acres:.2f} acres "
        f"(≥{_LARGE_ACREAGE} acre threshold)"
    ]
    recommended: List[str] = []

    if not builder_matches and not buyer_matches:
        confidence += 15
        evidence.append("No immediate buyer match — hold candidate")
    else:
        confidence += 10
        evidence.append("Some buyer interest present but large-scale development may be optimal")
        recommended = [m.buyer_name for m in (builder_matches + buyer_matches)[:2]]

    if parcel.zoning:
        evidence.append(f"Zoning: {parcel.zoning}")

    return DispositionPath(
        path_type="HOLD_FOR_DEVELOPMENT",
        confidence=min(confidence, 100),
        evidence=evidence,
        recommended_buyers=recommended,
    )


def _retail_listing(
    parcel: Parcel,
    buyer_matches: List[ParcelMatch],
    builder_matches: List[ParcelMatch],
) -> DispositionPath | None:
    if _is_vacant(parcel):
        return None  # vacant parcels have better-targeted paths above
    if parcel.distressed:
        return None  # distressed goes to rehab/wholesale

    confidence = 20
    evidence = [
        f"Improved {parcel.land_use or 'residential'} parcel "
        f"at {parcel.address or parcel.parcel_id}"
    ]
    recommended: List[str] = []

    if not buyer_matches and not builder_matches:
        confidence += 20
        evidence.append("No strong entity-buyer match — retail MLS listing recommended")
    else:
        confidence += 10
        evidence.append(
            "Entity buyers present but standard retail path also viable"
        )
        recommended = [m.buyer_name for m in buyer_matches[:2]]

    if parcel.days_on_market < 30:
        confidence += 10
        evidence.append(f"Recently listed ({parcel.days_on_market} days on market)")

    return DispositionPath(
        path_type="RETAIL_LISTING",
        confidence=min(confidence, 100),
        evidence=evidence,
        recommended_buyers=recommended,
    )


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def identify_disposition_paths(opportunity: ParcelOpportunity) -> List[DispositionPath]:
    parcel = opportunity.parcel
    buyer_matches = opportunity.top_buyer_matches
    builder_matches = opportunity.top_builder_matches

    candidates = [
        _infill_build(parcel, builder_matches),
        _wholesale_to_investor(parcel, buyer_matches),
        _rehab_flip(parcel, buyer_matches),
        _hold_for_development(parcel, builder_matches, buyer_matches),
        _retail_listing(parcel, buyer_matches, builder_matches),
    ]
    paths = [p for p in candidates if p is not None]
    # Sort by confidence descending
    return sorted(paths, key=lambda p: p.confidence, reverse=True)


def enrich_opportunities(opportunities: List[ParcelOpportunity]) -> None:
    """Attaches disposition paths and opportunity summary in-place."""
    for opp in opportunities:
        opp.disposition_paths = identify_disposition_paths(opp)
        opp.summary = _opportunity_summary(opp)


def _opportunity_summary(opp: ParcelOpportunity) -> str:
    parcel = opp.parcel
    parts: List[str] = [
        f"Parcel {parcel.parcel_id} ({parcel.land_use or 'N/A'}) "
        f"in ZIP {parcel.zip_code or 'N/A'}."
    ]
    if parcel.effective_price > 0:
        parts.append(f"Price: ${parcel.effective_price:,.0f}.")
    if opp.primary_disposition:
        pd = opp.primary_disposition
        parts.append(
            f"Primary disposition: {pd.path_type} "
            f"(confidence {pd.confidence}/100)."
        )
    all_matches = opp.top_buyer_matches + opp.top_builder_matches
    if all_matches:
        best = max(all_matches, key=lambda m: m.match_score)
        parts.append(
            f"Best match: '{best.buyer_name}' "
            f"({best.match_type}, score {best.match_score}/100)."
        )
    return " ".join(parts)


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
