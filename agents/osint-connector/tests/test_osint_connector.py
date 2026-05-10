"""
Tests for the OSINT connector.
Does NOT require live backends — validates provenance shape, enrichment logic,
queue priority, and compliance audit generation.

Run: python3 -m pytest agents/osint-connector/tests/ -v
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import (
    ALLOWED_USE,
    _collect_missing_fields,
    _enrich_entity_from_builder,
    _enrich_entity_from_buyer,
    _enrich_entity_from_distress,
    _enrich_property_from_lot,
    _queue_entry,
    missing,
    provenance,
    write_compliance_audit,
)

TS = "2026-05-10T00:00:00Z"
NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)

_DISTRESS_RECORD = {
    "id": "dp-001",
    "owner": "Crestline Holdings",
    "entity_type": "LLC",
    "distress_score": 84,
    "properties": ["prop-1", "prop-2"],
    "distress_indicators": {"loan_delinquency_days": 120},
    "motivation_signals": ["motivated seller"],
    "source_evidence": [],
}

_BUYER_RECORD = {
    "id": "ob-001",
    "name": "Pinnacle Equity",
    "buyer_type": "private_equity",
    "leverage_score": 87,
    "dispo_priority": "downgraded",
    "leverage_indicators": {"portfolio_ltv": 0.92},
    "acquisition_posture": {},
    "risk_flags": ["overleveraged"],
    "source_evidence": [],
}

_BUILDER_RECORD = {
    "id": "sb-001",
    "name": "Vanguard Southwest",
    "builder_type": "residential",
    "stall_score": 89,
    "role_classification": "motivated_seller",
    "buyer_disqualification_reason": "stalled pipeline",
    "stalled_projects": [],
    "financial_distress": {"mechanic_liens": 3},
    "motivation_signals": [],
    "source_evidence": [],
}

_LOT_ROW = {
    "Address": "1234 Jeff St, Dallas, TX 75208",
    "Price": "$45000",
    "Size (Acres)": "0.15",
    "Details": "Cleared corner lot.",
    "Contact Information": "John Smith | (214) 555-0101",
}


# ── provenance() ──────────────────────────────────────────────────────────────

def test_provenance_all_required_keys():
    p = provenance("Dallas", "public_record", "CAD", "/data/cad.json", TS, "high")
    for key in ("value", "source_type", "source_name", "source_path_or_url",
                "collected_at", "confidence", "allowed_use"):
        assert key in p, f"missing key: {key}"


def test_provenance_allowed_use_constant():
    p = provenance(42, "internal_record", "src", "/p", TS, "medium")
    assert p["allowed_use"] == ALLOWED_USE


def test_provenance_no_naked_value():
    p = provenance("test", "broker_lead", "csv", "/f", TS, "low")
    assert isinstance(p, dict)
    assert p["value"] == "test"


# ── missing() ─────────────────────────────────────────────────────────────────

def test_missing_source_type():
    m = missing(TS)
    assert m["source_type"] == "missing"


def test_missing_value_is_none():
    assert missing(TS)["value"] is None


def test_missing_confidence_is_none():
    assert missing(TS)["confidence"] == "none"


def test_missing_carries_allowed_use():
    assert missing(TS)["allowed_use"] == ALLOWED_USE


# ── _collect_missing_fields() ─────────────────────────────────────────────────

def test_collect_missing_identifies_missing():
    record = {
        "entity_id": "x",
        "name": provenance("Acme", "internal_record", "src", "/p", TS, "high"),
        "sos_status": missing(TS),
        "loan_balance": missing(TS),
    }
    mf = _collect_missing_fields(record)
    assert set(mf) == {"sos_status", "loan_balance"}


def test_collect_missing_excludes_filled():
    record = {
        "entity_id": "x",
        "distress_score": provenance(84, "internal_record", "src", "/p", TS, "high"),
    }
    assert _collect_missing_fields(record) == []


# ── _queue_entry() ────────────────────────────────────────────────────────────

def test_queue_priority_high():
    q = _queue_entry("e-001", "entity", ["a", "b", "c", "d", "e"], TS)
    assert q["priority"] == "high"


def test_queue_priority_medium():
    q = _queue_entry("e-002", "entity", ["a", "b"], TS)
    assert q["priority"] == "medium"


def test_queue_priority_low():
    q = _queue_entry("e-003", "entity", ["a"], TS)
    assert q["priority"] == "low"


def test_queue_carries_allowed_use():
    q = _queue_entry("e-004", "property", ["x"], TS)
    assert q["allowed_use"] == ALLOWED_USE


# ── _enrich_entity_from_distress() ────────────────────────────────────────────

def test_distress_entity_all_provenance_wrapped():
    entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/path.json", TS)
    for key, val in entity.items():
        if key == "entity_id":
            continue
        assert isinstance(val, dict), f"'{key}' is not provenance-wrapped"
        assert "source_type" in val, f"'{key}' missing source_type"
        assert "allowed_use" in val, f"'{key}' missing allowed_use"


def test_distress_entity_known_fields_are_high_confidence():
    entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/p", TS)
    assert entity["distress_score"]["confidence"] == "high"
    assert entity["distress_score"]["source_type"] == "internal_record"


def test_distress_entity_public_record_fields_are_missing():
    entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/p", TS)
    for field in ("sos_status", "registered_agent", "estimated_equity", "loan_balance"):
        assert entity[field]["source_type"] == "missing", f"'{field}' should be missing"


def test_distress_entity_portfolio_count_from_properties_list():
    entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/p", TS)
    assert entity["portfolio_count"]["value"] == 2


# ── _enrich_entity_from_buyer() ───────────────────────────────────────────────

def test_buyer_entity_all_provenance_wrapped():
    entity = _enrich_entity_from_buyer(_BUYER_RECORD, "/buyers.json", TS)
    for key, val in entity.items():
        if key == "entity_id":
            continue
        assert isinstance(val, dict), f"'{key}' is not provenance-wrapped"


def test_buyer_entity_leverage_score_internal():
    entity = _enrich_entity_from_buyer(_BUYER_RECORD, "/p", TS)
    assert entity["leverage_score"]["value"] == 87
    assert entity["leverage_score"]["source_type"] == "internal_record"


def test_buyer_entity_distress_score_missing():
    entity = _enrich_entity_from_buyer(_BUYER_RECORD, "/p", TS)
    assert entity["distress_score"]["source_type"] == "missing"


# ── _enrich_entity_from_builder() ─────────────────────────────────────────────

def test_builder_entity_all_provenance_wrapped():
    entity = _enrich_entity_from_builder(_BUILDER_RECORD, "/builders.json", TS)
    for key, val in entity.items():
        if key == "entity_id":
            continue
        assert isinstance(val, dict), f"'{key}' is not provenance-wrapped"


def test_builder_entity_role_classification_internal():
    entity = _enrich_entity_from_builder(_BUILDER_RECORD, "/p", TS)
    assert entity["role_classification"]["value"] == "motivated_seller"
    assert entity["role_classification"]["source_type"] == "internal_record"


# ── _enrich_property_from_lot() ───────────────────────────────────────────────

def test_lot_property_all_provenance_wrapped():
    prop = _enrich_property_from_lot(_LOT_ROW, "/lots.csv", TS)
    for key, val in prop.items():
        if key == "property_id":
            continue
        assert isinstance(val, dict), f"'{key}' is not provenance-wrapped"


def test_lot_property_address_is_broker_lead():
    prop = _enrich_property_from_lot(_LOT_ROW, "/p", TS)
    assert prop["address"]["source_type"] == "broker_lead"
    assert prop["address"]["confidence"] == "high"


def test_lot_property_owner_is_missing():
    prop = _enrich_property_from_lot(_LOT_ROW, "/p", TS)
    assert prop["owner_name"]["source_type"] == "missing"


def test_lot_property_public_record_fields_are_missing():
    prop = _enrich_property_from_lot(_LOT_ROW, "/p", TS)
    for field in ("assessed_value", "liens_recorded", "permit_activity", "zoning_classification"):
        assert prop[field]["source_type"] == "missing", f"'{field}' should be missing"


# ── write_compliance_audit() ──────────────────────────────────────────────────

def test_compliance_audit_file_created():
    with tempfile.TemporaryDirectory() as d:
        entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/p", TS)
        audit = write_compliance_audit([entity], [], [], NOW, Path(d) / "reports")
        assert audit.exists()


def test_compliance_audit_contains_required_sections():
    with tempfile.TemporaryDirectory() as d:
        entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/p", TS)
        prop = _enrich_property_from_lot(_LOT_ROW, "/p", TS)
        queue = [_queue_entry("dp-001", "entity", ["sos_status", "loan_balance"], TS)]
        audit = write_compliance_audit([entity], [prop], queue, NOW, Path(d) / "reports")
        content = audit.read_text()
        assert "OSINT Compliance Audit" in content
        assert "lawful_osint_only" in content
        assert "Fill rate" in content
        assert "Enrichment Queue" in content
        assert "Source Type Breakdown" in content


def test_compliance_audit_no_fabricated_values():
    with tempfile.TemporaryDirectory() as d:
        entity = _enrich_entity_from_distress(_DISTRESS_RECORD, "/p", TS)
        audit = write_compliance_audit([entity], [], [], NOW, Path(d) / "reports")
        content = audit.read_text()
        assert "missing" in content
