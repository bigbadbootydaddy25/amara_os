"""
AMARA OS — Learning Protocol
After every deal, update system knowledge.
Always prioritize learned data over assumptions.

Protocol steps:
1. Record deal result
2. Identify pricing gaps
3. Update buyer buy box
4. Update market observations
5. Adjust future MAO logic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from system.vault import (
    append_observation,
    record_deal_result,
    read_vault_file,
    write_vault_file,
    find_buyer_file,
    find_deal_file,
)
from system.config import (
    SFR_MIN_ASSIGNMENT_FEE,
    SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD,
)


@dataclass
class DealOutcome:
    deal_id: str
    asset_type: str
    address: str
    zip_code: str
    city: str
    state: str
    buyer_id: str
    buyer_name: str

    # Pricing
    contract_price: float        # What we paid / went under contract for
    buyer_price: float           # What buyer paid
    assignment_fee: float        # Actual fee collected
    estimated_repairs: float     # Repairs estimated at time of offer
    actual_repairs: float = 0    # If known post-close

    # Projected
    projected_fee: float = 0     # What we targeted

    # Qualitative
    result: str = "closed"       # closed / fell_through / dead
    buyer_feedback: str = ""
    price_feedback: str = ""     # too_high / right / left_money
    lessons: str = ""


@dataclass
class LearningReport:
    deal_id: str
    pricing_gap: float           # Projected minus actual fee
    pricing_gap_pct: float       # As a percentage
    observations_created: list[str] = field(default_factory=list)
    buy_box_updates: list[str] = field(default_factory=list)
    mao_adjustments: list[str] = field(default_factory=list)
    result_id: str = ""

    def summary(self) -> str:
        direction = "OVER" if self.pricing_gap > 0 else "UNDER"
        lines = [
            f"{'═' * 55}",
            f"LEARNING REPORT — {self.deal_id}",
            f"{'─' * 55}",
            f"Pricing Gap: ${abs(self.pricing_gap):,.0f} {direction} target ({self.pricing_gap_pct:+.1f}%)",
            f"Result recorded: {self.result_id}",
        ]
        if self.observations_created:
            lines.append("Observations created: " + ", ".join(self.observations_created))
        if self.buy_box_updates:
            lines.append("Buy box updates:")
            for u in self.buy_box_updates:
                lines.append(f"  → {u}")
        if self.mao_adjustments:
            lines.append("MAO adjustments:")
            for a in self.mao_adjustments:
                lines.append(f"  → {a}")
        lines.append(f"{'═' * 55}")
        return "\n".join(lines)


def run_learning_protocol(outcome: DealOutcome) -> LearningReport:
    """
    Execute all 5 learning protocol steps after a deal closes.
    Returns a LearningReport with all changes made.
    """
    observations = []
    buy_box_updates = []
    mao_adjustments = []

    # ── Step 1: Record deal result ─────────────────────────────────────────
    result_id, result_path = record_deal_result(
        deal_id=outcome.deal_id,
        contract_price=outcome.contract_price,
        buyer_price=outcome.buyer_price,
        assignment_fee=outcome.assignment_fee,
        buyer_feedback=outcome.buyer_feedback,
        lessons=outcome.lessons,
    )

    # ── Step 2: Identify pricing gaps ─────────────────────────────────────
    projected = outcome.projected_fee or SFR_TARGET_ASSIGNMENT_FEE
    gap = projected - outcome.assignment_fee
    gap_pct = (gap / projected * 100) if projected else 0

    if abs(gap) >= 1_000:
        direction = "below" if gap > 0 else "above"
        obs_text = (
            f"Deal {outcome.deal_id} closed with assignment fee ${outcome.assignment_fee:,.0f}, "
            f"${abs(gap):,.0f} {direction} projected ${projected:,.0f}. "
            f"Buyer feedback: '{outcome.price_feedback}'. "
            f"Location: {outcome.city}, {outcome.state} {outcome.zip_code}."
        )
        obs_id, _ = append_observation(
            observation_text=obs_text,
            obs_type="pricing",
            related_deal=outcome.deal_id,
            related_buyer=outcome.buyer_id,
            related_market=f"{outcome.city}, {outcome.state}",
        )
        observations.append(obs_id)

    # ── Step 3: Update buyer buy box ───────────────────────────────────────
    buyer_file = find_buyer_file(outcome.buyer_id)
    if buyer_file:
        content = buyer_file.read_text(encoding="utf-8")
        from datetime import date
        today = date.today().isoformat()

        # Append deal to buyer's history table
        new_row = (
            f"| {today} | {outcome.deal_id} | {outcome.asset_type} "
            f"| {outcome.address} | {'Yes' if outcome.result == 'closed' else 'No'} "
            f"| Fee: ${outcome.assignment_fee:,.0f} |"
        )
        # Find the table header and append
        content = content.replace(
            "|      |         |      |         |           |       |",
            f"|      |         |      |         |           |       |\n{new_row}",
            1,
        )

        # Update last contact date
        import re
        content = re.sub(
            r"- \*\*Last Contact:\*\*.*",
            f"- **Last Contact:** {today}",
            content,
        )

        # If buyer said price was "left_money", note it
        if outcome.price_feedback == "left_money":
            note = (
                f"\n> [{today}] Buyer indicated we left money on table on {outcome.deal_id}. "
                f"Consider increasing buyer price target in this corridor.\n"
            )
            content += note
            buy_box_updates.append(
                f"Buyer {outcome.buyer_id}: flagged as left-money-on-table in "
                f"{outcome.city}, {outcome.state} {outcome.zip_code}"
            )
        elif outcome.price_feedback == "too_high":
            note = (
                f"\n> [{today}] Buyer indicated price was too high on {outcome.deal_id}. "
                f"Adjust max buy price down in this corridor.\n"
            )
            content += note
            buy_box_updates.append(
                f"Buyer {outcome.buyer_id}: flagged as too-high in "
                f"{outcome.city}, {outcome.state} {outcome.zip_code}"
            )

        buyer_file.write_text(content, encoding="utf-8")
        buy_box_updates.append(f"Buyer {outcome.buyer_id}: deal history updated")

    # ── Step 4: Update market observations ────────────────────────────────
    market_obs = (
        f"ZIP {outcome.zip_code} ({outcome.city}, {outcome.state}): "
        f"Deal {outcome.deal_id} closed. "
        f"Buyer price ${outcome.buyer_price:,.0f}, "
        f"repairs ${outcome.estimated_repairs:,.0f}, "
        f"assignment fee ${outcome.assignment_fee:,.0f}. "
        f"Buyer feedback on price: {outcome.price_feedback or 'none recorded'}."
    )
    market_id, _ = append_observation(
        observation_text=market_obs,
        obs_type="market",
        related_deal=outcome.deal_id,
        related_market=f"{outcome.city}, {outcome.state}",
    )
    observations.append(market_id)

    # ── Step 5: Adjust MAO logic recommendations ───────────────────────────
    if outcome.price_feedback == "left_money":
        mao_adjustments.append(
            f"In {outcome.zip_code}: buyer price may support higher. "
            f"Current ceiling of ${outcome.buyer_price:,.0f} may be conservative."
        )
    if outcome.actual_repairs and abs(outcome.actual_repairs - outcome.estimated_repairs) > 5_000:
        diff = outcome.actual_repairs - outcome.estimated_repairs
        direction = "under" if diff > 0 else "over"
        mao_adjustments.append(
            f"Repair estimate was ${abs(diff):,.0f} {direction} — "
            f"calibrate repair estimates for {outcome.city}, {outcome.state}."
        )

    return LearningReport(
        deal_id=outcome.deal_id,
        pricing_gap=gap,
        pricing_gap_pct=gap_pct,
        observations_created=observations,
        buy_box_updates=buy_box_updates,
        mao_adjustments=mao_adjustments,
        result_id=result_id,
    )
