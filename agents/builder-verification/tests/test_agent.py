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
    BuyerType,
    BuilderVerificationAgent,
    BuyerSignals,
    _detect_builder_keywords,
    _detect_entity,
    _addresses_mismatch,
    _normalize_owner,
    _extract_signals,
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


if __name__ == "__main__":
    unittest.main()
