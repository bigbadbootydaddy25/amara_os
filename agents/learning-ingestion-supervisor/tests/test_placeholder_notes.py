"""
Tests for placeholder note detection.

Notes containing TODO / placeholder / insert-content-here signals must:
 - receive a heavily penalised notes score
 - prevent promotion (verdict QUARANTINE or REVIEW, not PROMOTE)
 - surface the issue in reports
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from quality import (
    VERDICT_PROMOTE,
    VERDICT_QUARANTINE,
    VERDICT_REVIEW,
    score_notes,
    score_transcript,
    score_workflow,
    score_authenticity,
    compute_overall,
)
from supervisor import LearningIngestionSupervisor
from tests.conftest import GOOD_TRANSCRIPT, GOOD_WORKFLOW


PLACEHOLDER_SAMPLES = [
    "TODO: insert content here",
    "placeholder — notes not generated yet",
    "## Summary\n\nN/A",
    "lorem ipsum dolor sit amet",
    "<no notes>",
    "FIXME: fill this in",
    "transcript not available",
]


class TestNotesScoring:
    @pytest.mark.parametrize("text", PLACEHOLDER_SAMPLES)
    def test_placeholder_text_penalised(self, tmp_path, text):
        p = tmp_path / "notes.md"
        p.write_text(text, encoding="utf-8")
        dim = score_notes(p)
        assert dim.score < 60.0, f"Expected penalty for: {text!r}"
        assert dim.issues, "Expected at least one issue to be reported"

    def test_empty_notes_scores_zero(self, tmp_path):
        p = tmp_path / "notes.md"
        p.write_text("", encoding="utf-8")
        dim = score_notes(p)
        assert dim.score == 0.0

    def test_title_only_penalised(self, tmp_path):
        p = tmp_path / "notes.md"
        p.write_text("# My Video\n", encoding="utf-8")
        dim = score_notes(p)
        assert dim.score < 70.0
        assert any("title" in i.lower() or "body" in i.lower() for i in dim.issues)

    def test_no_structure_penalised(self, tmp_path):
        p = tmp_path / "notes.md"
        p.write_text(" ".join(["word"] * 150), encoding="utf-8")
        dim = score_notes(p)
        assert any("structure" in i.lower() for i in dim.issues)

    def test_good_notes_score_high(self, tmp_path):
        from tests.conftest import GOOD_NOTES
        p = tmp_path / "notes.md"
        p.write_text(GOOD_NOTES, encoding="utf-8")
        dim = score_notes(p)
        assert dim.score >= 70.0
        assert not dim.issues

    def test_missing_notes_file_scores_zero(self, tmp_path):
        dim = score_notes(tmp_path / "notes.md")
        assert dim.score == 0.0


class TestPlaceholderNotesVerdict:
    def test_placeholder_notes_prevent_promotion(self, tmp_path):
        tx = tmp_path / "transcript.txt"
        tx.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        notes = tmp_path / "notes.md"
        notes.write_text("TODO: insert content here\nplaceholder", encoding="utf-8")
        wf = tmp_path / "workflow.md"
        wf.write_text(GOOD_WORKFLOW, encoding="utf-8")

        t = score_transcript(tx)
        n = score_notes(notes)
        w = score_workflow(wf)
        a = score_authenticity(None)
        assessment = compute_overall("s", t, n, w, a)

        assert assessment.verdict != VERDICT_PROMOTE, (
            f"Placeholder notes should not be promoted (got {assessment.verdict}, "
            f"score={assessment.overall_score})"
        )

    def test_placeholder_notes_issue_surfaced(self, tmp_path):
        notes = tmp_path / "notes.md"
        notes.write_text("TODO: insert content here", encoding="utf-8")
        dim = score_notes(notes)
        assert any("placeholder" in i.lower() for i in dim.issues)


class TestPlaceholderNotesEndToEnd:
    def test_placeholder_session_not_promoted(self, placeholder_notes_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=placeholder_notes_brain,
            output_dir=output_dir,
        )
        sup.run()

        a = sup.assessments["session-placeholder"]
        assert a.verdict != VERDICT_PROMOTE

    def test_placeholder_issues_appear_in_failures_or_score(self, placeholder_notes_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=placeholder_notes_brain,
            output_dir=output_dir,
        )
        sup.run()

        score_data = (output_dir / "EXTRACTION_QUALITY_SCORE.json").read_text()
        assert "session-placeholder" in score_data
        assert "placeholder" in score_data.lower() or "notes" in score_data.lower()

    def test_recommendations_mention_low_quality(self, placeholder_notes_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=placeholder_notes_brain,
            output_dir=output_dir,
        )
        sup.run()

        recs = (output_dir / "LEARNING_RECOMMENDATIONS.md").read_text()
        assert "QUARANTINE" in recs or "REVIEW" in recs or "quality" in recs.lower()
