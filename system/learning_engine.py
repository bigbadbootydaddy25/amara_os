"""
AMARA OS — Learning Engine (Enhanced Feedback Loop)

Four sub-engines that run after every closed deal or market event:

1. Learning Intake      — parse closed deal outcomes, identify gaps
2. Observation Engine   — generate structured vault observations
3. Buyer Update Engine  — update buy box, pricing, and activity scores
4. Market Update Engine — update ZIP corridors and market snapshots
5. Markdown Sync Engine — write all updates back to vault files

Core rule: every learning event must produce a vault update.
An observation with an empty Action field is incomplete.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from system.config import (
    SFR_MIN_ASSIGNMENT_FEE, SFR_TARGET_ASSIGNMENT_FEE,
    LAND_MIN_SPREAD, VAULT_BUYERS, VAULT_OBSERVATIONS,
    VAULT_DEAL_RESULTS, VAULT_ZIP_CORRIDORS,
)
from system.vault import (
    read_vault_file, write_vault_file, list_vault,
    append_observation, next_id,
)


# ─── Deal Outcome (Learning Intake input) ─────────────────────────────────────

@dataclass
class DealOutcome:
    deal_id:               str
    address:               str
    zip_code:              str
    asset_type:            str      # SFR / land
    buyer_id:              str
    buyer_name:            str

    # Projected (from MAO / offer queue)
    projected_buyer_price: float
    projected_repairs:     float
    projected_mao:         float
    projected_fee:         float

    # Actual (from closed deal)
    actual_contract_price: float    # seller agreed price
    actual_buyer_price:    float    # what buyer paid
    actual_repairs:        float    # final repair cost
    actual_fee:            float    # assignment fee collected

    # Timing
    offer_sent_date:       date | None = None
    contract_date:         date | None = None
    closed_date:           date | None = None

    # Qualitative
    seller_motivation:     str = ""
    notes:                 str = ""


# ─── Learning Event ───────────────────────────────────────────────────────────

@dataclass
class LearningEvent:
    event_id:      str = field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:6].upper()}")
    event_type:    str = ""     # deal_closed / mao_gap / buyer_pattern / market_shift
    source_id:     str = ""     # deal_id / buyer_id / zip
    source_type:   str = ""     # deal / buyer / market
    summary:       str = ""
    payload:       dict = field(default_factory=dict)
    created_at:    str = field(default_factory=lambda: date.today().isoformat())


# ─── Learning Report ──────────────────────────────────────────────────────────

@dataclass
class LearningReport:
    deal_id:          str
    address:          str
    zip_code:         str
    asset_type:       str

    # Gap analysis
    fee_gap:          float      # actual_fee - projected_fee (positive = better than expected)
    repair_gap:       float      # actual_repairs - projected_repairs (positive = over-estimated)
    buyer_price_gap:  float      # actual_buyer_price - projected_buyer_price

    # Verdicts
    mao_verdict:      str        # accurate / conservative / aggressive
    repair_verdict:   str        # accurate / over / under
    buyer_verdict:    str        # accurate / above / below

    # Actions taken
    events:           list[LearningEvent] = field(default_factory=list)
    vault_updates:    list[str]           = field(default_factory=list)   # files updated
    observation_id:   str                 = ""

    # Recommendations
    mao_adjustment:   str = ""   # e.g. "increase buyer price by 5% for 77008"
    repair_adjustment:str = ""
    buyer_adjustment: str = ""

    def summary(self) -> str:
        lines = [
            f"Learning Report — {self.deal_id} | {self.address}",
            f"  Asset Type: {self.asset_type}",
            f"  Fee Gap:      ${self.fee_gap:+,.0f} ({self.mao_verdict})",
            f"  Repair Gap:   ${self.repair_gap:+,.0f} ({self.repair_verdict})",
            f"  Buyer Gap:    ${self.buyer_price_gap:+,.0f} ({self.buyer_verdict})",
        ]
        if self.mao_adjustment:
            lines.append(f"  MAO Adj:      {self.mao_adjustment}")
        if self.vault_updates:
            lines.append(f"  Vault Updates: {', '.join(self.vault_updates)}")
        return "\n".join(lines)


# ─── Engine 1: Learning Intake ────────────────────────────────────────────────

def intake_closed_deal(outcome: DealOutcome) -> LearningReport:
    """
    Parse a closed deal outcome, compute gaps, and produce initial learning report.
    Step 1 of the learning protocol.
    """
    fee_gap          = outcome.actual_fee            - outcome.projected_fee
    repair_gap       = outcome.projected_repairs     - outcome.actual_repairs   # positive = over-estimated repairs
    buyer_price_gap  = outcome.actual_buyer_price    - outcome.projected_buyer_price

    # Verdict logic
    def _gap_verdict(gap: float, threshold_pct: float, projected: float, labels: tuple) -> str:
        if projected <= 0:
            return "unknown"
        pct = abs(gap) / projected
        if pct <= threshold_pct:
            return labels[0]   # accurate
        return labels[1] if gap > 0 else labels[2]

    mao_verdict    = _gap_verdict(fee_gap, 0.15, outcome.projected_fee,
                                  ("accurate", "better_than_projected", "worse_than_projected"))
    repair_verdict = _gap_verdict(repair_gap, 0.20, outcome.projected_repairs,
                                  ("accurate", "over_estimated", "under_estimated"))
    buyer_verdict  = _gap_verdict(buyer_price_gap, 0.10, outcome.projected_buyer_price,
                                  ("accurate", "above_estimate", "below_estimate"))

    # Recommendations
    mao_adj     = ""
    repair_adj  = ""
    buyer_adj   = ""

    if "worse" in mao_verdict:
        mao_adj = f"Lower MAO ceiling by ~5% for ZIP {outcome.zip_code}. Projected fee was overstated."
    elif "better" in mao_verdict and fee_gap > 10_000:
        mao_adj = f"MAO in {outcome.zip_code} was conservative by ${fee_gap:,.0f}. Consider raising buyer price slightly."

    if repair_verdict == "under_estimated":
        repair_adj = f"Repairs under-estimated by ${abs(repair_gap):,.0f}. Add repair buffer for {outcome.zip_code}."
    elif repair_verdict == "over_estimated" and abs(repair_gap) > 10_000:
        repair_adj = f"Repairs over-estimated by ${repair_gap:,.0f}. Reduce repair rate for {outcome.zip_code} comps."

    if buyer_verdict == "below_estimate":
        buyer_adj = f"Buyer paid less than estimated. Verify buyer buy box for {outcome.buyer_id}."

    return LearningReport(
        deal_id          = outcome.deal_id,
        address          = outcome.address,
        zip_code         = outcome.zip_code,
        asset_type       = outcome.asset_type,
        fee_gap          = fee_gap,
        repair_gap       = repair_gap,
        buyer_price_gap  = buyer_price_gap,
        mao_verdict      = mao_verdict,
        repair_verdict   = repair_verdict,
        buyer_verdict    = buyer_verdict,
        mao_adjustment   = mao_adj,
        repair_adjustment= repair_adj,
        buyer_adjustment = buyer_adj,
    )


# ─── Engine 2: Observation Generator ─────────────────────────────────────────

def generate_observation(outcome: DealOutcome, report: LearningReport) -> str:
    """
    Generate a structured market observation from a closed deal.
    Returns observation_id (OBS-XXXX).
    Step 4 of the learning protocol.
    """
    today   = date.today().isoformat()
    market  = f"{outcome.zip_code}"
    if outcome.notes:
        market_context = outcome.notes
    else:
        market_context = f"{outcome.asset_type} deal in {outcome.zip_code}"

    # Build insight lines
    insights = []
    if report.mao_adjustment:
        insights.append(f"MAO Calibration: {report.mao_adjustment}")
    if report.repair_adjustment:
        insights.append(f"Repair Calibration: {report.repair_adjustment}")
    if report.buyer_adjustment:
        insights.append(f"Buyer Pattern: {report.buyer_adjustment}")

    if not insights:
        insights.append(f"Deal closed as projected. MAO and repair estimates were accurate.")

    insight_text = "\n".join(f"- {i}" for i in insights)

    # Impact
    impact_lines = []
    if report.fee_gap > 0:
        impact_lines.append(f"Fee exceeded projection by ${report.fee_gap:,.0f}. Model performing well.")
    elif report.fee_gap < -5_000:
        impact_lines.append(f"Fee below projection by ${abs(report.fee_gap):,.0f}. Review MAO formula for {outcome.zip_code}.")
    if abs(report.repair_gap) > 10_000:
        direction = "over" if report.repair_gap > 0 else "under"
        impact_lines.append(f"Repairs {direction}-estimated by ${abs(report.repair_gap):,.0f}. Adjust fast-repair rate.")

    impact_text = "\n".join(f"- {i}" for i in impact_lines) if impact_lines else "- No material model impact identified."

    # Action
    action_lines = []
    if report.mao_adjustment:
        action_lines.append(f"Update MAO calibration note in observations for ZIP {outcome.zip_code}.")
    if report.buyer_adjustment:
        action_lines.append(f"Review buyer file {outcome.buyer_id} — confirm buy box accuracy.")
    if report.repair_adjustment:
        action_lines.append(f"Update comp_intelligence.py repair rate or add corridor note.")
    action_lines.append(f"Record deal result in deal-results/.")

    action_text = "\n".join(f"- {a}" for a in action_lines)

    content = f"""# Closed Deal — {outcome.address}

## Market
{market}

## Insight
**Projected vs. Actual:**
- Fee: projected ${outcome.projected_fee:,.0f} → actual ${outcome.actual_fee:,.0f} ({report.mao_verdict})
- Repairs: projected ${outcome.projected_repairs:,.0f} → actual ${outcome.actual_repairs:,.0f} ({report.repair_verdict})
- Buyer Price: projected ${outcome.projected_buyer_price:,.0f} → actual ${outcome.actual_buyer_price:,.0f} ({report.buyer_verdict})

**Calibration Notes:**
{insight_text}

## Impact
{impact_text}

## Action
{action_text}

---

- **Deal ID:** {outcome.deal_id}
- **Buyer:** {outcome.buyer_id} — {outcome.buyer_name}
- **Closed:** {outcome.closed_date or today}
- **Asset Type:** {outcome.asset_type}
"""

    obs_id = append_observation(content, topic=f"Closed_{outcome.deal_id}")
    report.observation_id = obs_id or f"OBS-{uuid.uuid4().hex[:4].upper()}"
    return report.observation_id


# ─── Engine 3: Buyer Update Engine ───────────────────────────────────────────

def update_buyer_from_outcome(outcome: DealOutcome, report: LearningReport) -> list[str]:
    """
    Update buyer vault file with new deal activity and buy box refinements.
    Returns list of updated file paths.
    Step 3 of the learning protocol.
    """
    updated = []
    buyer_files = list_vault("buyers")

    for path in buyer_files:
        if path.name == "TEMPLATE.md":
            continue
        stem = path.stem.upper()
        if outcome.buyer_id.upper() not in stem:
            continue

        content = path.read_text(encoding="utf-8")
        lines   = content.splitlines()

        today = date.today().isoformat()

        # Append to deal activity section if present
        new_lines = []
        in_activity = False
        deal_line_added = False

        for line in lines:
            new_lines.append(line)
            if "## Deal Activity" in line:
                in_activity = True
            if in_activity and not deal_line_added and line.strip().startswith("- **12mo:**"):
                # Insert new deal record after activity header
                deal_line_added = True
            if in_activity and "## " in line and "Deal Activity" not in line:
                if not deal_line_added:
                    new_lines.insert(-1, f"- **Last Deal:** {today} — {outcome.address} (${outcome.actual_fee:,.0f} fee)")
                    deal_line_added = True
                in_activity = False

        if not deal_line_added:
            new_lines.append(f"\n- **Last Deal:** {today} — {outcome.address} (${outcome.actual_fee:,.0f} fee)")

        # Append calibration note
        if report.buyer_adjustment:
            new_lines.append(f"\n<!-- Learning note {today}: {report.buyer_adjustment} -->")

        path.write_text("\n".join(new_lines), encoding="utf-8")
        updated.append(str(path))

    report.vault_updates.extend(updated)
    return updated


# ─── Engine 4: Market Update Engine ──────────────────────────────────────────

def update_market_from_outcome(outcome: DealOutcome, report: LearningReport) -> list[str]:
    """
    Update ZIP corridor and market vault files with closed deal data.
    Returns list of updated file paths.
    Step 4 (market portion) of the learning protocol.
    """
    updated = []
    corridor_files = list_vault("zip-corridors")
    today = date.today().isoformat()

    for path in corridor_files:
        content = path.read_text(encoding="utf-8")
        if outcome.zip_code not in content:
            continue

        # Append a note to the corridor file
        note = f"\n\n<!-- Deal closed {today}: {outcome.address} | fee ${outcome.actual_fee:,.0f} | {outcome.asset_type} -->"
        if report.mao_adjustment:
            note += f"\n<!-- MAO note: {report.mao_adjustment} -->"

        path.write_text(content + note, encoding="utf-8")
        updated.append(str(path))

    report.vault_updates.extend(updated)
    return updated


# ─── Engine 5: Markdown Sync ──────────────────────────────────────────────────

def record_deal_result(outcome: DealOutcome, report: LearningReport) -> str:
    """
    Write a closed deal record to deal-results/ vault.
    Returns filename of created record.
    Step 1 of the learning protocol.
    """
    today    = date.today().isoformat()
    result_id = next_id("RESULT", "deal-results")
    slug     = "".join(c if c.isalnum() else "_" for c in outcome.address)[:30]
    filename = f"{result_id}_{slug}.md"

    content = f"""# {outcome.address}

## Result Summary
- **Deal ID:** {outcome.deal_id}
- **Closed:** {outcome.closed_date or today}
- **Asset Type:** {outcome.asset_type}
- **Buyer:** {outcome.buyer_id} — {outcome.buyer_name}

## Financial Outcome
| | Projected | Actual | Gap |
|---|---|---|---|
| Contract Price | ${outcome.projected_mao:,.0f} | ${outcome.actual_contract_price:,.0f} | ${outcome.actual_contract_price - outcome.projected_mao:+,.0f} |
| Buyer Price | ${outcome.projected_buyer_price:,.0f} | ${outcome.actual_buyer_price:,.0f} | ${outcome.buyer_price_gap:+,.0f} |
| Repairs | ${outcome.projected_repairs:,.0f} | ${outcome.actual_repairs:,.0f} | ${report.repair_gap:+,.0f} |
| Assignment Fee | ${outcome.projected_fee:,.0f} | ${outcome.actual_fee:,.0f} | ${report.fee_gap:+,.0f} |

## Verdicts
- MAO Accuracy: **{report.mao_verdict}**
- Repair Accuracy: **{report.repair_verdict}**
- Buyer Price Accuracy: **{report.buyer_verdict}**

## Calibration Notes
{report.mao_adjustment or 'None'}
{report.repair_adjustment or ''}
{report.buyer_adjustment or ''}

## Observation
{report.observation_id or 'Not yet logged'}

## Notes
{outcome.notes or 'None'}
"""
    write_vault_file("deal-results", filename, content)
    report.vault_updates.append(f"deal-results/{filename}")
    return filename


# ─── Full Learning Protocol ───────────────────────────────────────────────────

def run_full_learning_protocol(outcome: DealOutcome) -> LearningReport:
    """
    Run all 5 learning steps for a closed deal:
    1. Intake — compute gaps and verdicts
    2. Record deal result to vault
    3. Update buyer vault file
    4. Generate market observation
    5. Update ZIP corridor files

    Returns complete LearningReport.
    """
    # Step 1: Intake
    report = intake_closed_deal(outcome)

    # Step 2: Record deal result
    record_deal_result(outcome, report)

    # Step 3: Update buyer
    update_buyer_from_outcome(outcome, report)

    # Step 4: Generate observation (includes market impact)
    generate_observation(outcome, report)

    # Step 5: Update market/corridor files
    update_market_from_outcome(outcome, report)

    return report


# ─── Market Shift Event ───────────────────────────────────────────────────────

@dataclass
class MarketShiftSignal:
    zip_code:         str
    signal_type:      str       # buyer_pullback / price_compression / demand_surge / no_buyers
    description:      str
    recommended_action: str


def log_market_shift(signal: MarketShiftSignal) -> str:
    """Log a market shift observation to the vault. Returns observation_id."""
    today = date.today().isoformat()
    content = f"""# Market Shift — {signal.zip_code}

## Market
{signal.zip_code}

## Insight
Signal: **{signal.signal_type.replace('_', ' ').title()}**

{signal.description}

## Impact
This signal may affect MAO calculations and buyer matching for ZIP {signal.zip_code}.

## Action
{signal.recommended_action}

---

- **Date:** {today}
- **Signal Type:** {signal.signal_type}
"""
    return append_observation(content, topic=f"MarketShift_{signal.zip_code}_{today}")


# ─── No-Buyer Signal ─────────────────────────────────────────────────────────

def log_no_buyer_signal(zip_code: str, asset_type: str, count: int = 1) -> None:
    """
    Log that N leads in a ZIP had no buyer match.
    Triggers a market observation if count >= 3.
    """
    if count < 3:
        return

    signal = MarketShiftSignal(
        zip_code   = zip_code,
        signal_type = "no_buyers",
        description = (
            f"{count} leads in ZIP {zip_code} ({asset_type}) found no buyer match "
            f"in the past session. This may indicate the buyer vault is missing "
            f"active buyers for this corridor."
        ),
        recommended_action = (
            f"Run PropStream buyer search for ZIP {zip_code}. "
            f"Check BuyerVault for inactive or paused buyers. "
            f"Consider expanding ZIP tolerance for nearby active buyers."
        ),
    )
    log_market_shift(signal)
