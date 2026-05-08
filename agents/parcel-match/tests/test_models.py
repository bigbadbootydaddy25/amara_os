"""Tests for Parcel and LoadedBuyerProfile model loading."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import LoadedBuyerProfile, Parcel


class TestParcel:
    def test_from_dict_basic(self):
        d = {
            "parcel_id": "P-001",
            "address": "123 Main St",
            "zip_code": "85001",
            "land_use": "Vacant Land",
            "is_vacant": True,
            "asking_price": 90000,
            "sale_price": 80000,
        }
        p = Parcel.from_dict(d)
        assert p.parcel_id == "P-001"
        assert p.zip_code == "85001"
        assert p.land_use == "VACANT LAND"  # uppercased
        assert p.is_vacant is True

    def test_effective_price_prefers_asking(self):
        p = Parcel.from_dict({"parcel_id": "X", "asking_price": 120000, "sale_price": 80000})
        assert p.effective_price == 120000

    def test_effective_price_falls_back_to_sale(self):
        p = Parcel.from_dict({"parcel_id": "X", "asking_price": 0, "sale_price": 80000})
        assert p.effective_price == 80000

    def test_effective_price_zero_when_neither(self):
        p = Parcel.from_dict({"parcel_id": "X"})
        assert p.effective_price == 0.0

    def test_handles_missing_optional_fields(self):
        p = Parcel.from_dict({"parcel_id": "P-MIN"})
        assert p.address == ""
        assert p.acres == 0.0
        assert p.distressed is False
        assert p.permit_count == 0

    def test_accepts_property_address_alias(self):
        p = Parcel.from_dict({"parcel_id": "P-X", "property_address": "99 Elm St"})
        assert "ELM" in p.address

    def test_accepts_zip_alias(self):
        p = Parcel.from_dict({"parcel_id": "P-X", "zip": "85001"})
        assert p.zip_code == "85001"


class TestLoadedBuyerProfile:
    def test_from_dict_basic(self):
        d = {
            "owner_name": "MESA BUILDER LLC",
            "parcel_count": 3,
            "zip_codes": ["85001"],
            "total_spend": 300000,
            "builder_score": 80,
            "investor_score": 60,
            "is_verified_builder": True,
            "is_possible_cash_buyer": True,
            "is_quarantined": False,
            "signal_evidence": [
                {"type": "LLC_COMPANY", "value": "LLC", "weight": 15, "evidence": "has LLC"}
            ],
        }
        p = LoadedBuyerProfile.from_dict(d)
        assert p.owner_name == "MESA BUILDER LLC"
        assert p.parcel_count == 3
        assert p.builder_score == 80
        assert "LLC_COMPANY" in p.signal_types

    def test_avg_price_computed(self):
        p = LoadedBuyerProfile.from_dict({
            "owner_name": "X LLC",
            "parcel_count": 4,
            "total_spend": 400000,
        })
        assert p.avg_price == 100000.0

    def test_price_range_40_percent_band(self):
        p = LoadedBuyerProfile.from_dict({
            "owner_name": "X LLC",
            "parcel_count": 2,
            "total_spend": 200000,
        })
        lo, hi = p.price_range
        assert lo == 60000.0
        assert hi == 140000.0

    def test_price_range_zero_when_no_spend(self):
        p = LoadedBuyerProfile.from_dict({"owner_name": "X"})
        assert p.price_range == (0.0, 0.0)

    def test_quarantined_flag(self):
        p = LoadedBuyerProfile.from_dict({
            "owner_name": "JOHN SMITH",
            "is_quarantined": True,
        })
        assert p.is_quarantined is True

    def test_signal_types_extracted_from_evidence(self):
        d = {
            "owner_name": "Y LLC",
            "signal_evidence": [
                {"type": "BUILDER_KEYWORD", "value": "HOMES", "weight": 20, "evidence": "x"},
                {"type": "PERMIT_ACTIVITY", "value": "3", "weight": 25, "evidence": "y"},
            ],
        }
        p = LoadedBuyerProfile.from_dict(d)
        assert "BUILDER_KEYWORD" in p.signal_types
        assert "PERMIT_ACTIVITY" in p.signal_types
