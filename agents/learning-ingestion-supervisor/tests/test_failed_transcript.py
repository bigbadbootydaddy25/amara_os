"""
Tests for failed transcript extraction detection.

A session whose transcript.txt is missing or empty must:
 - receive a transcript score of 0
 - be assigned verdict FAILED (not merely QUARANTINE)
 - appear in INGESTION_FAILURES.md
 - NOT appear in VERIFIED_LEARNING.md
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from quality import (
    VERDICT_FAILED,
    score_transcript,
    score_notes,
    score_workflow,
    compute_overall,
)
from inspectors import UniversalSkillLearnerInspector
from supervisor import LearningIngestionSupervisor
from tests.conftest import GOOD_NOTES, GOOD_WORKFLOW


class TestTranscriptScoring:
    def test_missing_transcript_path_scores_zero(self):
        dim = score_transcript(None)
        assert dim.score == 0.0
        assert any("No transcript" in i for i in dim.issues)

    def test_nonexistent_file_scores_zero(self, tmp_path):
        ghost = tmp_path / "ghost.txt"
        dim = score_transcript(ghost)
        assert dim.score == 0.0
        assert any("missing" in i.lower() for i in dim.issues)

    def test_empty_file_scores_zero(self, tmp_path):
        empty = tmp_path / "transcript.txt"
        empty.write_text("", encoding="utf-8")
        dim = score_transcript(empty)
        assert dim.score == 0.0
        assert any("empty" in i.lower() for i in dim.issues)

    def test_whitespace_only_scores_zero(self, tmp_path):
        ws = tmp_path / "transcript.txt"
        ws.write_text("   \n\n\t  ", encoding="utf-8")
        dim = score_transcript(ws)
        assert dim.score == 0.0

    def test_timestamps_only_penalised(self, tmp_path):
        t = tmp_path / "transcript.txt"
        t.write_text("\n".join(f"[{i}:00]" for i in range(80)), encoding="utf-8")
        dim = score_transcript(t)
        assert dim.score < 50.0
        assert any("timestamp" in i.lower() for i in dim.issues)

    def test_placeholder_text_penalised(self, tmp_path):
        t = tmp_path / "transcript.txt"
        t.write_text("transcript not available\nfailed to extract\n" * 5, encoding="utf-8")
        dim = score_transcript(t)
        assert dim.score < 60.0
        assert any("placeholder" in i.lower() or "error" in i.lower() for i in dim.issues)

    def test_good_transcript_scores_high(self, tmp_path):
        from tests.conftest import GOOD_TRANSCRIPT
        t = tmp_path / "transcript.txt"
        t.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        dim = score_transcript(t)
        assert dim.score >= 70.0
        assert not dim.issues


class TestFailedTranscriptVerdict:
    def test_empty_transcript_yields_failed_verdict(self, tmp_path):
        notes = tmp_path / "notes.md"
        notes.write_text(GOOD_NOTES, encoding="utf-8")
        wf = tmp_path / "workflow.md"
        wf.write_text(GOOD_WORKFLOW, encoding="utf-8")
        empty_tx = tmp_path / "transcript.txt"
        empty_tx.write_text("", encoding="utf-8")

        t = score_transcript(empty_tx)
        n = score_notes(notes)
        w = score_workflow(wf)
        from quality import score_authenticity
        a = score_authenticity(None)

        assessment = compute_overall("session-x", t, n, w, a)
        assert assessment.verdict == VERDICT_FAILED

    def test_missing_transcript_caps_overall_score(self, tmp_path):
        notes = tmp_path / "notes.md"
        notes.write_text(GOOD_NOTES, encoding="utf-8")
        t = score_transcript(None)
        n = score_notes(notes)
        w = score_workflow(None)
        from quality import score_authenticity
        a = score_authenticity(None)
        assessment = compute_overall("s", t, n, w, a)
        assert assessment.overall_score <= 20.0


class TestFailedTranscriptEndToEnd:
    def test_failed_session_quarantined(self, failed_transcript_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=failed_transcript_brain,
            output_dir=output_dir,
            dry_run=True,
        )
        exit_code = sup.run()
        assert exit_code == 0

        assert "session-failed-tx" in sup.assessments
        verdict = sup.assessments["session-failed-tx"].verdict
        assert verdict == VERDICT_FAILED

    def test_failed_session_in_failures_report(self, failed_transcript_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=failed_transcript_brain,
            output_dir=output_dir,
        )
        sup.run()

        failures_md = (output_dir / "INGESTION_FAILURES.md").read_text()
        assert "session-failed-tx" in failures_md

        verified_md = (output_dir / "VERIFIED_LEARNING.md").read_text()
        assert "session-failed-tx" not in verified_md

    def test_quality_score_json_records_failed_verdict(self, failed_transcript_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=failed_transcript_brain,
            output_dir=output_dir,
        )
        sup.run()

        data = json.loads((output_dir / "EXTRACTION_QUALITY_SCORE.json").read_text())
        failed_session = next(
            s for s in data["sessions"] if s["session_id"] == "session-failed-tx"
        )
        assert failed_session["verdict"] == VERDICT_FAILED
        assert failed_session["overall_score"] <= 20.0
