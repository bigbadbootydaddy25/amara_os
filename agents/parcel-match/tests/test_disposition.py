"""Tests for disposition path identification."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import DispositionPath, LoadedBuyerProfile, Parcel, ParcelMatch, ParcelOpportunity
from disposition import (
    identify_disposition_paths,
    enrich_opportunities,
)


def make_parcel(**kwargs) -> Parcel:
    defaults = dict(
        parcel_id="P-001",
        address="100 TEST ST",
        zip_code="85001",
        land_use="SINGLE FAMILY",
        is_vacant=False,
        asking_price=200000,
        sale_price=0,
        arv=0,
        acres=0.2,
        distressed=False,
        days_on_market=30,
        permit_count=0,
        zoning="R-1",
    )
    defaults.update(kwargs)
    return Parcel(**{k: v for k, v in defaults.items() if k in Parcel.__dataclass_fields__})


def make_match(buyer_name="BUILDER LLC", score=70, match_type="BUILDER") -> ParcelMatch:
    return ParcelMatch(
        parcel_id="P-001",
        buyer_name=buyer_name,
        match_score=score,
        match_type=match_type,
    )


def make_opportunity(parcel: Parcel, buyer_matches=None, builder_matches=None) -> ParcelOpportunity:
    return ParcelOpportunity(
        parcel=parcel,
        top_buyer_matches=buyer_matches or [],
        top_builder_matches=builder_matches or [],
    )


class TestInfillBuild:
    def test_vacant_with_builder_match(self):
        p = make_parcel(is_vacant=True, land_use="VACANT LAND", acres=0.25)
        m = make_match(score=80, match_type="BUILDER")
        opp = make_opportunity(p, builder_matches=[m])
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "INFILL_BUILD" in types

    def test_not_vacant_no_infill(self):
        p = make_parcel(is_vacant=False, land_use="SINGLE FAMILY")
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "INFILL_BUILD" not in types

    def test_infill_confidence_increases_with_builder_score(self):
        p = make_parcel(is_vacant=True)
        m_low = make_match(score=30)
        m_high = make_match(score=80)
        opp_low = make_opportunity(p, builder_matches=[m_low])
        opp_high = make_opportunity(p, builder_matches=[m_high])
        paths_low = {p.path_type: p for p in identify_disposition_paths(opp_low)}
        paths_high = {p.path_type: p for p in identify_disposition_paths(opp_high)}
        if "INFILL_BUILD" in paths_low and "INFILL_BUILD" in paths_high:
            assert paths_high["INFILL_BUILD"].confidence >= paths_low["INFILL_BUILD"].confidence


class TestWholesaleToInvestor:
    def test_distressed_with_cash_buyer(self):
        p = make_parcel(distressed=True, days_on_market=100)
        m = make_match(score=70, match_type="CASH_BUYER")
        opp = make_opportunity(p, buyer_matches=[m])
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "WHOLESALE_TO_INVESTOR" in types

    def test_long_dom_increases_confidence(self):
        p = make_parcel(distressed=True, days_on_market=120)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        w = next((p for p in paths if p.path_type == "WHOLESALE_TO_INVESTOR"), None)
        assert w is not None
        assert w.confidence >= 15

    def test_not_distressed_no_wholesale_without_dom(self):
        p = make_parcel(distressed=False, days_on_market=5)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "WHOLESALE_TO_INVESTOR" not in types


class TestRehabFlip:
    def test_distressed_with_arv_spread(self):
        p = make_parcel(distressed=True, asking_price=150000, arv=220000)
        m = make_match(score=60, match_type="CASH_BUYER")
        opp = make_opportunity(p, buyer_matches=[m])
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "REHAB_FLIP" in types

    def test_not_distressed_no_rehab(self):
        p = make_parcel(distressed=False, asking_price=150000, arv=220000)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        assert "REHAB_FLIP" not in [p.path_type for p in paths]

    def test_insufficient_arv_spread_no_rehab(self):
        # ARV < 120% of price
        p = make_parcel(distressed=True, asking_price=150000, arv=165000)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        assert "REHAB_FLIP" not in [p.path_type for p in paths]


class TestHoldForDevelopment:
    def test_large_vacant_parcel(self):
        p = make_parcel(is_vacant=True, acres=2.0, land_use="VACANT")
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "HOLD_FOR_DEVELOPMENT" in types

    def test_small_parcel_no_hold(self):
        p = make_parcel(is_vacant=True, acres=0.25)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        assert "HOLD_FOR_DEVELOPMENT" not in [p.path_type for p in paths]

    def test_improved_large_no_hold(self):
        p = make_parcel(is_vacant=False, acres=5.0)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        assert "HOLD_FOR_DEVELOPMENT" not in [p.path_type for p in paths]


class TestRetailListing:
    def test_standard_residential(self):
        p = make_parcel(is_vacant=False, distressed=False, land_use="SINGLE FAMILY")
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        types = [path.path_type for path in paths]
        assert "RETAIL_LISTING" in types

    def test_vacant_no_retail(self):
        p = make_parcel(is_vacant=True, land_use="VACANT LAND")
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        assert "RETAIL_LISTING" not in [p.path_type for p in paths]

    def test_distressed_no_retail(self):
        p = make_parcel(is_vacant=False, distressed=True)
        opp = make_opportunity(p)
        paths = identify_disposition_paths(opp)
        assert "RETAIL_LISTING" not in [p.path_type for p in paths]


class TestEnrichOpportunities:
    def test_attaches_disposition_and_summary(self):
        p = make_parcel(is_vacant=True, acres=0.25, land_use="VACANT LAND")
        m = make_match(score=70, match_type="BUILDER")
        opp = make_opportunity(p, builder_matches=[m])
        enrich_opportunities([opp])
        assert len(opp.disposition_paths) > 0
        assert opp.summary != ""

    def test_primary_disposition_is_highest_confidence(self):
        p = make_parcel(is_vacant=True, acres=0.25)
        m = make_match(score=80, match_type="BUILDER")
        opp = make_opportunity(p, builder_matches=[m])
        enrich_opportunities([opp])
        if opp.disposition_paths:
            primary = opp.primary_disposition
            assert primary.confidence == max(d.confidence for d in opp.disposition_paths)
