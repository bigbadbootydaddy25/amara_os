"""
AMARA OS — Deal Analyzer
Analyzes SFR and Land deals for viability.
Applies MAO formula, enforces minimums, and scores deal quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from system.config import (
    ASSET_TYPE_SFR,
    ASSET_TYPE_MFR,
    ASSET_TYPE_LAND,
    SFR_MIN_ASSIGNMENT_FEE,
    SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
    LAND_TARGET_SPREAD,
)
from system.mao_calculator import (
    calculate_sfr_mao,
    calculate_sfr_mao_for_minimum,
    calculate_land_spread,
    what_buyer_price_is_needed,
    MAOResult,
)


@dataclass
class DealAnalysis:
    deal_id: str
    asset_type: str
    address: str
    arv: float
    buyer_price: float
    repairs: float
    seller_asking: float
    mao_result: MAOResult
    grade: str                      # A / B / C / F
    grade_reason: str
    flags: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def is_viable(self) -> bool:
        return self.mao_result.is_viable and self.grade not in ("F",)

    def summary(self) -> str:
        lines = [
            f"{'═' * 55}",
            f"DEAL ANALYSIS — {self.deal_id}",
            f"Address:  {self.address}",
            f"Type:     {self.asset_type}",
            f"{'─' * 55}",
            self.mao_result.summary(),
            f"{'─' * 55}",
            f"Grade:    {self.grade}  ({self.grade_reason})",
        ]
        if self.flags:
            lines.append("Flags:")
            for f in self.flags:
                lines.append(f"  ⚠  {f}")
        if self.recommendations:
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  →  {r}")
        lines.append(f"{'═' * 55}")
        return "\n".join(lines)


def analyze_sfr_deal(
    deal_id: str,
    address: str,
    arv: float,
    buyer_price: float,
    repairs: float,
    seller_asking: float,
    target_fee: float = SFR_TARGET_ASSIGNMENT_FEE,
) -> DealAnalysis:
    """
    Full SFR deal analysis.

    Args:
        deal_id: Unique identifier
        address: Property address
        arv: After Repair Value (from comps)
        buyer_price: What the end buyer will pay
        repairs: Estimated repair cost
        seller_asking: Seller's asking price
        target_fee: Desired assignment fee

    Returns:
        DealAnalysis with grade and recommendations
    """
    flags = []
    recommendations = []

    mao_result = calculate_sfr_mao(buyer_price, repairs, target_fee)
    mao = mao_result.mao

    # Check if MAO covers seller ask
    if seller_asking > mao:
        gap = seller_asking - mao
        flags.append(f"Seller asking ${seller_asking:,.0f} is ${gap:,.0f} over MAO ${mao:,.0f}")
        recommendations.append(f"Negotiate seller down to ${mao:,.0f} or below")
        recommendations.append(
            f"At minimum, get to ${calculate_sfr_mao_for_minimum(buyer_price, repairs).mao:,.0f} "
            f"to preserve ${SFR_MIN_ASSIGNMENT_FEE:,.0f} min fee"
        )

    # ARV sanity check: buyer price shouldn't exceed ARV
    if buyer_price > arv:
        flags.append(f"Buyer price ${buyer_price:,.0f} exceeds ARV ${arv:,.0f}")
        recommendations.append("Re-run comps — buyer price cannot exceed ARV")

    # Buyer price vs ARV ratio (informational, not rule-based)
    if arv > 0:
        ratio = buyer_price / arv
        if ratio > 0.85:
            flags.append(f"Buyer price is {ratio:.0%} of ARV — leaving thin margin for buyer")
        elif ratio < 0.60:
            recommendations.append(f"Buyer price at {ratio:.0%} of ARV — strong equity position, can push fee higher")

    # Assignment fee assessment
    actual_fee = buyer_price - repairs - seller_asking if seller_asking <= mao else 0

    if actual_fee >= SFR_TARGET_ASSIGNMENT_FEE:
        grade = "A"
        grade_reason = f"Assignment fee ${actual_fee:,.0f} meets target"
    elif actual_fee >= SFR_MIN_ASSIGNMENT_FEE:
        grade = "B"
        grade_reason = f"Assignment fee ${actual_fee:,.0f} meets minimum but below ${SFR_TARGET_ASSIGNMENT_FEE:,.0f} target"
        recommendations.append(f"Push for ${SFR_TARGET_ASSIGNMENT_FEE:,.0f} fee — renegotiate or find higher buyer")
    elif mao_result.mao > 0 and seller_asking > mao:
        grade = "C"
        grade_reason = "Seller price gap exists — deal requires negotiation"
        recommendations.append("Do not go under contract until seller meets MAO")
    else:
        grade = "F"
        grade_reason = "Deal is upside down — not viable at current numbers"
        recommendations.append("Walk away or find a higher buyer price")

    return DealAnalysis(
        deal_id=deal_id,
        asset_type=ASSET_TYPE_SFR,
        address=address,
        arv=arv,
        buyer_price=buyer_price,
        repairs=repairs,
        seller_asking=seller_asking,
        mao_result=mao_result,
        grade=grade,
        grade_reason=grade_reason,
        flags=flags,
        recommendations=recommendations,
    )


def analyze_land_deal(
    deal_id: str,
    address: str,
    retail_value: float,
    acquisition_cost: float,
    assignment_fee: float = 0,
) -> DealAnalysis:
    """
    Full land deal analysis.

    Args:
        deal_id: Unique identifier
        address: Parcel address / description
        retail_value: Developer or market value
        acquisition_cost: Contract price from seller
        assignment_fee: Any wholesale / assignment fee layered on top

    Returns:
        DealAnalysis with grade and spread analysis
    """
    flags = []
    recommendations = []

    mao_result = calculate_land_spread(retail_value, acquisition_cost, assignment_fee)
    spread = mao_result.spread

    if spread is None or spread < 0:
        grade = "F"
        grade_reason = "Negative spread — deal is upside down"
        recommendations.append("Do not pursue at current pricing")
    elif spread < LAND_MIN_SPREAD:
        grade = "C"
        grade_reason = f"Spread ${spread:,.0f} below minimum ${LAND_MIN_SPREAD:,.0f}"
        recommendations.append(f"Need ${LAND_MIN_SPREAD - spread:,.0f} more spread — renegotiate or find better buyer")
        flags.append(f"Below minimum spread threshold of ${LAND_MIN_SPREAD:,.0f}")
    elif spread < LAND_TARGET_SPREAD:
        grade = "B"
        grade_reason = f"Spread ${spread:,.0f} meets minimum but below target ${LAND_TARGET_SPREAD:,.0f}"
        recommendations.append("Viable but aim for 6-figure+ spread on land deals")
    else:
        grade = "A"
        grade_reason = f"Spread ${spread:,.0f} — excellent land deal"

    if retail_value <= 0:
        flags.append("Retail value not established — get developer comps before proceeding")

    return DealAnalysis(
        deal_id=deal_id,
        asset_type=ASSET_TYPE_LAND,
        address=address,
        arv=retail_value,
        buyer_price=retail_value,
        repairs=0,
        seller_asking=acquisition_cost,
        mao_result=mao_result,
        grade=grade,
        grade_reason=grade_reason,
        flags=flags,
        recommendations=recommendations,
    )


def quick_screen(
    asset_type: str,
    buyer_price: float,
    repairs: float,
    seller_asking: float,
) -> dict:
    """
    Fast go/no-go screen before full analysis.
    Returns a dict with: viable (bool), max_fee (float), min_fee_viable (bool)
    """
    if asset_type in (ASSET_TYPE_SFR, ASSET_TYPE_MFR):
        at_target = calculate_sfr_mao(buyer_price, repairs, SFR_TARGET_ASSIGNMENT_FEE)
        at_min = calculate_sfr_mao_for_minimum(buyer_price, repairs)

        return {
            "viable": seller_asking <= at_min.mao,
            "viable_at_target_fee": seller_asking <= at_target.mao,
            "mao_at_target_fee": at_target.mao,
            "mao_at_min_fee": at_min.mao,
            "max_fee_at_asking": max(0, buyer_price - repairs - seller_asking),
            "meets_min_fee": (buyer_price - repairs - seller_asking) >= SFR_MIN_ASSIGNMENT_FEE,
        }
    elif asset_type == ASSET_TYPE_LAND:
        spread = buyer_price - seller_asking
        return {
            "viable": spread >= LAND_MIN_SPREAD,
            "spread": spread,
            "meets_min_spread": spread >= LAND_MIN_SPREAD,
            "meets_target_spread": spread >= LAND_TARGET_SPREAD,
        }
    else:
        return {"viable": False, "reason": f"Unknown asset type: {asset_type}"}
