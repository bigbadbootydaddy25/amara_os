"""
Tests for the OSINT External Lookup Runner.
Does NOT require live backends or source files.
Validates adapters, inference, cache, normalization, and report generation.

Run: python3 -m pytest agents/osint-external-lookup/tests/ -v
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import (
    ALLOWED_USE, INFERRED, RESOLVED, UNRESOLVED, LOW_CONFIDENCE, STALE,
    AdapterResult,
    CacheLayer,
    CountyAssessorAdapter, SOSBusinessAdapter, PropStreamAdapter,
    InferenceAdapter,
    _best_result, _field_status,
    missing, provenance,
    normalize_entity_name, normalize_address, normalize_apn,
    resolve_record,
    write_fill_report, write_remaining_gaps, write_lookup_audit,
    ALL_ADAPTERS,
)

TS = "2026-05-10T00:00:00Z"
NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)


# ── Normalization ─────────────────────────────────────────────────────────────

def test_normalize_strips_llc():
    assert "CRESTLINE" in normalize_entity_name("Crestline Capital Holdings LLC")


def test_normalize_strips_fund():
    assert "IRONWOOD" in normalize_entity_name("Ironwood Fund III")
    assert "FUND" not in normalize_entity_name("Ironwood Fund III")


def test_normalize_address_abbreviates_street():
    assert normalize_address("1234 Jeff Street") == "1234 JEFF ST"


def test_normalize_address_handles_none():
    assert normalize_address(None) == ""


def test_normalize_apn_strips_hyphens():
    assert normalize_apn("123-456-789") == "123456789"


def test_normalize_apn_handles_none():
    assert normalize_apn(None) == ""


# ── CacheLayer ────────────────────────────────────────────────────────────────

def test_cache_miss_on_empty():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d))
        assert cache.get("nonexistent_key") is None


def test_cache_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d))
        data = {"value": "test", "source_type": "inferred"}
        cache.set("key1", data)
        assert cache.get("key1") == data


def test_cache_expired_with_zero_ttl():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d), ttl_days=0)
        cache.set("key2", {"value": "x"})
        assert cache.is_expired("key2") is True


def test_cache_not_expired_fresh_write():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d), ttl_days=30)
        cache.set("key3", {"value": "x"})
        assert cache.is_expired("key3") is False


# ── AdapterResult / _best_result ──────────────────────────────────────────────

def _ar(field: str, confidence: str, status: str) -> AdapterResult:
    return AdapterResult(
        field=field, value=f"val_{confidence}", source_type="test",
        source_name="test", source_path="/p", collected_at=TS,
        confidence=confidence, status=status,
    )


def test_best_result_prefers_resolved_over_inferred():
    candidates = [_ar("f", "low", RESOLVED), _ar("f", "medium", INFERRED)]
    best = _best_result(candidates)
    assert best.status == RESOLVED


def test_best_result_prefers_higher_confidence():
    candidates = [_ar("f", "low", INFERRED), _ar("f", "medium", INFERRED)]
    best = _best_result(candidates)
    assert best.confidence == "medium"


def test_best_result_single_candidate():
    candidates = [_ar("f", "high", RESOLVED)]
    assert _best_result(candidates).confidence == "high"


# ── Adapter: field coverage ───────────────────────────────────────────────────

def test_county_assessor_covers_assessed_value():
    assert CountyAssessorAdapter().can_resolve("assessed_value")


def test_county_assessor_does_not_cover_sos():
    assert not CountyAssessorAdapter().can_resolve("sos_status")


def test_sos_adapter_covers_sos_status():
    assert SOSBusinessAdapter().can_resolve("sos_status")


def test_propstream_covers_portfolio_count():
    assert PropStreamAdapter().can_resolve("portfolio_count")


def test_all_adapters_have_source_type():
    for adapter in ALL_ADAPTERS:
        assert adapter.source_type, f"{adapter.__class__.__name__} missing source_type"


# ── InferenceAdapter ──────────────────────────────────────────────────────────

_DISTRESS_ENTITY = {
    "entity_id": "DP-001",
    "name": provenance("Crestline Capital Holdings LLC", "internal_record", "src", "/p", TS, "high"),
    "distress_score": provenance(84, "internal_record", "src", "/p", TS, "high"),
    "distress_indicators": provenance(
        {"loan_delinquency_days": 97, "debt_service_coverage_ratio": 0.71,
         "foreclosure_notices": 2, "maturity_wall_months": 4},
        "internal_record", "src", "/p", TS, "high",
    ),
    "estimated_equity": missing(TS),
    "loan_balance": missing(TS),
    "sos_status": missing(TS),
}

_BUILDER_ENTITY = {
    "entity_id": "SB-001",
    "name": provenance("Vanguard Southwest", "internal_record", "src", "/p", TS, "high"),
    "stall_score": provenance(89, "internal_record", "src", "/p", TS, "high"),
    "stalled_projects": provenance(
        [{"project_name": "Project A", "address": "123 Main St, Phoenix, AZ",
          "permit_pull_date": "2024-01-01", "last_inspection_passed": "2024-06-01",
          "months_since_meaningful_progress": 7}],
        "internal_record", "src", "/p", TS, "high",
    ),
    "associated_addresses": missing(TS),
    "permit_activity": missing(TS),
    "portfolio_count": missing(TS),
}

_BISHOP_ARTS_PROPERTY = {
    "property_id": "1234_jeff_st",
    "address": provenance("1234 Jeff St, Dallas, TX 75208", "broker_lead", "src", "/p", TS, "high"),
    "broker_details": provenance(
        "Cleared corner lot. Bishop Arts corridor. Builder-ready.",
        "broker_lead", "src", "/p", TS, "high",
    ),
    "zoning_classification": missing(TS),
}

_TRINITY_PROPERTY = {
    "property_id": "420_w_12th",
    "address": provenance("420 W 12th St, Dallas, TX 75208", "broker_lead", "src", "/p", TS, "high"),
    "broker_details": provenance("Trinity Groves adjacent. Cleared lot.", "broker_lead", "src", "/p", TS, "high"),
    "zoning_classification": missing(TS),
}

_INFILL_PROPERTY = {
    "property_id": "other_lot",
    "address": provenance("999 Random St, Dallas, TX", "broker_lead", "src", "/p", TS, "high"),
    "broker_details": provenance("Cleared lot. Builder-ready infill site.", "broker_lead", "src", "/p", TS, "high"),
    "zoning_classification": missing(TS),
}


inf = InferenceAdapter()


def test_inference_loan_balance_from_delinquent_days():
    result = inf.lookup_entity(_DISTRESS_ENTITY, "loan_balance", [], TS)
    assert result is not None
    assert result.status == INFERRED
    assert "delinquent" in result.value.lower()
    assert result.confidence == "low"


def test_inference_estimated_equity_high_distress():
    result = inf.lookup_entity(_DISTRESS_ENTITY, "estimated_equity", [], TS)
    assert result is not None
    assert result.status == INFERRED
    assert "impaired" in result.value.lower() or "negative" in result.value.lower()


def test_inference_sos_status_returns_none():
    result = inf.lookup_entity(_DISTRESS_ENTITY, "sos_status", [], TS)
    assert result is None


def test_inference_associated_addresses_from_stalled_projects():
    result = inf.lookup_entity(_BUILDER_ENTITY, "associated_addresses", [], TS)
    assert result is not None
    assert result.status == INFERRED
    assert isinstance(result.value, list)
    assert "123 Main St, Phoenix, AZ" in result.value


def test_inference_permit_activity_from_stalled_projects():
    result = inf.lookup_entity(_BUILDER_ENTITY, "permit_activity", [], TS)
    assert result is not None
    assert isinstance(result.value, list)
    assert result.value[0]["status"] == "stalled"


def test_inference_portfolio_count_from_stalled_projects():
    result = inf.lookup_entity(_BUILDER_ENTITY, "portfolio_count", [], TS)
    assert result is not None
    assert result.value == 1


def test_inference_zoning_bishop_arts():
    result = inf.lookup_property(_BISHOP_ARTS_PROPERTY, "zoning_classification", [], TS)
    assert result is not None
    assert "Bishop Arts" in result.value
    assert result.confidence == "medium"


def test_inference_zoning_trinity_groves():
    result = inf.lookup_property(_TRINITY_PROPERTY, "zoning_classification", [], TS)
    assert result is not None
    assert "Trinity Groves" in result.value


def test_inference_zoning_generic_infill():
    result = inf.lookup_property(_INFILL_PROPERTY, "zoning_classification", [], TS)
    assert result is not None
    assert result.confidence == "low"


def test_inference_zoning_carried_allowed_use():
    result = inf.lookup_property(_BISHOP_ARTS_PROPERTY, "zoning_classification", [], TS)
    prov = result.to_provenance()
    assert prov["allowed_use"] == ALLOWED_USE


# ── resolve_record ────────────────────────────────────────────────────────────

def test_resolve_record_fills_inferred_field():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d))
        sources = Path(d) / "sources"
        result = resolve_record(
            _DISTRESS_ENTITY.copy(),
            ["loan_balance"],
            "lookup_entity",
            sources,
            cache,
            TS,
        )
        assert result["loan_balance"]["source_type"] == "inferred"
        assert result["loan_balance"]["value"] is not None


def test_resolve_record_unresolvable_stays_missing():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d))
        sources = Path(d) / "sources"
        entity = {**_DISTRESS_ENTITY, "sos_status": missing(TS)}
        result = resolve_record(entity, ["sos_status"], "lookup_entity", sources, cache, TS)
        assert result["sos_status"]["source_type"] == "missing"


def test_resolve_record_uses_cache_on_second_call():
    with tempfile.TemporaryDirectory() as d:
        cache = CacheLayer(Path(d))
        sources = Path(d) / "sources"
        entity = _DISTRESS_ENTITY.copy()
        r1 = resolve_record(entity, ["loan_balance"], "lookup_entity", sources, cache, TS)
        r2 = resolve_record(entity, ["loan_balance"], "lookup_entity", sources, cache, TS)
        assert r1["loan_balance"] == r2["loan_balance"]


# ── _field_status ─────────────────────────────────────────────────────────────

def test_field_status_counts_unresolved():
    record = {"entity_id": "x", "sos_status": missing(TS), "name": provenance("A", "internal_record", "", "", TS, "high")}
    counts = _field_status(record)
    assert counts[UNRESOLVED] >= 1


# ── write_fill_report ─────────────────────────────────────────────────────────

def test_fill_report_written():
    with tempfile.TemporaryDirectory() as d:
        queue = [{"entity_id": "DP-001", "entity_type": "entity", "missing_fields": ["sos_status", "loan_balance"]}]
        report = write_fill_report(queue, [_DISTRESS_ENTITY], [], NOW, Path(d) / "report.json")
        assert report["original_missing_field_slots"] == 2
        assert "gap_reduction" in report


def test_fill_report_original_slot_count():
    with tempfile.TemporaryDirectory() as d:
        queue = [
            {"entity_id": "A", "entity_type": "entity", "missing_fields": ["f1", "f2", "f3"]},
            {"entity_id": "B", "entity_type": "property", "missing_fields": ["f4"]},
        ]
        report = write_fill_report(queue, [], [], NOW, Path(d) / "r.json")
        assert report["original_missing_field_slots"] == 4


# ── write_remaining_gaps ──────────────────────────────────────────────────────

def test_remaining_gaps_only_missing():
    with tempfile.TemporaryDirectory() as d:
        entity = {
            "entity_id": "X",
            "sos_status": missing(TS),
            "loan_balance": provenance("val", "inferred", "src", "/p", TS, "low"),
        }
        gaps = write_remaining_gaps([entity], [], Path(d) / "gaps.json")
        assert len(gaps) == 1
        assert "sos_status" in gaps[0]["missing_fields"]
        assert "loan_balance" not in gaps[0]["missing_fields"]


def test_remaining_gaps_empty_when_all_resolved():
    with tempfile.TemporaryDirectory() as d:
        entity = {
            "entity_id": "Y",
            "name": provenance("Corp", "internal_record", "s", "/p", TS, "high"),
        }
        gaps = write_remaining_gaps([entity], [], Path(d) / "gaps.json")
        assert gaps == []


# ── write_lookup_audit ────────────────────────────────────────────────────────

def test_lookup_audit_created():
    with tempfile.TemporaryDirectory() as d:
        fill_report = {
            "original_missing_field_slots": 10, "remaining_unresolved": 6,
            "gap_reduction": 4, "gap_reduction_pct": 40,
            "entity_field_statuses": {RESOLVED: 2, INFERRED: 2, UNRESOLVED: 6, LOW_CONFIDENCE: 0, STALE: 0},
            "property_field_statuses": {RESOLVED: 0, INFERRED: 0, UNRESOLVED: 0, LOW_CONFIDENCE: 0, STALE: 0},
        }
        audit = write_lookup_audit(
            [], [], fill_report, [],
            Path(d) / "sources",
            NOW, Path(d) / "reports",
        )
        assert audit.exists()
        content = audit.read_text()
        assert "OSINT External Lookup Audit" in content
        assert "Gap Reduction" in content
        assert "Remaining Gaps" in content
        assert "Compliance Notes" in content


def test_lookup_audit_lists_adapter_patterns_when_no_sources():
    with tempfile.TemporaryDirectory() as d:
        fill_report = {
            "original_missing_field_slots": 5, "remaining_unresolved": 5,
            "gap_reduction": 0, "gap_reduction_pct": 0,
            "entity_field_statuses": {RESOLVED: 0, INFERRED: 0, UNRESOLVED: 5, LOW_CONFIDENCE: 0, STALE: 0},
            "property_field_statuses": {RESOLVED: 0, INFERRED: 0, UNRESOLVED: 0, LOW_CONFIDENCE: 0, STALE: 0},
        }
        audit = write_lookup_audit([], [], fill_report, [], Path(d) / "sources", NOW, Path(d) / "reports")
        content = audit.read_text()
        assert "data/osint/sources/" in content
        assert "PropStream" in content
