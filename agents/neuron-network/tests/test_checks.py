"""
Tests for the neuron-network check infrastructure.
Does NOT require live backends — validates the classifier and report builders.

Run: python3 -m pytest agents/neuron-network/tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import (
    CheckResult,
    _classify_failure,
    build_status_md,
    build_connector_health_json,
    DATA_FLOW_MAP,
)
from datetime import datetime, timezone


# ── _classify_failure ─────────────────────────────────────────────────────────

def test_classify_test_command_missing():
    assert _classify_failure("test -f agents/foo/run.py", "", "") == "missing"

def test_classify_test_d_missing():
    assert _classify_failure("test -d integrations/MiroFish", "", "") == "missing"

def test_classify_command_not_found():
    assert _classify_failure(
        "hermes --version", "", "hermes: command not found"
    ) == "missing"

def test_classify_module_not_found():
    assert _classify_failure(
        "python3 -c \"import mem0\"",
        "",
        "ModuleNotFoundError: No module named 'mem0'",
    ) == "not_installed"

def test_classify_no_credentials_supabase():
    assert _classify_failure(
        "python3 -c \"...\"",
        "AssertionError: SUPABASE_URL/KEY not set",
        "",
    ) == "no_credentials"

def test_classify_generic_failure():
    assert _classify_failure("docker ps", "", "Cannot connect to the Docker daemon") == "failed"


# ── build_status_md ───────────────────────────────────────────────────────────

def _make_results(statuses: list[tuple]) -> list[CheckResult]:
    results = []
    for name, cat, status in statuses:
        installed = status == "ok"
        connected = status == "ok"
        results.append(CheckResult(
            name=name, category=cat, command=f"test -f {name}",
            status=status, output="", error="some error" if status != "ok" else "",
            duration_ms=12, installed=installed, connected=connected,
        ))
    return results


def test_status_md_contains_portfolio_distress_section():
    results = _make_results([
        ("Deal Scoring Engine", "ai_agent", "ok"),
        ("Hermes", "backend", "missing"),
    ])
    ts = datetime(2026, 5, 10, 0, 0, 0, tzinfo=timezone.utc)
    md = build_status_md(results, ts, "20260510T000000Z")
    # Summary table must be present
    assert "| ✅ OK | 1 |" in md
    assert "| ❌ Missing | 1 |" in md
    # Failure detail block
    assert "Hermes" in md
    assert "MISSING" in md


def test_status_md_no_fake_greens():
    """Every missing check must not appear as OK."""
    results = _make_results([
        ("Mem0", "python_lib", "not_installed"),
        ("Neo4j Docker", "backend", "failed"),
    ])
    ts = datetime(2026, 5, 10, tzinfo=timezone.utc)
    md = build_status_md(results, ts, "20260510T000000Z")
    assert "| ✅ OK | 0 |" in md
    assert "NOT INSTALLED" in md
    assert "FAILED" in md


# ── build_connector_health_json ───────────────────────────────────────────────

def test_connector_health_summary_counts():
    results = _make_results([
        ("A", "backend", "ok"),
        ("B", "python_lib", "not_installed"),
        ("C", "ai_agent", "missing"),
        ("D", "integration", "no_credentials"),
    ])
    ts = datetime(2026, 5, 10, tzinfo=timezone.utc)
    health = build_connector_health_json(results, ts)
    assert health["summary"]["ok"] == 1
    assert health["summary"]["not_installed"] == 1
    assert health["summary"]["missing"] == 1
    assert health["summary"]["no_credentials"] == 1
    assert health["summary"]["total"] == 4
    assert len(health["checks"]) == 4


def test_connector_health_preserves_command():
    results = _make_results([("Deal Scoring Engine", "ai_agent", "ok")])
    ts = datetime(2026, 5, 10, tzinfo=timezone.utc)
    health = build_connector_health_json(results, ts)
    assert health["checks"][0]["command"] == "test -f Deal Scoring Engine"


# ── DATA_FLOW_MAP ─────────────────────────────────────────────────────────────

def test_data_flow_map_has_nodes_and_edges():
    assert "nodes" in DATA_FLOW_MAP
    assert "edges" in DATA_FLOW_MAP
    assert len(DATA_FLOW_MAP["nodes"]) > 0
    assert len(DATA_FLOW_MAP["edges"]) > 0


def test_data_flow_map_deal_scoring_receives_distress():
    edges = DATA_FLOW_MAP["edges"]
    distress_to_scoring = [
        e for e in edges
        if e["from"] == "portfolio_distress" and e["to"] == "deal_scoring"
    ]
    assert len(distress_to_scoring) == 1


def test_data_flow_map_all_edge_nodes_exist():
    node_ids = {n["id"] for n in DATA_FLOW_MAP["nodes"]}
    for edge in DATA_FLOW_MAP["edges"]:
        assert edge["from"] in node_ids, f"unknown 'from' node: {edge['from']}"
        assert edge["to"] in node_ids, f"unknown 'to' node: {edge['to']}"
