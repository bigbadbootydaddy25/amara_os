"""
PropVision analysis pipeline: ARV → Rehab → MAO → ROI → Buyer Match → Tier.

RULES (from CLAUDE.md — never override):
- MAO = (ARV × 0.75) - rehab - $10,000
- Minimum assignment fee: $10,000
- No buyer = no deal (buyer-first enforced)
- DO NOT use 70% ARV as the only filter — use buyer-matched MAO
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from workers.remote.normalizer import NormalizedListing
from workers.remote.markets import Market

logger = logging.getLogger(__name__)

# ─── Rehab rates ($/sqft) ────────────────────────────────────────────────────
REHAB_RATES = {"light": 20, "medium": 35, "heavy": 50}
REHAB_DEFAULT_SQFT = 1_200   # fallback when sqft missing
DEFAULT_CONDITION = "medium"

# ─── ARV: sqft-based (primary) — reflects renovated comp value, not distressed ask ──
# $/sqft by market tier (post-renovation retail value)
ARV_PER_SQFT_BY_STATE: dict[str, dict[str, int]] = {
    "CA": {"light": 200, "medium": 185, "heavy": 165},
    "NV": {"light": 145, "medium": 135, "heavy": 118},
    "AZ": {"light": 135, "medium": 125, "heavy": 110},
    "NM": {"light": 100, "medium": 90,  "heavy": 78},
    "TX": {"light": 130, "medium": 120, "heavy": 105},
    "MI": {"light": 70,  "medium": 60,  "heavy": 50},
    "IN": {"light": 110, "medium": 100, "heavy": 88},
    "OH": {"light": 105, "medium": 95,  "heavy": 82},
    "KY": {"light": 105, "medium": 95,  "heavy": 82},
    "NC": {"light": 125, "medium": 115, "heavy": 100},
    "FL": {"light": 145, "medium": 135, "heavy": 118},
    "AR": {"light": 95,  "medium": 85,  "heavy": 73},
    "LA": {"light": 95,  "medium": 85,  "heavy": 73},
    "VA": {"light": 160, "medium": 148, "heavy": 130},
    "NH": {"light": 180, "medium": 165, "heavy": 145},
    "TN": {"light": 120, "medium": 110, "heavy": 96},
    "DEFAULT": {"light": 115, "medium": 105, "heavy": 90},
}
# Fallback multiplier when sqft is missing (applied to asking price — less accurate)
ARV_FALLBACK_MULTIPLIERS = {"light": 1.50, "medium": 1.65, "heavy": 1.80}

# ─── Buyer percent of ARV ─────────────────────────────────────────────────────
BUYER_PCT = 0.75

# ─── Assignment fee ───────────────────────────────────────────────────────────
MIN_FEE = 10_000
TARGET_FEE = 15_000

# ─── Tier thresholds ──────────────────────────────────────────────────────────
TIER1_SPREAD = 25_000
TIER2_SPREAD = 10_000


def _infer_condition(keywords: list[str]) -> str:
    heavy_signals = {"fire damage", "foundation", "structural", "gutted", "foreclosure",
                     "pre-foreclosure", "preforeclosure", "probate", "inherited"}
    light_signals = {"light", "updated kitchen", "fresh paint", "move-in"}
    kw_set = set(kw.lower() for kw in keywords)
    if kw_set & heavy_signals:
        return "heavy"
    if kw_set & light_signals:
        return "light"
    return "medium"


def _estimate_rehab(sqft: int, condition: str) -> int:
    effective_sqft = sqft if sqft > 0 else REHAB_DEFAULT_SQFT
    base = effective_sqft * REHAB_RATES[condition]
    # Round to nearest $5k
    return round(base / 5_000) * 5_000


def _estimate_arv(listing: NormalizedListing, condition: str, state: str = "DEFAULT") -> int:
    rates = ARV_PER_SQFT_BY_STATE.get(state, ARV_PER_SQFT_BY_STATE["DEFAULT"])
    if listing.sqft > 0:
        arv = listing.sqft * rates[condition]
    else:
        # Fallback: price × multiplier when sqft unknown
        arv = int(listing.price * ARV_FALLBACK_MULTIPLIERS[condition])
    return round(arv / 1_000) * 1_000


def _calc_roi(arv: int, price: int, rehab: int) -> float:
    total_in = price + rehab
    if total_in <= 0:
        return 0.0
    return round((arv - total_in) / total_in, 3)


def _determine_strategy(roi: float, arv: int, mao: int, price: int) -> str:
    if price > mao:
        return "reject"
    if roi >= 0.25:
        return "flip"
    if roi >= 0.15:
        return "wholesale"
    if roi >= 0.08:
        return "brrrr"
    return "reject"


@dataclass
class BuyBox:
    buyer_id: str
    buyer_name: str
    zips: list[str]
    price_min: int
    price_max: int
    strategy: str
    activity_level: str = "unknown"


@dataclass
class DealResult:
    listing_id: str
    address: str
    zip_code: str
    price: int
    arv: int
    rehab: int
    mao: int
    assignment_fee: int
    roi: float
    condition: str
    strategy: str
    tier: str                          # "Tier 1" | "Tier 2" | "Tier 3"
    matched_buyers: list[str]
    keywords: list[str]
    url: str
    market_name: str = ""
    disqualified: bool = False
    disqualify_reason: str = ""


def analyze(
    listing: NormalizedListing,
    market: Market,
    buyers: list[BuyBox],
) -> DealResult:
    """
    Run full PropVision analysis on a single listing.
    Buyer-first: disqualifies if no buyer match in ZIP.
    """
    condition = _infer_condition(listing.keywords)
    rehab = _estimate_rehab(listing.sqft, condition)
    arv = _estimate_arv(listing, condition, market.state)
    mao = int((arv * BUYER_PCT) - rehab - MIN_FEE)
    assignment_fee = max(0, int((arv * BUYER_PCT) - rehab - listing.price))
    roi = _calc_roi(arv, listing.price, rehab)
    strategy = _determine_strategy(roi, arv, mao, listing.price)

    # ─── Buyer-first enforcement ───────────────────────────────────
    matched = _match_buyers(listing, buyers)
    if not matched:
        return DealResult(
            listing_id=listing.listing_id,
            address=listing.address,
            zip_code=listing.zip_code,
            price=listing.price,
            arv=arv,
            rehab=rehab,
            mao=mao,
            assignment_fee=assignment_fee,
            roi=roi,
            condition=condition,
            strategy="reject",
            tier="Tier 3",
            matched_buyers=[],
            keywords=listing.keywords,
            url=listing.url,
            market_name=market.name,
            disqualified=True,
            disqualify_reason="no_buyer_match",
        )

    # ─── Reject if strategy is reject ─────────────────────────────
    if strategy == "reject" or assignment_fee < MIN_FEE:
        return DealResult(
            listing_id=listing.listing_id,
            address=listing.address,
            zip_code=listing.zip_code,
            price=listing.price,
            arv=arv,
            rehab=rehab,
            mao=mao,
            assignment_fee=assignment_fee,
            roi=roi,
            condition=condition,
            strategy=strategy,
            tier="Tier 3",
            matched_buyers=matched,
            keywords=listing.keywords,
            url=listing.url,
            market_name=market.name,
            disqualified=True,
            disqualify_reason="below_minimum_fee" if assignment_fee < MIN_FEE else "no_go",
        )

    # ─── Tier classification ──────────────────────────────────────
    if assignment_fee >= TIER1_SPREAD and len(matched) >= 1:
        tier = "Tier 1"
    elif assignment_fee >= TIER2_SPREAD:
        tier = "Tier 2"
    else:
        tier = "Tier 3"

    return DealResult(
        listing_id=listing.listing_id,
        address=listing.address,
        zip_code=listing.zip_code,
        price=listing.price,
        arv=arv,
        rehab=rehab,
        mao=mao,
        assignment_fee=assignment_fee,
        roi=roi,
        condition=condition,
        strategy=strategy,
        tier=tier,
        matched_buyers=matched,
        keywords=listing.keywords,
        url=listing.url,
        market_name=market.name,
    )


def _match_buyers(listing: NormalizedListing, buyers: list[BuyBox]) -> list[str]:
    matched = []
    for b in buyers:
        if listing.zip_code not in b.zips:
            continue
        if not (b.price_min <= listing.price <= b.price_max * 1.10):
            continue
        matched.append(b.buyer_name)
    return matched


def analyze_batch(
    listings: list[NormalizedListing],
    market: Market,
    buyers: list[BuyBox],
) -> list[DealResult]:
    results = []
    for listing in listings:
        try:
            result = analyze(listing, market, buyers)
            results.append(result)
        except Exception as e:
            logger.warning("Analysis failed for %s: %s", listing.address, e)
    return results


def filter_actionable(results: list[DealResult]) -> list[DealResult]:
    """Return only Tier 1 and Tier 2 deals, sorted by assignment fee desc."""
    actionable = [r for r in results if r.tier in ("Tier 1", "Tier 2") and not r.disqualified]
    actionable.sort(key=lambda x: (x.tier == "Tier 1", x.assignment_fee), reverse=True)
    return actionable


def to_output_record(r: DealResult) -> dict:
    return {
        "address": r.address,
        "price": r.price,
        "arv": r.arv,
        "rehab": r.rehab,
        "mao": r.mao,
        "assignment_fee": r.assignment_fee,
        "roi": r.roi,
        "tier": r.tier,
        "strategy": r.strategy,
        "matched_buyers": r.matched_buyers,
        "keywords": r.keywords,
        "url": r.url,
        "market": r.market_name,
        "zip_code": r.zip_code,
        "condition": r.condition,
    }
