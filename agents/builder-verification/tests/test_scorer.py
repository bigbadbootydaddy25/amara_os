"""Tests for the confidence scoring engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import BuyerProfile, DetectedSignal, OwnerRecord
from confidence_scorer import compute_scores


def make_profile(*signal_types: str, parcel_count: int = 1) -> BuyerProfile:
    profile = BuyerProfile(owner_name="TEST OWNER LLC")
    for i in range(parcel_count):
        profile.parcel_ids.append(f"P{i}")
        profile.records.append(
            OwnerRecord(parcel_id=f"P{i}", owner_name="TEST OWNER LLC")
        )
    for st in signal_types:
        profile.signals.append(DetectedSignal(
            signal_type=st, value=st, weight=10, evidence=f"test signal {st}",
        ))
    return profile


class TestComputeScores:
    def test_builder_signals_contribute_to_builder_score(self):
        p = make_profile("LLC_COMPANY", "BUILDER_KEYWORD", "PERMIT_ACTIVITY")
        compute_scores(p)
        assert p.builder_score > 0

    def test_investor_signals_contribute_to_investor_score(self):
        p = make_profile("LLC_COMPANY", "MAILING_MISMATCH", "REPEAT_ACQUISITIONS")
        compute_scores(p)
        assert p.investor_score > 0

    def test_score_capped_at_100(self):
        # All possible builder signals at once
        all_builder = [
            "LLC_COMPANY", "BUILDER_KEYWORD", "VACANT_LAND", "PERMIT_ACTIVITY",
            "MULTIPLE_NEARBY_PARCELS", "VACANT_LAND_CONCENTRATION", "INFILL_ACTIVITY",
            "REPEAT_ACQUISITIONS", "RECENT_PURCHASE_CLUSTERING",
        ]
        p = make_profile(*all_builder)
        compute_scores(p)
        assert p.builder_score <= 100

    def test_no_signals_zero_score(self):
        p = make_profile()
        compute_scores(p)
        assert p.builder_score == 0
        assert p.investor_score == 0

    def test_each_signal_type_counted_once(self):
        # Two signals of the same type should not double-count
        p = BuyerProfile(owner_name="DUPE LLC")
        p.parcel_ids.append("P1")
        p.records.append(OwnerRecord(parcel_id="P1", owner_name="DUPE LLC"))
        p.signals.append(DetectedSignal("LLC_COMPANY", "LLC", 15, "first"))
        p.signals.append(DetectedSignal("LLC_COMPANY", "LLC", 15, "second"))
        compute_scores(p)
        # LLC_COMPANY builder weight = 15; should not be 30
        assert p.builder_score == 15

    def test_parcel_count_bonus(self):
        p1 = make_profile("LLC_COMPANY", parcel_count=1)
        p5 = make_profile("LLC_COMPANY", parcel_count=5)
        compute_scores(p1)
        compute_scores(p5)
        assert p5.builder_score > p1.builder_score

    def test_infill_activity_in_builder_score(self):
        p = make_profile("INFILL_ACTIVITY")
        compute_scores(p)
        assert p.builder_score == 25  # INFILL_ACTIVITY weight = 25

    def test_investor_keyword_in_investor_score(self):
        p = make_profile("INVESTOR_KEYWORD")
        compute_scores(p)
        assert p.investor_score == 15
        assert p.builder_score == 0  # INVESTOR_KEYWORD doesn't affect builder

    def test_signal_not_in_either_category_ignored(self):
        p = make_profile("UNKNOWN_SIGNAL_XYZ")
        compute_scores(p)
        assert p.builder_score == 0
        assert p.investor_score == 0
