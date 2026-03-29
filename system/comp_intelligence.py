"""
AMARA OS — Comp Intelligence + Fast Underwriting
Orchestrates the full deal evaluation pipeline in under 60 seconds logic time.

Skill flow:
  SFR:  playbooks/comps/sfr_comp_reading.md
        → playbooks/underwriting/sfr_fast_math.md
  Land: playbooks/comps/land_comp_logic.md
        → playbooks/underwriting/land_ldp.md

Enforced minimums:
  SFR  assignment fee >= $10,000
  Land spread         >= $100,000
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from system.config import (
    ASSET_TYPE_SFR,
    ASSET_TYPE_LAND,
    SFR_MIN_ASSIGNMENT_FEE,
    SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
)
from system.mao_calculator import (
    calculate_sfr_mao,
    calculate_ldp,
    MAOResult,
    LDPResult,
)


# ─── Repair Tiers ─────────────────────────────────────────────────────────────

class RepairCondition(str, Enum):
    LIGHT  = "light"    # cosmetic — paint, floors, fixtures
    MEDIUM = "medium"   # kitchen, baths, systems
    HEAVY  = "heavy"    # full gut / structural


REPAIR_RATE = {
    RepairCondition.LIGHT:  (15, 20),   # (low, high) per sqft
    RepairCondition.MEDIUM: (30, 45),
    RepairCondition.HEAVY:  (60, 90),
}

# Market repair multipliers — apply on top of base rate
MARKET_REPAIR_MULTIPLIER = {
    "phoenix": 1.18,   # 18% labor premium
    "dallas":  1.00,
    "houston": 1.00,
    "default": 1.00,
}


# ─── Land Signal Scoring ──────────────────────────────────────────────────────

@dataclass
class LandSignals:
    """Four demand signals for land comp logic."""
    nearby_builders: bool = False
    active_subdivisions: bool = False
    new_construction_prices_available: bool = False
    expansion_direction_confirmed: bool = False

    def score(self) -> int:
        return sum([
            self.nearby_builders,
            self.active_subdivisions,
            self.new_construction_prices_available,
            self.expansion_direction_confirmed,
        ])

    def is_viable(self) -> bool:
        return self.score() >= 2

    def required_spread(self) -> float:
        """Minimum spread threshold based on signal strength."""
        s = self.score()
        if s >= 3:
            return LAND_MIN_SPREAD          # $100,000
        elif s == 2:
            return 250_000                  # conservative — higher bar
        else:
            return float("inf")             # not viable

    def summary(self) -> str:
        checks = {
            "Nearby builders":               self.nearby_builders,
            "Active subdivisions":           self.active_subdivisions,
            "New construction prices":       self.new_construction_prices_available,
            "Expansion direction confirmed": self.expansion_direction_confirmed,
        }
        lines = [f"Land Signals ({self.score()}/4):"]
        for label, val in checks.items():
            mark = "✓" if val else "✗"
            lines.append(f"  {mark}  {label}")
        lines.append(f"  Required spread: ${self.required_spread():,.0f}")
        return "\n".join(lines)


# ─── Underwriting Results ─────────────────────────────────────────────────────

@dataclass
class SFRUnderwriteResult:
    deal_id: str
    address: str
    zip_code: str
    buyer_id: str
    buyer_price: float
    repairs: float
    seller_asking: float
    assignment_fee: float
    mao: float
    decision: str               # go / no_go / negotiate
    decision_reason: str
    fee_tier: str               # strong / minimum / below_minimum
    elapsed_ms: float = 0

    def is_go(self) -> bool:
        return self.decision == "go"

    def summary(self) -> str:
        icon = {"go": "GO", "negotiate": "NEGOTIATE", "no_go": "NO-GO"}[self.decision]
        lines = [
            f"{'═' * 50}",
            f"SFR FAST UNDERWRITE — {icon}",
            f"Deal:      {self.deal_id}  {self.address}",
            f"ZIP:       {self.zip_code}",
            f"{'─' * 50}",
            f"Buyer Price:   ${self.buyer_price:>10,.0f}",
            f"Repairs:     - ${self.repairs:>10,.0f}",
            f"Fee (target):- ${'15,000':>10}",
            f"{'─' * 50}",
            f"MAO:           ${self.mao:>10,.0f}",
            f"Seller Asking: ${self.seller_asking:>10,.0f}",
            f"Gap:           ${self.seller_asking - self.mao:>+10,.0f}",
            f"{'─' * 50}",
            f"Assignment Fee: ${self.assignment_fee:,.0f}  [{self.fee_tier.upper()}]",
            f"Decision: {icon} — {self.decision_reason}",
            f"Time: {self.elapsed_ms:.0f}ms",
            f"{'═' * 50}",
        ]
        return "\n".join(lines)


@dataclass
class LandUnderwriteResult:
    deal_id: str
    address: str
    signals: LandSignals
    ldp: LDPResult
    decision: str               # go / no_go / conservative
    decision_reason: str
    elapsed_ms: float = 0

    def is_go(self) -> bool:
        return self.decision in ("go", "conservative")

    def summary(self) -> str:
        icon = {"go": "GO", "conservative": "GO (CONSERVATIVE)", "no_go": "NO-GO"}[self.decision]
        lines = [
            f"{'═' * 50}",
            f"LAND FAST UNDERWRITE — {icon}",
            f"Deal:  {self.deal_id}  {self.address}",
            f"{'─' * 50}",
            self.signals.summary(),
            f"{'─' * 50}",
            self.ldp.summary(),
            f"{'─' * 50}",
            f"Decision: {icon} — {self.decision_reason}",
            f"Time: {self.elapsed_ms:.0f}ms",
            f"{'═' * 50}",
        ]
        return "\n".join(lines)


# ─── Fast Repair Estimator ────────────────────────────────────────────────────

def fast_repair_estimate(
    sqft: float,
    condition: str | RepairCondition,
    market: str = "default",
) -> float:
    """
    Fast repair estimate from sqft + condition.
    Always uses high end of range. Rounds up to nearest $5,000.
    """
    cond = RepairCondition(condition) if isinstance(condition, str) else condition
    _, high_rate = REPAIR_RATE[cond]
    multiplier = MARKET_REPAIR_MULTIPLIER.get(market.lower(), 1.00)
    raw = sqft * high_rate * multiplier
    # Round up to nearest $5,000
    return (int(raw / 5_000) + 1) * 5_000


# ─── SFR Underwriting Engine ──────────────────────────────────────────────────

def underwrite_sfr(
    deal_id: str,
    address: str,
    zip_code: str,
    buyer_id: str,
    buyer_price: float,
    seller_asking: float,
    sqft: float = 0,
    repairs: float = 0,
    condition: str = "medium",
    market: str = "default",
    target_fee: float = SFR_TARGET_ASSIGNMENT_FEE,
) -> SFRUnderwriteResult:
    """
    Fast SFR underwrite. Runs MAO formula, classifies decision.

    Reads:
      playbooks/comps/sfr_comp_reading.md   — buyer price source
      playbooks/underwriting/sfr_fast_math.md — formula and decision tree

    Enforces: assignment fee >= $10,000 (hard floor).

    Args:
        deal_id:       Deal file ID
        address:       Property address
        zip_code:      ZIP code
        buyer_id:      Matched buyer ID (must be confirmed before calling)
        buyer_price:   Buyer's price from comp read
        seller_asking: Seller's asking price
        sqft:          Property sqft (used for fast repair estimate if repairs=0)
        repairs:       Repair estimate (if 0, estimated from sqft + condition)
        condition:     light / medium / heavy (used only if repairs=0)
        market:        Market name for repair multiplier
        target_fee:    Desired assignment fee (defaults to $15,000)

    Returns:
        SFRUnderwriteResult with decision and reasoning
    """
    t0 = time.monotonic()

    # Enforce buyer-first
    if not buyer_id:
        return SFRUnderwriteResult(
            deal_id=deal_id, address=address, zip_code=zip_code,
            buyer_id="", buyer_price=buyer_price, repairs=0,
            seller_asking=seller_asking, assignment_fee=0,
            mao=0, decision="no_go",
            decision_reason="No buyer confirmed. Buyer-first rule: cannot underwrite without a buyer.",
            fee_tier="none",
        )

    # Estimate repairs if not provided
    if repairs == 0 and sqft > 0:
        repairs = fast_repair_estimate(sqft, condition, market)

    # Run MAO
    mao_result = calculate_sfr_mao(buyer_price, repairs, target_fee)
    mao = mao_result.mao

    # Actual fee at seller's asking price
    actual_fee = buyer_price - repairs - seller_asking

    # Classify fee tier
    if actual_fee >= SFR_TARGET_ASSIGNMENT_FEE:
        fee_tier = "strong"
    elif actual_fee >= SFR_MIN_ASSIGNMENT_FEE:
        fee_tier = "minimum"
    else:
        fee_tier = "below_minimum"

    # Decision
    if actual_fee >= SFR_MIN_ASSIGNMENT_FEE and seller_asking <= mao:
        decision = "go"
        reason = (
            f"Seller asking ${seller_asking:,.0f} ≤ MAO ${mao:,.0f}. "
            f"Fee ${actual_fee:,.0f} clears ${SFR_MIN_ASSIGNMENT_FEE:,.0f} minimum."
        )
    elif mao > 0 and seller_asking > mao:
        gap = seller_asking - mao
        decision = "negotiate"
        reason = (
            f"Seller asking ${seller_asking:,.0f} is ${gap:,.0f} over MAO. "
            f"Negotiate to ${mao:,.0f} or below to hit ${target_fee:,.0f} fee."
        )
    else:
        decision = "no_go"
        reason = (
            f"Fee of ${actual_fee:,.0f} at asking price is below ${SFR_MIN_ASSIGNMENT_FEE:,.0f} minimum. "
            f"Deal is not viable at current numbers."
        )

    elapsed = (time.monotonic() - t0) * 1000

    return SFRUnderwriteResult(
        deal_id=deal_id,
        address=address,
        zip_code=zip_code,
        buyer_id=buyer_id,
        buyer_price=buyer_price,
        repairs=repairs,
        seller_asking=seller_asking,
        assignment_fee=actual_fee,
        mao=mao,
        decision=decision,
        decision_reason=reason,
        fee_tier=fee_tier,
        elapsed_ms=elapsed,
    )


# ─── Land Underwriting Engine ─────────────────────────────────────────────────

def underwrite_land(
    deal_id: str,
    address: str,
    acres: float,
    median_home_price: float,
    asking_price: float,
    signals: LandSignals,
    density: float = 3.5,
    lot_multiplier: float = 0.23,
    dev_cost_per_lot: float = 60_000,
) -> LandUnderwriteResult:
    """
    Fast land underwrite. Runs LDP formula, applies signal-adjusted thresholds.

    Reads:
      playbooks/comps/land_comp_logic.md       — signal scoring
      playbooks/underwriting/land_ldp.md       — LDP formula

    Enforces: spread >= $100,000 (hard floor). $250,000 if signals score < 3.

    Args:
        deal_id:          Deal file ID
        address:          Parcel address
        acres:            Total acreage
        median_home_price: New construction sale price in the ZIP
        asking_price:     Seller's asking price
        signals:          LandSignals with demand signal flags
        density:          Lots per acre
        lot_multiplier:   Lot value as % of median home price
        dev_cost_per_lot: Dev cost per lot

    Returns:
        LandUnderwriteResult with decision and reasoning
    """
    t0 = time.monotonic()

    # Apply conservative inputs if signal score is low
    if signals.score() == 2:
        density = min(density, 3.0)
        lot_multiplier = min(lot_multiplier, 0.20)

    ldp = calculate_ldp(
        acres=acres,
        median_home_price=median_home_price,
        asking_price=asking_price,
        density=density,
        lot_value_multiplier=lot_multiplier,
        dev_cost_per_lot=dev_cost_per_lot,
    )

    required = signals.required_spread()

    if not signals.is_viable():
        decision = "no_go"
        reason = (
            f"Only {signals.score()}/4 land demand signals confirmed. "
            f"Insufficient market validation to pursue."
        )
    elif ldp.spread < LAND_MIN_SPREAD:
        decision = "no_go"
        reason = (
            f"Spread ${ldp.spread:,.0f} below hard minimum ${LAND_MIN_SPREAD:,.0f}. "
            f"Walk away."
        )
    elif ldp.spread < required:
        decision = "no_go"
        reason = (
            f"Spread ${ldp.spread:,.0f} below ${required:,.0f} required for {signals.score()}/4 signals. "
            f"Need stronger demand confirmation or better price."
        )
    elif signals.score() == 2:
        decision = "conservative"
        reason = (
            f"2/4 signals confirmed. Spread ${ldp.spread:,.0f} meets ${required:,.0f} conservative threshold. "
            f"Proceed with caution — confirm builder interest before going under contract."
        )
    else:
        decision = "go"
        reason = (
            f"{signals.score()}/4 signals confirmed. Spread ${ldp.spread:,.0f} — {ldp.spread_tier}."
        )

    elapsed = (time.monotonic() - t0) * 1000

    return LandUnderwriteResult(
        deal_id=deal_id,
        address=address,
        signals=signals,
        ldp=ldp,
        decision=decision,
        decision_reason=reason,
        elapsed_ms=elapsed,
    )


# ─── Batch Screener ───────────────────────────────────────────────────────────

@dataclass
class BatchScreenInput:
    deal_id: str
    asset_type: str          # SFR or Land
    address: str
    zip_code: str
    buyer_id: str
    # SFR fields
    buyer_price: float = 0
    seller_asking: float = 0
    repairs: float = 0
    sqft: float = 0
    condition: str = "medium"
    market: str = "default"
    # Land fields
    acres: float = 0
    median_home_price: float = 0
    land_asking: float = 0
    signals: LandSignals | None = None


def batch_screen(inputs: list[BatchScreenInput]) -> list[SFRUnderwriteResult | LandUnderwriteResult]:
    """
    Run fast underwriting on a list of deals.
    Returns results sorted by decision (go first) then by fee/spread descending.
    """
    results = []
    for inp in inputs:
        if inp.asset_type.upper() == ASSET_TYPE_SFR:
            r = underwrite_sfr(
                deal_id=inp.deal_id,
                address=inp.address,
                zip_code=inp.zip_code,
                buyer_id=inp.buyer_id,
                buyer_price=inp.buyer_price,
                seller_asking=inp.seller_asking,
                sqft=inp.sqft,
                repairs=inp.repairs,
                condition=inp.condition,
                market=inp.market,
            )
            results.append(r)
        elif inp.asset_type.upper() == ASSET_TYPE_LAND:
            signals = inp.signals or LandSignals()
            r = underwrite_land(
                deal_id=inp.deal_id,
                address=inp.address,
                acres=inp.acres,
                median_home_price=inp.median_home_price,
                asking_price=inp.land_asking,
                signals=signals,
            )
            results.append(r)

    # Sort: go first, then negotiate, then no_go; within tier by fee/spread
    def sort_key(r):
        order = {"go": 0, "conservative": 0, "negotiate": 1, "no_go": 2}
        score = order.get(r.decision, 3)
        value = r.assignment_fee if isinstance(r, SFRUnderwriteResult) else r.ldp.spread
        return (score, -value)

    results.sort(key=sort_key)
    return results
