"""
Tests for the Learning Ingestion Supervisor Agent.

Coverage:
  - Failed transcript extraction → FAILED status
  - Placeholder note generation → QUARANTINED status
  - Duplicate video detection → second copy QUARANTINED
  - Weak workflow (single-step, low gym score) → QUARANTINED status
  - Successful real-world workflow ingestion → VERIFIED status
  - Scoring edge cases and recommendation generation
  - CLI entry point (dry-run)
"""

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path so we can import run.py directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import (
    QUALITY_PASS_THRESHOLD,
    IngestionStatus,
    LearningIngestionSupervisor,
    QualitySignals,
    _detect_placeholders,
    _extract_signals,
    _score,
    _determine_status,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures (mirror the JSON files in tests/fixtures/)
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict | list:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


FAILED_TRANSCRIPT = _load_fixture("failed_transcript.json")
PLACEHOLDER_NOTES = _load_fixture("placeholder_notes.json")
DUPLICATE_PAIR = _load_fixture("duplicate_video.json")
WEAK_WORKFLOW = _load_fixture("weak_workflow.json")
SUCCESSFUL = _load_fixture("successful_ingestion.json")


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


class TestDetectPlaceholders(unittest.TestCase):
    def test_finds_bracket_placeholder(self):
        matches = _detect_placeholders("[placeholder]")
        self.assertTrue(matches)

    def test_finds_todo(self):
        matches = _detect_placeholders("TODO: add more content here")
        self.assertTrue(matches)

    def test_finds_insert_here(self):
        matches = _detect_placeholders("[Insert step here]")
        self.assertTrue(matches)

    def test_finds_no_transcript_found(self):
        matches = _detect_placeholders("no transcript found")
        self.assertTrue(matches)

    def test_clean_text_returns_empty(self):
        matches = _detect_placeholders(
            "FastAPI is a modern Python web framework for building REST APIs."
        )
        self.assertEqual(matches, [])

    def test_case_insensitive(self):
        matches = _detect_placeholders("LOREM IPSUM dolor sit amet")
        self.assertTrue(matches)


class TestExtractSignals(unittest.TestCase):
    def test_empty_artifact_has_no_transcript(self):
        sig = _extract_signals({"ingestion_id": "x", "title": "x", "agent_source": "x"})
        self.assertFalse(sig.has_transcript)
        self.assertEqual(sig.transcript_word_count, 0)

    def test_notes_list_is_joined(self):
        artifact = {
            "ingestion_id": "x",
            "title": "x",
            "agent_source": "x",
            "transcript": "real content " * 20,
            "notes": ["[placeholder]", "more stuff"],
        }
        sig = _extract_signals(artifact)
        self.assertTrue(sig.has_placeholder_content)

    def test_authenticity_gate_dict_form(self):
        artifact = {
            "ingestion_id": "x",
            "title": "x",
            "agent_source": "x",
            "authenticity_gate": {"passed": False},
        }
        sig = _extract_signals(artifact)
        self.assertFalse(sig.authenticity_gate_passed)

    def test_authenticity_gate_bool_form(self):
        artifact = {
            "ingestion_id": "x",
            "title": "x",
            "agent_source": "x",
            "authenticity_gate": True,
        }
        sig = _extract_signals(artifact)
        self.assertTrue(sig.authenticity_gate_passed)

    def test_duplicate_of_field(self):
        artifact = {
            "ingestion_id": "dup",
            "title": "x",
            "agent_source": "x",
            "duplicate_of": "original-id",
        }
        sig = _extract_signals(artifact)
        self.assertTrue(sig.is_duplicate)
        self.assertEqual(sig.duplicate_of, "original-id")


class TestScoring(unittest.TestCase):
    def test_score_is_zero_for_empty_signals(self):
        sig = QualitySignals()
        self.assertEqual(_score(sig), 0.0)

    def test_score_is_bounded_0_to_1(self):
        # Fully populated positive signals
        sig = QualitySignals(
            has_transcript=True,
            transcript_word_count=500,
            has_placeholder_content=False,
            workflow_step_count=10,
            has_executable_workflows=True,
            cognitive_gym_score=1.0,
            authenticity_gate_passed=True,
            source_evidence_preserved=True,
        )
        s = _score(sig)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_authenticity_gate_failure_lowers_score(self):
        sig_pass = QualitySignals(
            has_transcript=True,
            transcript_word_count=200,
            authenticity_gate_passed=True,
        )
        sig_fail = QualitySignals(
            has_transcript=True,
            transcript_word_count=200,
            authenticity_gate_passed=False,
        )
        self.assertGreater(_score(sig_pass), _score(sig_fail))

    def test_partial_workflow_credit(self):
        sig_no_wf = QualitySignals(
            has_transcript=True,
            transcript_word_count=200,
            workflow_step_count=0,
            has_executable_workflows=False,
        )
        sig_partial_wf = QualitySignals(
            has_transcript=True,
            transcript_word_count=200,
            workflow_step_count=1,
            has_executable_workflows=False,
        )
        self.assertGreater(_score(sig_partial_wf), _score(sig_no_wf))


class TestDetermineStatus(unittest.TestCase):
    def test_duplicate_is_quarantined(self):
        sig = QualitySignals(is_duplicate=True, duplicate_of="orig")
        status, reasons = _determine_status(sig, 0.9)
        self.assertEqual(status, IngestionStatus.QUARANTINED)
        self.assertTrue(any("duplicate" in r for r in reasons))

    def test_authenticity_gate_false_is_quarantined(self):
        sig = QualitySignals(authenticity_gate_passed=False)
        status, _ = _determine_status(sig, 0.9)
        self.assertEqual(status, IngestionStatus.QUARANTINED)

    def test_placeholder_content_is_quarantined(self):
        sig = QualitySignals(
            has_placeholder_content=True,
            placeholder_matches=["[placeholder]"],
            has_transcript=True,
            transcript_word_count=200,
        )
        status, reasons = _determine_status(sig, 0.9)
        self.assertEqual(status, IngestionStatus.QUARANTINED)
        self.assertTrue(any("placeholder" in r for r in reasons))

    def test_no_transcript_is_failed(self):
        sig = QualitySignals(has_transcript=False)
        status, _ = _determine_status(sig, 0.0)
        self.assertEqual(status, IngestionStatus.FAILED)

    def test_low_score_is_quarantined(self):
        sig = QualitySignals(
            has_transcript=True, transcript_word_count=200
        )
        status, _ = _determine_status(sig, QUALITY_PASS_THRESHOLD - 0.01)
        self.assertEqual(status, IngestionStatus.QUARANTINED)

    def test_high_quality_is_verified(self):
        sig = QualitySignals(
            has_transcript=True,
            transcript_word_count=500,
            has_placeholder_content=False,
            has_executable_workflows=True,
            workflow_step_count=8,
            authenticity_gate_passed=True,
            cognitive_gym_score=0.9,
            source_evidence_preserved=True,
        )
        status, _ = _determine_status(sig, _score(sig))
        self.assertEqual(status, IngestionStatus.VERIFIED)


# ---------------------------------------------------------------------------
# Integration tests: full supervisor run
# ---------------------------------------------------------------------------


class TestFailedTranscriptIngestion(unittest.TestCase):
    """Artifact with empty transcript → FAILED."""

    def setUp(self):
        self.supervisor = LearningIngestionSupervisor()

    def test_failed_transcript_produces_failed_status(self):
        report = self.supervisor.run([FAILED_TRANSCRIPT])
        self.assertEqual(len(report.failed), 1)
        self.assertEqual(len(report.verified), 0)

    def test_failed_transcript_has_low_quality_score(self):
        # An artifact with source evidence but no transcript scores above 0
        # but must be well below the pass threshold.
        report = self.supervisor.run([FAILED_TRANSCRIPT])
        record = report.failed[0]
        self.assertLess(record.quality_score, QUALITY_PASS_THRESHOLD)

    def test_failure_reason_mentions_transcript(self):
        report = self.supervisor.run([FAILED_TRANSCRIPT])
        record = report.failed[0]
        reasons_text = " ".join(record.failure_reasons).lower()
        self.assertIn("transcript", reasons_text)

    def test_pass_rate_is_zero(self):
        report = self.supervisor.run([FAILED_TRANSCRIPT])
        self.assertEqual(report.overall_pass_rate, 0.0)

    def test_recommendation_suggests_requeue(self):
        report = self.supervisor.run([FAILED_TRANSCRIPT])
        recs = " ".join(report.recommendations).lower()
        self.assertIn("requeue", recs)


class TestPlaceholderNotesIngestion(unittest.TestCase):
    """Artifact with placeholder content → QUARANTINED."""

    def setUp(self):
        self.supervisor = LearningIngestionSupervisor()

    def test_placeholder_notes_are_quarantined(self):
        report = self.supervisor.run([PLACEHOLDER_NOTES])
        self.assertEqual(len(report.quarantined), 1)
        self.assertEqual(len(report.verified), 0)

    def test_record_has_placeholder_signals(self):
        report = self.supervisor.run([PLACEHOLDER_NOTES])
        record = report.quarantined[0]
        self.assertTrue(record.signals.has_placeholder_content)
        self.assertTrue(record.signals.placeholder_matches)

    def test_failure_reason_mentions_placeholder(self):
        report = self.supervisor.run([PLACEHOLDER_NOTES])
        record = report.quarantined[0]
        reasons_text = " ".join(record.failure_reasons).lower()
        self.assertIn("placeholder", reasons_text)

    def test_recommendation_mentions_universal_skill_learner(self):
        report = self.supervisor.run([PLACEHOLDER_NOTES])
        recs = " ".join(report.recommendations).lower()
        self.assertIn("universal-skill-learner", recs)


class TestDuplicateVideoIngestion(unittest.TestCase):
    """Two ingestions with identical transcript content — second is QUARANTINED."""

    def setUp(self):
        self.supervisor = LearningIngestionSupervisor()
        self.report = self.supervisor.run(DUPLICATE_PAIR)

    def test_exactly_one_verified(self):
        self.assertEqual(len(self.report.verified), 1)

    def test_exactly_one_quarantined_as_duplicate(self):
        self.assertEqual(len(self.report.quarantined), 1)
        dup = self.report.quarantined[0]
        self.assertTrue(dup.signals.is_duplicate)

    def test_duplicate_points_to_original(self):
        dup = self.report.quarantined[0]
        original = self.report.verified[0]
        self.assertEqual(dup.signals.duplicate_of, original.ingestion_id)

    def test_recommendation_mentions_duplicate(self):
        recs = " ".join(self.report.recommendations).lower()
        self.assertIn("duplicate", recs)

    def test_original_ingestion_id_is_correct(self):
        original = self.report.verified[0]
        self.assertEqual(original.ingestion_id, "vid-003-original")


class TestWeakWorkflowIngestion(unittest.TestCase):
    """Ingestion with only a single-step workflow and low gym score → QUARANTINED."""

    def setUp(self):
        self.supervisor = LearningIngestionSupervisor()

    def test_weak_workflow_is_quarantined(self):
        report = self.supervisor.run([WEAK_WORKFLOW])
        self.assertEqual(len(report.quarantined), 1)
        self.assertEqual(len(report.verified), 0)

    def test_workflow_signals_reflect_weakness(self):
        report = self.supervisor.run([WEAK_WORKFLOW])
        record = report.quarantined[0]
        self.assertFalse(record.signals.has_executable_workflows)
        self.assertEqual(record.signals.workflow_step_count, 1)

    def test_quality_score_below_threshold(self):
        report = self.supervisor.run([WEAK_WORKFLOW])
        record = report.quarantined[0]
        self.assertLess(record.quality_score, QUALITY_PASS_THRESHOLD)

    def test_failure_reason_mentions_workflow(self):
        report = self.supervisor.run([WEAK_WORKFLOW])
        record = report.quarantined[0]
        reasons_text = " ".join(record.failure_reasons).lower()
        self.assertIn("workflow", reasons_text)

    def test_recommendation_mentions_cognitive_gym(self):
        report = self.supervisor.run([WEAK_WORKFLOW])
        recs = " ".join(report.recommendations).lower()
        self.assertIn("cognitive-gym", recs)


class TestSuccessfulRealWorkflowIngestion(unittest.TestCase):
    """High-quality artifact with real transcript and multi-step workflows → VERIFIED."""

    def setUp(self):
        self.supervisor = LearningIngestionSupervisor()

    def test_successful_ingestion_is_verified(self):
        report = self.supervisor.run([SUCCESSFUL])
        self.assertEqual(len(report.verified), 1)
        self.assertEqual(len(report.quarantined), 0)
        self.assertEqual(len(report.failed), 0)

    def test_quality_score_above_threshold(self):
        report = self.supervisor.run([SUCCESSFUL])
        record = report.verified[0]
        self.assertGreaterEqual(record.quality_score, QUALITY_PASS_THRESHOLD)

    def test_signals_show_rich_content(self):
        report = self.supervisor.run([SUCCESSFUL])
        record = report.verified[0]
        self.assertTrue(record.signals.has_transcript)
        self.assertGreaterEqual(record.signals.transcript_word_count, 50)
        self.assertTrue(record.signals.has_executable_workflows)
        self.assertGreater(record.signals.workflow_step_count, 2)

    def test_no_placeholder_content(self):
        report = self.supervisor.run([SUCCESSFUL])
        record = report.verified[0]
        self.assertFalse(record.signals.has_placeholder_content)

    def test_authenticity_gate_passed(self):
        report = self.supervisor.run([SUCCESSFUL])
        record = report.verified[0]
        self.assertTrue(record.signals.authenticity_gate_passed)

    def test_pass_rate_is_1(self):
        report = self.supervisor.run([SUCCESSFUL])
        self.assertEqual(report.overall_pass_rate, 1.0)

    def test_recommendation_mentions_memory_promotion(self):
        report = self.supervisor.run([SUCCESSFUL])
        recs = " ".join(report.recommendations).lower()
        self.assertIn("memory", recs)


# ---------------------------------------------------------------------------
# Output generation tests
# ---------------------------------------------------------------------------


class TestOutputGeneration(unittest.TestCase):
    """Ensure write_outputs produces all four expected files."""

    def setUp(self):
        import tempfile

        self.tmp_dir = Path(tempfile.mkdtemp())
        self.supervisor = LearningIngestionSupervisor(reports_dir=self.tmp_dir)

    def test_all_four_output_files_created(self):
        report = self.supervisor.run([SUCCESSFUL, FAILED_TRANSCRIPT])
        self.supervisor.write_outputs(report)

        expected = [
            "VERIFIED_LEARNING.md",
            "INGESTION_FAILURES.md",
            "EXTRACTION_QUALITY_SCORE.json",
            "LEARNING_RECOMMENDATIONS.md",
        ]
        for fname in expected:
            path = self.tmp_dir / fname
            self.assertTrue(path.exists(), f"Missing output: {fname}")

    def test_extraction_quality_score_is_valid_json(self):
        report = self.supervisor.run([SUCCESSFUL])
        self.supervisor.write_outputs(report)
        content = (self.tmp_dir / "EXTRACTION_QUALITY_SCORE.json").read_text()
        data = json.loads(content)
        self.assertIn("overall_pass_rate", data)
        self.assertIn("per_ingestion", data)
        self.assertIn("counts", data)

    def test_verified_learning_contains_title(self):
        report = self.supervisor.run([SUCCESSFUL])
        self.supervisor.write_outputs(report)
        content = (self.tmp_dir / "VERIFIED_LEARNING.md").read_text()
        self.assertIn(SUCCESSFUL["title"], content)

    def test_ingestion_failures_contains_failed_id(self):
        report = self.supervisor.run([FAILED_TRANSCRIPT])
        self.supervisor.write_outputs(report)
        content = (self.tmp_dir / "INGESTION_FAILURES.md").read_text()
        self.assertIn(FAILED_TRANSCRIPT["ingestion_id"], content)

    def test_recommendations_file_has_heading(self):
        report = self.supervisor.run([SUCCESSFUL])
        self.supervisor.write_outputs(report)
        content = (self.tmp_dir / "LEARNING_RECOMMENDATIONS.md").read_text()
        self.assertIn("# LEARNING_RECOMMENDATIONS", content)


# ---------------------------------------------------------------------------
# Mixed batch test
# ---------------------------------------------------------------------------


class TestMixedBatch(unittest.TestCase):
    """Run all fixtures together to verify counts and isolation."""

    def setUp(self):
        self.supervisor = LearningIngestionSupervisor()
        all_artifacts = [
            FAILED_TRANSCRIPT,
            PLACEHOLDER_NOTES,
            *DUPLICATE_PAIR,
            WEAK_WORKFLOW,
            SUCCESSFUL,
        ]
        self.report = self.supervisor.run(all_artifacts)

    def test_total_inspected_is_six(self):
        self.assertEqual(self.report.total_inspected, 6)

    def test_exactly_two_verified(self):
        # SUCCESSFUL + vid-003-original
        self.assertEqual(len(self.report.verified), 2)

    def test_exactly_three_quarantined(self):
        # PLACEHOLDER_NOTES + vid-003-duplicate + WEAK_WORKFLOW
        self.assertEqual(len(self.report.quarantined), 3)

    def test_exactly_one_failed(self):
        self.assertEqual(len(self.report.failed), 1)

    def test_pass_rate_is_correct(self):
        self.assertAlmostEqual(self.report.overall_pass_rate, 2 / 6, places=4)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):
    def test_dry_run_from_stdin(self):
        artifact_json = json.dumps([SUCCESSFUL])
        with patch("sys.stdin", StringIO(artifact_json)):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                exit_code = main(["--dry-run"])
        self.assertEqual(exit_code, 0)
        output = mock_out.getvalue()
        self.assertIn("Verified", output)

    def test_nonexistent_path_returns_error(self):
        exit_code = main(["/nonexistent/path/artifacts.json"])
        self.assertEqual(exit_code, 1)

    def test_bad_stdin_json_returns_error(self):
        with patch("sys.stdin", StringIO("not valid json")):
            exit_code = main(["--dry-run"])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
