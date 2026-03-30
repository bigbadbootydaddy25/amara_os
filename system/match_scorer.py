"""
AMARA Auto Matcher — Stage 8: Final Match Score + Stage 9: Approval Gate

Stage 8: Computes weighted composite score for each deal.
Stage 9: Applies the approval gate — enforces buyer-first and minimum profit thresholds.

SFR final score:
  0.30 buyer_match_score
  0.25 profit_score
  0.20 distress_score
  0.15 comp_confidence
  0.10 speed_to_close_score

Land final score:
  0.30 builder_match_score
  0.25 spread_score
  0.20 dead_paper_score
  0.15 location_score
  0.10 ownership_score
"""

from __future__ import annotations

from dataclasses import dataclass
from system.config import SFR_MIN_ASSIGNMENT_FEE, LAND_MIN_SPREAD
from system.comp_intelligence import SFRUnderwriteResult, LandUnderwriteResult
from system.distress_scorer import SFRDistressScore, LandDistressScore


# ─── Score Inputs ─────────────────────────────────────────────────────────────

@dataclass
class SFRScoreInputs:
    property_id:        str
    buyer_match_score:  float       # 0.0–1.0 — how well deal fits buyer buy box
    underwrite:         SFRUnderwriteResult
    distress:           SFRDistressScore
    comp_confidence:    float       # 0.0–1.0 — quality of comp read
    speed_to_close:     float       # 0.0–1.0 — seller urgency / timeline


@dataclass
class LandScoreInputs:
    property_id:        str
    builder_match_score: float      # 0.0–1.0 — builder confirmed in corridor
    underwrite:         LandUnderwriteResult
    distress:           LandDistressScore
    location_score:     float       # 0.0–1.0 — expansion direction / infra confirmed
    ownership_score:    float       # 0.0–1.0 — clean title / motivated seller


# ─── Score Outputs ────────────────────────────────────────────────────────────

@dataclass
class SFRFinalScore:
    property_id:        str
    buyer_match_score:  float
    profit_score:       float
    distress_score:     float
    comp_confidence:    float
    speed_to_close:     float
    final_score:        float
    gate_passed:        bool
    gate_fail_reason:   str = ""

    def grade(self) -> str:
        if self.final_score >= 0.80: return "A"
        if self.final_score >= 0.65: return "B"
        if self.final_score >= 0.50: return "C"
        return "F"

    def summary(self) -> str:
        status = "APPROVED" if self.gate_passed else f"REJECTED — {self.gate_fail_reason}"
        return (
            f"SFR Score [{self.grade()}] {self.final_score:.2f} | {status}\n"
            f"  buyer_match={self.buyer_match_score:.2f}  profit={self.profit_score:.2f}  "
            f"distress={self.distress_score:.2f}  comps={self.comp_confidence:.2f}  "
            f"speed={self.speed_to_close:.2f}"
        )


@dataclass
class LandFinalScore:
    property_id:         str
    builder_match_score: float
    spread_score:        float
    dead_paper_score:    float
    location_score:      float
    ownership_score:     float
    final_score:         float
    gate_passed:         bool
    gate_fail_reason:    str = ""

    def grade(self) -> str:
        if self.final_score >= 0.80: return "A"
        if self.final_score >= 0.65: return "B"
        if self.final_score >= 0.50: return "C"
        return "F"

    def summary(self) -> str:
        status = "APPROVED" if self.gate_passed else f"REJECTED — {self.gate_fail_reason}"
        return (
            f"Land Score [{self.grade()}] {self.final_score:.2f} | {status}\n"
            f"  builder={self.builder_match_score:.2f}  spread={self.spread_score:.2f}  "
            f"dead_paper={self.dead_paper_score:.2f}  location={self.location_score:.2f}  "
            f"ownership={self.ownership_score:.2f}"
        )


# ─── Profit Score Helpers ─────────────────────────────────────────────────────

def _sfr_profit_score(assignment_fee: float) -> float:
    """
    Score 0.0–1.0 based on assignment fee.
    Floor: $10,000. Target: $15,000. Peak: $25,000+.
    """
    if assignment_fee < SFR_MIN_ASSIGNMENT_FEE:
        return 0.0
    if assignment_fee < 15_000:
        # $10k–$15k → 0.40–0.60
        return 0.40 + (assignment_fee - 10_000) / 5_000 * 0.20
    if assignment_fee < 20_000:
        # $15k–$20k → 0.60–0.80
        return 0.60 + (assignment_fee - 15_000) / 5_000 * 0.20
    if assignment_fee < 25_000:
        # $20k–$25k → 0.80–1.00
        return 0.80 + (assignment_fee - 20_000) / 5_000 * 0.20
    return 1.0


def _land_spread_score(spread: float) -> float:
    """
    Score 0.0–1.0 based on land spread.
    Floor: $100k. Preferred: $250k. Priority: $1M+.
    """
    if spread < LAND_MIN_SPREAD:
        return 0.0
    if spread < 250_000:
        return 0.40 + (spread - 100_000) / 150_000 * 0.20
    if spread < 500_000:
        return 0.60 + (spread - 250_000) / 250_000 * 0.20
    if spread < 1_000_000:
        return 0.80 + (spread - 500_000) / 500_000 * 0.15
    return 1.0


def _speed_to_close_score(dom: int, has_urgent_signal: bool) -> float:
    """Estimate how quickly this deal can close."""
    if has_urgent_signal:
        return 1.0
    if dom > 90:
        return 0.80   # seller probably motivated, flexible
    if dom > 30:
        return 0.50
    return 0.20       # fresh listing — seller not yet motivated


# ─── Stage 8: Score Computation ──────────────────────────────────────────────

def compute_sfr_final_score(inputs: SFRScoreInputs) -> SFRFinalScore:
    """
    Stage 8 (SFR): Compute weighted final score.

    Weights:
      0.30 buyer_match_score
      0.25 profit_score
      0.20 distress_score
      0.15 comp_confidence
      0.10 speed_to_close_score
    """
    profit_score = _sfr_profit_score(inputs.underwrite.assignment_fee)

    final = (
        inputs.buyer_match_score * 0.30
        + profit_score           * 0.25
        + inputs.distress.total_distress_score * 0.20
        + inputs.comp_confidence * 0.15
        + inputs.speed_to_close  * 0.10
    )

    # ── Stage 9: Approval gate ────────────────────────────────────────────────
    gate_passed    = False
    gate_fail      = ""

    if not inputs.underwrite.buyer_id:
        gate_fail = "No confirmed buyer"
    elif inputs.buyer_match_score < 0.40:
        gate_fail = f"Buyer match score {inputs.buyer_match_score:.2f} below 0.40 threshold"
    elif inputs.underwrite.assignment_fee < SFR_MIN_ASSIGNMENT_FEE:
        gate_fail = f"Assignment fee ${inputs.underwrite.assignment_fee:,.0f} below ${SFR_MIN_ASSIGNMENT_FEE:,.0f} minimum"
    elif inputs.underwrite.decision == "no_go":
        gate_fail = f"Underwriting no-go: {inputs.underwrite.decision_reason}"
    else:
        gate_passed = True

    return SFRFinalScore(
        property_id       = inputs.property_id,
        buyer_match_score = round(inputs.buyer_match_score, 3),
        profit_score      = round(profit_score, 3),
        distress_score    = round(inputs.distress.total_distress_score, 3),
        comp_confidence   = round(inputs.comp_confidence, 3),
        speed_to_close    = round(inputs.speed_to_close, 3),
        final_score       = round(final, 3),
        gate_passed       = gate_passed,
        gate_fail_reason  = gate_fail,
    )


def compute_land_final_score(inputs: LandScoreInputs) -> LandFinalScore:
    """
    Stage 8 (Land): Compute weighted final score.

    Weights:
      0.30 builder_match_score
      0.25 spread_score
      0.20 dead_paper_score
      0.15 location_score
      0.10 ownership_score
    """
    spread       = inputs.underwrite.ldp.spread if inputs.underwrite.ldp else 0
    spread_score = _land_spread_score(spread)
    dead_paper   = inputs.distress.total_distress_score

    final = (
        inputs.builder_match_score * 0.30
        + spread_score             * 0.25
        + dead_paper               * 0.20
        + inputs.location_score    * 0.15
        + inputs.ownership_score   * 0.10
    )

    # ── Stage 9: Approval gate ────────────────────────────────────────────────
    gate_passed = False
    gate_fail   = ""

    if inputs.builder_match_score == 0:
        gate_fail = "No confirmed builder or land buyer"
    elif spread < LAND_MIN_SPREAD:
        gate_fail = f"Spread ${spread:,.0f} below ${LAND_MIN_SPREAD:,.0f} minimum"
    elif not inputs.underwrite.is_go():
        gate_fail = f"Underwriting no-go: {inputs.underwrite.decision_reason}"
    else:
        gate_passed = True

    return LandFinalScore(
        property_id          = inputs.property_id,
        builder_match_score  = round(inputs.builder_match_score, 3),
        spread_score         = round(spread_score, 3),
        dead_paper_score     = round(dead_paper, 3),
        location_score       = round(inputs.location_score, 3),
        ownership_score      = round(inputs.ownership_score, 3),
        final_score          = round(final, 3),
        gate_passed          = gate_passed,
        gate_fail_reason     = gate_fail,
    )


def buyer_match_score_from_zip(
    buyer_zips: list[str],
    deal_zip: str,
    buyer_max_price: float,
    deal_price: float,
    buyer_min_beds: int,
    deal_beds: float,
) -> float:
    """
    Compute a simple 0.0–1.0 buyer match score from buy box criteria.
    Used when full buyer_matcher.py result is not available.
    """
    score = 0.0

    # ZIP match (highest weight)
    if deal_zip in buyer_zips:
        score += 0.50
    else:
        return 0.0  # ZIP miss = no match

    # Price fit
    if buyer_max_price > 0:
        if deal_price <= buyer_max_price:
            score += 0.30
        elif deal_price <= buyer_max_price * 1.10:
            score += 0.15  # within 10% — borderline
        # else 0

    # Beds
    if buyer_min_beds == 0 or deal_beds >= buyer_min_beds:
        score += 0.20

    return round(min(score, 1.0), 3)
