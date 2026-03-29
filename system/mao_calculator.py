"""
AMARA OS — MAO Calculator
Formula: MAO = Buyer Price - Repairs - Assignment Fee

Rules:
- SFR: Min assignment fee = $10,000. Target = $15,000+
- Land: Min spread = $100,000. Target = $500,000+
- DO NOT use 70% ARV rule.
"""

from dataclasses import dataclass
from system.config import (
    SFR_MIN_ASSIGNMENT_FEE,
    SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
    ASSET_TYPE_SFR,
    ASSET_TYPE_MFR,
    ASSET_TYPE_LAND,
)


@dataclass
class MAOResult:
    asset_type: str
    buyer_price: float
    repairs: float
    assignment_fee: float
    mao: float
    is_viable: bool
    viability_reason: str
    spread: float | None = None  # Land deals only

    def summary(self) -> str:
        lines = [
            f"Asset Type:        {self.asset_type}",
            f"Buyer Price:     ${self.buyer_price:>12,.0f}",
            f"Repairs:       - ${self.repairs:>12,.0f}",
            f"Assignment Fee:- ${self.assignment_fee:>12,.0f}",
            f"{'─' * 40}",
            f"MAO:             ${self.mao:>12,.0f}",
            f"",
            f"Viable: {'YES' if self.is_viable else 'NO — ' + self.viability_reason}",
        ]
        if self.spread is not None:
            lines.append(f"Spread:          ${self.spread:>12,.0f}")
        return "\n".join(lines)


def calculate_sfr_mao(
    buyer_price: float,
    repairs: float,
    assignment_fee: float = SFR_TARGET_ASSIGNMENT_FEE,
) -> MAOResult:
    """
    Calculate MAO for SFR deal.

    Args:
        buyer_price: What the end buyer will pay
        repairs: Estimated repair cost
        assignment_fee: Desired assignment fee (defaults to $15,000 target)

    Returns:
        MAOResult with calculated MAO and viability
    """
    if assignment_fee < SFR_MIN_ASSIGNMENT_FEE:
        assignment_fee = SFR_MIN_ASSIGNMENT_FEE

    mao = buyer_price - repairs - assignment_fee
    is_viable = mao > 0 and assignment_fee >= SFR_MIN_ASSIGNMENT_FEE

    if mao <= 0:
        reason = f"MAO is negative (${mao:,.0f}). Deal is upside down."
    elif assignment_fee < SFR_MIN_ASSIGNMENT_FEE:
        reason = f"Assignment fee ${assignment_fee:,.0f} is below minimum ${SFR_MIN_ASSIGNMENT_FEE:,.0f}."
    else:
        reason = "OK"

    return MAOResult(
        asset_type=ASSET_TYPE_SFR,
        buyer_price=buyer_price,
        repairs=repairs,
        assignment_fee=assignment_fee,
        mao=mao,
        is_viable=is_viable,
        viability_reason=reason,
    )


def calculate_sfr_mao_for_minimum(
    buyer_price: float,
    repairs: float,
) -> MAOResult:
    """Calculate MAO using the minimum assignment fee floor ($10k)."""
    return calculate_sfr_mao(buyer_price, repairs, SFR_MIN_ASSIGNMENT_FEE)


def calculate_sfr_mao_for_target(
    buyer_price: float,
    repairs: float,
) -> MAOResult:
    """Calculate MAO using the target assignment fee ($15k+)."""
    return calculate_sfr_mao(buyer_price, repairs, SFR_TARGET_ASSIGNMENT_FEE)


def calculate_land_spread(
    retail_value: float,
    acquisition_cost: float,
    assignment_fee: float = 0,
) -> MAOResult:
    """
    Calculate spread for land / dead paper deal.

    Args:
        retail_value: Developer / market value of the land
        acquisition_cost: Cost to acquire (contract price from seller)
        assignment_fee: Any additional assignment/wholesale fee

    Returns:
        MAOResult with spread analysis
    """
    spread = retail_value - acquisition_cost - assignment_fee
    is_viable = spread >= LAND_MIN_SPREAD

    if spread < LAND_MIN_SPREAD:
        reason = f"Spread ${spread:,.0f} is below minimum ${LAND_MIN_SPREAD:,.0f}."
    else:
        reason = "OK"

    return MAOResult(
        asset_type=ASSET_TYPE_LAND,
        buyer_price=retail_value,
        repairs=0,
        assignment_fee=assignment_fee,
        mao=acquisition_cost,
        is_viable=is_viable,
        viability_reason=reason,
        spread=spread,
    )


def calculate_max_offer_at_fee(
    buyer_price: float,
    repairs: float,
    desired_fee: float,
) -> float:
    """
    Given a desired fee, return the maximum offer price.
    Used when negotiating with sellers.
    """
    return buyer_price - repairs - desired_fee


def calculate_fee_at_price(
    offer_price: float,
    buyer_price: float,
    repairs: float,
) -> float:
    """
    Given an offer price already under contract, return the
    assignment fee that would be generated at that buyer price.
    """
    return buyer_price - repairs - offer_price


def what_buyer_price_is_needed(
    offer_price: float,
    repairs: float,
    target_fee: float = SFR_TARGET_ASSIGNMENT_FEE,
) -> float:
    """
    Given an offer price, return the minimum buyer price needed
    to hit the target assignment fee.
    """
    return offer_price + repairs + target_fee
