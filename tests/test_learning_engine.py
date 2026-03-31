"""Tests for Learning Engine — feedback loop, intake, and verdicts."""

import pytest
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.learning_engine import (
    DealOutcome,
    intake_closed_deal,
    LearningReport,
)


def make_outcome(**kwargs):
    defaults = dict(
        deal_id               = "DEAL-TEST",
        address               = "100 Learn St",
        zip_code              = "77008",
        asset_type            = "SFR",
        buyer_id              = "BUY-001",
        buyer_name            = "Test Buyer",
        projected_buyer_price = 200_000,
        projected_repairs     = 30_000,
        projected_mao         = 155_000,
        projected_fee         = 15_000,
        actual_contract_price = 155_000,
        actual_buyer_price    = 200_000,
        actual_repairs        = 28_000,
        actual_fee            = 17_000,
        closed_date           = date(2026, 3, 15),
    )
    defaults.update(kwargs)
    return DealOutcome(**defaults)


class TestIntakeClosedDeal:
    def test_positive_fee_gap_when_actual_higher(self):
        outcome = make_outcome(projected_fee=15_000, actual_fee=17_000)
        report  = intake_closed_deal(outcome)
        assert report.fee_gap == 2_000

    def test_negative_fee_gap_when_actual_lower(self):
        outcome = make_outcome(projected_fee=15_000, actual_fee=12_000)
        report  = intake_closed_deal(outcome)
        assert report.fee_gap == -3_000

    def test_repair_gap_positive_when_over_estimated(self):
        outcome = make_outcome(projected_repairs=30_000, actual_repairs=20_000)
        report  = intake_closed_deal(outcome)
        assert report.repair_gap == 10_000  # over-estimated by 10k

    def test_repair_gap_negative_when_under_estimated(self):
        outcome = make_outcome(projected_repairs=20_000, actual_repairs=35_000)
        report  = intake_closed_deal(outcome)
        assert report.repair_gap == -15_000

    def test_mao_verdict_accurate_for_small_gap(self):
        outcome = make_outcome(projected_fee=15_000, actual_fee=15_500)
        report  = intake_closed_deal(outcome)
        assert report.mao_verdict == "accurate"

    def test_mao_verdict_worse_for_big_negative_gap(self):
        outcome = make_outcome(projected_fee=15_000, actual_fee=5_000)
        report  = intake_closed_deal(outcome)
        assert "worse" in report.mao_verdict

    def test_mao_verdict_better_for_big_positive_gap(self):
        outcome = make_outcome(projected_fee=10_000, actual_fee=25_000)
        report  = intake_closed_deal(outcome)
        assert "better" in report.mao_verdict

    def test_repair_verdict_over_estimated(self):
        outcome = make_outcome(projected_repairs=30_000, actual_repairs=10_000)
        report  = intake_closed_deal(outcome)
        assert report.repair_verdict == "over_estimated"

    def test_repair_verdict_under_estimated(self):
        outcome = make_outcome(projected_repairs=15_000, actual_repairs=40_000)
        report  = intake_closed_deal(outcome)
        assert report.repair_verdict == "under_estimated"

    def test_repair_verdict_accurate(self):
        outcome = make_outcome(projected_repairs=30_000, actual_repairs=31_000)
        report  = intake_closed_deal(outcome)
        assert report.repair_verdict == "accurate"

    def test_mao_adjustment_when_worse_than_projected(self):
        outcome = make_outcome(projected_fee=15_000, actual_fee=5_000)
        report  = intake_closed_deal(outcome)
        assert report.mao_adjustment != ""
        assert "lower" in report.mao_adjustment.lower() or "overstated" in report.mao_adjustment.lower()

    def test_repair_adjustment_when_under_estimated(self):
        outcome = make_outcome(projected_repairs=15_000, actual_repairs=40_000)
        report  = intake_closed_deal(outcome)
        assert report.repair_adjustment != ""

    def test_buyer_gap_computed(self):
        outcome = make_outcome(
            projected_buyer_price=200_000, actual_buyer_price=190_000
        )
        report = intake_closed_deal(outcome)
        assert report.buyer_price_gap == -10_000

    def test_report_has_all_fields(self):
        outcome = make_outcome()
        report  = intake_closed_deal(outcome)
        assert report.deal_id == "DEAL-TEST"
        assert report.address == "100 Learn St"
        assert report.zip_code == "77008"
        assert isinstance(report.events, list)
        assert isinstance(report.vault_updates, list)
