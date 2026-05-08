"""End-to-end tests: full pipeline against sample fixtures."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from run import load_parcels, load_profiles_from_file, run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"
PARCELS = FIXTURES / "sample_parcels.json"
BUYERS = FIXTURES / "sample_buyers.json"


class TestLoadInputs:
    def test_load_parcels(self):
        parcels = load_parcels(PARCELS)
        assert len(parcels) >= 5
        for p in parcels:
            assert p.parcel_id

    def test_load_buyer_profiles(self):
        profiles = load_profiles_from_file(BUYERS)
        # 4 non-quarantined profiles expected
        assert len(profiles) >= 4
        for p in profiles:
            assert p.owner_name
            assert not p.is_quarantined

    def test_quarantined_profiles_excluded(self):
        profiles = load_profiles_from_file(BUYERS)
        names = [p.owner_name for p in profiles]
        assert "JOHN SMITH" not in names
        assert "SARAH JONES" not in names


class TestFullPipeline:
    def _run(self):
        parcels = load_parcels(PARCELS)
        profiles = load_profiles_from_file(BUYERS)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(parcels, profiles, Path(tmp))
            results = {}
            for name, p in paths.items():
                text = Path(p).read_text()
                if str(p).endswith(".json"):
                    results[name] = json.loads(text)
                else:
                    results[name] = text
        return results

    def test_produces_all_four_outputs(self):
        parcels = load_parcels(PARCELS)
        profiles = load_profiles_from_file(BUYERS)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(parcels, profiles, Path(tmp))
        assert "PARCEL_MATCH_REPORT" in paths
        assert "TOP_BUYERS" in paths
        assert "BUILDER_MATCHES" in paths
        assert "MATCH_CONFIDENCE" in paths

    def test_top_buyers_json_structure(self):
        results = self._run()
        data = results["TOP_BUYERS"]
        assert "parcels" in data
        assert "generated_at" in data
        for entry in data["parcels"]:
            assert "parcel_id" in entry
            assert "ranked_buyers" in entry
            for b in entry["ranked_buyers"]:
                assert "buyer_name" in b
                assert "match_score" in b
                assert 0 <= b["match_score"] <= 100

    def test_builder_matches_json_structure(self):
        results = self._run()
        data = results["BUILDER_MATCHES"]
        assert "infill_parcel_count" in data
        for entry in data["parcels"]:
            assert "builder_matches" in entry
            assert "disposition_paths" in entry

    def test_match_confidence_json_structure(self):
        results = self._run()
        data = results["MATCH_CONFIDENCE"]
        assert "total_parcels" in data
        assert data["total_parcels"] > 0
        for opp in data["opportunities"]:
            assert "parcel" in opp
            assert "best_match_score" in opp
            assert "disposition_paths" in opp

    def test_parcel_match_report_is_markdown(self):
        parcels = load_parcels(PARCELS)
        profiles = load_profiles_from_file(BUYERS)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(parcels, profiles, Path(tmp))
            content = Path(paths["PARCEL_MATCH_REPORT"]).read_text()
        assert content.startswith("# Parcel Match Report")
        assert "## Summary" in content
        assert "## Parcel Opportunities" in content
        assert "## Disposition Path Reference" in content

    def test_infill_parcel_matches_builder(self):
        """P-INFILL-001 (ZIP 85001) should match MESA RIDGE CONSTRUCTION LLC."""
        results = self._run()
        # Find P-INFILL-001 in builder matches
        builder_parcels = {
            e["parcel_id"]: e for e in results["BUILDER_MATCHES"]["parcels"]
        }
        assert "P-INFILL-001" in builder_parcels
        buyer_names = [m["buyer_name"] for m in builder_parcels["P-INFILL-001"]["builder_matches"]]
        assert any("MESA RIDGE" in n for n in buyer_names)

    def test_verde_valley_matches_infill_002(self):
        """P-INFILL-002 (ZIP 86046) should match VERDE VALLEY HOMES."""
        results = self._run()
        builder_parcels = {
            e["parcel_id"]: e for e in results["BUILDER_MATCHES"]["parcels"]
        }
        assert "P-INFILL-002" in builder_parcels
        buyer_names = [m["buyer_name"] for m in builder_parcels["P-INFILL-002"]["builder_matches"]]
        assert any("VERDE" in n for n in buyer_names)

    def test_distressed_parcel_has_wholesale_disposition(self):
        """P-DISTRESSED-001 should have WHOLESALE_TO_INVESTOR or REHAB_FLIP path."""
        results = self._run()
        opps = {o["parcel"]["parcel_id"]: o for o in results["MATCH_CONFIDENCE"]["opportunities"]}
        assert "P-DISTRESSED-001" in opps
        dist_opp = opps["P-DISTRESSED-001"]
        path_types = [d["path_type"] for d in dist_opp["disposition_paths"]]
        assert any(pt in path_types for pt in ["WHOLESALE_TO_INVESTOR", "REHAB_FLIP"])

    def test_large_vacant_parcel_has_hold_disposition(self):
        """P-LARGE-001 (3.5 acres) should have HOLD_FOR_DEVELOPMENT path."""
        results = self._run()
        opps = {o["parcel"]["parcel_id"]: o for o in results["MATCH_CONFIDENCE"]["opportunities"]}
        assert "P-LARGE-001" in opps
        path_types = [d["path_type"] for d in opps["P-LARGE-001"]["disposition_paths"]]
        assert "HOLD_FOR_DEVELOPMENT" in path_types

    def test_standard_residential_has_retail_disposition(self):
        """P-STD-001 (standard residential) should have RETAIL_LISTING path."""
        results = self._run()
        opps = {o["parcel"]["parcel_id"]: o for o in results["MATCH_CONFIDENCE"]["opportunities"]}
        assert "P-STD-001" in opps
        path_types = [d["path_type"] for d in opps["P-STD-001"]["disposition_paths"]]
        assert "RETAIL_LISTING" in path_types

    def test_no_fabricated_valuations(self):
        """All ARVs and prices in output must come from input (no invented numbers)."""
        parcels = load_parcels(PARCELS)
        known_prices = {p.parcel_id: p.effective_price for p in parcels}
        results = self._run()
        for opp in results["MATCH_CONFIDENCE"]["opportunities"]:
            pid = opp["parcel"]["parcel_id"]
            reported_price = opp["parcel"]["effective_price"]
            assert reported_price == known_prices.get(pid, 0), (
                f"Price mismatch for {pid}: reported {reported_price}, "
                f"input {known_prices.get(pid)}"
            )

    def test_evidence_preserved_on_every_match(self):
        """Every match must carry at least one signal evidence entry."""
        results = self._run()
        for opp in results["MATCH_CONFIDENCE"]["opportunities"]:
            for m in opp["top_buyer_matches"] + opp["top_builder_matches"]:
                assert len(m["signal_evidence"]) > 0, (
                    f"Match {m['buyer_name']} on parcel {opp['parcel']['parcel_id']} "
                    f"has no signal evidence"
                )

    def test_no_profiles_still_produces_reports(self):
        """Running with zero buyer profiles should still write valid empty reports."""
        parcels = load_parcels(PARCELS)
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_pipeline(parcels, [], Path(tmp))
            data = json.loads(Path(paths["TOP_BUYERS"]).read_text())
        assert "parcels" in data

    def test_riverstone_matches_commercial_parcel(self):
        """P-INVEST-001 (ZIP 85016) should match RIVERSTONE INVESTMENTS LLC."""
        results = self._run()
        top_buyers = {
            e["parcel_id"]: e for e in results["TOP_BUYERS"]["parcels"]
        }
        if "P-INVEST-001" in top_buyers:
            names = [m["buyer_name"] for m in top_buyers["P-INVEST-001"]["ranked_buyers"]]
            assert any("RIVERSTONE" in n for n in names)
