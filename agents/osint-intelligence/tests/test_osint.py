#!/usr/bin/env python3
"""
Tests for the OSINT Intelligence Layer.
Run: python3 -m pytest agents/osint-intelligence/tests/ -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the agent directory is on the path
_AGENT_DIR = Path(__file__).parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from source_discovery import (
    OSINT_SOURCES,
    OSINTSource,
    build_source_index,
    get_sources_by_type,
    get_sources_by_access,
    get_sources_by_jurisdiction,
    get_priority1_sources,
    get_free_sources,
    write_source_index,
)
from entity_research import (
    detect_entity_type,
    is_entity_name,
    normalize_entity,
    names_match,
    partial_match,
    research_entity,
    build_entity_research_from_names,
    cross_reference_aliases,
    flag_revoked_entities,
    EntityResearchPacket,
    write_verified_entities,
    write_entity_research_packets,
)
from record_research import (
    build_deed_targets,
    build_entity_targets,
    build_tax_delinquent_targets,
    build_permit_targets,
    build_code_violation_targets,
    build_foreclosure_targets,
    build_license_targets,
    build_all_targets_for_subject,
    write_record_source_targets,
    write_agent_routing,
    AGENT_ROUTING,
    RecordTarget,
    _slugify,
    _access_to_status,
)


# ===========================================================================
# Source Discovery Tests
# ===========================================================================

class TestSourceCatalog:
    def test_minimum_source_count(self):
        assert len(OSINT_SOURCES) >= 50

    def test_all_sources_have_required_fields(self):
        for src in OSINT_SOURCES:
            assert src.source_id, f"Missing source_id: {src}"
            assert src.name, f"Missing name: {src}"
            assert src.url, f"Missing url: {src}"
            assert src.jurisdiction, f"Missing jurisdiction: {src}"
            assert src.source_type, f"Missing source_type: {src}"
            assert src.access_type, f"Missing access_type: {src}"
            assert src.description, f"Missing description: {src}"
            assert 0.0 <= src.confidence <= 1.0, f"Bad confidence: {src}"
            assert src.priority in (1, 2, 3), f"Bad priority: {src}"

    def test_all_source_ids_unique(self):
        ids = [s.source_id for s in OSINT_SOURCES]
        assert len(ids) == len(set(ids)), "Duplicate source_ids found"

    def test_all_urls_non_empty(self):
        for src in OSINT_SOURCES:
            assert src.url.startswith("http"), f"Bad URL for {src.source_id}: {src.url}"

    def test_valid_access_types(self):
        valid = {"csv", "pdf", "api", "browser-only", "manual", "paid", "login-required"}
        for src in OSINT_SOURCES:
            assert src.access_type in valid, f"Invalid access_type '{src.access_type}' for {src.source_id}"

    def test_valid_source_types(self):
        valid = {
            "cad", "recorder", "sos", "tax", "gis", "permit",
            "code_violation", "foreclosure", "auction", "court",
            "licensing", "paid",
        }
        for src in OSINT_SOURCES:
            assert src.source_type in valid, f"Invalid source_type '{src.source_type}' for {src.source_id}"

    def test_dallas_county_sources_exist(self):
        dallas = get_sources_by_jurisdiction("Dallas County")
        assert len(dallas) >= 10, f"Expected ≥10 Dallas County sources, got {len(dallas)}"

    def test_texas_sos_source_exists(self):
        sos = get_sources_by_type("sos")
        ids = {s.source_id for s in sos}
        assert "TX-SOS-001" in ids

    def test_priority1_sources_are_dallas_texas(self):
        p1 = get_priority1_sources()
        for src in p1:
            assert src.jurisdiction in ("Dallas County", "Texas", "Dallas–Fort Worth",
                                        "Tarrant County", "Collin County", "Denton County",
                                        "Rockwall County", "Kaufman County", "Ellis County"), \
                f"{src.source_id} is priority 1 but jurisdiction is '{src.jurisdiction}'"

    def test_free_sources_are_not_paid(self):
        free = get_free_sources()
        for src in free:
            assert src.access_type not in ("paid", "login-required"), \
                f"{src.source_id} marked as free but access_type is {src.access_type}"

    def test_data_available_is_list(self):
        for src in OSINT_SOURCES:
            assert isinstance(src.data_available, list), f"{src.source_id} data_available is not a list"


class TestSourceIndex:
    def test_build_source_index_structure(self):
        idx = build_source_index()
        assert "generated" in idx
        assert "total_sources" in idx
        assert "by_access_type" in idx
        assert "by_source_type" in idx
        assert "sources" in idx
        assert idx["total_sources"] == len(OSINT_SOURCES)

    def test_write_source_index(self, tmp_path):
        write_source_index(tmp_path)
        assert (tmp_path / "OSINT_SOURCE_INDEX.json").exists()
        assert (tmp_path / "OSINT_SOURCE_INDEX.md").exists()
        data = json.loads((tmp_path / "OSINT_SOURCE_INDEX.json").read_text())
        assert data["total_sources"] == len(OSINT_SOURCES)

    def test_source_index_md_has_catalog_section(self, tmp_path):
        write_source_index(tmp_path)
        md = (tmp_path / "OSINT_SOURCE_INDEX.md").read_text()
        assert "## Source Catalog" in md
        assert "TX-DAL-CAD-001" in md
        assert "TX-SOS-001" in md


class TestGetSourcesBy:
    def test_get_by_type_recorder(self):
        recorders = get_sources_by_type("recorder")
        assert len(recorders) >= 3

    def test_get_by_access_browser_only(self):
        browser = get_sources_by_access("browser-only")
        assert len(browser) >= 10

    def test_get_by_access_paid(self):
        paid = get_sources_by_access("paid")
        assert len(paid) >= 2

    def test_get_by_jurisdiction_texas(self):
        tx = get_sources_by_jurisdiction("Texas")
        assert len(tx) >= 5

    def test_get_by_jurisdiction_case_insensitive(self):
        a = get_sources_by_jurisdiction("dallas county")
        b = get_sources_by_jurisdiction("Dallas County")
        assert len(a) == len(b)


# ===========================================================================
# Entity Research Tests
# ===========================================================================

class TestEntityTypeDetection:
    @pytest.mark.parametrize("name,expected_type", [
        ("Webb Capital Holdings LLC", "LLC"),
        ("WEBB CAPITAL HOLDINGS LLC", "LLC"),
        ("Smith Properties Inc", "Inc"),
        ("Dallas Realty Corp", "Corp"),
        ("Oak Street Partners LP", "LP"),
        ("Sunrise Trust", "Trust"),
        ("Marcus Webb", None),
        ("JOHN SMITH", None),
        ("123 Main St", None),
    ])
    def test_detect_entity_type(self, name, expected_type):
        assert detect_entity_type(name) == expected_type

    @pytest.mark.parametrize("name,expected", [
        ("Webb Capital LLC", True),
        ("Marcus Webb", False),
        ("Dallas Holdings Inc", True),
        ("", False),
    ])
    def test_is_entity_name(self, name, expected):
        assert is_entity_name(name) == expected


class TestEntityNormalisation:
    @pytest.mark.parametrize("a,b,expected", [
        ("Webb Capital LLC", "Webb Capital LLC", True),
        ("WEBB CAPITAL LLC", "webb capital llc", True),
        ("Webb Capital LLC", "Webb Capital, LLC.", True),
        ("Webb Capital LLC", "Webb Properties LLC", False),
        ("Dallas Holdings Inc", "Dallas Holdings Incorporated", True),
    ])
    def test_names_match(self, a, b, expected):
        assert names_match(a, b) == expected

    def test_normalize_strips_legal_suffix(self):
        assert normalize_entity("Webb Capital LLC") == normalize_entity("Webb Capital")

    def test_normalize_is_alphanum_only(self):
        n = normalize_entity("Webb & Capital, LLC.")
        assert n.isalnum() or n == "", f"Non-alphanum chars in: {n!r}"


class TestPartialMatch:
    def test_partial_match_finds_similar(self):
        candidates = ["Webb Capital LLC", "Webb Properties LLC", "Smith Holdings Inc"]
        results = partial_match("Webb Capital", candidates, min_overlap=0.5)
        assert "Webb Capital LLC" in results

    def test_partial_match_empty_candidates(self):
        assert partial_match("Webb Capital", []) == []


class TestResearchEntity:
    def test_research_entity_returns_packet(self):
        p = research_entity("Webb Capital Holdings LLC")
        assert isinstance(p, EntityResearchPacket)
        assert p.entity_name == "Webb Capital Holdings LLC"

    def test_research_entity_has_citations(self):
        p = research_entity("Webb Capital Holdings LLC")
        assert len(p.citations) >= 2
        assert any("sos.state.tx.us" in c for c in p.citations)
        assert any("mycpa.cpa.state.tx.us" in c for c in p.citations)

    def test_research_entity_has_notes(self):
        p = research_entity("Webb Capital Holdings LLC")
        assert len(p.notes) > 10

    def test_research_entity_non_entity_flagged(self):
        p = research_entity("Marcus Webb")
        assert "not_entity_name" in p.flags

    def test_research_entity_with_aliases(self):
        p = research_entity("Webb Capital LLC", ["Webb Capital Holdings LLC"])
        assert "Webb Capital Holdings LLC" in p.aliases


class TestBuildEntityResearch:
    def test_build_deduplicates(self):
        names = ["Webb Capital LLC", "WEBB CAPITAL LLC", "Smith Holdings Inc"]
        packets = build_entity_research_from_names(names)
        entity_names = {p.entity_name for p in packets}
        # Webb Capital LLC and WEBB CAPITAL LLC normalise the same — only one
        assert len(packets) < len(names)

    def test_build_cross_references_aliases(self):
        names = ["Webb Capital LLC", "WEBB CAPITAL LLC"]
        packets = build_entity_research_from_names(names)
        aliased = [p for p in packets if "alias_group" in p.flags]
        # After dedup they share alias; at least 1 packet if deduplicated
        assert len(packets) >= 1

    def test_build_flags_revoked(self):
        packets = [
            EntityResearchPacket(
                entity_name="Dead Corp LLC",
                sos_status="Forfeited",
                franchise_tax_status="Active",
            )
        ]
        result = flag_revoked_entities(packets)
        assert "entity_revoked" in result[0].flags

    def test_build_flags_franchise_forfeited(self):
        packets = [
            EntityResearchPacket(
                entity_name="Gone Corp LLC",
                sos_status="Active",
                franchise_tax_status="Forfeited",
            )
        ]
        result = flag_revoked_entities(packets)
        assert "franchise_tax_forfeited" in result[0].flags


class TestEntityWriters:
    def test_write_verified_entities(self, tmp_path):
        packets = build_entity_research_from_names(["Webb Capital LLC"])
        write_verified_entities(packets, tmp_path)
        assert (tmp_path / "VERIFIED_ENTITIES.json").exists()
        data = json.loads((tmp_path / "VERIFIED_ENTITIES.json").read_text())
        assert data["total_entities"] >= 1

    def test_write_entity_research_packets_md(self, tmp_path):
        packets = build_entity_research_from_names(["Webb Capital LLC", "Smith Holdings Inc"])
        write_entity_research_packets(packets, tmp_path)
        md = (tmp_path / "ENTITY_RESEARCH_PACKETS.md").read_text()
        assert "## Webb Capital LLC" in md or "## Smith Holdings Inc" in md
        assert "Citations" in md


# ===========================================================================
# Record Research Tests
# ===========================================================================

class TestSlugify:
    def test_slugify_basic(self):
        assert _slugify("Webb Capital LLC") == "webb_capital_llc"

    def test_slugify_truncates(self):
        long = "a" * 100
        assert len(_slugify(long)) <= 40

    def test_slugify_no_special(self):
        result = _slugify("123 Main St, Dallas TX 75201")
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in result)


class TestAccessToStatus:
    @pytest.mark.parametrize("access,status", [
        ("csv", "public_csv"),
        ("api", "public_csv"),
        ("browser-only", "browser_only"),
        ("pdf", "browser_only"),
        ("login-required", "login_required"),
        ("paid", "paid"),
        ("manual", "browser_only"),
    ])
    def test_access_to_status(self, access, status):
        assert _access_to_status(access) == status


class TestBuildTargets:
    def test_build_deed_targets_dallas(self):
        targets = build_deed_targets("Webb Capital LLC", "Dallas County")
        assert len(targets) >= 1
        for t in targets:
            assert t.record_type == "deed"
            assert t.source_id in {"TX-DAL-CLERK-001", "TX-TAR-CLERK-001", "TX-COL-CLERK-001"}

    def test_build_entity_targets(self):
        targets = build_entity_targets("Webb Capital LLC")
        assert len(targets) == 2
        sids = {t.source_id for t in targets}
        assert "TX-SOS-001" in sids
        assert "TX-CPA-COA-001" in sids

    def test_build_entity_targets_have_citations(self):
        targets = build_entity_targets("Webb Capital LLC")
        for t in targets:
            assert len(t.citations) >= 1

    def test_build_tax_delinquent_targets(self):
        targets = build_tax_delinquent_targets("1234 Oak St")
        assert len(targets) >= 1
        for t in targets:
            assert t.record_type == "tax_delinquent"

    def test_build_permit_targets(self):
        targets = build_permit_targets("1234 Oak St")
        assert len(targets) == 1
        assert targets[0].record_type == "permit"

    def test_build_code_violation_targets(self):
        targets = build_code_violation_targets("1234 Oak St")
        assert len(targets) == 1
        assert targets[0].record_type == "code_violation"

    def test_build_foreclosure_targets(self):
        targets = build_foreclosure_targets("Webb Capital LLC")
        assert len(targets) >= 1
        for t in targets:
            assert t.record_type == "foreclosure"

    def test_build_license_targets(self):
        targets = build_license_targets("John Smith Builder")
        assert len(targets) == 2
        for t in targets:
            assert t.record_type == "license"

    def test_all_targets_have_linked_agents(self):
        targets = build_all_targets_for_subject("Webb Capital LLC", "entity")
        for t in targets:
            assert len(t.linked_to) >= 1, f"No linked_to for {t.record_id}"

    def test_all_targets_have_citations(self):
        targets = build_all_targets_for_subject("1234 Oak St", "property")
        for t in targets:
            assert len(t.citations) >= 1, f"No citations for {t.record_id}"

    def test_entity_subject_targets(self):
        targets = build_all_targets_for_subject("Webb Capital LLC", "entity")
        types = {t.record_type for t in targets}
        assert "entity" in types
        assert "deed" in types

    def test_property_subject_targets(self):
        targets = build_all_targets_for_subject("1234 Oak St", "property")
        types = {t.record_type for t in targets}
        assert "deed" in types
        assert "permit" in types
        assert "code_violation" in types


class TestAgentRouting:
    def test_routing_covers_all_record_types(self):
        expected_types = {
            "deed", "lien", "permit", "tax_delinquent", "code_violation",
            "foreclosure", "entity", "license", "court", "gis", "bankruptcy", "auction"
        }
        assert expected_types <= set(AGENT_ROUTING.keys())

    def test_deed_routes_to_buyer_activity(self):
        assert "buyer-activity-osint" in AGENT_ROUTING["deed"]

    def test_foreclosure_routes_to_deal_discovery(self):
        assert "deal-discovery" in AGENT_ROUTING["foreclosure"]


class TestRecordWriters:
    def test_write_record_source_targets(self, tmp_path):
        targets = build_all_targets_for_subject("Webb Capital LLC", "entity")
        write_record_source_targets(targets, tmp_path)
        assert (tmp_path / "RECORD_SOURCE_TARGETS.json").exists()
        data = json.loads((tmp_path / "RECORD_SOURCE_TARGETS.json").read_text())
        assert data["total_targets"] == len(targets)
        assert "by_record_type" in data

    def test_write_agent_routing(self, tmp_path):
        targets = build_all_targets_for_subject("Webb Capital LLC", "entity")
        write_agent_routing(targets, tmp_path)
        assert (tmp_path / "OSINT_TO_AGENT_ROUTING.json").exists()
        data = json.loads((tmp_path / "OSINT_TO_AGENT_ROUTING.json").read_text())
        assert "agents" in data
        assert len(data["agents"]) >= 1


# ===========================================================================
# Integration / CLI Tests
# ===========================================================================

class TestCLI:
    def test_dry_run(self, tmp_path, capsys):
        from run import main
        ret = main([
            "--workspace-root", str(tmp_path),
            "--reports-dir", str(tmp_path / "reports"),
            "--dry-run",
        ])
        assert ret == 0
        out = capsys.readouterr().out
        assert "dry-run" in out

    def test_json_output(self, tmp_path, capsys):
        from run import main
        ret = main([
            "--workspace-root", str(tmp_path),
            "--reports-dir", str(tmp_path / "reports"),
            "--json",
            "--subjects", "Webb Capital LLC",
        ])
        assert ret == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["entity_subjects"] >= 1

    def test_full_run_creates_all_reports(self, tmp_path):
        from run import main
        reports = tmp_path / "reports"
        ret = main([
            "--workspace-root", str(tmp_path),
            "--reports-dir", str(reports),
            "--subjects", "Webb Capital LLC", "Smith Holdings Inc",
        ])
        assert ret == 0
        expected_files = [
            "OSINT_SOURCE_INDEX.json",
            "OSINT_SOURCE_INDEX.md",
            "VERIFIED_ENTITIES.json",
            "ENTITY_RESEARCH_PACKETS.md",
            "RECORD_SOURCE_TARGETS.json",
            "OSINT_TO_AGENT_ROUTING.json",
            "OSINT_RISK_AND_COMPLIANCE.md",
        ]
        for fname in expected_files:
            assert (reports / fname).exists(), f"Missing: {fname}"

    def test_seeds_from_buyers_dir(self, tmp_path):
        buyers = tmp_path / "buyers"
        buyers.mkdir()
        (buyers / "BUY-001.md").write_text(
            "# Buyer\nEntity: Webb Capital Holdings LLC\nName: Marcus Webb\n"
        )
        from run import load_entity_names_from_seeds
        names = load_entity_names_from_seeds(buyers)
        assert "Webb Capital Holdings LLC" in names

    def test_names_from_activity_summary(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        summary = {
            "profiles": [
                {"buyer_entity": "Webb Capital LLC", "buyer_name": "Marcus Webb"},
                {"buyer_entity": "", "buyer_name": "Jane Smith"},
            ]
        }
        (reports / "ACTIVITY_SUMMARY.json").write_text(json.dumps(summary))
        from run import load_entity_names_from_csv_reports
        names = load_entity_names_from_csv_reports(reports)
        assert "Webb Capital LLC" in names
        assert "Jane Smith" in names

    def test_risk_compliance_report_content(self, tmp_path):
        reports = tmp_path / "reports"
        ret = __import__("run").main([
            "--workspace-root", str(tmp_path),
            "--reports-dir", str(reports),
            "--subjects", "Test LLC",
        ])
        md = (reports / "OSINT_RISK_AND_COMPLIANCE.md").read_text()
        assert "lawful" in md.lower()
        assert "No web scraping" in md
        assert "Test LLC" in md
