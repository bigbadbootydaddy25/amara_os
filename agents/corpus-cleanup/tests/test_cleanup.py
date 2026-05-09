"""
Tests for the Corpus Cleanup Agent.

Coverage
--------
Signal extraction unit tests
  - key-leakage detection (title= / topic= / transcript= / youtube=)
  - placeholder content detection
  - malformed title detection
  - code-fence contamination detection
  - body word-count / short-body flag
  - missing source evidence flag
  - cross-batch duplicate detection

Scoring unit tests
  - empty signals → score 0.0
  - full poison → score 1.0
  - each signal contributes independently
  - score clamped 0..1

Routing unit tests
  - score >= REMOVE_THRESHOLD → REMOVED
  - ARCHIVE_THRESHOLD <= score < REMOVE_THRESHOLD → ARCHIVED
  - duplicate → ARCHIVED regardless of score
  - score < ARCHIVE_THRESHOLD → CLEAN

Integration: clean workflow
Integration: key-leakage artifact
Integration: placeholder notes artifact
Integration: code-fence contamination artifact
Integration: fake source packet artifact
Integration: duplicate pair detection
Integration: mixed batch counts

Output generation tests (all four files)

Filesystem action tests (backup, removal — using temp dirs)

CLI tests (dry-run, bad path, bad stdin, from-file)
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from run import (
    _ARCHIVE_THRESHOLD,
    _REMOVE_THRESHOLD,
    _MIN_BODY_WORDS,
    ArtifactDisposition,
    ArtifactRecord,
    CorpusCleanupAgent,
    PoisonSignals,
    _extract_signals,
    _first_line_matches,
    _poison_score,
    _route,
    _scan_for_placeholders,
    _KEY_LEAKAGE_PATTERNS,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


CLEAN_WORKFLOW       = _load("clean_workflow")
KEY_LEAKAGE          = _load("key_leakage")
PLACEHOLDER_NOTES    = _load("placeholder_notes")
CODEFENCE            = _load("codefence_contamination")
FAKE_SOURCE          = _load("fake_source_packet")


def _sig(record: dict, seen: dict | None = None) -> PoisonSignals:
    return _extract_signals(record, seen if seen is not None else {})


# ---------------------------------------------------------------------------
# Unit: key-leakage pattern helpers
# ---------------------------------------------------------------------------


class TestKeyLeakagePatterns(unittest.TestCase):

    def test_title_equals_matches(self):
        matches = _first_line_matches("title=Foo Bar", _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)

    def test_topic_equals_matches(self):
        matches = _first_line_matches("topic=networking", _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)

    def test_transcript_equals_matches(self):
        matches = _first_line_matches("transcript=some content here", _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)

    def test_youtube_equals_matches(self):
        matches = _first_line_matches("youtube=https://youtube.com/watch?v=abc", _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)

    def test_url_equals_matches(self):
        matches = _first_line_matches("url=https://example.com", _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)

    def test_clean_prose_does_not_match(self):
        clean = "FastAPI is a modern Python web framework for building REST APIs."
        matches = _first_line_matches(clean, _KEY_LEAKAGE_PATTERNS)
        self.assertEqual(matches, [])

    def test_empty_rhs_does_not_match(self):
        # "transcript=" with nothing after = should NOT match (requires .+)
        matches = _first_line_matches("transcript=", _KEY_LEAKAGE_PATTERNS)
        self.assertEqual(matches, [])

    def test_case_insensitive(self):
        matches = _first_line_matches("TITLE=Foo Bar", _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)

    def test_multiline_body_finds_leakage_line(self):
        body = "Good prose paragraph.\ntopic=networking\nMore good prose."
        matches = _first_line_matches(body, _KEY_LEAKAGE_PATTERNS)
        self.assertTrue(matches)
        self.assertTrue(any("topic" in m.lower() for m in matches))


# ---------------------------------------------------------------------------
# Unit: placeholder detection
# ---------------------------------------------------------------------------


class TestPlaceholderDetection(unittest.TestCase):

    def test_bracket_placeholder(self):
        self.assertTrue(_scan_for_placeholders("[placeholder]"))

    def test_summary_pending(self):
        self.assertTrue(_scan_for_placeholders("[summary pending]"))

    def test_no_transcript_found(self):
        self.assertTrue(_scan_for_placeholders("no transcript found"))

    def test_todo(self):
        self.assertTrue(_scan_for_placeholders("TODO: fill in content"))

    def test_lorem_ipsum(self):
        self.assertTrue(_scan_for_placeholders("lorem ipsum dolor sit"))

    def test_extraction_failed(self):
        self.assertTrue(_scan_for_placeholders("extraction failed"))

    def test_clean_text_no_matches(self):
        self.assertEqual(
            _scan_for_placeholders("FastAPI uses async generators for dependency injection."),
            [],
        )


# ---------------------------------------------------------------------------
# Unit: signal extraction
# ---------------------------------------------------------------------------


class TestExtractSignals(unittest.TestCase):

    def test_clean_workflow_has_no_signals(self):
        sig = _sig(CLEAN_WORKFLOW)
        self.assertFalse(sig.has_key_leakage)
        self.assertFalse(sig.has_placeholder_content)
        self.assertFalse(sig.has_malformed_title)
        self.assertFalse(sig.has_codefence_contamination)
        self.assertFalse(sig.body_too_short)
        self.assertFalse(sig.missing_source_evidence)
        self.assertFalse(sig.is_duplicate)

    def test_key_leakage_detected_in_title_and_body(self):
        sig = _sig(KEY_LEAKAGE)
        self.assertTrue(sig.has_key_leakage)
        self.assertTrue(sig.key_leakage_matches)

    def test_malformed_title_detected_for_title_equals(self):
        sig = _sig(KEY_LEAKAGE)
        self.assertTrue(sig.has_malformed_title)

    def test_malformed_title_detected_for_undefined(self):
        sig = _sig(FAKE_SOURCE)
        self.assertTrue(sig.has_malformed_title)

    def test_malformed_title_detected_for_empty_string(self):
        record = {"artifact_id": "x", "title": "", "body": "some content here"}
        sig = _sig(record)
        self.assertTrue(sig.has_malformed_title)

    def test_placeholder_detected_in_placeholder_notes(self):
        sig = _sig(PLACEHOLDER_NOTES)
        self.assertTrue(sig.has_placeholder_content)
        self.assertIn("[placeholder]", " ".join(sig.placeholder_matches).lower())

    def test_codefence_contamination_detected(self):
        sig = _sig(CODEFENCE)
        self.assertTrue(sig.has_codefence_contamination)
        self.assertGreater(sig.codefence_count, 0)

    def test_codefence_count_correct(self):
        # fixture has 3 code blocks = 6 fences
        sig = _sig(CODEFENCE)
        self.assertEqual(sig.codefence_count, 6)

    def test_short_body_flag_set_below_minimum(self):
        sig = _sig(KEY_LEAKAGE)
        self.assertTrue(sig.body_too_short)
        self.assertLess(sig.body_word_count, _MIN_BODY_WORDS)

    def test_short_body_flag_clear_on_long_body(self):
        sig = _sig(CLEAN_WORKFLOW)
        self.assertFalse(sig.body_too_short)
        self.assertGreaterEqual(sig.body_word_count, _MIN_BODY_WORDS)

    def test_missing_source_evidence_when_no_fields(self):
        sig = _sig(FAKE_SOURCE)
        self.assertTrue(sig.missing_source_evidence)

    def test_source_evidence_present_when_url_set(self):
        sig = _sig(CLEAN_WORKFLOW)
        self.assertFalse(sig.missing_source_evidence)

    def test_source_evidence_present_via_source_evidence_field(self):
        record = {"artifact_id": "x", "title": "T", "body": "body", "source_evidence": "log.txt"}
        sig = _sig(record)
        self.assertFalse(sig.missing_source_evidence)

    def test_notes_list_joined_for_scanning(self):
        record = {
            "artifact_id": "x",
            "title": "T",
            "body": "",
            "notes": ["[placeholder]", "real content"],
        }
        sig = _sig(record)
        self.assertTrue(sig.has_placeholder_content)

    def test_duplicate_detected_on_identical_body(self):
        seen: dict[str, str] = {}
        rec_a = dict(CLEAN_WORKFLOW, artifact_id="orig")
        rec_b = dict(CLEAN_WORKFLOW, artifact_id="dup")
        _extract_signals(rec_a, seen)
        sig_b = _extract_signals(rec_b, seen)
        self.assertTrue(sig_b.is_duplicate)
        self.assertEqual(sig_b.duplicate_of, "orig")

    def test_no_false_duplicate_on_different_bodies(self):
        seen: dict[str, str] = {}
        _extract_signals(CLEAN_WORKFLOW, seen)
        sig_b = _extract_signals(KEY_LEAKAGE, seen)
        self.assertFalse(sig_b.is_duplicate)


# ---------------------------------------------------------------------------
# Unit: scoring
# ---------------------------------------------------------------------------


class TestPoisonScoring(unittest.TestCase):

    def test_zero_signals_gives_zero_score(self):
        self.assertEqual(_poison_score(PoisonSignals()), 0.0)

    def test_all_signals_gives_max_score(self):
        sig = PoisonSignals(
            has_key_leakage=True,
            has_placeholder_content=True,
            has_malformed_title=True,
            has_codefence_contamination=True,
            codefence_count=10,
            body_too_short=True,
            missing_source_evidence=True,
        )
        self.assertAlmostEqual(_poison_score(sig), 1.0, places=4)

    def test_score_is_bounded_0_to_1(self):
        sig = PoisonSignals(
            has_key_leakage=True,
            has_placeholder_content=True,
            has_malformed_title=True,
            has_codefence_contamination=True,
            codefence_count=100,
            body_too_short=True,
            missing_source_evidence=True,
            is_duplicate=True,
        )
        s = _poison_score(sig)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_key_leakage_contributes(self):
        s0 = _poison_score(PoisonSignals())
        s1 = _poison_score(PoisonSignals(has_key_leakage=True))
        self.assertGreater(s1, s0)

    def test_placeholder_contributes(self):
        s0 = _poison_score(PoisonSignals())
        s1 = _poison_score(PoisonSignals(has_placeholder_content=True))
        self.assertGreater(s1, s0)

    def test_malformed_title_contributes(self):
        s0 = _poison_score(PoisonSignals())
        s1 = _poison_score(PoisonSignals(has_malformed_title=True))
        self.assertGreater(s1, s0)

    def test_duplicate_boosts_existing_score(self):
        base_sig = PoisonSignals(has_key_leakage=True)
        dup_sig  = PoisonSignals(has_key_leakage=True, is_duplicate=True)
        self.assertGreater(_poison_score(dup_sig), _poison_score(base_sig))

    def test_heavy_codefence_scores_higher_than_light(self):
        light = PoisonSignals(has_codefence_contamination=True, codefence_count=2)
        heavy = PoisonSignals(has_codefence_contamination=True, codefence_count=10)
        self.assertGreater(_poison_score(heavy), _poison_score(light))

    def test_clean_workflow_scores_zero(self):
        sig = _sig(CLEAN_WORKFLOW)
        self.assertEqual(_poison_score(sig), 0.0)

    def test_key_leakage_fixture_scores_at_remove_threshold(self):
        sig = _sig(KEY_LEAKAGE)
        self.assertGreaterEqual(_poison_score(sig), _REMOVE_THRESHOLD)

    def test_placeholder_fixture_scores_between_thresholds(self):
        sig = _sig(PLACEHOLDER_NOTES)
        score = _poison_score(sig)
        self.assertGreaterEqual(score, _ARCHIVE_THRESHOLD)
        self.assertLess(score, _REMOVE_THRESHOLD)


# ---------------------------------------------------------------------------
# Unit: routing
# ---------------------------------------------------------------------------


class TestRouting(unittest.TestCase):

    def test_high_score_routes_to_removed(self):
        sig = PoisonSignals(has_key_leakage=True, has_placeholder_content=True,
                            has_malformed_title=True, body_too_short=True,
                            missing_source_evidence=True)
        score = _poison_score(sig)
        disp, _ = _route(sig, score)
        self.assertEqual(disp, ArtifactDisposition.REMOVED)

    def test_mid_score_routes_to_archived(self):
        sig = PoisonSignals(has_placeholder_content=True,
                            body_too_short=True, missing_source_evidence=True)
        score = _poison_score(sig)
        disp, _ = _route(sig, score)
        self.assertEqual(disp, ArtifactDisposition.ARCHIVED)

    def test_low_score_routes_to_clean(self):
        disp, _ = _route(PoisonSignals(), 0.0)
        self.assertEqual(disp, ArtifactDisposition.CLEAN)

    def test_duplicate_routes_to_archived_even_with_low_score(self):
        sig = PoisonSignals(is_duplicate=True, duplicate_of="original")
        disp, _ = _route(sig, 0.0)
        self.assertEqual(disp, ArtifactDisposition.ARCHIVED)

    def test_reasons_list_populated_for_removed(self):
        sig = PoisonSignals(
            has_key_leakage=True, key_leakage_matches=["title=X"],
            has_placeholder_content=True, placeholder_matches=["[placeholder]"],
            has_malformed_title=True, malformed_title_reason="test",
            body_too_short=True, body_word_count=3,
            missing_source_evidence=True,
        )
        _, reasons = _route(sig, _poison_score(sig))
        self.assertTrue(reasons)
        reasons_text = " ".join(reasons).lower()
        self.assertIn("key", reasons_text)

    def test_clean_has_empty_reasons(self):
        _, reasons = _route(PoisonSignals(), 0.0)
        self.assertEqual(reasons, [])


# ---------------------------------------------------------------------------
# Integration: clean workflow
# ---------------------------------------------------------------------------


class TestCleanWorkflowIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = CorpusCleanupAgent()

    def test_classified_as_clean(self):
        report = self.agent.run([CLEAN_WORKFLOW])
        self.assertEqual(len(report.clean), 1)
        self.assertEqual(len(report.removed), 0)
        self.assertEqual(len(report.archived), 0)

    def test_poison_confidence_is_zero(self):
        report = self.agent.run([CLEAN_WORKFLOW])
        self.assertEqual(report.clean[0].poison_confidence, 0.0)

    def test_not_in_rerun_candidates(self):
        report = self.agent.run([CLEAN_WORKFLOW])
        self.assertNotIn("art-001", report.rerun_candidates)

    def test_no_disposition_reasons(self):
        report = self.agent.run([CLEAN_WORKFLOW])
        self.assertEqual(report.clean[0].disposition_reasons, [])


# ---------------------------------------------------------------------------
# Integration: key-leakage artifact
# ---------------------------------------------------------------------------


class TestKeyLeakageIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = CorpusCleanupAgent()
        self.report = self.agent.run([KEY_LEAKAGE])

    def test_classified_as_removed(self):
        self.assertEqual(len(self.report.removed), 1)
        self.assertEqual(len(self.report.clean), 0)

    def test_poison_confidence_at_remove_threshold(self):
        self.assertGreaterEqual(self.report.removed[0].poison_confidence, _REMOVE_THRESHOLD)

    def test_key_leakage_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.has_key_leakage)

    def test_malformed_title_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.has_malformed_title)

    def test_disposition_reasons_mention_leakage(self):
        reasons_text = " ".join(self.report.removed[0].disposition_reasons).lower()
        self.assertIn("key", reasons_text)

    def test_in_rerun_candidates(self):
        self.assertIn("art-002", self.report.rerun_candidates)


# ---------------------------------------------------------------------------
# Integration: placeholder notes
# ---------------------------------------------------------------------------


class TestPlaceholderNotesIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = CorpusCleanupAgent()
        self.report = self.agent.run([PLACEHOLDER_NOTES])

    def test_classified_as_archived(self):
        self.assertEqual(len(self.report.archived), 1)
        self.assertEqual(len(self.report.removed), 0)
        self.assertEqual(len(self.report.clean), 0)

    def test_poison_confidence_between_thresholds(self):
        score = self.report.archived[0].poison_confidence
        self.assertGreaterEqual(score, _ARCHIVE_THRESHOLD)
        self.assertLess(score, _REMOVE_THRESHOLD)

    def test_placeholder_signal_set(self):
        self.assertTrue(self.report.archived[0].signals.has_placeholder_content)

    def test_short_body_signal_set(self):
        self.assertTrue(self.report.archived[0].signals.body_too_short)

    def test_missing_source_signal_set(self):
        self.assertTrue(self.report.archived[0].signals.missing_source_evidence)

    def test_in_rerun_candidates(self):
        self.assertIn("art-003", self.report.rerun_candidates)


# ---------------------------------------------------------------------------
# Integration: code-fence contamination
# ---------------------------------------------------------------------------


class TestCodefenceIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = CorpusCleanupAgent()
        self.report = self.agent.run([CODEFENCE])

    def test_classified_as_archived(self):
        self.assertEqual(len(self.report.archived), 1)

    def test_codefence_signal_set(self):
        rec = self.report.archived[0]
        self.assertTrue(rec.signals.has_codefence_contamination)
        self.assertGreater(rec.signals.codefence_count, 0)

    def test_placeholder_signal_also_set(self):
        self.assertTrue(self.report.archived[0].signals.has_placeholder_content)

    def test_missing_source_signal_set(self):
        self.assertTrue(self.report.archived[0].signals.missing_source_evidence)

    def test_poison_confidence_between_thresholds(self):
        score = self.report.archived[0].poison_confidence
        self.assertGreaterEqual(score, _ARCHIVE_THRESHOLD)
        self.assertLess(score, _REMOVE_THRESHOLD)

    def test_disposition_reasons_mention_codefence(self):
        reasons_text = " ".join(self.report.archived[0].disposition_reasons).lower()
        self.assertIn("code", reasons_text)


# ---------------------------------------------------------------------------
# Integration: fake source packet
# ---------------------------------------------------------------------------


class TestFakeSourcePacketIntegration(unittest.TestCase):

    def setUp(self):
        self.agent = CorpusCleanupAgent()
        self.report = self.agent.run([FAKE_SOURCE])

    def test_classified_as_removed(self):
        self.assertEqual(len(self.report.removed), 1)

    def test_malformed_title_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.has_malformed_title)

    def test_placeholder_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.has_placeholder_content)

    def test_key_leakage_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.has_key_leakage)

    def test_missing_source_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.missing_source_evidence)

    def test_short_body_signal_set(self):
        self.assertTrue(self.report.removed[0].signals.body_too_short)

    def test_poison_confidence_at_remove_threshold(self):
        self.assertGreaterEqual(self.report.removed[0].poison_confidence, _REMOVE_THRESHOLD)


# ---------------------------------------------------------------------------
# Integration: duplicate pair detection
# ---------------------------------------------------------------------------


class TestDuplicateDetection(unittest.TestCase):

    def test_second_identical_artifact_is_archived(self):
        orig = dict(CLEAN_WORKFLOW, artifact_id="orig-001")
        dup  = dict(CLEAN_WORKFLOW, artifact_id="dup-001")
        agent  = CorpusCleanupAgent()
        report = agent.run([orig, dup])
        # Original stays clean; duplicate is archived
        self.assertEqual(len(report.clean),    1)
        self.assertEqual(len(report.archived), 1)

    def test_duplicate_points_to_original(self):
        orig = dict(CLEAN_WORKFLOW, artifact_id="orig-001")
        dup  = dict(CLEAN_WORKFLOW, artifact_id="dup-001")
        agent  = CorpusCleanupAgent()
        report = agent.run([orig, dup])
        dup_record = report.archived[0]
        self.assertEqual(dup_record.signals.duplicate_of, "orig-001")

    def test_duplicate_is_in_rerun_candidates(self):
        orig = dict(CLEAN_WORKFLOW, artifact_id="orig-001")
        dup  = dict(CLEAN_WORKFLOW, artifact_id="dup-001")
        agent  = CorpusCleanupAgent()
        report = agent.run([orig, dup])
        self.assertIn("dup-001", report.rerun_candidates)

    def test_three_way_duplicate(self):
        recs = [
            dict(CLEAN_WORKFLOW, artifact_id=f"a-{i}") for i in range(3)
        ]
        agent  = CorpusCleanupAgent()
        report = agent.run(recs)
        self.assertEqual(len(report.clean),    1)
        self.assertEqual(len(report.archived), 2)


# ---------------------------------------------------------------------------
# Integration: mixed batch
# ---------------------------------------------------------------------------


class TestMixedBatch(unittest.TestCase):

    def setUp(self):
        self.agent = CorpusCleanupAgent()
        self.report = self.agent.run([
            CLEAN_WORKFLOW,
            KEY_LEAKAGE,
            PLACEHOLDER_NOTES,
            CODEFENCE,
            FAKE_SOURCE,
        ])

    def test_total_scanned_is_five(self):
        self.assertEqual(self.report.total_scanned, 5)

    def test_exactly_one_clean(self):
        self.assertEqual(len(self.report.clean), 1)

    def test_exactly_two_removed(self):
        self.assertEqual(len(self.report.removed), 2)

    def test_exactly_two_archived(self):
        self.assertEqual(len(self.report.archived), 2)

    def test_zero_quarantined(self):
        self.assertEqual(len(self.report.quarantined), 0)

    def test_rerun_candidates_contain_mutated_ids(self):
        expected = {"art-002", "art-003", "art-004", "art-005"}
        self.assertTrue(expected.issubset(set(self.report.rerun_candidates)))

    def test_clean_artifact_not_in_rerun_candidates(self):
        self.assertNotIn("art-001", self.report.rerun_candidates)


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


class TestOutputGeneration(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.agent = CorpusCleanupAgent(reports_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_four_output_files_created(self):
        report = self.agent.run([CLEAN_WORKFLOW, KEY_LEAKAGE, PLACEHOLDER_NOTES])
        self.agent.write_outputs(report)
        for fname in [
            "CLEANUP_REPORT.md",
            "REMOVED_ARTIFACTS.json",
            "ARCHIVED_ARTIFACTS.json",
            "POST_CLEANUP_SCORECARD.md",
        ]:
            self.assertTrue((self.tmp / fname).exists(), f"Missing: {fname}")

    def test_removed_artifacts_json_is_valid_list(self):
        report = self.agent.run([KEY_LEAKAGE])
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "REMOVED_ARTIFACTS.json").read_text())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_removed_artifacts_json_contains_signals(self):
        report = self.agent.run([KEY_LEAKAGE])
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "REMOVED_ARTIFACTS.json").read_text())
        self.assertIn("signals", data[0])
        self.assertIn("poison_confidence", data[0])

    def test_archived_artifacts_json_is_valid_list(self):
        report = self.agent.run([PLACEHOLDER_NOTES])
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "ARCHIVED_ARTIFACTS.json").read_text())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_empty_removed_produces_empty_json_array(self):
        report = self.agent.run([CLEAN_WORKFLOW])
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "REMOVED_ARTIFACTS.json").read_text())
        self.assertEqual(data, [])

    def test_cleanup_report_contains_summary_table(self):
        report = self.agent.run([CLEAN_WORKFLOW, KEY_LEAKAGE])
        self.agent.write_outputs(report)
        content = (self.tmp / "CLEANUP_REPORT.md").read_text()
        self.assertIn("Total scanned", content)
        self.assertIn("Removed", content)

    def test_cleanup_report_contains_artifact_title(self):
        report = self.agent.run([KEY_LEAKAGE])
        self.agent.write_outputs(report)
        content = (self.tmp / "CLEANUP_REPORT.md").read_text()
        # Malformed title still appears in report
        self.assertIn("art-002", content)

    def test_scorecard_lists_rerun_candidates(self):
        report = self.agent.run([KEY_LEAKAGE])
        self.agent.write_outputs(report)
        content = (self.tmp / "POST_CLEANUP_SCORECARD.md").read_text()
        self.assertIn("art-002", content)
        self.assertIn("semantic-authenticity-gate", content)
        self.assertIn("cognitive-gym", content)

    def test_scorecard_clean_corpus_message(self):
        report = self.agent.run([CLEAN_WORKFLOW])
        self.agent.write_outputs(report)
        content = (self.tmp / "POST_CLEANUP_SCORECARD.md").read_text()
        self.assertIn("fully clean", content.lower())


# ---------------------------------------------------------------------------
# Filesystem actions (backup / remove)
# ---------------------------------------------------------------------------


class TestFilesystemActions(unittest.TestCase):

    def setUp(self):
        self.tmp      = Path(tempfile.mkdtemp())
        self.corpus   = self.tmp / "corpus"
        self.reports  = self.tmp / "reports"
        self.backups  = self.tmp / "backups"
        self.corpus.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_fixture(self, name: str, fixture: dict) -> Path:
        p = self.corpus / f"{name}.json"
        p.write_text(json.dumps(fixture), encoding="utf-8")
        return p

    def test_dry_run_does_not_delete_files(self):
        p = self._write_fixture("key_leakage", KEY_LEAKAGE)
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=True
        )
        agent.run_from_directory(self.corpus)
        self.assertTrue(p.exists(), "dry-run must not delete original file")

    def test_live_run_deletes_removed_file(self):
        p = self._write_fixture("key_leakage", KEY_LEAKAGE)
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=False
        )
        agent.run_from_directory(self.corpus)
        self.assertFalse(p.exists(), "live-run must delete a REMOVED file")

    def test_live_run_creates_backup_for_removed(self):
        self._write_fixture("key_leakage", KEY_LEAKAGE)
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=False
        )
        agent.run_from_directory(self.corpus)
        backups = list(self.backups.glob("key_leakage_*.json"))
        self.assertTrue(backups, "backup must be created before deletion")

    def test_live_run_keeps_archived_file_but_writes_backup(self):
        p = self._write_fixture("placeholder_notes", PLACEHOLDER_NOTES)
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=False
        )
        agent.run_from_directory(self.corpus)
        # Archived = backup exists; original is NOT deleted
        backups = list(self.backups.glob("placeholder_notes_*.json"))
        self.assertTrue(backups, "backup must be written for archived file")
        self.assertTrue(p.exists(), "original archived file must remain")

    def test_live_run_leaves_clean_file_intact(self):
        p = self._write_fixture("clean_workflow", CLEAN_WORKFLOW)
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=False
        )
        agent.run_from_directory(self.corpus)
        self.assertTrue(p.exists(), "clean file must never be touched")
        backups = list(self.backups.glob("clean_workflow_*.json"))
        self.assertEqual(backups, [], "clean file must not produce a backup")

    def test_backup_path_recorded_in_record(self):
        self._write_fixture("key_leakage", KEY_LEAKAGE)
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=False
        )
        report = agent.run_from_directory(self.corpus)
        self.assertTrue(report.removed)
        self.assertIsNotNone(report.removed[0].backup_path)

    def test_malformed_json_produces_skipped_record(self):
        bad = self.corpus / "bad.json"
        bad.write_text("not { valid json", encoding="utf-8")
        agent = CorpusCleanupAgent(
            reports_dir=self.reports, backup_dir=self.backups, dry_run=True
        )
        report = agent.run_from_directory(self.corpus)
        self.assertEqual(len(report.skipped), 1)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_from_stdin(self):
        payload = json.dumps([CLEAN_WORKFLOW])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO) as out:
                code = main(["--reports-dir", str(self.tmp)])
        self.assertEqual(code, 0)
        self.assertIn("Scanned", out.getvalue())

    def test_single_dict_stdin_accepted(self):
        payload = json.dumps(CLEAN_WORKFLOW)
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--reports-dir", str(self.tmp)])
        self.assertEqual(code, 0)

    def test_nonexistent_path_returns_error(self):
        code = main(["/nonexistent/path/artifacts.json", "--reports-dir", str(self.tmp)])
        self.assertEqual(code, 1)

    def test_bad_stdin_json_returns_error(self):
        with patch("sys.stdin", StringIO("not json")):
            code = main(["--reports-dir", str(self.tmp)])
        self.assertEqual(code, 1)

    def test_all_poison_batch_returns_nonzero(self):
        # All 4 poisoned = poison_count == total → exit 1
        payload = json.dumps([KEY_LEAKAGE, PLACEHOLDER_NOTES, CODEFENCE, FAKE_SOURCE])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--reports-dir", str(self.tmp)])
        self.assertEqual(code, 1)

    def test_load_from_json_file(self):
        f = self.tmp / "input.json"
        f.write_text(json.dumps([CLEAN_WORKFLOW]), encoding="utf-8")
        with patch("sys.stdout", new_callable=StringIO):
            code = main([str(f), "--reports-dir", str(self.tmp)])
        self.assertEqual(code, 0)

    def test_reports_written_to_specified_dir(self):
        out_dir = self.tmp / "out"
        payload = json.dumps([CLEAN_WORKFLOW])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                main(["--reports-dir", str(out_dir)])
        self.assertTrue((out_dir / "CLEANUP_REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
