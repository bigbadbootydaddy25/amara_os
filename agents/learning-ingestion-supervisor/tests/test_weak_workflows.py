"""
Tests for weak / fabricated workflow detection.

Workflows with vague steps, too few steps, or placeholder content must:
 - receive a penalised workflow score
 - lower the overall score enough to prevent promotion unless other dims are excellent
 - surface specific issues in the score report
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from quality import (
    VERDICT_PROMOTE,
    score_workflow,
    score_transcript,
    score_notes,
    score_authenticity,
    compute_overall,
    MIN_WORKFLOW_STEPS,
)
from supervisor import LearningIngestionSupervisor
from tests.conftest import GOOD_TRANSCRIPT, GOOD_NOTES, GOOD_WORKFLOW


VAGUE_WORKFLOW_SAMPLES = [
    ("empty", ""),
    ("single_vague_step", "1. Do the thing\n"),
    ("steps_too_short", "1. Go\n2. Run\n3. Stop\n"),
    ("placeholder_steps", "1. TODO: add step\n2. FIXME: fill in\n3. placeholder\n"),
    ("too_few_steps", "1. Open the file\n2. Save it\n"),
]


class TestWorkflowScoring:
    @pytest.mark.parametrize("label,text", VAGUE_WORKFLOW_SAMPLES)
    def test_weak_workflow_penalised(self, tmp_path, label, text):
        p = tmp_path / f"workflow_{label}.md"
        p.write_text(text, encoding="utf-8")
        dim = score_workflow(p)
        assert dim.score < 70.0, f"[{label}] Expected penalty, got score={dim.score}"

    def test_no_workflow_file_is_neutral_penalty(self, tmp_path):
        dim = score_workflow(tmp_path / "workflow.md")
        assert dim.score == 30.0

    def test_no_workflow_path_gives_partial_score(self):
        dim = score_workflow(None)
        assert dim.score == 50.0
        assert dim.issues  # should note the absence

    def test_good_workflow_scores_high(self, tmp_path):
        p = tmp_path / "workflow.md"
        p.write_text(GOOD_WORKFLOW, encoding="utf-8")
        dim = score_workflow(p)
        assert dim.score >= 70.0
        assert not dim.issues

    def test_vague_steps_issue_reported(self, tmp_path):
        p = tmp_path / "workflow.md"
        p.write_text("1. Do the thing\n2. Follow steps\n3. Repeat\n", encoding="utf-8")
        dim = score_workflow(p)
        assert any("vague" in i.lower() or "fabricat" in i.lower() for i in dim.issues)

    def test_too_few_steps_issue_reported(self, tmp_path):
        p = tmp_path / "workflow.md"
        p.write_text("1. Open the IDE\n2. Save the file\n", encoding="utf-8")
        dim = score_workflow(p)
        assert any("few" in i.lower() or "step" in i.lower() for i in dim.issues)

    def test_step_count_evidence_recorded(self, tmp_path):
        p = tmp_path / "workflow.md"
        p.write_text(GOOD_WORKFLOW, encoding="utf-8")
        dim = score_workflow(p)
        assert any("step" in e.lower() for e in dim.evidence)

    def test_minimum_steps_boundary(self, tmp_path):
        """Exactly MIN_WORKFLOW_STEPS steps with good content should not trigger the low-count penalty."""
        steps = "\n".join(
            f"{i+1}. Configure the {['server', 'database', 'cache'][i]} settings correctly"
            for i in range(MIN_WORKFLOW_STEPS)
        )
        p = tmp_path / "workflow.md"
        p.write_text(steps, encoding="utf-8")
        dim = score_workflow(p)
        assert not any("few" in i.lower() for i in dim.issues)


class TestWeakWorkflowVerdict:
    def test_vague_workflow_does_not_promote(self, tmp_path):
        tx = tmp_path / "t.txt"
        tx.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        notes = tmp_path / "n.md"
        notes.write_text(GOOD_NOTES, encoding="utf-8")
        wf = tmp_path / "wf.md"
        wf.write_text("1. Do the thing\n2. Repeat\n3. Etc.\n", encoding="utf-8")

        t_s = score_transcript(tx)
        w_s = score_workflow(wf)
        n_s = score_notes(notes)
        a_s = score_authenticity(None)

        # keyword args: workflow must come before notes per compute_overall signature
        assessment = compute_overall(
            session_id="s",
            transcript=t_s,
            workflow=w_s,
            notes=n_s,
            authenticity=a_s,
        )
        assert assessment.verdict != VERDICT_PROMOTE


class TestWeakWorkflowEndToEnd:
    def test_weak_workflow_session_not_promoted(self, weak_workflow_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=weak_workflow_brain,
            output_dir=output_dir,
        )
        sup.run()

        a = sup.assessments["session-weak-wf"]
        assert a.verdict != VERDICT_PROMOTE
        assert a.workflow.score < 70.0

    def test_workflow_issues_appear_in_score_json(self, weak_workflow_brain, tmp_path):
        import json
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=weak_workflow_brain,
            output_dir=output_dir,
        )
        sup.run()

        data = json.loads((output_dir / "EXTRACTION_QUALITY_SCORE.json").read_text())
        session = next(s for s in data["sessions"] if s["session_id"] == "session-weak-wf")
        assert session["dimensions"]["workflow"]["issues"]

    def test_recommendations_mention_workflow_quality(self, weak_workflow_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=weak_workflow_brain,
            output_dir=output_dir,
        )
        sup.run()

        recs = (output_dir / "LEARNING_RECOMMENDATIONS.md").read_text()
        assert "workflow" in recs.lower()
