"""Tests for MAO calculator — core deal math."""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.mao_calculator import (
    calculate_sfr_mao,
    calculate_sfr_mao_for_minimum,
    calculate_land_spread,
    calculate_ldp,
    what_buyer_price_is_needed,
    calculate_fee_at_price,
)
from system.config import SFR_MIN_ASSIGNMENT_FEE, SFR_TARGET_ASSIGNMENT_FEE


class TestCalculateSfrMao:
    def test_basic_mao(self):
        result = calculate_sfr_mao(
            buyer_price=200_000,
            repairs=30_000,
            assignment_fee=15_000,
        )
        assert result.mao == 155_000
        assert result.assignment_fee == 15_000
        assert result.buyer_price == 200_000

    def test_mao_equals_buyer_minus_repairs_minus_fee(self):
        result = calculate_sfr_mao(
            buyer_price=150_000,
            repairs=20_000,
            assignment_fee=10_000,
        )
        assert result.mao == 120_000

    def test_no_go_below_min_fee(self):
        # MAO at asking price would yield fee < $10k
        result = calculate_sfr_mao(
            buyer_price=100_000,
            repairs=89_000,    # leaves only $1k for fee
            assignment_fee=10_000,
        )
        # MAO = 100k - 89k - 10k = 1k (not a no-go on its own — MAO can be negative)
        assert result.mao == 1_000

    def test_negative_mao(self):
        result = calculate_sfr_mao(
            buyer_price=100_000,
            repairs=95_000,
            assignment_fee=15_000,
        )
        assert result.mao == -10_000

    def test_decision_go_when_fee_meets_target(self):
        result = calculate_sfr_mao(
            buyer_price=200_000,
            repairs=20_000,
            assignment_fee=15_000,
        )
        assert result.mao == 165_000


class TestCalculateSfrMaoForMinimum:
    def test_returns_mao_at_minimum_fee(self):
        result = calculate_sfr_mao_for_minimum(
            buyer_price=200_000,
            repairs=30_000,
        )
        # MAO = 200k - 30k - 10k = 160k
        assert result.mao == 160_000
        assert result.assignment_fee == SFR_MIN_ASSIGNMENT_FEE


class TestCalculateLandSpread:
    def test_positive_spread(self):
        result = calculate_land_spread(
            retail_value=500_000,
            acquisition_cost=200_000,
        )
        assert result.spread == 300_000

    def test_zero_spread(self):
        result = calculate_land_spread(
            retail_value=200_000,
            acquisition_cost=200_000,
        )
        assert result.spread == 0

    def test_negative_spread(self):
        result = calculate_land_spread(
            retail_value=150_000,
            acquisition_cost=200_000,
        )
        assert result.spread == -50_000


class TestCalculateLdp:
    def test_ldp_basic(self):
        result = calculate_ldp(
            acres=10.0,
            median_home_price=350_000,
            asking_price=500_000,
        )
        assert result.spread == result.max_land_value - 500_000
        assert result.gross_value > 0
        assert result.max_land_value > 0

    def test_ldp_spread_positive_for_cheap_land(self):
        result = calculate_ldp(
            acres=20.0,
            median_home_price=400_000,
            asking_price=100_000,
        )
        assert result.spread > 0

    def test_ldp_spread_negative_for_expensive_land(self):
        result = calculate_ldp(
            acres=1.0,
            median_home_price=200_000,
            asking_price=5_000_000,
        )
        assert result.spread < 0


class TestWhatBuyerPriceIsNeeded:
    def test_basic(self):
        needed = what_buyer_price_is_needed(
            offer_price=120_000,
            repairs=20_000,
            target_fee=15_000,
        )
        # buyer_price = offer_price + repairs + fee = 155_000
        assert needed == 155_000

    def test_minimum_fee(self):
        needed = what_buyer_price_is_needed(
            offer_price=100_000,
            repairs=15_000,
            target_fee=10_000,
        )
        assert needed == 125_000


class TestCalculateFeeAtPrice:
    def test_fee_at_price(self):
        # fee = buyer_price - repairs - offer_price
        fee = calculate_fee_at_price(
            offer_price=150_000,
            buyer_price=200_000,
            repairs=30_000,
        )
        assert fee == 20_000

    def test_zero_fee(self):
        fee = calculate_fee_at_price(
            offer_price=120_000,
            buyer_price=150_000,
            repairs=30_000,
        )
        assert fee == 0

    def test_negative_fee_returned(self):
        fee = calculate_fee_at_price(
            offer_price=100_000,
            buyer_price=100_000,
            repairs=50_000,
        )
        assert fee == -50_000
