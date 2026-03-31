"""Tests for Buyer Discovery Engine — scoring, buy box inference, ZIP liquidity."""

import pytest
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.buyer_discovery import (
    BuyerTransaction,
    score_buyer,
    infer_buy_box,
    qualify_new_buyer,
    compute_zip_liquidity,
    _activity_score,
    _speed_score,
    _zip_concentration_score,
    _activity_level,
)
from system.config import ACTIVITY_HOT, ACTIVITY_WARM, ACTIVITY_COLD, ACTIVITY_UNKNOWN


TODAY = date(2026, 3, 30)


def make_txn(zip_code="77008", price=150_000, days_ago=30, beds=3, sqft=1400,
             is_cash=True, days_to_close=10):
    purchase_date = TODAY - timedelta(days=days_ago)
    return BuyerTransaction(
        address       = f"{days_ago} Test St",
        zip_code      = zip_code,
        purchase_date = purchase_date,
        purchase_price = price,
        beds          = beds,
        sqft          = sqft,
        is_cash       = is_cash,
        days_to_close = days_to_close,
    )


class TestActivityScore:
    def test_zero_for_no_transactions(self):
        assert _activity_score(0, 0) == 0.0

    def test_full_score_at_12_or_more(self):
        assert _activity_score(12, 12) == 1.0
        assert _activity_score(20, 20) == 1.0

    def test_partial_scores(self):
        assert _activity_score(3, 3) == 0.55
        assert _activity_score(5, 5) == 0.70

    def test_recent_fallback_to_24mo(self):
        assert _activity_score(0, 3) == 0.20
        assert _activity_score(0, 1) == 0.10


class TestSpeedScore:
    def test_unknown_speed_neutral(self):
        assert _speed_score(0) == 0.50

    def test_fast_buyer_high_score(self):
        assert _speed_score(7) == 1.0
        assert _speed_score(14) == 0.85

    def test_slow_buyer_low_score(self):
        assert _speed_score(45) == 0.40
        assert _speed_score(60) == 0.25


class TestZipConcentration:
    def test_single_zip_returns_1(self):
        txns = [make_txn(zip_code="77008") for _ in range(5)]
        assert _zip_concentration_score(txns) == 1.0

    def test_scattered_returns_low(self):
        txns = [make_txn(zip_code=str(i)) for i in range(10)]
        assert _zip_concentration_score(txns) <= 0.40

    def test_three_zips_returns_0_80(self):
        txns = (
            [make_txn(zip_code="77008") for _ in range(3)] +
            [make_txn(zip_code="77009") for _ in range(2)] +
            [make_txn(zip_code="77010")]
        )
        assert _zip_concentration_score(txns) == 0.80


class TestScoreBuyer:
    def test_active_buyer_high_score(self):
        txns  = [make_txn(days_ago=i*20) for i in range(12)]
        score = score_buyer("BUY-001", "Test Buyer", txns, today=TODAY)
        assert score.composite_score > 0.60
        assert score.txns_12mo == 12

    def test_inactive_buyer_low_score(self):
        txns  = [make_txn(days_ago=400), make_txn(days_ago=500)]
        score = score_buyer("BUY-002", "Inactive", txns, today=TODAY)
        assert score.txns_12mo == 0
        assert score.activity_score <= 0.20

    def test_activity_level_hot(self):
        txns  = [make_txn(days_ago=i*20) for i in range(7)]
        score = score_buyer("BUY-003", "Hot Buyer", txns, today=TODAY)
        assert score.activity_level == ACTIVITY_HOT

    def test_activity_level_cold(self):
        txns  = [make_txn(days_ago=400)]
        score = score_buyer("BUY-004", "Cold Buyer", txns, today=TODAY)
        assert score.activity_level == ACTIVITY_COLD

    def test_avg_price_computed(self):
        txns  = [make_txn(price=100_000), make_txn(price=200_000)]
        score = score_buyer("BUY-005", "Avg Buyer", txns, today=TODAY)
        assert score.avg_purchase_price == 150_000


class TestInferBuyBox:
    def test_returns_none_for_single_transaction(self):
        txns = [make_txn(price=150_000)]
        result = infer_buy_box("BUY-001", txns, today=TODAY)
        assert result is None

    def test_infers_price_range(self):
        txns = [
            make_txn(price=100_000),
            make_txn(price=150_000),
            make_txn(price=200_000),
        ]
        buy_box = infer_buy_box("BUY-001", txns, today=TODAY)
        assert buy_box is not None
        assert buy_box.min_price <= 100_000
        assert buy_box.max_price >= 200_000

    def test_confidence_increases_with_txn_count(self):
        few  = [make_txn(price=150_000) for _ in range(2)]
        many = [make_txn(price=150_000) for _ in range(10)]
        bb_few  = infer_buy_box("BUY-001", few,  today=TODAY)
        bb_many = infer_buy_box("BUY-001", many, today=TODAY)
        assert bb_many.confidence > bb_few.confidence


class TestQualifyNewBuyer:
    def test_rejects_insufficient_cash_txns(self):
        txns = [make_txn(is_cash=True)]  # only 1
        with pytest.raises(ValueError, match="Minimum 2 required"):
            qualify_new_buyer("Test Buyer", "Test LLC", txns)

    def test_accepts_two_cash_txns(self):
        txns = [make_txn(is_cash=True), make_txn(is_cash=True)]
        score, buy_box = qualify_new_buyer("Test Buyer", "Test LLC", txns, today=TODAY)
        assert score is not None

    def test_non_cash_txns_dont_count(self):
        txns = [
            make_txn(is_cash=False),
            make_txn(is_cash=False),
            make_txn(is_cash=True),
        ]
        with pytest.raises(ValueError):
            qualify_new_buyer("Test", "LLC", txns)


class TestComputeZipLiquidity:
    def test_no_transactions_yields_low_demand(self):
        snap = compute_zip_liquidity("77099", [], today=TODAY)
        # Speed component defaults to 0.50 neutral, so score will be > 0 but low
        assert snap.demand_score < 0.20
        assert snap.deal_count_90d == 0

    def test_recent_transactions_increase_demand(self):
        txns = [make_txn(zip_code="77008", days_ago=30) for _ in range(8)]
        snap = compute_zip_liquidity("77008", txns, today=TODAY)
        assert snap.demand_score > 0.0
        assert snap.deal_count_90d == 8

    def test_only_counts_correct_zip(self):
        txns = [
            make_txn(zip_code="77008", days_ago=10),
            make_txn(zip_code="77009", days_ago=10),
        ]
        snap = compute_zip_liquidity("77008", txns, today=TODAY)
        assert snap.deal_count_90d == 1
