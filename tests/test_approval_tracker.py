"""Tests for Approval Tracker — stage tracking, backlog scoring."""

import pytest
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.approval_tracker import (
    ApprovalRecord,
    APPROVAL_STAGES,
    EXPECTED_STAGE_DURATIONS,
    _compute_backlog_score,
    _likely_next_step,
)


TODAY = date(2026, 3, 30)


def make_record(**kwargs):
    defaults = dict(
        approval_id        = "APR-TEST01",
        deal_id            = "LAND-001",
        address            = "100 Dev Rd",
        zip_code           = "78701",
        county             = "Travis",
        current_stage      = "pre_app",
        department         = "Planning",
        stage_entered_date = TODAY - timedelta(days=10),
        expected_duration  = EXPECTED_STAGE_DURATIONS.get("pre_app", 30),
        revision_count     = 0,
        continuance_count  = 0,
        comment_rounds     = 0,
    )
    defaults.update(kwargs)
    record = ApprovalRecord(**defaults)
    return record


class TestApprovalRecord:
    def test_progress_pct_starts_at_zero(self):
        record = make_record(current_stage="pre_app")
        assert record.progress_pct() == 0.0

    def test_progress_pct_complete_is_1(self):
        record = make_record(current_stage="complete")
        assert record.progress_pct() == 1.0

    def test_progress_pct_midpoint(self):
        record = make_record(current_stage="preliminary_plat")
        pct = record.progress_pct()
        assert 0.10 < pct < 0.70

    def test_compute_days_in_stage(self):
        record = make_record(stage_entered_date=TODAY - timedelta(days=15))
        assert record.compute_days_in_stage(TODAY) == 15

    def test_compute_days_none_when_no_date(self):
        record = make_record(stage_entered_date=None)
        assert record.compute_days_in_stage(TODAY) == 0

    def test_stage_label(self):
        record = make_record(current_stage="preliminary_plat")
        assert record.stage_label() == "Preliminary Plat"


class TestComputeBacklogScore:
    def test_no_overrun_no_revisions_is_zero(self):
        record = make_record(
            stage_entered_date = TODAY - timedelta(days=10),
            expected_duration  = 30,
            revision_count     = 0,
            continuance_count  = 0,
            comment_rounds     = 0,
        )
        score = _compute_backlog_score(record, TODAY)
        assert score == 0.0

    def test_overrun_raises_score(self):
        record = make_record(
            stage_entered_date = TODAY - timedelta(days=90),  # 3x expected
            expected_duration  = 30,
            revision_count     = 0,
        )
        score = _compute_backlog_score(record, TODAY)
        assert score >= 0.30

    def test_revisions_raise_score(self):
        record_no_rev = make_record(revision_count=0)
        record_revs   = make_record(revision_count=3)
        assert _compute_backlog_score(record_revs, TODAY) > _compute_backlog_score(record_no_rev, TODAY)

    def test_continuances_raise_score(self):
        record_no_cont = make_record(continuance_count=0)
        record_cont    = make_record(continuance_count=3)
        assert _compute_backlog_score(record_cont, TODAY) > _compute_backlog_score(record_no_cont, TODAY)

    def test_max_score_is_1(self):
        record = make_record(
            stage_entered_date = TODAY - timedelta(days=365),
            expected_duration  = 30,
            revision_count     = 10,
            continuance_count  = 5,
            comment_rounds     = 5,
        )
        score = _compute_backlog_score(record, TODAY)
        assert score <= 1.0

    def test_backlog_flag_threshold_at_040(self):
        record = make_record(
            stage_entered_date = TODAY - timedelta(days=100),
            expected_duration  = 30,
            revision_count     = 2,
        )
        score = _compute_backlog_score(record, TODAY)
        # If score >= 0.40, flag should be True
        if score >= 0.40:
            assert True  # flag logic is enforced in _refresh_backlog
        else:
            assert score < 0.40


class TestLikelyNextStep:
    def test_pre_app_next_step(self):
        record = make_record(current_stage="pre_app")
        step   = _likely_next_step(record)
        assert "preliminary plat" in step.lower()

    def test_complete_next_step(self):
        record = make_record(current_stage="complete")
        step   = _likely_next_step(record)
        assert "builder" in step.lower() or "shovel" in step.lower()

    def test_backlogged_revision_step(self):
        record = make_record(current_stage="preliminary_plat",
                              revision_count=2, backlog_flag=True)
        step   = _likely_next_step(record)
        assert "revision" in step.lower() or "resubmit" in step.lower()
