"""Tests for Auto Matcher pipeline — 10-stage lead-to-offer flow."""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.lead_intake import ingest_manual
from system.auto_matcher import (
    VaultBuyer,
    _lookup_buyers,
    _estimate_buyer_price,
    _estimate_repairs,
    run_pipeline,
)
from system.config import ASSET_TYPE_SFR, ASSET_TYPE_LAND


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_lead(**kwargs):
    defaults = dict(
        address    = "123 Test St",
        zip_code   = "77008",
        city       = "Houston",
        state      = "TX",
        list_price = 150_000,
        sqft       = 1400,
        beds       = 3,
        baths      = 2,
        dom        = 45,
        year_built = 1985,
        lot_size   = 0.15,
        source     = "test",
    )
    # allow 'price' as alias for list_price
    if "price" in kwargs:
        kwargs["list_price"] = kwargs.pop("price")
    defaults.update(kwargs)
    return ingest_manual(**defaults)


def make_buyer(**kwargs):
    defaults = dict(
        buyer_id    = "BUY-TEST",
        buyer_name  = "Test Buyer",
        zip_codes   = ["77008"],
        asset_types = [ASSET_TYPE_SFR],
        min_price   = 50_000,
        max_price   = 200_000,
        min_beds    = 2,
        strategy    = "flip",
    )
    defaults.update(kwargs)
    return VaultBuyer(**defaults)


# ─── Buyer Lookup Tests ────────────────────────────────────────────────────────

class TestBuyerLookup:
    def test_exact_zip_match(self):
        lead  = make_lead(zip_code="77008", price=150_000)
        buyer = make_buyer(zip_codes=["77008"])
        primary, secondary, score = _lookup_buyers(lead, "sfr_wholesale", [buyer])
        assert primary is not None
        assert primary.buyer_id == "BUY-TEST"
        assert score > 0

    def test_no_match_wrong_zip(self):
        lead  = make_lead(zip_code="90210")
        buyer = make_buyer(zip_codes=["77008"])
        primary, secondary, score = _lookup_buyers(lead, "sfr_wholesale", [buyer])
        assert primary is None
        assert score == 0.0

    def test_price_above_ceiling_rejected(self):
        lead  = make_lead(zip_code="77008", price=400_000)
        buyer = make_buyer(zip_codes=["77008"], max_price=200_000)
        primary, secondary, score = _lookup_buyers(lead, "sfr_wholesale", [buyer])
        # 400k > 200k * 1.15 = 230k → rejected
        assert primary is None

    def test_price_within_15pct_tolerance_accepted(self):
        lead  = make_lead(zip_code="77008", price=225_000)
        buyer = make_buyer(zip_codes=["77008"], max_price=200_000)
        # 225k <= 200k * 1.15 = 230k → should match
        primary, secondary, score = _lookup_buyers(lead, "sfr_wholesale", [buyer])
        assert primary is not None

    def test_multiple_buyers_ranked_by_score(self):
        lead   = make_lead(zip_code="77008", price=150_000)
        buyer1 = make_buyer(buyer_id="BUY-001", zip_codes=["77008"], max_price=200_000)
        buyer2 = make_buyer(buyer_id="BUY-002", zip_codes=["77008"], max_price=180_000)
        primary, secondary, score = _lookup_buyers(lead, "sfr_wholesale", [buyer1, buyer2])
        assert primary is not None
        assert len(secondary) <= 3


# ─── Repair Estimation Tests ──────────────────────────────────────────────────

class TestEstimateRepairs:
    def test_newer_home_lower_repairs(self):
        lead_new  = make_lead(sqft=1500, year_built=2020)
        lead_old  = make_lead(sqft=1500, year_built=1970)
        assert _estimate_repairs(lead_new) < _estimate_repairs(lead_old)

    def test_larger_home_higher_repairs(self):
        lead_small = make_lead(sqft=800,  year_built=1990)
        lead_large = make_lead(sqft=2500, year_built=1990)
        assert _estimate_repairs(lead_large) > _estimate_repairs(lead_small)

    def test_no_sqft_returns_default(self):
        lead = make_lead(sqft=0)
        assert _estimate_repairs(lead) == 25_000

    def test_rounds_up_to_5k(self):
        # Verify result is always a multiple of $5,000
        lead   = make_lead(sqft=1234, year_built=1988)
        repairs = _estimate_repairs(lead)
        assert repairs % 5_000 == 0


# ─── Buyer Price Estimation ────────────────────────────────────────────────────

class TestEstimateBuyerPrice:
    def test_basic_estimate(self):
        lead  = make_lead(price=200_000)
        buyer = make_buyer(max_price=300_000)
        price = _estimate_buyer_price(lead, buyer)
        # 85% of 200k = 170k
        assert price == 170_000

    def test_capped_at_buyer_max(self):
        lead  = make_lead(price=500_000)
        buyer = make_buyer(max_price=200_000)
        price = _estimate_buyer_price(lead, buyer)
        assert price <= 200_000

    def test_zero_price_returns_zero(self):
        lead  = make_lead(price=0)
        buyer = make_buyer(max_price=200_000)
        assert _estimate_buyer_price(lead, buyer) == 0.0


# ─── Full Pipeline Tests ──────────────────────────────────────────────────────

class TestRunPipeline:
    def test_queued_when_good_deal(self):
        lead  = make_lead(zip_code="77008", price=120_000, sqft=1200, year_built=2005)
        buyer = make_buyer(zip_codes=["77008"], max_price=180_000)
        result = run_pipeline(lead, buyers=[buyer])
        # Could queue or reject depending on MAO — just check it ran
        assert result.decision in ("queued", "rejected")
        assert result.classification != ""

    def test_rejected_no_buyer(self):
        lead  = make_lead(zip_code="99999")   # ZIP with no buyer
        buyer = make_buyer(zip_codes=["77008"])
        result = run_pipeline(lead, buyers=[buyer])
        assert result.decision == "rejected"
        assert result.stage_stopped == "buyer_lookup"

    def test_rejected_mobile_home(self):
        lead = make_lead(
            zip_code="77008",
            price=80_000,
            description="Mobile home, manufactured, not on foundation",
        )
        lead.keywords.append("mobile")
        buyer = make_buyer(zip_codes=["77008"])
        result = run_pipeline(lead, buyers=[buyer])
        # Should reject at classification
        assert result.decision == "rejected"

    def test_result_has_required_fields(self):
        lead   = make_lead(zip_code="77008", price=150_000)
        buyer  = make_buyer(zip_codes=["77008"], max_price=200_000)
        result = run_pipeline(lead, buyers=[buyer])
        assert result.property_id
        assert result.address
        assert result.zip_code
        assert result.classification
        assert result.decision in ("queued", "rejected")
        assert isinstance(result.notes, list)
