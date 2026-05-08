"""Tests for signal detection logic in signals.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import BuyerProfile, OwnerRecord
from signals import (
    detect_builder_keywords,
    detect_infill_activity,
    detect_investor_keywords,
    detect_llc_company,
    detect_mailing_mismatch,
    detect_multiple_nearby_parcels,
    detect_permit_activity,
    detect_recent_purchase_clustering,
    detect_repeat_acquisitions,
    detect_round_price,
    detect_vacant_land,
    detect_vacant_land_concentration,
)


def make_record(**kwargs) -> OwnerRecord:
    defaults = dict(
        parcel_id="TEST-001",
        owner_name="TEST OWNER LLC",
        mailing_address="100 MAIN ST PHOENIX AZ 85001",
        property_address="200 ELM ST PHOENIX AZ 85001",
        sale_date="2024-01-01",
        sale_price=100000,
        land_use="SINGLE FAMILY",
        city="PHOENIX",
        state="AZ",
        zip_code="85001",
        permit_count=0,
        is_vacant=False,
    )
    defaults.update(kwargs)
    return OwnerRecord(**defaults)


# ---------------------------------------------------------------------------
# LLC / company detection
# ---------------------------------------------------------------------------

class TestLlcCompany:
    def test_detects_llc(self):
        r = make_record(owner_name="MESA RIDGE LLC")
        sigs = detect_llc_company(r)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "LLC_COMPANY"

    def test_detects_inc(self):
        r = make_record(owner_name="VERDE HOMES INC")
        sigs = detect_llc_company(r)
        assert len(sigs) == 1

    def test_detects_trust(self):
        r = make_record(owner_name="THE BROWN FAMILY TRUST")
        sigs = detect_llc_company(r)
        assert len(sigs) == 1

    def test_no_signal_for_individual(self):
        r = make_record(owner_name="JOHN SMITH")
        assert detect_llc_company(r) == []

    def test_detects_holdings(self):
        r = make_record(owner_name="SUNBELT HOLDINGS")
        sigs = detect_llc_company(r)
        assert len(sigs) == 1

    def test_weight_is_positive(self):
        r = make_record(owner_name="ABC CORP")
        sigs = detect_llc_company(r)
        assert sigs[0].weight > 0


# ---------------------------------------------------------------------------
# Builder keyword detection
# ---------------------------------------------------------------------------

class TestBuilderKeywords:
    def test_detects_construction(self):
        r = make_record(owner_name="MESA RIDGE CONSTRUCTION LLC")
        sigs = detect_builder_keywords(r)
        types = [s.signal_type for s in sigs]
        assert "BUILDER_KEYWORD" in types

    def test_detects_homes(self):
        r = make_record(owner_name="VERDE VALLEY HOMES INC")
        sigs = detect_builder_keywords(r)
        assert any(s.value == "HOMES" for s in sigs)

    def test_detects_development(self):
        r = make_record(owner_name="SUNBELT DEVELOPMENT GROUP")
        sigs = detect_builder_keywords(r)
        assert any(s.value == "DEVELOPMENT" for s in sigs)

    def test_no_keyword_for_plain_name(self):
        r = make_record(owner_name="JOHN SMITH TRUST")
        sigs = detect_builder_keywords(r)
        assert sigs == []


# ---------------------------------------------------------------------------
# Investor keyword detection
# ---------------------------------------------------------------------------

class TestInvestorKeywords:
    def test_detects_investments(self):
        r = make_record(owner_name="RIVERSTONE INVESTMENTS LLC")
        sigs = detect_investor_keywords(r)
        assert any(s.signal_type == "INVESTOR_KEYWORD" for s in sigs)

    def test_detects_capital(self):
        r = make_record(owner_name="SUNBELT CAPITAL FUND")
        sigs = detect_investor_keywords(r)
        assert any(s.signal_type == "INVESTOR_KEYWORD" for s in sigs)


# ---------------------------------------------------------------------------
# Vacant land detection
# ---------------------------------------------------------------------------

class TestVacantLand:
    def test_is_vacant_flag(self):
        r = make_record(is_vacant=True, land_use="SINGLE FAMILY")
        sigs = detect_vacant_land(r)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "VACANT_LAND"

    def test_land_use_vacant(self):
        r = make_record(is_vacant=False, land_use="VACANT LAND")
        sigs = detect_vacant_land(r)
        assert len(sigs) == 1

    def test_land_use_unimproved(self):
        r = make_record(is_vacant=False, land_use="UNIMPROVED LOT")
        sigs = detect_vacant_land(r)
        assert len(sigs) == 1

    def test_no_signal_for_improved(self):
        r = make_record(is_vacant=False, land_use="SINGLE FAMILY")
        assert detect_vacant_land(r) == []


# ---------------------------------------------------------------------------
# Permit activity
# ---------------------------------------------------------------------------

class TestPermitActivity:
    def test_detects_permits(self):
        r = make_record(permit_count=3)
        sigs = detect_permit_activity(r)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "PERMIT_ACTIVITY"

    def test_no_signal_zero_permits(self):
        r = make_record(permit_count=0)
        assert detect_permit_activity(r) == []


# ---------------------------------------------------------------------------
# Mailing address mismatch
# ---------------------------------------------------------------------------

class TestMailingMismatch:
    def test_detects_mismatch(self):
        r = make_record(
            mailing_address="PO BOX 100 CHICAGO IL 60601",
            property_address="200 ELM ST PHOENIX AZ 85001",
        )
        sigs = detect_mailing_mismatch(r)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "MAILING_MISMATCH"

    def test_no_mismatch_same_address(self):
        r = make_record(
            mailing_address="200 ELM ST PHOENIX AZ 85001",
            property_address="200 ELM ST PHOENIX AZ 85001",
        )
        assert detect_mailing_mismatch(r) == []

    def test_no_signal_when_missing_address(self):
        r = make_record(mailing_address="", property_address="200 ELM ST")
        assert detect_mailing_mismatch(r) == []


# ---------------------------------------------------------------------------
# Round sale price
# ---------------------------------------------------------------------------

class TestRoundPrice:
    def test_detects_round_price(self):
        r = make_record(sale_price=250000)
        sigs = detect_round_price(r)
        assert len(sigs) == 1

    def test_no_signal_non_round(self):
        r = make_record(sale_price=312457)
        assert detect_round_price(r) == []

    def test_no_signal_below_threshold(self):
        r = make_record(sale_price=5000)
        assert detect_round_price(r) == []


# ---------------------------------------------------------------------------
# Cross-record (profile-level) signals
# ---------------------------------------------------------------------------

def make_profile_with_records(records) -> BuyerProfile:
    profile = BuyerProfile(owner_name=records[0].owner_name)
    for r in records:
        profile.parcel_ids.append(r.parcel_id)
        profile.records.append(r)
    return profile


class TestRepeatAcquisitions:
    def test_three_parcels(self):
        records = [make_record(parcel_id=f"P{i}", owner_name="BIG BUILDER LLC") for i in range(3)]
        profile = make_profile_with_records(records)
        sigs = detect_repeat_acquisitions(profile)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "REPEAT_ACQUISITIONS"

    def test_two_parcels_no_signal(self):
        records = [make_record(parcel_id=f"P{i}", owner_name="OWNER LLC") for i in range(2)]
        profile = make_profile_with_records(records)
        assert detect_repeat_acquisitions(profile) == []

    def test_five_parcels_higher_weight(self):
        records = [make_record(parcel_id=f"P{i}") for i in range(5)]
        profile = make_profile_with_records(records)
        sigs = detect_repeat_acquisitions(profile)
        assert sigs[0].weight == 25


class TestMultipleNearbyParcels:
    def test_same_zip_two_parcels(self):
        records = [
            make_record(parcel_id="P1", zip_code="85001"),
            make_record(parcel_id="P2", zip_code="85001"),
        ]
        profile = make_profile_with_records(records)
        sigs = detect_multiple_nearby_parcels(profile)
        assert len(sigs) == 1
        assert sigs[0].value == "85001"

    def test_different_zips_no_signal(self):
        records = [
            make_record(parcel_id="P1", zip_code="85001"),
            make_record(parcel_id="P2", zip_code="85012"),
        ]
        profile = make_profile_with_records(records)
        assert detect_multiple_nearby_parcels(profile) == []


class TestRecentPurchaseClustering:
    def test_two_purchases_within_90_days(self):
        records = [
            make_record(parcel_id="P1", sale_date="2024-01-01"),
            make_record(parcel_id="P2", sale_date="2024-01-15"),
        ]
        profile = make_profile_with_records(records)
        sigs = detect_recent_purchase_clustering(profile)
        assert len(sigs) == 1

    def test_purchases_outside_window(self):
        records = [
            make_record(parcel_id="P1", sale_date="2024-01-01"),
            make_record(parcel_id="P2", sale_date="2024-06-01"),
        ]
        profile = make_profile_with_records(records)
        assert detect_recent_purchase_clustering(profile) == []


class TestVacantLandConcentration:
    def test_two_vacant_parcels(self):
        records = [
            make_record(parcel_id="P1", is_vacant=True),
            make_record(parcel_id="P2", is_vacant=True),
        ]
        profile = make_profile_with_records(records)
        sigs = detect_vacant_land_concentration(profile)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "VACANT_LAND_CONCENTRATION"

    def test_one_vacant_no_signal(self):
        records = [
            make_record(parcel_id="P1", is_vacant=True),
            make_record(parcel_id="P2", is_vacant=False),
        ]
        profile = make_profile_with_records(records)
        assert detect_vacant_land_concentration(profile) == []


class TestInfillActivity:
    def test_vacant_with_permits(self):
        records = [
            make_record(parcel_id="P1", is_vacant=True, permit_count=2),
        ]
        profile = make_profile_with_records(records)
        sigs = detect_infill_activity(profile)
        assert len(sigs) == 1
        assert sigs[0].signal_type == "INFILL_ACTIVITY"

    def test_vacant_no_permits_no_signal(self):
        records = [
            make_record(parcel_id="P1", is_vacant=True, permit_count=0),
        ]
        profile = make_profile_with_records(records)
        assert detect_infill_activity(profile) == []

    def test_permits_not_vacant_no_signal(self):
        records = [
            make_record(parcel_id="P1", is_vacant=False, permit_count=3),
        ]
        profile = make_profile_with_records(records)
        assert detect_infill_activity(profile) == []
