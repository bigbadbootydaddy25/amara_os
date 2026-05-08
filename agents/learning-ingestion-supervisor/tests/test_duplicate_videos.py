"""
Tests for duplicate video detection.

When two sessions share the same video URL:
 - Only one (the canonical / first-by-session_id) should be eligible for promotion
 - The duplicate must be quarantined with is_duplicate=True
 - The canonical session may still be promoted on its own merits
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from inspectors import (
    IngestionRecord,
    UniversalSkillLearnerInspector,
    detect_duplicates,
)
from quality import VERDICT_QUARANTINE, VERDICT_PROMOTE, VERDICT_REVIEW
from supervisor import LearningIngestionSupervisor
from tests.conftest import GOOD_TRANSCRIPT, GOOD_NOTES, GOOD_WORKFLOW, _usl_session


class TestDuplicateDetection:
    def test_detect_two_sessions_same_url(self):
        records = [
            IngestionRecord("session-a", "usl", video_url="https://example.com/v/1"),
            IngestionRecord("session-b", "usl", video_url="https://example.com/v/1"),
            IngestionRecord("session-c", "usl", video_url="https://example.com/v/2"),
        ]
        dupes = detect_duplicates(records)
        # session-a is canonical (first alphabetically); session-b is a duplicate
        assert "session-b" in dupes
        assert dupes["session-b"] == "session-a"
        assert "session-a" not in dupes
        assert "session-c" not in dupes

    def test_no_duplicates_when_urls_unique(self):
        records = [
            IngestionRecord("s1", "usl", video_url="https://example.com/v/1"),
            IngestionRecord("s2", "usl", video_url="https://example.com/v/2"),
        ]
        assert detect_duplicates(records) == {}

    def test_records_with_no_url_not_flagged(self):
        records = [
            IngestionRecord("s1", "usl", video_url=None),
            IngestionRecord("s2", "usl", video_url=None),
        ]
        assert detect_duplicates(records) == {}

    def test_url_comparison_is_case_insensitive(self):
        records = [
            IngestionRecord("s1", "usl", video_url="https://Example.com/v/1"),
            IngestionRecord("s2", "usl", video_url="https://example.com/v/1"),
        ]
        dupes = detect_duplicates(records)
        assert len(dupes) == 1

    def test_three_sessions_same_url_yields_two_duplicates(self):
        records = [
            IngestionRecord("s1", "usl", video_url="https://example.com/v/1"),
            IngestionRecord("s2", "usl", video_url="https://example.com/v/1"),
            IngestionRecord("s3", "usl", video_url="https://example.com/v/1"),
        ]
        dupes = detect_duplicates(records)
        assert "s1" not in dupes
        assert "s2" in dupes
        assert "s3" in dupes


class TestDuplicateScoring:
    def test_duplicate_verdict_is_quarantine(self, tmp_path):
        from quality import score_transcript, score_notes, score_workflow, score_authenticity, compute_overall
        tx = tmp_path / "t.txt"
        tx.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        n = tmp_path / "n.md"
        n.write_text(GOOD_NOTES, encoding="utf-8")
        w = tmp_path / "w.md"
        w.write_text(GOOD_WORKFLOW, encoding="utf-8")

        t_s = score_transcript(tx)
        n_s = score_notes(n)
        w_s = score_workflow(w)
        a_s = score_authenticity(None)

        assessment = compute_overall(
            "s-dup", t_s, n_s, w_s, a_s,
            is_duplicate=True, duplicate_of="s-original"
        )
        assert assessment.verdict == VERDICT_QUARANTINE
        assert assessment.is_duplicate is True
        assert assessment.duplicate_of == "s-original"

    def test_duplicate_caps_overall_score(self, tmp_path):
        from quality import score_transcript, score_notes, score_workflow, score_authenticity, compute_overall
        tx = tmp_path / "t.txt"
        tx.write_text(GOOD_TRANSCRIPT, encoding="utf-8")
        n = tmp_path / "n.md"
        n.write_text(GOOD_NOTES, encoding="utf-8")
        w = tmp_path / "w.md"
        w.write_text(GOOD_WORKFLOW, encoding="utf-8")

        t_s = score_transcript(tx)
        n_s = score_notes(n)
        w_s = score_workflow(w)
        a_s = score_authenticity(None)
        assessment = compute_overall("s", t_s, n_s, w_s, a_s, is_duplicate=True, duplicate_of="x")
        assert assessment.overall_score <= 35.0


class TestDuplicateEndToEnd:
    def test_duplicate_quarantined_canonical_may_promote(self, duplicate_videos_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=duplicate_videos_brain,
            output_dir=output_dir,
            min_quality_score=60.0,
        )
        sup.run()

        assert "session-canonical" in sup.assessments
        assert "session-zz-duplicate" in sup.assessments

        dup_verdict = sup.assessments["session-zz-duplicate"].verdict
        assert dup_verdict == VERDICT_QUARANTINE
        assert sup.assessments["session-zz-duplicate"].is_duplicate is True

        # Canonical session should not be marked as a duplicate
        canonical = sup.assessments["session-canonical"]
        assert canonical.is_duplicate is False

    def test_duplicate_in_failures_report(self, duplicate_videos_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=duplicate_videos_brain,
            output_dir=output_dir,
        )
        sup.run()

        failures = (output_dir / "INGESTION_FAILURES.md").read_text()
        assert "session-zz-duplicate" in failures

    def test_duplicate_score_json_has_duplicate_flag(self, duplicate_videos_brain, tmp_path):
        import json
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=duplicate_videos_brain,
            output_dir=output_dir,
        )
        sup.run()

        data = json.loads((output_dir / "EXTRACTION_QUALITY_SCORE.json").read_text())
        dup_session = next(s for s in data["sessions"] if s["session_id"] == "session-zz-duplicate")
        assert dup_session["is_duplicate"] is True
        assert dup_session["duplicate_of"] == "session-canonical"

    def test_recommendations_mention_duplicates(self, duplicate_videos_brain, tmp_path):
        output_dir = tmp_path / "reports"
        sup = LearningIngestionSupervisor(
            brain_dir=duplicate_videos_brain,
            output_dir=output_dir,
        )
        sup.run()

        recs = (output_dir / "LEARNING_RECOMMENDATIONS.md").read_text()
        assert "duplicate" in recs.lower()
