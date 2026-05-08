"""Tests for grouping, enrichment, classification, and quarantine logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import OwnerRecord
from analyzers import (
    classify_builders,
    classify_cash_buyers,
    enrich_profiles,
    group_records_by_owner,
    quarantine_weak_profiles,
    validate_record,
)
from confidence_scorer import score_all_profiles


def make_record(**kwargs) -> OwnerRecord:
    defaults = dict(
        parcel_id="TEST-001",
        owner_name="DEFAULT OWNER LLC",
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
# Validation
# ---------------------------------------------------------------------------

class TestValidateRecord:
    def test_valid_record(self):
        ok, reason = validate_record(make_record())
        assert ok is True
        assert reason == ""

    def test_missing_parcel_id(self):
        ok, reason = validate_record(make_record(parcel_id=""))
        assert ok is False
        assert "parcel_id" in reason

    def test_missing_owner_name(self):
        ok, reason = validate_record(make_record(owner_name=""))
        assert ok is False

    def test_noise_owner_name(self):
        ok, reason = validate_record(make_record(owner_name="UNKNOWN"))
        assert ok is False


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

class TestGroupRecords:
    def test_groups_by_owner(self):
        records = [
            make_record(parcel_id="P1", owner_name="MESA BUILDER LLC"),
            make_record(parcel_id="P2", owner_name="MESA BUILDER LLC"),
            make_record(parcel_id="P3", owner_name="OTHER OWNER LLC"),
        ]
        profiles, quarantine = group_records_by_owner(records)
        assert len(quarantine) == 0
        # Two unique owners
        assert len(profiles) == 2
        # MESA BUILDER has 2 parcels
        mesa_key = [k for k in profiles if "MESA" in k][0]
        assert profiles[mesa_key].parcel_count == 2

    def test_quarantines_invalid_records(self):
        records = [
            make_record(parcel_id="P1", owner_name="VALID OWNER LLC"),
            make_record(parcel_id="", owner_name="VALID OWNER LLC"),  # bad parcel_id
            make_record(parcel_id="P3", owner_name=""),              # bad owner name
        ]
        profiles, quarantine = group_records_by_owner(records)
        assert len(quarantine) == 2

    def test_deduplicates_same_parcel(self):
        records = [
            make_record(parcel_id="P1", owner_name="OWNER LLC"),
            make_record(parcel_id="P1", owner_name="OWNER LLC"),  # duplicate
        ]
        profiles, _ = group_records_by_owner(records)
        key = list(profiles.keys())[0]
        assert profiles[key].parcel_count == 1


# ---------------------------------------------------------------------------
# Full pipeline: group → enrich → score → quarantine → classify
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def _run(self, records):
        profiles, quarantined = group_records_by_owner(records)
        enrich_profiles(profiles)
        score_all_profiles(profiles)
        quarantine_weak_profiles(profiles)
        builders = classify_builders(profiles)
        for p in builders:
            p.is_verified_builder = True
        cash_buyers = classify_cash_buyers(profiles)
        for p in cash_buyers:
            p.is_possible_cash_buyer = True
        return profiles, quarantined, builders, cash_buyers

    def test_builder_identified(self):
        records = [
            make_record(parcel_id="P1", owner_name="MESA RIDGE CONSTRUCTION LLC",
                        is_vacant=True, permit_count=2, zip_code="85001",
                        mailing_address="PO BOX 5500 AZ 85001",
                        property_address="123 VACANT RD AZ 85001"),
            make_record(parcel_id="P2", owner_name="MESA RIDGE CONSTRUCTION LLC",
                        is_vacant=True, permit_count=1, zip_code="85001",
                        mailing_address="PO BOX 5500 AZ 85001",
                        property_address="125 VACANT RD AZ 85001"),
            make_record(parcel_id="P3", owner_name="MESA RIDGE CONSTRUCTION LLC",
                        is_vacant=True, permit_count=0, zip_code="85001",
                        mailing_address="PO BOX 5500 AZ 85001",
                        property_address="127 VACANT RD AZ 85001"),
        ]
        _, _, builders, _ = self._run(records)
        assert len(builders) >= 1
        assert any("MESA" in b.owner_name for b in builders)

    def test_cash_buyer_identified(self):
        records = [
            make_record(parcel_id="P1", owner_name="SUNBELT ACQUISITIONS CAPITAL LLC",
                        mailing_address="1800 N CENTRAL AVE PHOENIX AZ 85012",
                        property_address="4400 W THOMAS RD PHOENIX AZ 85031",
                        sale_date="2024-01-10", sale_price=250000),
            make_record(parcel_id="P2", owner_name="SUNBELT ACQUISITIONS CAPITAL LLC",
                        mailing_address="1800 N CENTRAL AVE PHOENIX AZ 85012",
                        property_address="4420 W THOMAS RD PHOENIX AZ 85031",
                        sale_date="2024-01-18", sale_price=245000),
            make_record(parcel_id="P3", owner_name="SUNBELT ACQUISITIONS CAPITAL LLC",
                        mailing_address="1800 N CENTRAL AVE PHOENIX AZ 85012",
                        property_address="212 S 59TH AVE PHOENIX AZ 85043",
                        sale_date="2024-02-05", sale_price=275000),
        ]
        _, _, _, cash_buyers = self._run(records)
        assert len(cash_buyers) >= 1
        assert any("SUNBELT" in b.owner_name for b in cash_buyers)

    def test_individual_owner_quarantined(self):
        records = [
            make_record(parcel_id="P1", owner_name="JOHN SMITH",
                        mailing_address="99 OAK ST TEMPE AZ 85281",
                        property_address="99 OAK ST TEMPE AZ 85281",
                        sale_price=312000, is_vacant=False, permit_count=0),
        ]
        profiles, _, builders, cash_buyers = self._run(records)
        # Individual with no signals should be quarantined
        john_key = [k for k in profiles if "JOHN" in k][0]
        assert profiles[john_key].is_quarantined is True
        assert not any("JOHN" in b.owner_name for b in builders)
        assert not any("JOHN" in b.owner_name for b in cash_buyers)

    def test_no_fabricated_buyers(self):
        """With empty input, no profiles should be created."""
        profiles, quarantined, builders, cash_buyers = self._run([])
        assert len(profiles) == 0
        assert len(builders) == 0
        assert len(cash_buyers) == 0
