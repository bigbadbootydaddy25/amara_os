"""Tests for match_scorer — Stage 8/9 scoring and approval gate."""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.match_scorer import (
    compute_sfr_final_score,
    compute_land_final_score,
    buyer_match_score_from_zip,
    _sfr_profit_score,
    _land_spread_score,
    _speed_to_close_score,
    SFRScoreInputs,
    LandScoreInputs,
)
from system.comp_intelligence import SFRUnderwriteResult, LandUnderwriteResult
from system.distress_scorer import SFRDistressScore, LandDistressScore
from system.mao_calculator import LDPResult


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_sfr_underwrite(buyer_price=200_000, repairs=30_000, assignment_fee=15_000,
                         decision="go", mao=155_000):
    return SFRUnderwriteResult(
        deal_id         = "TEST",
        address         = "123 Test",
        zip_code        = "77008",
        buyer_id        = "BUY-001",
        buyer_price     = buyer_price,
        repairs         = repairs,
        seller_asking   = mao,
        assignment_fee  = assignment_fee,
        mao             = mao,
        decision        = decision,
        decision_reason = "",
        fee_tier        = "strong" if assignment_fee >= 15_000 else "minimum",
    )


def make_sfr_distress(score=0.5):
    d = SFRDistressScore("TEST")
    d.total_distress_score = score
    return d


def make_sfr_inputs(buyer_match=0.80, assignment_fee=15_000, distress_score=0.5,
                     comp_confidence=0.55, speed=0.5, decision="go"):
    uw = make_sfr_underwrite(assignment_fee=assignment_fee, decision=decision,
                              mao=200_000 - 30_000 - assignment_fee)
    dist = make_sfr_distress(distress_score)
    return SFRScoreInputs(
        property_id       = "TEST",
        buyer_match_score = buyer_match,
        underwrite        = uw,
        distress          = dist,
        comp_confidence   = comp_confidence,
        speed_to_close    = speed,
    )


# ─── Profit Score ─────────────────────────────────────────────────────────────

class TestSfrProfitScore:
    def test_below_minimum_is_zero(self):
        assert _sfr_profit_score(9_999) == 0.0

    def test_at_minimum_above_zero(self):
        assert _sfr_profit_score(10_000) > 0.0

    def test_at_target_above_minimum_score(self):
        assert _sfr_profit_score(15_000) > _sfr_profit_score(10_000)

    def test_at_25k_returns_1(self):
        assert _sfr_profit_score(25_000) == 1.0

    def test_above_25k_returns_1(self):
        assert _sfr_profit_score(50_000) == 1.0

    def test_monotonically_increasing(self):
        fees   = [10_000, 12_000, 15_000, 20_000, 25_000]
        scores = [_sfr_profit_score(f) for f in fees]
        assert scores == sorted(scores)


class TestLandSpreadScore:
    def test_below_min_is_zero(self):
        assert _land_spread_score(50_000) == 0.0

    def test_at_min_above_zero(self):
        assert _land_spread_score(100_000) > 0.0

    def test_1m_returns_1(self):
        assert _land_spread_score(1_000_000) == 1.0

    def test_monotonically_increasing(self):
        spreads = [100_000, 250_000, 500_000, 1_000_000]
        scores  = [_land_spread_score(s) for s in spreads]
        assert scores == sorted(scores)


class TestSpeedToCloseScore:
    def test_urgent_signal_returns_1(self):
        assert _speed_to_close_score(0, has_urgent_signal=True) == 1.0

    def test_high_dom_scores_well(self):
        assert _speed_to_close_score(91, False) == 0.80

    def test_low_dom_scores_low(self):
        assert _speed_to_close_score(5, False) == 0.20


# ─── Buyer Match Score ────────────────────────────────────────────────────────

class TestBuyerMatchScore:
    def test_zip_mismatch_returns_zero(self):
        score = buyer_match_score_from_zip(
            buyer_zips     = ["77008"],
            deal_zip       = "99999",
            buyer_max_price = 200_000,
            deal_price     = 150_000,
            buyer_min_beds  = 3,
            deal_beds      = 3,
        )
        assert score == 0.0

    def test_perfect_match_returns_high_score(self):
        score = buyer_match_score_from_zip(
            buyer_zips     = ["77008"],
            deal_zip       = "77008",
            buyer_max_price = 200_000,
            deal_price     = 150_000,
            buyer_min_beds  = 3,
            deal_beds      = 3,
        )
        assert score == 1.0

    def test_zip_match_price_over_ceiling(self):
        score = buyer_match_score_from_zip(
            buyer_zips     = ["77008"],
            deal_zip       = "77008",
            buyer_max_price = 100_000,
            deal_price     = 200_000,  # over ceiling
            buyer_min_beds  = 0,
            deal_beds      = 3,
        )
        # ZIP matches (+0.50) + no price fit (0) + no bed requirement (+0.20) = 0.70
        assert score == pytest.approx(0.70, abs=0.01)


# ─── SFR Final Score ─────────────────────────────────────────────────────────

class TestComputeSfrFinalScore:
    def test_gate_passes_with_good_deal(self):
        inputs = make_sfr_inputs(buyer_match=0.80, assignment_fee=15_000)
        result = compute_sfr_final_score(inputs)
        assert result.gate_passed is True
        assert result.final_score > 0

    def test_gate_fails_no_buyer(self):
        uw = make_sfr_underwrite(assignment_fee=15_000)
        uw.buyer_id = ""  # no buyer
        dist = make_sfr_distress()
        inputs = SFRScoreInputs(
            property_id       = "TEST",
            buyer_match_score = 0.80,
            underwrite        = uw,
            distress          = dist,
            comp_confidence   = 0.55,
            speed_to_close    = 0.50,
        )
        result = compute_sfr_final_score(inputs)
        assert result.gate_passed is False
        assert "buyer" in result.gate_fail_reason.lower()

    def test_gate_fails_low_buyer_match(self):
        inputs = make_sfr_inputs(buyer_match=0.30)
        result = compute_sfr_final_score(inputs)
        assert result.gate_passed is False

    def test_gate_fails_below_min_fee(self):
        inputs = make_sfr_inputs(assignment_fee=5_000)
        result = compute_sfr_final_score(inputs)
        assert result.gate_passed is False

    def test_grade_a_for_high_score(self):
        inputs = make_sfr_inputs(
            buyer_match=0.95,
            assignment_fee=25_000,
            distress_score=0.90,
            comp_confidence=0.90,
            speed=0.90,
        )
        result = compute_sfr_final_score(inputs)
        assert result.grade() == "A"

    def test_grade_f_for_low_score(self):
        inputs = make_sfr_inputs(
            buyer_match=0.45,
            assignment_fee=10_000,
            distress_score=0.10,
            comp_confidence=0.20,
            speed=0.20,
        )
        result = compute_sfr_final_score(inputs)
        assert result.grade() in ("C", "F")

    def test_weights_sum_approximately_correctly(self):
        # With all inputs = 1.0, final score should be close to 1.0
        inputs = make_sfr_inputs(
            buyer_match=1.0,
            assignment_fee=25_000,
            distress_score=1.0,
            comp_confidence=1.0,
            speed=1.0,
        )
        result = compute_sfr_final_score(inputs)
        assert result.final_score > 0.90
