"""End-to-end test: run the full pipeline against the sample fixtures."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import OwnerRecord
from run import load_records, run_pipeline


FIXTURES = Path(__file__).parent / "fixtures" / "sample_records.json"


class TestEndToEnd:
    def test_fixture_file_exists(self):
        assert FIXTURES.exists()

    def test_load_records(self):
        records = load_records(FIXTURES)
        assert len(records) >= 10

    def test_full_pipeline_produces_outputs(self):
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            assert "VERIFIED_BUILDERS" in paths
            assert "POSSIBLE_CASH_BUYERS" in paths
            assert "BUYER_CONFIDENCE_SCORES" in paths
            assert "BUYER_ACTIVITY_REPORT" in paths

            for path in paths.values():
                assert Path(path).exists()

    def test_verified_builders_json_structure(self):
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["VERIFIED_BUILDERS"]).read_text())

        assert "generated_at" in data
        assert "count" in data
        assert "builders" in data
        assert isinstance(data["builders"], list)
        assert data["count"] == len(data["builders"])

        for builder in data["builders"]:
            assert "owner_name" in builder
            assert "builder_score" in builder
            assert builder["builder_score"] >= 40  # must meet threshold

    def test_possible_cash_buyers_json_structure(self):
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["POSSIBLE_CASH_BUYERS"]).read_text())

        assert "cash_buyers" in data
        for buyer in data["cash_buyers"]:
            assert "investor_score" in buyer
            assert buyer["investor_score"] >= 30  # must meet threshold

    def test_confidence_scores_includes_all_profiles(self):
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["BUYER_CONFIDENCE_SCORES"]).read_text())

        assert "profiles" in data
        assert "quarantine" in data
        assert data["total_profiles"] > 0

    def test_activity_report_is_markdown(self):
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            content = Path(paths["BUYER_ACTIVITY_REPORT"]).read_text()

        assert content.startswith("# Buyer Activity Report")
        assert "## Verified Builders" in content
        assert "## Possible Cash Buyers" in content
        assert "## Quarantine Log" in content

    def test_sample_mesa_ridge_is_builder(self):
        """MESA RIDGE CONSTRUCTION LLC should be a verified builder."""
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["VERIFIED_BUILDERS"]).read_text())

        names = [b["owner_name"] for b in data["builders"]]
        assert any("MESA RIDGE" in n for n in names)

    def test_sample_sunbelt_is_cash_buyer(self):
        """SUNBELT ACQUISITIONS CAPITAL LLC should be a possible cash buyer."""
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["POSSIBLE_CASH_BUYERS"]).read_text())

        names = [b["owner_name"] for b in data["cash_buyers"]]
        assert any("SUNBELT" in n for n in names)

    def test_empty_record_is_quarantined(self):
        """The blank record in fixtures should be quarantined."""
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["BUYER_CONFIDENCE_SCORES"]).read_text())

        assert data["quarantined_records"] >= 1

    def test_individual_owner_not_in_builders(self):
        """JOHN SMITH (individual, no signals) should not appear as a builder."""
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["VERIFIED_BUILDERS"]).read_text())

        names = [b["owner_name"] for b in data["builders"]]
        assert not any("JOHN SMITH" in n for n in names)

    def test_evidence_paths_preserved(self):
        """Every builder entry must have signal_evidence with evidence strings."""
        records = load_records(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(records, Path(tmp))
            data = json.loads(Path(paths["VERIFIED_BUILDERS"]).read_text())

        for builder in data["builders"]:
            assert len(builder["signal_evidence"]) > 0
            for sig in builder["signal_evidence"]:
                assert sig["evidence"]  # must be non-empty string
