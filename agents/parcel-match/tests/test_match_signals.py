"""Tests for match signal detectors."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import LoadedBuyerProfile, Parcel
from match_signals import (
    compute_match_score,
    detect_distressed_match,
    detect_entity_type_match,
    detect_high_score,
    detect_infill_opportunity,
    detect_land_use_alignment,
    detect_nearby_builder_activity,
    detect_permit_alignment,
    detect_price_fit,
    detect_recent_area_activity,
    detect_zip_match,
    BUYER_SIGNAL_WEIGHTS,
)


def make_parcel(**kwargs) -> Parcel:
    defaults = dict(
        parcel_id="P-TEST",
        address="100 TEST ST",
        zip_code="85001",
        land_use="SINGLE FAMILY",
        is_vacant=False,
        asking_price=200000,
        sale_price=180000,
        acres=0.2,
        distressed=False,
        permit_count=0,
    )
    defaults.update(kwargs)
    return Parcel(**{k: v for k, v in defaults.items() if k in Parcel.__dataclass_fields__})


def make_profile(**kwargs) -> LoadedBuyerProfile:
    defaults = dict(
        owner_name="TEST BUYER LLC",
        parcel_count=3,
        zip_codes=["85001"],
        acquisition_dates=["2025-06-01", "2025-07-01"],
        total_spend=600000,
        builder_score=80,
        investor_score=70,
        is_verified_builder=True,
        is_possible_cash_buyer=True,
        is_quarantined=False,
        signal_types=["LLC_COMPANY", "BUILDER_KEYWORD", "PERMIT_ACTIVITY"],
    )
    defaults.update(kwargs)
    return LoadedBuyerProfile(**defaults)


class TestZipMatch:
    def test_matching_zip(self):
        p = make_parcel(zip_code="85001")
        b = make_profile(zip_codes=["85001", "85002"])
        sigs = detect_zip_match(p, b)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "ZIP_MATCH"
        assert sigs[0].weight == BUYER_SIGNAL_WEIGHTS["ZIP_MATCH"]

    def test_non_matching_zip(self):
        p = make_parcel(zip_code="99999")
        b = make_profile(zip_codes=["85001"])
        assert detect_zip_match(p, b) == []

    def test_empty_parcel_zip(self):
        p = make_parcel(zip_code="")
        b = make_profile(zip_codes=["85001"])
        assert detect_zip_match(p, b) == []


class TestPriceFit:
    def test_price_in_range(self):
        p = make_parcel(asking_price=100000)
        b = make_profile(parcel_count=2, total_spend=200000)  # avg=100k, range 60k-140k
        sigs = detect_price_fit(p, b)
        types = [s.signal_type for s in sigs]
        assert "PRICE_FIT" in types

    def test_price_below_avg_bonus(self):
        p = make_parcel(asking_price=80000)
        b = make_profile(parcel_count=2, total_spend=200000)  # avg=100k
        sigs = detect_price_fit(p, b)
        types = [s.signal_type for s in sigs]
        assert "PRICE_BELOW_AVG" in types

    def test_price_out_of_range(self):
        p = make_parcel(asking_price=500000)
        b = make_profile(parcel_count=2, total_spend=200000)  # avg=100k, range 60k-140k
        sigs = detect_price_fit(p, b)
        assert not any(s.signal_type == "PRICE_FIT" for s in sigs)

    def test_no_signal_when_price_unknown(self):
        p = make_parcel(asking_price=0, sale_price=0)
        b = make_profile(parcel_count=2, total_spend=200000)
        assert detect_price_fit(p, b) == []

    def test_no_signal_when_buyer_no_spend(self):
        p = make_parcel(asking_price=100000)
        b = make_profile(parcel_count=0, total_spend=0)
        assert detect_price_fit(p, b) == []


class TestLandUseAlignment:
    def test_vacant_to_builder(self):
        p = make_parcel(is_vacant=True, land_use="VACANT LAND")
        b = make_profile(is_verified_builder=True, is_possible_cash_buyer=False)
        sigs = detect_land_use_alignment(p, b)
        assert any(s.signal_type == "LAND_USE_ALIGNMENT" for s in sigs)

    def test_improved_to_investor(self):
        p = make_parcel(is_vacant=False, land_use="SINGLE FAMILY")
        b = make_profile(is_verified_builder=False, is_possible_cash_buyer=True)
        sigs = detect_land_use_alignment(p, b)
        assert any(s.signal_type == "LAND_USE_ALIGNMENT" for s in sigs)

    def test_vacant_to_investor_no_signal(self):
        p = make_parcel(is_vacant=True)
        b = make_profile(is_verified_builder=False, is_possible_cash_buyer=True)
        sigs = detect_land_use_alignment(p, b)
        assert sigs == []


class TestInfillOpportunity:
    def test_vacant_plus_builder_signals(self):
        p = make_parcel(is_vacant=True)
        b = make_profile(builder_score=80, signal_types=["PERMIT_ACTIVITY"])
        sigs = detect_infill_opportunity(p, b)
        assert any(s.signal_type == "INFILL_OPPORTUNITY" for s in sigs)

    def test_not_vacant_no_signal(self):
        p = make_parcel(is_vacant=False)
        b = make_profile(builder_score=80)
        assert detect_infill_opportunity(p, b) == []

    def test_vacant_low_builder_score_no_signal(self):
        p = make_parcel(is_vacant=True)
        b = make_profile(builder_score=10, signal_types=[])
        assert detect_infill_opportunity(p, b) == []


class TestRecentAreaActivity:
    def test_recent_purchase_in_zip(self):
        from datetime import date, timedelta
        recent = (date.today() - timedelta(days=30)).isoformat()
        p = make_parcel(zip_code="85001")
        b = make_profile(zip_codes=["85001"], acquisition_dates=[recent])
        sigs = detect_recent_area_activity(p, b)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "RECENT_AREA_ACTIVITY"

    def test_old_purchase_no_signal(self):
        p = make_parcel(zip_code="85001")
        b = make_profile(zip_codes=["85001"], acquisition_dates=["2010-01-01"])
        assert detect_recent_area_activity(p, b) == []

    def test_wrong_zip_no_signal(self):
        from datetime import date, timedelta
        recent = (date.today() - timedelta(days=30)).isoformat()
        p = make_parcel(zip_code="99999")
        b = make_profile(zip_codes=["85001"], acquisition_dates=[recent])
        assert detect_recent_area_activity(p, b) == []


class TestNearbyBuilderActivity:
    def test_detects_builder_in_zip(self):
        p = make_parcel(zip_code="85001")
        builder = make_profile(zip_codes=["85001"], is_verified_builder=True)
        investor = make_profile(owner_name="INVESTOR LLC", zip_codes=["85001"], is_verified_builder=False)
        sigs = detect_nearby_builder_activity(p, [builder, investor])
        assert len(sigs) == 1
        assert sigs[0].signal_type == "NEARBY_BUILDER_ACTIVITY"

    def test_no_builder_in_zip(self):
        p = make_parcel(zip_code="85001")
        builder = make_profile(zip_codes=["99999"], is_verified_builder=True)
        assert detect_nearby_builder_activity(p, [builder]) == []

    def test_quarantined_builder_excluded(self):
        p = make_parcel(zip_code="85001")
        builder = make_profile(zip_codes=["85001"], is_verified_builder=True, is_quarantined=True)
        assert detect_nearby_builder_activity(p, [builder]) == []


class TestEntityTypeMatch:
    def test_llc_to_vacant(self):
        p = make_parcel(is_vacant=True, land_use="VACANT")
        b = make_profile(signal_types=["LLC_COMPANY"])
        sigs = detect_entity_type_match(p, b)
        assert any(s.signal_type == "ENTITY_TYPE_MATCH" for s in sigs)

    def test_llc_to_commercial(self):
        p = make_parcel(is_vacant=False, land_use="COMMERCIAL")
        b = make_profile(signal_types=["LLC_COMPANY"])
        sigs = detect_entity_type_match(p, b)
        assert any(s.signal_type == "ENTITY_TYPE_MATCH" for s in sigs)

    def test_no_llc_no_signal(self):
        p = make_parcel(is_vacant=True)
        b = make_profile(signal_types=["BUILDER_KEYWORD"])
        assert detect_entity_type_match(p, b) == []


class TestPermitAlignment:
    def test_vacant_plus_permit_history(self):
        p = make_parcel(is_vacant=True)
        b = make_profile(signal_types=["PERMIT_ACTIVITY"])
        sigs = detect_permit_alignment(p, b)
        assert any(s.signal_type == "PERMIT_ALIGNMENT" for s in sigs)

    def test_not_vacant_no_signal(self):
        p = make_parcel(is_vacant=False)
        b = make_profile(signal_types=["PERMIT_ACTIVITY"])
        assert detect_permit_alignment(p, b) == []


class TestDistressedMatch:
    def test_distressed_plus_cash_buyer(self):
        p = make_parcel(distressed=True)
        b = make_profile(is_possible_cash_buyer=True)
        sigs = detect_distressed_match(p, b)
        assert any(s.signal_type == "DISTRESSED_MATCH" for s in sigs)

    def test_not_distressed_no_signal(self):
        p = make_parcel(distressed=False)
        b = make_profile(is_possible_cash_buyer=True)
        assert detect_distressed_match(p, b) == []

    def test_distressed_no_cash_buyer_no_signal(self):
        p = make_parcel(distressed=True)
        b = make_profile(is_possible_cash_buyer=False)
        assert detect_distressed_match(p, b) == []


class TestComputeMatchScore:
    def test_sum_of_weights(self):
        from models import MatchSignal
        sigs = [
            MatchSignal("ZIP_MATCH", "85001", 25, "zip"),
            MatchSignal("PRICE_FIT", "$100k", 20, "price"),
        ]
        assert compute_match_score(sigs) == 45

    def test_capped_at_100(self):
        from models import MatchSignal
        sigs = [
            MatchSignal(t, "x", 25, "e")
            for t in ["ZIP_MATCH", "PRICE_FIT", "LAND_USE_ALIGNMENT",
                      "INFILL_OPPORTUNITY", "NEARBY_BUILDER_ACTIVITY"]
        ]
        assert compute_match_score(sigs) == 100

    def test_no_duplicate_signal_types(self):
        from models import MatchSignal
        sigs = [
            MatchSignal("ZIP_MATCH", "85001", 25, "first"),
            MatchSignal("ZIP_MATCH", "85001", 25, "second"),
        ]
        assert compute_match_score(sigs) == 25

    def test_empty_signals_zero(self):
        assert compute_match_score([]) == 0
