"""
Tests for the Builder Verification Agent.

Coverage:
  - Verified builder (LLC, builder keywords, permits, nearby parcels, repeat)
  - Possible cash buyer (LLC, repeat, mailing mismatch, vacant land, cluster)
  - Repeat buyer (individual, ≥3 acquisitions, below builder/investor thresholds)
  - Weak record (missing required owner_name field)
  - Individual homeowner (no signals → quarantined)
  - Cross-record batch repeat detection
  - Signal extraction unit tests
  - Scoring unit tests
  - Output file generation
  - CLI entry point (dry-run, bad path, bad stdin)
  - Mixed-batch counts
  - Research evidence extraction (SOS, website, profiles, county records)
  - Source-backed confidence scoring and boosts
  - Entity matching across batches
  - Entity intelligence report generation
"""

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from run import (
    BUILDER_THRESHOLD,
    INVESTOR_THRESHOLD,
    REPEAT_BUYER_MIN,
    _MAX_BUILDER_BOOST,
    _MAX_INVESTOR_BOOST,
    _WR_SOS_ACTIVE,
    _WR_CONSTRUCTION_PROFILE,
    _WR_WEBSITE_CONSTRUCTION,
    _WR_COUNTY_PERMIT_HEAVY,
    _WR_CORROBORATION_3PLUS,
    BuyerType,
    SourceType,
    SourceCitation,
    ResearchEvidence,
    BuilderVerificationAgent,
    BuyerSignals,
    _detect_builder_keywords,
    _detect_entity,
    _addresses_mismatch,
    _normalize_owner,
    _extract_signals,
    _extract_research_evidence,
    _research_confidence,
    _research_builder_boost,
    _research_investor_boost,
    _builder_score,
    _investor_score,
    _route,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


VERIFIED_BUILDER    = _load("verified_builder")
CASH_BUYER          = _load("cash_buyer")
REPEAT_BUYER        = _load("repeat_buyer")
WEAK_RECORD         = _load("weak_record")
HOMEOWNER           = _load("individual_homeowner")

_SINGLE_BATCH: dict[str, int] = {
    "apex construction llc": 1,
    "westside capital holdings llc": 1,
    "robert chen": 1,
    "": 1,
    "maria santos": 1,
}


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


class TestNormalizeOwner(unittest.TestCase):
    def test_lowercases_and_strips(self):
        self.assertEqual(_normalize_owner("  APEX LLC  "), "apex llc")

    def test_collapses_punctuation(self):
        # Punctuation is replaced by space then collapsed → single space
        self.assertEqual(_normalize_owner("Smith, John R."), "smith john r")

    def test_unicode_normalised(self):
        # Accented chars should survive normalisation as ascii equivalents
        result = _normalize_owner("José García")
        self.assertIsInstance(result, str)


class TestDetectBuilderKeywords(unittest.TestCase):
    def test_construction_matched(self):
        self.assertIn("construction", _detect_builder_keywords("Apex Construction LLC"))

    def test_builder_matched(self):
        matches = _detect_builder_keywords("Smith Builders Inc")
        self.assertTrue(any("build" in m for m in matches))

    def test_developer_matched(self):
        matches = _detect_builder_keywords("Premier Developers Group")
        self.assertTrue(any("develop" in m for m in matches))

    def test_no_match_on_clean_name(self):
        self.assertEqual(_detect_builder_keywords("Maria Santos"), [])

    def test_no_match_on_holding_company(self):
        self.assertEqual(
            _detect_builder_keywords("Westside Capital Holdings LLC"), []
        )

    def test_case_insensitive(self):
        matches = _detect_builder_keywords("INFILL HOMES TRUST")
        self.assertTrue(matches)

    def test_deduplicates_matches(self):
        matches = _detect_builder_keywords("Builder builder BUILDER")
        self.assertEqual(len(matches), 1)


class TestDetectEntity(unittest.TestCase):
    def test_llc_detected(self):
        self.assertIsNotNone(_detect_entity("Apex Construction LLC"))

    def test_inc_detected(self):
        self.assertIsNotNone(_detect_entity("Smith Building Inc"))

    def test_trust_detected(self):
        self.assertIsNotNone(_detect_entity("Oak Street Trust"))

    def test_individual_not_detected(self):
        self.assertIsNone(_detect_entity("Maria Santos"))

    def test_holdings_detected(self):
        self.assertIsNotNone(_detect_entity("Westside Capital Holdings LLC"))


class TestAddressMismatch(unittest.TestCase):
    def test_different_addresses_are_mismatch(self):
        self.assertTrue(
            _addresses_mismatch("412 Elm St, Springfield", "800 Industrial Pkwy, Springfield")
        )

    def test_same_addresses_not_mismatch(self):
        self.assertFalse(
            _addresses_mismatch("631 Pine Street, Alton, IL", "631 Pine Street, Alton, IL")
        )

    def test_none_parcel_is_not_mismatch(self):
        self.assertFalse(_addresses_mismatch(None, "123 Main St"))

    def test_none_mailing_is_not_mismatch(self):
        self.assertFalse(_addresses_mismatch("123 Main St", None))

    def test_case_insensitive_match(self):
        self.assertFalse(
            _addresses_mismatch("123 MAIN ST", "123 main st")
        )

    def test_whitespace_normalised(self):
        self.assertFalse(
            _addresses_mismatch("123  Main  St", "123 Main St")
        )


class TestExtractSignals(unittest.TestCase):
    def _sig(self, record: dict) -> BuyerSignals:
        batch = {_normalize_owner(str(record.get("owner_name", ""))): 1}
        return _extract_signals(record, batch)

    def test_builder_keywords_extracted(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertTrue(sig.has_builder_keywords)
        self.assertTrue(sig.builder_keyword_matches)

    def test_company_owned_flag(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertTrue(sig.is_company_owned)

    def test_permit_count_extracted(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertEqual(sig.permit_count, 7)
        self.assertTrue(sig.has_permit_activity)

    def test_vacant_land_detected(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertTrue(sig.owns_vacant_land)

    def test_mailing_mismatch_detected(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertTrue(sig.mailing_address_mismatch)

    def test_purchase_cluster_detected(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertTrue(sig.has_purchase_cluster)
        self.assertEqual(sig.purchase_cluster_days, 22)

    def test_no_cluster_when_over_threshold(self):
        record = dict(REPEAT_BUYER, purchase_cluster_days=120)
        sig = self._sig(record)
        self.assertFalse(sig.has_purchase_cluster)

    def test_individual_has_no_company_flag(self):
        sig = self._sig(HOMEOWNER)
        self.assertFalse(sig.is_company_owned)

    def test_source_evidence_populated(self):
        sig = self._sig(VERIFIED_BUILDER)
        self.assertTrue(sig.source_evidence)

    def test_source_file_in_evidence(self):
        sig = self._sig(VERIFIED_BUILDER)
        evidence_text = " ".join(sig.source_evidence)
        self.assertIn("county_records", evidence_text)

    def test_batch_count_captured(self):
        batch = {"apex construction llc": 3}
        sig = _extract_signals(VERIFIED_BUILDER, batch)
        self.assertEqual(sig.batch_acquisition_count, 3)

    def test_effective_acquisitions_uses_max(self):
        # prior_acquisitions=6 in fixture; batch_count=2 → max=6
        batch = {"apex construction llc": 2}
        sig = _extract_signals(VERIFIED_BUILDER, batch)
        self.assertGreaterEqual(sig.prior_acquisitions, 6)


class TestBuilderScoring(unittest.TestCase):
    def _score(self, record: dict) -> float:
        batch = {_normalize_owner(str(record.get("owner_name", ""))): 1}
        sig = _extract_signals(record, batch)
        return _builder_score(sig)

    def test_verified_builder_scores_max(self):
        self.assertAlmostEqual(self._score(VERIFIED_BUILDER), 1.0, places=4)

    def test_cash_buyer_scores_below_threshold(self):
        score = self._score(CASH_BUYER)
        self.assertLess(score, BUILDER_THRESHOLD)

    def test_repeat_buyer_scores_low(self):
        score = self._score(REPEAT_BUYER)
        self.assertLess(score, BUILDER_THRESHOLD)

    def test_homeowner_scores_zero(self):
        self.assertEqual(self._score(HOMEOWNER), 0.0)

    def test_permits_contribute_to_score(self):
        with_permits = dict(HOMEOWNER, permit_count=5, owner_name="Maria Santos")
        without_permits = dict(HOMEOWNER, permit_count=0)
        self.assertGreater(self._score(with_permits), self._score(without_permits))

    def test_keywords_contribute_to_score(self):
        with_kw = dict(HOMEOWNER, owner_name="Santos Construction")
        self.assertGreater(self._score(with_kw), self._score(HOMEOWNER))

    def test_score_bounded_0_to_1(self):
        sig = BuyerSignals(
            has_builder_keywords=True,
            permit_count=100,
            is_company_owned=True,
            prior_acquisitions=100,
            nearby_parcel_count=100,
        )
        self.assertLessEqual(_builder_score(sig), 1.0)
        self.assertGreaterEqual(_builder_score(sig), 0.0)


class TestInvestorScoring(unittest.TestCase):
    def _score(self, record: dict) -> float:
        batch = {_normalize_owner(str(record.get("owner_name", ""))): 1}
        sig = _extract_signals(record, batch)
        return _investor_score(sig)

    def test_cash_buyer_scores_above_threshold(self):
        score = self._score(CASH_BUYER)
        self.assertGreaterEqual(score, INVESTOR_THRESHOLD)

    def test_verified_builder_investor_score_non_zero(self):
        # Builder also has investor signals; both scores can be high
        score = self._score(VERIFIED_BUILDER)
        self.assertGreater(score, 0.0)

    def test_homeowner_scores_zero(self):
        self.assertEqual(self._score(HOMEOWNER), 0.0)

    def test_repeat_buyer_scores_below_investor_threshold(self):
        score = self._score(REPEAT_BUYER)
        self.assertLess(score, INVESTOR_THRESHOLD)

    def test_mismatch_contributes_to_score(self):
        with_mismatch = dict(
            HOMEOWNER,
            mailing_address="999 Other Street, Chicago, IL",
        )
        self.assertGreater(self._score(with_mismatch), self._score(HOMEOWNER))

    def test_vacant_land_contributes_to_score(self):
        with_vacant = dict(HOMEOWNER, land_use="vacant")
        self.assertGreater(self._score(with_vacant), self._score(HOMEOWNER))

    def test_score_bounded_0_to_1(self):
        sig = BuyerSignals(
            prior_acquisitions=100,
            is_company_owned=True,
            mailing_address_mismatch=True,
            owns_vacant_land=True,
            has_purchase_cluster=True,
        )
        self.assertLessEqual(_investor_score(sig), 1.0)
        self.assertGreaterEqual(_investor_score(sig), 0.0)


# ---------------------------------------------------------------------------
# Integration tests: full agent run
# ---------------------------------------------------------------------------


class TestVerifiedBuilderIntegration(unittest.TestCase):
    """LLC with builder keywords, high permits, nearby parcels → VERIFIED_BUILDER."""

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([VERIFIED_BUILDER])

    def test_classified_as_verified_builder(self):
        self.assertEqual(len(self.report.verified_builders), 1)
        self.assertEqual(len(self.report.possible_cash_buyers), 0)

    def test_builder_confidence_at_max(self):
        profile = self.report.verified_builders[0]
        self.assertAlmostEqual(profile.builder_confidence, 1.0, places=4)

    def test_builder_confidence_above_threshold(self):
        profile = self.report.verified_builders[0]
        self.assertGreaterEqual(profile.builder_confidence, BUILDER_THRESHOLD)

    def test_keywords_in_signals(self):
        profile = self.report.verified_builders[0]
        self.assertTrue(profile.signals.has_builder_keywords)
        self.assertTrue(profile.signals.builder_keyword_matches)

    def test_entity_type_detected(self):
        profile = self.report.verified_builders[0]
        self.assertTrue(profile.signals.is_company_owned)

    def test_evidence_flags_populated(self):
        profile = self.report.verified_builders[0]
        self.assertTrue(profile.evidence_flags)

    def test_evidence_contains_permit_info(self):
        profile = self.report.verified_builders[0]
        evidence_text = " ".join(profile.evidence_flags)
        self.assertIn("permit", evidence_text.lower())

    def test_source_file_preserved(self):
        profile = self.report.verified_builders[0]
        self.assertEqual(profile.source_file, VERIFIED_BUILDER["source_file"])

    def test_sale_price_preserved(self):
        profile = self.report.verified_builders[0]
        self.assertEqual(profile.sale_price, float(VERIFIED_BUILDER["sale_price"]))

    def test_total_processed_is_one(self):
        self.assertEqual(self.report.total_processed, 1)


class TestCashBuyerIntegration(unittest.TestCase):
    """LLC holding company, repeat acquisitions, mailing mismatch, vacant land → POSSIBLE_CASH_BUYER."""

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([CASH_BUYER])

    def test_classified_as_possible_cash_buyer(self):
        self.assertEqual(len(self.report.possible_cash_buyers), 1)
        self.assertEqual(len(self.report.verified_builders), 0)

    def test_investor_confidence_above_threshold(self):
        profile = self.report.possible_cash_buyers[0]
        self.assertGreaterEqual(profile.investor_confidence, INVESTOR_THRESHOLD)

    def test_builder_confidence_below_threshold(self):
        profile = self.report.possible_cash_buyers[0]
        self.assertLess(profile.builder_confidence, BUILDER_THRESHOLD)

    def test_no_builder_keywords(self):
        profile = self.report.possible_cash_buyers[0]
        self.assertFalse(profile.signals.has_builder_keywords)

    def test_mailing_mismatch_signal(self):
        profile = self.report.possible_cash_buyers[0]
        self.assertTrue(profile.signals.mailing_address_mismatch)

    def test_vacant_land_signal(self):
        profile = self.report.possible_cash_buyers[0]
        self.assertTrue(profile.signals.owns_vacant_land)

    def test_purchase_cluster_signal(self):
        profile = self.report.possible_cash_buyers[0]
        self.assertTrue(profile.signals.has_purchase_cluster)

    def test_evidence_flags_include_mismatch(self):
        profile = self.report.possible_cash_buyers[0]
        evidence_text = " ".join(profile.evidence_flags)
        self.assertIn("mismatch", evidence_text.lower())

    def test_evidence_flags_include_vacant(self):
        profile = self.report.possible_cash_buyers[0]
        evidence_text = " ".join(profile.evidence_flags)
        self.assertIn("vacant", evidence_text.lower())


class TestRepeatBuyerIntegration(unittest.TestCase):
    """Individual with ≥3 acquisitions, no builder/investor signals → REPEAT_BUYER."""

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([REPEAT_BUYER])

    def test_classified_as_repeat_buyer(self):
        self.assertEqual(len(self.report.repeat_buyers), 1)
        self.assertEqual(len(self.report.verified_builders), 0)
        self.assertEqual(len(self.report.possible_cash_buyers), 0)

    def test_acquisitions_at_or_above_min(self):
        profile = self.report.repeat_buyers[0]
        self.assertGreaterEqual(profile.signals.prior_acquisitions, REPEAT_BUYER_MIN)

    def test_builder_confidence_below_threshold(self):
        profile = self.report.repeat_buyers[0]
        self.assertLess(profile.builder_confidence, BUILDER_THRESHOLD)

    def test_investor_confidence_below_threshold(self):
        profile = self.report.repeat_buyers[0]
        self.assertLess(profile.investor_confidence, INVESTOR_THRESHOLD)

    def test_no_company_ownership(self):
        profile = self.report.repeat_buyers[0]
        self.assertFalse(profile.signals.is_company_owned)

    def test_no_address_mismatch(self):
        profile = self.report.repeat_buyers[0]
        self.assertFalse(profile.signals.mailing_address_mismatch)

    def test_evidence_contains_acquisitions(self):
        profile = self.report.repeat_buyers[0]
        evidence_text = " ".join(profile.evidence_flags)
        self.assertIn("acqui", evidence_text.lower())


class TestWeakRecordIntegration(unittest.TestCase):
    """Record missing owner_name → WEAK_RECORD, not scored."""

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([WEAK_RECORD])

    def test_classified_as_weak_record(self):
        self.assertEqual(len(self.report.weak_records), 1)
        self.assertEqual(len(self.report.verified_builders), 0)

    def test_weak_reason_mentions_owner_name(self):
        profile = self.report.weak_records[0]
        reasons_text = " ".join(profile.weak_reasons).lower()
        self.assertIn("owner_name", reasons_text)

    def test_record_id_preserved(self):
        profile = self.report.weak_records[0]
        self.assertEqual(profile.record_id, WEAK_RECORD["record_id"])

    def test_both_scores_below_threshold(self):
        profile = self.report.weak_records[0]
        self.assertLess(profile.builder_confidence, BUILDER_THRESHOLD)
        self.assertLess(profile.investor_confidence, INVESTOR_THRESHOLD)


class TestIndividualHomeownerIntegration(unittest.TestCase):
    """Regular owner-occupant with no investor/builder signals → QUARANTINED."""

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([HOMEOWNER])

    def test_classified_as_quarantined(self):
        self.assertEqual(len(self.report.quarantined), 1)
        self.assertEqual(len(self.report.verified_builders), 0)
        self.assertEqual(len(self.report.possible_cash_buyers), 0)

    def test_both_confidence_scores_are_zero(self):
        profile = self.report.quarantined[0]
        self.assertEqual(profile.builder_confidence, 0.0)
        self.assertEqual(profile.investor_confidence, 0.0)

    def test_weak_reasons_mention_thresholds(self):
        profile = self.report.quarantined[0]
        text = " ".join(profile.weak_reasons).lower()
        self.assertIn("below", text)

    def test_no_company_flag(self):
        profile = self.report.quarantined[0]
        self.assertFalse(profile.signals.is_company_owned)

    def test_no_builder_keywords(self):
        profile = self.report.quarantined[0]
        self.assertFalse(profile.signals.has_builder_keywords)

    def test_acquisitions_below_repeat_min(self):
        profile = self.report.quarantined[0]
        self.assertLess(profile.signals.prior_acquisitions, REPEAT_BUYER_MIN)


# ---------------------------------------------------------------------------
# Cross-record batch detection
# ---------------------------------------------------------------------------


class TestBatchRepeatDetection(unittest.TestCase):
    """Same owner appearing multiple times in a batch should get higher repeat signal."""

    def test_two_records_same_owner_boosts_acquisitions(self):
        rec_a = dict(HOMEOWNER, record_id="h-001", parcel_id="p-001")
        rec_b = dict(HOMEOWNER, record_id="h-002", parcel_id="p-002")
        agent = BuilderVerificationAgent()
        report = agent.run([rec_a, rec_b])
        all_profiles = (
            report.verified_builders + report.possible_cash_buyers
            + report.repeat_buyers + report.quarantined + report.weak_records
        )
        for p in all_profiles:
            # Both should see batch_count=2
            self.assertEqual(p.signals.batch_acquisition_count, 2)

    def test_three_records_same_owner_triggers_repeat_buyer(self):
        # Maria Santos × 3 → batch_count=3 ≥ REPEAT_BUYER_MIN
        recs = [
            dict(HOMEOWNER, record_id=f"h-{i:03d}", parcel_id=f"p-{i:03d}")
            for i in range(3)
        ]
        agent = BuilderVerificationAgent()
        report = agent.run(recs)
        self.assertEqual(len(report.repeat_buyers), 3)
        self.assertEqual(len(report.quarantined), 0)

    def test_different_owners_not_conflated(self):
        rec_a = dict(HOMEOWNER, record_id="h-001", parcel_id="p-001", owner_name="Alice Jones")
        rec_b = dict(HOMEOWNER, record_id="h-002", parcel_id="p-002", owner_name="Bob Smith")
        agent = BuilderVerificationAgent()
        report = agent.run([rec_a, rec_b])
        for p in report.quarantined:
            self.assertEqual(p.signals.batch_acquisition_count, 1)


# ---------------------------------------------------------------------------
# Mixed-batch counts
# ---------------------------------------------------------------------------


class TestMixedBatch(unittest.TestCase):
    """All five fixture types together — verify exact bucket counts."""

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([
            VERIFIED_BUILDER,
            CASH_BUYER,
            REPEAT_BUYER,
            WEAK_RECORD,
            HOMEOWNER,
        ])

    def test_total_processed_is_five(self):
        self.assertEqual(self.report.total_processed, 5)

    def test_exactly_one_verified_builder(self):
        self.assertEqual(len(self.report.verified_builders), 1)

    def test_exactly_one_cash_buyer(self):
        self.assertEqual(len(self.report.possible_cash_buyers), 1)

    def test_exactly_one_repeat_buyer(self):
        self.assertEqual(len(self.report.repeat_buyers), 1)

    def test_exactly_one_quarantined(self):
        self.assertEqual(len(self.report.quarantined), 1)

    def test_exactly_one_weak_record(self):
        self.assertEqual(len(self.report.weak_records), 1)

    def test_builders_sorted_by_confidence_descending(self):
        scores = [p.builder_confidence for p in self.report.verified_builders]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_cash_buyers_sorted_by_investor_confidence_descending(self):
        scores = [p.investor_confidence for p in self.report.possible_cash_buyers]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


class TestOutputGeneration(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.agent = BuilderVerificationAgent(reports_dir=self.tmp_dir)

    def test_all_four_output_files_created(self):
        report = self.agent.run([VERIFIED_BUILDER, CASH_BUYER, HOMEOWNER])
        self.agent.write_outputs(report)
        expected = [
            "VERIFIED_BUILDERS.json",
            "POSSIBLE_CASH_BUYERS.json",
            "BUYER_ACTIVITY_REPORT.md",
            "BUYER_CONFIDENCE_SCORES.json",
        ]
        for fname in expected:
            self.assertTrue(
                (self.tmp_dir / fname).exists(), f"Missing: {fname}"
            )

    def test_verified_builders_json_is_valid(self):
        report = self.agent.run([VERIFIED_BUILDER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "VERIFIED_BUILDERS.json").read_text()
        )
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("builder_confidence", data[0])
        self.assertIn("evidence_flags", data[0])

    def test_possible_cash_buyers_json_is_valid(self):
        report = self.agent.run([CASH_BUYER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "POSSIBLE_CASH_BUYERS.json").read_text()
        )
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("investor_confidence", data[0])

    def test_buyer_confidence_scores_json_has_all_records(self):
        report = self.agent.run([VERIFIED_BUILDER, CASH_BUYER, HOMEOWNER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "BUYER_CONFIDENCE_SCORES.json").read_text()
        )
        self.assertEqual(data["counts"]["total"], 3)
        self.assertEqual(len(data["scores"]), 3)

    def test_buyer_confidence_scores_contains_thresholds(self):
        report = self.agent.run([VERIFIED_BUILDER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "BUYER_CONFIDENCE_SCORES.json").read_text()
        )
        self.assertIn("thresholds", data)
        self.assertEqual(data["thresholds"]["builder"], BUILDER_THRESHOLD)

    def test_activity_report_contains_owner_name(self):
        report = self.agent.run([VERIFIED_BUILDER])
        self.agent.write_outputs(report)
        content = (self.tmp_dir / "BUYER_ACTIVITY_REPORT.md").read_text()
        self.assertIn(VERIFIED_BUILDER["owner_name"], content)

    def test_activity_report_has_summary_table(self):
        report = self.agent.run([VERIFIED_BUILDER, HOMEOWNER])
        self.agent.write_outputs(report)
        content = (self.tmp_dir / "BUYER_ACTIVITY_REPORT.md").read_text()
        self.assertIn("Total processed", content)

    def test_empty_verified_builders_produces_empty_json_array(self):
        report = self.agent.run([HOMEOWNER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "VERIFIED_BUILDERS.json").read_text()
        )
        self.assertEqual(data, [])

    def test_evidence_flags_preserved_in_json(self):
        report = self.agent.run([VERIFIED_BUILDER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "VERIFIED_BUILDERS.json").read_text()
        )
        self.assertTrue(data[0]["evidence_flags"])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):

    def test_dry_run_from_stdin_verified_builder(self):
        payload = json.dumps([VERIFIED_BUILDER])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO) as out:
                code = main(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("Verified builders", out.getvalue())

    def test_dry_run_with_single_dict_stdin(self):
        # Single dict (not list) should also be accepted
        payload = json.dumps(VERIFIED_BUILDER)
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run"])
        self.assertEqual(code, 0)

    def test_nonexistent_path_returns_error(self):
        code = main(["/nonexistent/does_not_exist.json"])
        self.assertEqual(code, 1)

    def test_bad_stdin_json_returns_error(self):
        with patch("sys.stdin", StringIO("not { json }")):
            code = main(["--dry-run"])
        self.assertEqual(code, 1)

    def test_only_quarantined_records_returns_nonzero(self):
        payload = json.dumps([HOMEOWNER])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run"])
        # No actionable (builder or cash buyer) → non-zero exit
        self.assertEqual(code, 1)

    def test_empty_batch_returns_zero(self):
        payload = json.dumps([])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run"])
        self.assertEqual(code, 0)

    def test_load_from_file(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump([VERIFIED_BUILDER], f)
            fname = f.name
        try:
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run", fname])
            self.assertEqual(code, 0)
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# Load research fixtures
# ---------------------------------------------------------------------------

SOURCED_BUILDER  = _load("sourced_builder")
PARTIAL_RESEARCH = _load("partial_research")


# ---------------------------------------------------------------------------
# Unit tests: SourceType enum
# ---------------------------------------------------------------------------


class TestSourceType(unittest.TestCase):

    def test_all_five_types_exist(self):
        types = {
            SourceType.SECRETARY_OF_STATE,
            SourceType.WEBSITE,
            SourceType.BUSINESS_PROFILE,
            SourceType.SOCIAL_PROFILE,
            SourceType.COUNTY_RECORDS,
        }
        self.assertEqual(len(types), 5)

    def test_str_serialisable(self):
        # str(Enum) returns repr in some Python versions; use .value for the raw string
        self.assertEqual(SourceType.SECRETARY_OF_STATE.value, "secretary_of_state")

    def test_used_as_dict_key(self):
        d = {SourceType.WEBSITE: 0.72}
        self.assertEqual(d[SourceType.WEBSITE], 0.72)


# ---------------------------------------------------------------------------
# Unit tests: SourceCitation
# ---------------------------------------------------------------------------


class TestSourceCitation(unittest.TestCase):

    def test_fields_populated(self):
        sc = SourceCitation(
            source_type=SourceType.SECRETARY_OF_STATE,
            name="Illinois SOS",
            url="https://apps.ilsos.gov/",
            reliability=0.97,
        )
        self.assertEqual(sc.source_type, SourceType.SECRETARY_OF_STATE)
        self.assertEqual(sc.reliability, 0.97)

    def test_url_optional(self):
        sc = SourceCitation(source_type=SourceType.WEBSITE, name="site")
        self.assertIsNone(sc.url)

    def test_reliability_default_zero(self):
        sc = SourceCitation(source_type=SourceType.SOCIAL_PROFILE, name="LinkedIn")
        self.assertEqual(sc.reliability, 0.0)


# ---------------------------------------------------------------------------
# Unit tests: ResearchEvidence
# ---------------------------------------------------------------------------


class TestResearchEvidence(unittest.TestCase):

    def test_source_count_distinct_types(self):
        ev = ResearchEvidence()
        ev.sources.append(
            SourceCitation(source_type=SourceType.SECRETARY_OF_STATE, name="SOS", reliability=0.97)
        )
        ev.sources.append(
            SourceCitation(source_type=SourceType.WEBSITE, name="web", reliability=0.72)
        )
        # Two of the same type should still count as 1
        ev.sources.append(
            SourceCitation(source_type=SourceType.WEBSITE, name="web2", reliability=0.72)
        )
        self.assertEqual(ev.source_count, 2)

    def test_default_booleans_false(self):
        ev = ResearchEvidence()
        self.assertFalse(ev.sos_registered)
        self.assertFalse(ev.sos_active)
        self.assertFalse(ev.website_construction)

    def test_construction_profile_platforms_default_empty(self):
        ev = ResearchEvidence()
        self.assertEqual(ev.construction_profile_platforms, [])

    def test_county_counts_default_zero(self):
        ev = ResearchEvidence()
        self.assertEqual(ev.county_deed_count, 0)
        self.assertEqual(ev.county_permit_count, 0)

    def test_source_count_zero_when_empty(self):
        ev = ResearchEvidence()
        self.assertEqual(ev.source_count, 0)


# ---------------------------------------------------------------------------
# Unit tests: _extract_research_evidence
# ---------------------------------------------------------------------------


class TestExtractResearchEvidence(unittest.TestCase):

    def test_returns_none_when_no_research_key(self):
        self.assertIsNone(_extract_research_evidence({"owner_name": "Foo"}))

    def test_returns_none_when_research_is_empty_dict(self):
        self.assertIsNone(_extract_research_evidence({"research": {}}))

    def test_returns_none_when_research_is_none(self):
        self.assertIsNone(_extract_research_evidence({"research": None}))

    def test_parses_sos_active(self):
        record = {
            "research": {
                "secretary_of_state": {
                    "registered": True,
                    "status": "active",
                    "legal_name": "TEST LLC",
                    "state": "IL",
                    "source_name": "IL SOS",
                }
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertTrue(ev.sos_registered)
        self.assertTrue(ev.sos_active)
        self.assertEqual(ev.sos_legal_name, "TEST LLC")
        self.assertEqual(ev.sos_state, "IL")

    def test_sos_inactive_when_status_not_active(self):
        record = {
            "research": {
                "secretary_of_state": {
                    "registered": True,
                    "status": "dissolved",
                    "legal_name": "OLD LLC",
                    "source_name": "SOS",
                }
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertTrue(ev.sos_registered)
        self.assertFalse(ev.sos_active)

    def test_parses_website_with_construction(self):
        record = {
            "research": {
                "website": {"url": "https://example.com", "mentions_construction": True}
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.website_url, "https://example.com")
        self.assertTrue(ev.website_construction)

    def test_parses_website_without_construction(self):
        record = {
            "research": {
                "website": {"url": "https://example.com", "mentions_construction": False}
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertFalse(ev.website_construction)

    def test_parses_construction_business_profiles(self):
        record = {
            "research": {
                "business_profiles": [
                    {"platform": "BBB", "categories": ["General Contractor"]},
                    {"platform": "Houzz", "categories": ["General Contractor"]},
                ]
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertIn("BBB", ev.construction_profile_platforms)
        self.assertIn("Houzz", ev.construction_profile_platforms)

    def test_non_construction_profile_not_in_platforms(self):
        record = {
            "research": {
                "business_profiles": [
                    {"platform": "Yelp", "categories": ["Restaurant"]},
                ]
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertNotIn("Yelp", ev.construction_profile_platforms)
        self.assertEqual(len(ev.sources), 1)

    def test_parses_county_records(self):
        record = {
            "research": {
                "county_records": {
                    "deed_count": 14,
                    "permit_count": 8,
                    "source_name": "Sangamon County",
                }
            }
        }
        ev = _extract_research_evidence(record)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.county_deed_count, 14)
        self.assertEqual(ev.county_permit_count, 8)
        self.assertEqual(ev.county_source_name, "Sangamon County")

    def test_source_count_reflects_distinct_types(self):
        ev = _extract_research_evidence(SOURCED_BUILDER)
        # SOS + website + business_profiles (2 but 1 type) + county = 4 types
        self.assertEqual(ev.source_count, 4)

    def test_multiple_business_profiles_each_add_citation(self):
        ev = _extract_research_evidence(SOURCED_BUILDER)
        bp_citations = [s for s in ev.sources if s.source_type == SourceType.BUSINESS_PROFILE]
        self.assertEqual(len(bp_citations), 2)  # BBB + Houzz

    def test_sos_only_gives_source_count_one(self):
        ev = _extract_research_evidence(PARTIAL_RESEARCH)
        self.assertEqual(ev.source_count, 1)


# ---------------------------------------------------------------------------
# Unit tests: _research_confidence
# ---------------------------------------------------------------------------


class TestResearchConfidence(unittest.TestCase):

    def test_returns_zero_for_no_sources(self):
        ev = ResearchEvidence()
        self.assertEqual(_research_confidence(ev), 0.0)

    def test_sos_only_returns_high_confidence(self):
        ev = _extract_research_evidence(PARTIAL_RESEARCH)
        rc = _research_confidence(ev)
        # SOS reliability=0.97, no corroboration bonus
        self.assertAlmostEqual(rc, 0.97, places=4)

    def test_corroboration_bonus_applied_for_multiple_types(self):
        # Build two evidence sets with equal per-source reliability but different counts
        ev_one = ResearchEvidence()
        ev_one.sources.append(
            SourceCitation(source_type=SourceType.SECRETARY_OF_STATE, name="SOS", reliability=0.80)
        )
        ev_two = ResearchEvidence()
        ev_two.sources.append(
            SourceCitation(source_type=SourceType.SECRETARY_OF_STATE, name="SOS", reliability=0.80)
        )
        ev_two.sources.append(
            SourceCitation(source_type=SourceType.WEBSITE, name="web", reliability=0.80)
        )
        # Same average reliability but ev_two has corroboration bonus → higher score
        self.assertGreater(_research_confidence(ev_two), _research_confidence(ev_one))

    def test_confidence_capped_at_one(self):
        ev = ResearchEvidence()
        for st in SourceType:
            ev.sources.append(SourceCitation(source_type=st, name=st, reliability=1.0))
        self.assertLessEqual(_research_confidence(ev), 1.0)


# ---------------------------------------------------------------------------
# Unit tests: _research_builder_boost
# ---------------------------------------------------------------------------


class TestResearchBuilderBoost(unittest.TestCase):

    def _ev_with(self, **kwargs) -> ResearchEvidence:
        ev = ResearchEvidence(**kwargs)
        return ev

    def test_zero_when_no_evidence(self):
        self.assertEqual(_research_builder_boost(ResearchEvidence()), 0.0)

    def test_sos_active_only(self):
        ev = ResearchEvidence(sos_active=True)
        self.assertAlmostEqual(_research_builder_boost(ev), _WR_SOS_ACTIVE, places=4)

    def test_construction_profiles_only(self):
        ev = ResearchEvidence(construction_profile_platforms=["BBB"])
        self.assertAlmostEqual(
            _research_builder_boost(ev), _WR_CONSTRUCTION_PROFILE, places=4
        )

    def test_website_construction_only(self):
        ev = ResearchEvidence(website_construction=True)
        self.assertAlmostEqual(
            _research_builder_boost(ev), _WR_WEBSITE_CONSTRUCTION, places=4
        )

    def test_county_permit_heavy(self):
        ev = ResearchEvidence(county_permit_count=5)
        self.assertAlmostEqual(
            _research_builder_boost(ev), _WR_COUNTY_PERMIT_HEAVY, places=4
        )

    def test_county_permit_below_threshold_no_boost(self):
        ev = ResearchEvidence(county_permit_count=4)
        self.assertEqual(_research_builder_boost(ev), 0.0)

    def test_capped_at_max_builder_boost(self):
        ev = _extract_research_evidence(SOURCED_BUILDER)
        # Sum would be > 0.20 without cap
        boost = _research_builder_boost(ev)
        self.assertLessEqual(boost, _MAX_BUILDER_BOOST)
        self.assertAlmostEqual(boost, _MAX_BUILDER_BOOST, places=4)

    def test_three_sources_add_corroboration(self):
        ev = ResearchEvidence()
        for st in (SourceType.SECRETARY_OF_STATE, SourceType.WEBSITE, SourceType.COUNTY_RECORDS):
            ev.sources.append(SourceCitation(source_type=st, name=st, reliability=0.9))
        boost = _research_builder_boost(ev)
        self.assertGreaterEqual(boost, _WR_CORROBORATION_3PLUS)


# ---------------------------------------------------------------------------
# Unit tests: _research_investor_boost
# ---------------------------------------------------------------------------


class TestResearchInvestorBoost(unittest.TestCase):

    def test_zero_when_no_evidence(self):
        self.assertEqual(_research_investor_boost(ResearchEvidence()), 0.0)

    def test_sos_active_boost(self):
        ev = ResearchEvidence(sos_active=True)
        boost = _research_investor_boost(ev)
        self.assertAlmostEqual(boost, 0.05, places=4)

    def test_county_deed_heavy_boost(self):
        ev = ResearchEvidence(county_deed_count=5)
        boost = _research_investor_boost(ev)
        self.assertAlmostEqual(boost, 0.06, places=4)

    def test_capped_at_max_investor_boost(self):
        ev = _extract_research_evidence(SOURCED_BUILDER)
        boost = _research_investor_boost(ev)
        self.assertLessEqual(boost, _MAX_INVESTOR_BOOST)


# ---------------------------------------------------------------------------
# Integration tests: sourced_builder (full research)
# ---------------------------------------------------------------------------


class TestSourcedBuilderIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([SOURCED_BUILDER])

    def test_classified_as_verified_builder(self):
        self.assertEqual(len(self.report.verified_builders), 1)

    def test_builder_confidence_is_max(self):
        profile = self.report.verified_builders[0]
        self.assertAlmostEqual(profile.builder_confidence, 1.0, places=4)

    def test_research_evidence_present(self):
        profile = self.report.verified_builders[0]
        self.assertIsNotNone(profile.signals.research_evidence)

    def test_sos_active_flag(self):
        profile = self.report.verified_builders[0]
        self.assertTrue(profile.signals.research_evidence.sos_active)

    def test_construction_profiles_populated(self):
        profile = self.report.verified_builders[0]
        platforms = profile.signals.research_evidence.construction_profile_platforms
        self.assertIn("BBB", platforms)
        self.assertIn("Houzz", platforms)

    def test_county_permit_count_extracted(self):
        profile = self.report.verified_builders[0]
        self.assertEqual(profile.signals.research_evidence.county_permit_count, 8)

    def test_entity_matches_contains_sos_legal_name(self):
        profile = self.report.verified_builders[0]
        self.assertIn("APEX CONSTRUCTION LLC", profile.entity_matches)

    def test_research_confidence_above_zero(self):
        profile = self.report.verified_builders[0]
        self.assertGreater(profile.research_confidence, 0.0)


# ---------------------------------------------------------------------------
# Integration tests: partial_research (SOS-only elevates borderline record)
# ---------------------------------------------------------------------------


class TestPartialResearchIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = BuilderVerificationAgent()
        self.report = self.agent.run([PARTIAL_RESEARCH])

    def test_classified_as_verified_builder_with_research(self):
        # With SOS boost, 0.63 + 0.05 = 0.68 ≥ BUILDER_THRESHOLD
        self.assertEqual(len(self.report.verified_builders), 1)

    def test_base_score_without_research_is_below_threshold(self):
        no_research = {k: v for k, v in PARTIAL_RESEARCH.items() if k != "research"}
        report_no_research = self.agent.run([no_research])
        self.assertEqual(len(report_no_research.verified_builders), 0)

    def test_research_confidence_is_sos_reliability(self):
        profile = self.report.verified_builders[0]
        self.assertAlmostEqual(profile.research_confidence, 0.97, places=4)

    def test_sos_active_true(self):
        profile = self.report.verified_builders[0]
        self.assertTrue(profile.signals.research_evidence.sos_active)

    def test_entity_matches_contains_sos_legal_name(self):
        profile = self.report.verified_builders[0]
        self.assertIn("SUMMIT BUILDERS LLC", profile.entity_matches)

    def test_builder_boost_is_sos_active_only(self):
        profile = self.report.verified_builders[0]
        ev = profile.signals.research_evidence
        boost = _research_builder_boost(ev)
        self.assertAlmostEqual(boost, _WR_SOS_ACTIVE, places=4)


# ---------------------------------------------------------------------------
# Entity matching tests
# ---------------------------------------------------------------------------


class TestEntityMatching(unittest.TestCase):

    def setUp(self):
        self.agent = BuilderVerificationAgent()

    def test_sourced_record_self_matches_sos_legal_name(self):
        report = self.agent.run([SOURCED_BUILDER])
        profile = report.verified_builders[0]
        self.assertTrue(profile.entity_matches)

    def test_unresearched_record_matches_sos_name_from_batch_peer(self):
        # verified_builder (no research) shares the same owner name "Apex Construction LLC"
        # with sourced_builder (has SOS legal_name = "APEX CONSTRUCTION LLC")
        report = self.agent.run([SOURCED_BUILDER, VERIFIED_BUILDER])
        all_profiles = report.verified_builders
        # Both records should have entity matches
        has_match = [p for p in all_profiles if p.entity_matches]
        self.assertGreater(len(has_match), 0)

    def test_record_with_no_research_has_no_entity_matches_in_isolation(self):
        report = self.agent.run([VERIFIED_BUILDER])
        profile = report.verified_builders[0]
        # No SOS data in the batch → no entity index → no matches
        self.assertEqual(profile.entity_matches, [])

    def test_entity_index_built_from_sos_data(self):
        report = self.agent.run([SOURCED_BUILDER, PARTIAL_RESEARCH])
        # Both have distinct SOS legal names; each should match their own name
        all_builders = report.verified_builders
        names = {n for p in all_builders for n in p.entity_matches}
        self.assertIn("APEX CONSTRUCTION LLC", names)
        self.assertIn("SUMMIT BUILDERS LLC", names)


# ---------------------------------------------------------------------------
# Entity intelligence report tests
# ---------------------------------------------------------------------------


class TestEntityIntelligenceReport(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.agent = BuilderVerificationAgent(reports_dir=self.tmp_dir)

    def test_entity_intelligence_report_created(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        self.assertTrue(
            (self.tmp_dir / "ENTITY_INTELLIGENCE_REPORT.md").exists()
        )

    def test_report_contains_sos_legal_name(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        content = (self.tmp_dir / "ENTITY_INTELLIGENCE_REPORT.md").read_text()
        self.assertIn("APEX CONSTRUCTION LLC", content)

    def test_report_contains_source_names(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        content = (self.tmp_dir / "ENTITY_INTELLIGENCE_REPORT.md").read_text()
        self.assertIn("Illinois Secretary of State", content)

    def test_report_contains_research_confidence(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        content = (self.tmp_dir / "ENTITY_INTELLIGENCE_REPORT.md").read_text()
        self.assertIn("Research confidence", content)

    def test_empty_research_batch_still_creates_file(self):
        report = self.agent.run([HOMEOWNER])
        self.agent.write_outputs(report)
        path = self.tmp_dir / "ENTITY_INTELLIGENCE_REPORT.md"
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("No research-backed", content)

    def test_report_contains_builder_boost(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        content = (self.tmp_dir / "ENTITY_INTELLIGENCE_REPORT.md").read_text()
        self.assertIn("research boost", content)


# ---------------------------------------------------------------------------
# Research fields in output files
# ---------------------------------------------------------------------------


class TestResearchInOutputFiles(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.agent = BuilderVerificationAgent(reports_dir=self.tmp_dir)

    def test_research_confidence_in_confidence_scores_json(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "BUYER_CONFIDENCE_SCORES.json").read_text()
        )
        score_entry = data["scores"][0]
        self.assertIn("research_confidence", score_entry)
        self.assertGreater(score_entry["research_confidence"], 0.0)

    def test_entity_matches_in_verified_builders_json(self):
        report = self.agent.run([SOURCED_BUILDER])
        self.agent.write_outputs(report)
        data = json.loads(
            (self.tmp_dir / "VERIFIED_BUILDERS.json").read_text()
        )
        self.assertIn("entity_matches", data[0])
        self.assertIn("APEX CONSTRUCTION LLC", data[0]["entity_matches"])

    def test_five_output_files_created_when_research_present(self):
        report = self.agent.run([SOURCED_BUILDER, HOMEOWNER])
        self.agent.write_outputs(report)
        expected = [
            "VERIFIED_BUILDERS.json",
            "POSSIBLE_CASH_BUYERS.json",
            "BUYER_ACTIVITY_REPORT.md",
            "BUYER_CONFIDENCE_SCORES.json",
            "ENTITY_INTELLIGENCE_REPORT.md",
        ]
        for fname in expected:
            self.assertTrue(
                (self.tmp_dir / fname).exists(), f"Missing: {fname}"
            )


if __name__ == "__main__":
    unittest.main()
