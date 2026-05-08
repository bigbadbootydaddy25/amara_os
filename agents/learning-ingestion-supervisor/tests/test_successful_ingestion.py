"""
Tests for a successful, high-quality ingestion.

A session with a good transcript, structured notes, a concrete workflow,
and a passing SAG verdict must:
 - score >= 70 overall
 - be assigned verdict PROMOTE
 - appear in VERIFIED_LEARNING.md
 - NOT appear in INGESTION_FAILURES.md
 - produce all four output reports
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from quality import (
    VERDICT_PROMOTE,
    score_transcript,
    score_notes,
    score_workflow,
    score_authenticity,
    compute_overall,
    PROMOTE_THRESHOLD,
)
from inspectors import UniversalSkillLearnerInspector
from supervisor import LearningIngestionSupervisor
from tests.conftest import GOOD_TRANSCRIPT, GOOD_NOTES, GOOD_WORKFLOW


class TestSuccessfulQualityScoring:
    def test_good_transcript_scores_above_threshold(self, tmp_path):
        tx = tmp_path / "t.txt"
        tx.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        dim = score_transcript(tx)
        assert dim.score >= PROMOTE_THRESHOLD
        assert not dim.issues

    def test_good_notes_score_above_threshold(self, tmp_path):
        n = tmp_path / "n.md"
        n.write_text(GOOD_NOTES, encoding="utf-8")
        dim = score_notes(n)
        assert dim.score >= PROMOTE_THRESHOLD
        assert not dim.issues

    def test_good_workflow_scores_above_threshold(self, tmp_path):
        w = tmp_path / "w.md"
        w.write_text(GOOD_WORKFLOW, encoding="utf-8")
        dim = score_workflow(w)
        assert dim.score >= PROMOTE_THRESHOLD
        assert not dim.issues

    def test_authentic_sag_result_scores_high(self):
        sag = {"session_id": "s", "verdict": "AUTHENTIC", "confidence": 0.92, "flags": []}
        dim = score_authenticity(sag)
        assert dim.score >= 80.0
        assert not dim.issues

    def test_overall_promote_with_all_good_artifacts(self, tmp_path):
        tx = tmp_path / "t.txt"
        tx.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        n = tmp_path / "n.md"
        n.write_text(GOOD_NOTES, encoding="utf-8")
        w = tmp_path / "w.md"
        w.write_text(GOOD_WORKFLOW, encoding="utf-8")
        sag = {"verdict": "AUTHENTIC", "confidence": 0.92, "flags": []}

        t_s = score_transcript(tx)
        n_s = score_notes(n)
        w_s = score_workflow(w)
        a_s = score_authenticity(sag)

        assessment = compute_overall("s", t_s, n_s, w_s, a_s)
        assert assessment.overall_score >= PROMOTE_THRESHOLD
        assert assessment.verdict == VERDICT_PROMOTE
        assert not assessment.is_duplicate


class TestSuccessfulIngestionInspection:
    def test_inspector_discovers_session(self, successful_ingestion_brain):
        inspector = UniversalSkillLearnerInspector(successful_ingestion_brain)
        records = inspector.collect()
        assert len(records) == 1
        r = records[0]
        assert r.session_id == "session-success"
        assert r.transcript_path is not None and r.transcript_path.exists()
        assert r.notes_path is not None and r.notes_path.exists()
        assert r.workflow_path is not None and r.workflow_path.exists()

    def test_enrichment_loads_sag_result(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        sup.run()
        record = next(r for r in sup.records if r.session_id == "session-success")
        assert record.authenticity_result is not None
        assert record.authenticity_result["verdict"] == "AUTHENTIC"


class TestSuccessfulIngestionEndToEnd:
    def test_successful_session_gets_promote_verdict(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
            min_quality_score=60.0,
        )
        exit_code = sup.run()

        assert exit_code == 0
        assert "session-success" in sup.assessments
        a = sup.assessments["session-success"]
        assert a.verdict == VERDICT_PROMOTE, (
            f"Expected PROMOTE, got {a.verdict} (score={a.overall_score}, "
            f"issues={a.transcript.issues + a.notes.issues + a.workflow.issues})"
        )

    def test_successful_session_in_verified_learning(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        sup.run()

        verified = (output_dir / "VERIFIED_LEARNING.md").read_text()
        assert "session-success" in verified

    def test_successful_session_not_in_failures(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        sup.run()

        failures = (output_dir / "INGESTION_FAILURES.md").read_text()
        assert "session-success" not in failures

    def test_all_four_reports_generated(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        sup.run()

        expected = [
            "VERIFIED_LEARNING.md",
            "INGESTION_FAILURES.md",
            "EXTRACTION_QUALITY_SCORE.json",
            "LEARNING_RECOMMENDATIONS.md",
        ]
        for fname in expected:
            path = output_dir / fname
            assert path.exists(), f"Expected report not found: {fname}"
            assert path.stat().st_size > 0, f"Report is empty: {fname}"

    def test_score_json_structure_valid(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        sup.run()

        data = json.loads((output_dir / "EXTRACTION_QUALITY_SCORE.json").read_text())
        assert "summary" in data
        assert "sessions" in data
        assert data["summary"]["total_sessions"] == 1
        assert data["summary"]["verdicts"]["PROMOTE"] == 1

        session = data["sessions"][0]
        assert session["session_id"] == "session-success"
        assert session["overall_score"] >= PROMOTE_THRESHOLD
        for dim in ("transcript", "workflow", "notes", "authenticity"):
            assert dim in session["dimensions"]

    def test_supervisor_exit_code_zero_on_success(self, successful_ingestion_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        assert sup.run() == 0

    def test_no_quarantine_files_written_for_promoted_session(
        self, successful_ingestion_brain, tmp_path
    ):
        output_dir = tmp_path / "reports"
        quarantine_dir = successful_ingestion_brain / "data" / "quarantine"
        sup = LearningIngestionSupervisor(
            brain_dir=successful_ingestion_brain,
            output_dir=output_dir,
        )
        sup.run()

        if quarantine_dir.exists():
            quarantined = [p for p in quarantine_dir.iterdir() if p.is_dir()]
            assert not any(
                "session-success" in str(p) for p in quarantined
            ), "Promoted session should not be quarantined"
