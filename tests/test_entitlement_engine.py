"""Tests for Entitlement Intelligence Engine."""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.entitlement_engine import (
    ZoningProfile,
    DensityProfile,
    PlatStatus,
    InfrastructureProfile,
    PermitPipeline,
    EntitlementInputs,
    analyze_entitlement,
    quick_entitlement_screen,
    _score_zoning,
    _score_density,
    _score_plat,
    _score_infrastructure,
    _score_permits,
    _estimate_time_to_build,
    _compute_risk_level,
)


class TestInfrastructureScore:
    def test_all_available_returns_1(self):
        infra = InfrastructureProfile(
            water_available=True, sewer_available=True,
            road_access=True, utilities_distance_ft=0,
        )
        assert infra.score() == 1.0

    def test_nothing_available_returns_0(self):
        infra = InfrastructureProfile(
            water_available=False, sewer_available=False,
            road_access=False, utilities_distance_ft=5000,
        )
        assert infra.score() < 0.20

    def test_partial_infrastructure(self):
        infra = InfrastructureProfile(
            water_available=True, sewer_available=False,
            road_access=True, utilities_distance_ft=0,
        )
        score = infra.score()
        assert 0.40 < score < 0.90


class TestPermitPipeline:
    def test_not_started_stage(self):
        p = PermitPipeline()
        assert p.stage() == "not_started"
        assert p.progress_score() == 0.0

    def test_permits_issued_stage(self):
        p = PermitPipeline(
            pre_app_submitted=True,
            preliminary_plat_submitted=True,
            final_plat_submitted=True,
            permits_issued=True,
        )
        assert p.stage() == "permits_issued"
        assert p.progress_score() == 1.0

    def test_preliminary_plat_stage(self):
        p = PermitPipeline(pre_app_submitted=True, preliminary_plat_submitted=True)
        assert p.stage() == "preliminary_plat"
        assert p.progress_score() == 0.50


class TestScoreZoning:
    def test_by_right_high_score(self):
        z = ZoningProfile(current_zoning="R2", target_zoning="R2", change_needed=False)
        score, change, risks, opps = _score_zoning(z)
        assert score == 0.90
        assert change is False
        assert any("by-right" in o.lower() for o in opps)

    def test_rezone_required_lowers_score(self):
        z = ZoningProfile(
            current_zoning="AG", target_zoning="R2",
            change_needed=True, change_type="rezone",
            change_probability=0.60,
        )
        score, change, risks, opps = _score_zoning(z)
        assert score < 0.60
        assert change is True

    def test_none_returns_neutral(self):
        score, change, risks, opps = _score_zoning(None)
        assert score == 0.50


class TestScorePlat:
    def test_recorded_high_score(self):
        p = PlatStatus(phase="recorded", recorded=True)
        score, dead_paper, risks, opps = _score_plat(p)
        assert score == 1.0

    def test_raw_low_score(self):
        p = PlatStatus(phase="raw")
        score, dead_paper, risks, opps = _score_plat(p)
        assert score == 0.25

    def test_dead_paper_boosts_score(self):
        p = PlatStatus(phase="raw", dead_paper=True)
        score, dead_paper_flag, risks, opps = _score_plat(p)
        assert score >= 0.70
        assert dead_paper_flag is True


class TestScoreDensity:
    def test_achievable_units_above_target(self):
        d = DensityProfile(
            max_density_per_acre=10, target_units=50,
            gross_acres=10, net_developable_acres=8,
        )
        score, risks, opps = _score_density(d)
        # 8 * 10 = 80 achievable vs 50 target → above target
        assert score >= 0.60
        assert d.actual_achievable_units == 80

    def test_density_shortfall(self):
        d = DensityProfile(
            max_density_per_acre=2, target_units=100,
            gross_acres=5, net_developable_acres=4,
        )
        score, risks, opps = _score_density(d)
        # 4 * 2 = 8 achievable vs 100 target → shortfall
        assert score < 0.40
        assert any("shortfall" in r.lower() for r in risks)


class TestTimeToBuild:
    def test_permits_issued_is_fast(self):
        months = _estimate_time_to_build(
            zoning_change=False, infra_gap=False,
            permit_stage="permits_issued", density_ok=True,
        )
        assert months <= 6

    def test_raw_with_rezoning_is_slow(self):
        months = _estimate_time_to_build(
            zoning_change=True, infra_gap=True,
            permit_stage="not_started", density_ok=False,
        )
        assert months >= 30


class TestComputeRiskLevel:
    def test_high_score_no_risks_is_low(self):
        assert _compute_risk_level(0.80, []) == "low"

    def test_rezone_required_is_critical(self):
        assert _compute_risk_level(0.40, ["Full rezoning required"]) == "critical"

    def test_low_score_is_high_risk(self):
        assert _compute_risk_level(0.30, []) == "high"


class TestQuickEntitlementScreen:
    def test_all_infra_with_recorded_plat(self):
        result = quick_entitlement_screen(
            deal_id="LAND-TEST",
            address="100 Dev Blvd",
            zip_code="78701",
            has_water=True, has_sewer=True, has_road=True,
            plat_phase="recorded",
            permits_stage="permits_issued",
        )
        assert result.entitlement_score >= 0.75
        assert result.risk_level in ("low", "medium")
        assert result.is_builder_ready()

    def test_raw_land_no_infra_is_high_risk(self):
        result = quick_entitlement_screen(
            deal_id="LAND-TEST2",
            address="Rural Rd",
            zip_code="78702",
            has_water=False, has_sewer=False, has_road=False,
            plat_phase="raw",
            permits_stage="not_started",
        )
        assert result.risk_level in ("high", "critical")
        assert not result.is_builder_ready()
        assert result.time_to_build_months >= 18

    def test_dead_paper_boosts_entitlement(self):
        without = quick_entitlement_screen(
            deal_id="A", address="Addr1", zip_code="78703",
            dead_paper=False, plat_phase="raw",
        )
        with_dp = quick_entitlement_screen(
            deal_id="B", address="Addr2", zip_code="78703",
            dead_paper=True, plat_phase="raw",
        )
        assert with_dp.entitlement_score > without.entitlement_score
