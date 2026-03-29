"""
AMARA OS — Buyer Matcher
Matches deals to buyers based on buy box criteria.
Buyer-first: always match buyers before pursuing deals.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from system.config import (
    BUYER_STATUS_ACTIVE,
    VAULT_BUYERS,
    SFR_MIN_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
)


@dataclass
class BuyBox:
    """Represents a buyer's acquisition criteria."""
    buyer_id: str
    buyer_name: str
    asset_types: list[str] = field(default_factory=list)
    target_states: list[str] = field(default_factory=list)
    target_cities: list[str] = field(default_factory=list)
    target_zips: list[str] = field(default_factory=list)
    min_price: float = 0
    max_price: float = float("inf")
    max_repairs: float = float("inf")
    min_beds: int = 0
    min_baths: float = 0
    min_sqft: float = 0
    max_sqft: float = float("inf")
    min_year_built: int = 0
    condition: list[str] = field(default_factory=lambda: ["any"])
    status: str = BUYER_STATUS_ACTIVE

    def is_active(self) -> bool:
        return self.status == BUYER_STATUS_ACTIVE


@dataclass
class DealProfile:
    """Lightweight deal profile for matching."""
    deal_id: str
    asset_type: str
    address: str
    city: str
    state: str
    zip_code: str
    buyer_price: float
    repairs: float
    beds: int = 0
    baths: float = 0
    sqft: float = 0
    year_built: int = 0
    condition: str = "unknown"
    arv: float = 0


@dataclass
class MatchResult:
    buyer_id: str
    buyer_name: str
    deal_id: str
    score: int               # 0–100, higher = better match
    match_reasons: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)
    is_match: bool = False

    def summary(self) -> str:
        status = "MATCH" if self.is_match else "NO MATCH"
        lines = [
            f"[{status}] Buyer: {self.buyer_name} ({self.buyer_id}) | Score: {self.score}/100",
        ]
        if self.match_reasons:
            lines.append("  Reasons: " + ", ".join(self.match_reasons))
        if self.disqualifiers:
            lines.append("  Disqualifiers: " + ", ".join(self.disqualifiers))
        return "\n".join(lines)


def match_deal_to_buyers(deal: DealProfile, buyers: list[BuyBox]) -> list[MatchResult]:
    """
    Match a deal against a list of buyer buy boxes.
    Returns ranked list of MatchResults (best matches first).
    Buyer-first rule is enforced — only active buyers are matched.
    """
    results = []

    for buyer in buyers:
        if not buyer.is_active():
            continue

        score = 0
        reasons = []
        disqualifiers = []

        # Asset type match
        if buyer.asset_types and deal.asset_type not in buyer.asset_types:
            disqualifiers.append(f"asset type {deal.asset_type} not in buy box")
        else:
            score += 20
            reasons.append("asset type")

        # Geography match — ZIP (highest priority)
        if buyer.target_zips:
            if deal.zip_code in buyer.target_zips:
                score += 30
                reasons.append(f"ZIP {deal.zip_code}")
            elif buyer.target_cities and deal.city.lower() in [c.lower() for c in buyer.target_cities]:
                score += 20
                reasons.append(f"city {deal.city}")
            elif buyer.target_states and deal.state.upper() in [s.upper() for s in buyer.target_states]:
                score += 10
                reasons.append(f"state {deal.state}")
            else:
                disqualifiers.append(f"location {deal.city}, {deal.state} {deal.zip_code} not in buy box")
        elif buyer.target_cities:
            if deal.city.lower() in [c.lower() for c in buyer.target_cities]:
                score += 25
                reasons.append(f"city {deal.city}")
            elif buyer.target_states and deal.state.upper() in [s.upper() for s in buyer.target_states]:
                score += 10
                reasons.append(f"state {deal.state}")
            else:
                disqualifiers.append(f"city {deal.city} not in buy box")
        elif buyer.target_states:
            if deal.state.upper() in [s.upper() for s in buyer.target_states]:
                score += 15
                reasons.append(f"state {deal.state}")
            else:
                disqualifiers.append(f"state {deal.state} not in buy box")
        else:
            score += 10  # No geo filter = takes anything
            reasons.append("no geo restriction")

        # Price range match
        if deal.buyer_price < buyer.min_price:
            disqualifiers.append(f"price ${deal.buyer_price:,.0f} below min ${buyer.min_price:,.0f}")
        elif deal.buyer_price > buyer.max_price:
            disqualifiers.append(f"price ${deal.buyer_price:,.0f} above max ${buyer.max_price:,.0f}")
        else:
            score += 20
            reasons.append("price in range")

        # Repair tolerance
        if deal.repairs > buyer.max_repairs:
            disqualifiers.append(f"repairs ${deal.repairs:,.0f} exceed max ${buyer.max_repairs:,.0f}")
        else:
            score += 10
            reasons.append("repairs ok")

        # Physical criteria (beds, sqft)
        if deal.beds and deal.beds < buyer.min_beds:
            disqualifiers.append(f"{deal.beds} beds below min {buyer.min_beds}")
        else:
            score += 5

        if deal.sqft and deal.sqft < buyer.min_sqft:
            disqualifiers.append(f"{deal.sqft:.0f} sqft below min {buyer.min_sqft:.0f}")
        elif deal.sqft and buyer.max_sqft and deal.sqft > buyer.max_sqft:
            disqualifiers.append(f"{deal.sqft:.0f} sqft above max {buyer.max_sqft:.0f}")
        else:
            score += 5

        # Condition
        if "any" not in buyer.condition and deal.condition not in buyer.condition:
            disqualifiers.append(f"condition '{deal.condition}' not accepted")
        else:
            score += 5

        is_match = len(disqualifiers) == 0 and score >= 40

        results.append(MatchResult(
            buyer_id=buyer.buyer_id,
            buyer_name=buyer.buyer_name,
            deal_id=deal.deal_id,
            score=score,
            match_reasons=reasons,
            disqualifiers=disqualifiers,
            is_match=is_match,
        ))

    # Sort: matched buyers first, then by score descending
    results.sort(key=lambda r: (not r.is_match, -r.score))
    return results


def top_matches(results: list[MatchResult], limit: int = 5) -> list[MatchResult]:
    """Return only confirmed matches, capped at limit."""
    return [r for r in results if r.is_match][:limit]


def print_match_report(deal: DealProfile, results: list[MatchResult]) -> None:
    print(f"\n{'═' * 60}")
    print(f"BUYER MATCH REPORT — {deal.deal_id}")
    print(f"Property: {deal.address}, {deal.city}, {deal.state} {deal.zip_code}")
    print(f"Type: {deal.asset_type} | Buyer Price: ${deal.buyer_price:,.0f} | Repairs: ${deal.repairs:,.0f}")
    print(f"{'─' * 60}")

    matched = [r for r in results if r.is_match]
    unmatched = [r for r in results if not r.is_match]

    print(f"\nMatched Buyers ({len(matched)}):")
    for r in matched:
        print(f"  {r.summary()}")

    if unmatched:
        print(f"\nNon-Matches ({len(unmatched)}):")
        for r in unmatched[:5]:  # Show top 5 near-misses
            print(f"  {r.summary()}")

    if not matched:
        print("\n  ⚠ NO BUYERS MATCHED. Do not pursue this deal without a buyer.")

    print(f"{'═' * 60}\n")
