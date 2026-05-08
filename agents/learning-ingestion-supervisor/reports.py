"""
Report generation for the Learning Ingestion Supervisor.

Produces four output documents per supervision run:

  VERIFIED_LEARNING.md         — sessions cleared for memory promotion
  INGESTION_FAILURES.md        — failed / quarantined sessions with diagnostics
  EXTRACTION_QUALITY_SCORE.json — machine-readable scores for all sessions
  LEARNING_RECOMMENDATIONS.md  — actionable guidance for improving ingestion
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inspectors import IngestionRecord
    from quality import QualityAssessment

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def generate_all(
    output_dir: Path,
    records: list["IngestionRecord"],
    assessments: dict[str, "QualityAssessment"],
    brain_dir: Path,
    run_timestamp: str,
) -> dict[str, Path]:
    """
    Write all four reports to output_dir.  Returns a mapping of report
    name → absolute path for logging / downstream use.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    by_verdict = _group_by_verdict(assessments)

    paths = {
        "VERIFIED_LEARNING.md": _write_verified(
            output_dir, records, assessments, by_verdict, run_timestamp
        ),
        "INGESTION_FAILURES.md": _write_failures(
            output_dir, records, assessments, by_verdict, run_timestamp
        ),
        "EXTRACTION_QUALITY_SCORE.json": _write_scores(
            output_dir, records, assessments, run_timestamp, brain_dir
        ),
        "LEARNING_RECOMMENDATIONS.md": _write_recommendations(
            output_dir, assessments, by_verdict, run_timestamp
        ),
    }

    log.info("Reports written to %s", output_dir)
    return paths


# ---------------------------------------------------------------------------
# VERIFIED_LEARNING.md
# ---------------------------------------------------------------------------


def _write_verified(
    output_dir: Path,
    records: list["IngestionRecord"],
    assessments: dict[str, "QualityAssessment"],
    by_verdict: dict[str, list[str]],
    run_timestamp: str,
) -> Path:
    promote_ids = by_verdict.get("PROMOTE", [])
    review_ids = by_verdict.get("REVIEW", [])

    rec_map = {r.session_id: r for r in records}

    lines: list[str] = [
        "# Verified Learning",
        "",
        f"_Generated: {run_timestamp}_",
        "",
        f"**{len(promote_ids)}** session(s) cleared for memory promotion  |  "
        f"**{len(review_ids)}** session(s) pending human review",
        "",
    ]

    if promote_ids:
        lines += ["## Promoted Sessions", ""]
        for sid in sorted(promote_ids):
            a = assessments[sid]
            r = rec_map.get(sid)
            lines.append(f"### {sid}")
            if r:
                lines.append(f"- **Title:** {r.video_title or '(unknown)'}")
                lines.append(f"- **URL:** {r.video_url or '(none)'}")
                lines.append(f"- **Source Agent:** {r.source_agent}")
            lines.append(f"- **Quality Score:** {a.overall_score}/100")
            lines.append(f"- **Transcript:** {a.transcript.score:.1f}/100")
            lines.append(f"- **Workflow:** {a.workflow.score:.1f}/100")
            lines.append(f"- **Notes:** {a.notes.score:.1f}/100")
            lines.append(f"- **Authenticity:** {a.authenticity.score:.1f}/100")
            lines.append("")

    if review_ids:
        lines += ["## Needs Human Review Before Promotion", ""]
        for sid in sorted(review_ids):
            a = assessments[sid]
            r = rec_map.get(sid)
            lines.append(f"### {sid}")
            if r:
                lines.append(f"- **Title:** {r.video_title or '(unknown)'}")
                lines.append(f"- **URL:** {r.video_url or '(none)'}")
            lines.append(f"- **Quality Score:** {a.overall_score}/100")
            all_issues = _flat_issues(a)
            if all_issues:
                lines.append("- **Issues:**")
                for issue in all_issues:
                    lines.append(f"  - {issue}")
            lines.append("")

    if not promote_ids and not review_ids:
        lines += ["_No sessions met the quality threshold in this run._", ""]

    path = output_dir / "VERIFIED_LEARNING.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", path)
    return path


# ---------------------------------------------------------------------------
# INGESTION_FAILURES.md
# ---------------------------------------------------------------------------


def _write_failures(
    output_dir: Path,
    records: list["IngestionRecord"],
    assessments: dict[str, "QualityAssessment"],
    by_verdict: dict[str, list[str]],
    run_timestamp: str,
) -> Path:
    failed_ids = by_verdict.get("FAILED", [])
    quarantined_ids = by_verdict.get("QUARANTINE", [])

    rec_map = {r.session_id: r for r in records}

    lines: list[str] = [
        "# Ingestion Failures",
        "",
        f"_Generated: {run_timestamp}_",
        "",
        f"**{len(failed_ids)}** extraction failure(s)  |  "
        f"**{len(quarantined_ids)}** session(s) quarantined",
        "",
    ]

    if failed_ids:
        lines += ["## Extraction Failures", "", "_These sessions have no usable source evidence._", ""]
        for sid in sorted(failed_ids):
            a = assessments[sid]
            r = rec_map.get(sid)
            lines.append(f"### {sid}")
            if r:
                lines.append(f"- **Title:** {r.video_title or '(unknown)'}")
                lines.append(f"- **URL:** {r.video_url or '(none)'}")
                lines.append(f"- **Source Agent:** {r.source_agent}")
            lines.append(f"- **Score:** {a.overall_score}/100")
            lines.append(f"- **Reason:** {a.verdict_reason}")
            issues = _flat_issues(a)
            if issues:
                lines.append("- **Diagnostic Issues:**")
                for issue in issues:
                    lines.append(f"  - {issue}")
            lines.append("")

    if quarantined_ids:
        lines += ["## Quarantined Sessions", "", "_Artifacts preserved; excluded from memory promotion._", ""]
        for sid in sorted(quarantined_ids):
            a = assessments[sid]
            r = rec_map.get(sid)
            lines.append(f"### {sid}")
            if r:
                lines.append(f"- **Title:** {r.video_title or '(unknown)'}")
                lines.append(f"- **URL:** {r.video_url or '(none)'}")
                if a.is_duplicate:
                    lines.append(f"- **Duplicate of:** {a.duplicate_of}")
            lines.append(f"- **Score:** {a.overall_score}/100")
            lines.append(f"- **Reason:** {a.verdict_reason}")
            issues = _flat_issues(a)
            if issues:
                lines.append("- **Issues:**")
                for issue in issues:
                    lines.append(f"  - {issue}")
            lines.append("")

    if not failed_ids and not quarantined_ids:
        lines += ["_No failures or quarantined sessions in this run._", ""]

    path = output_dir / "INGESTION_FAILURES.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", path)
    return path


# ---------------------------------------------------------------------------
# EXTRACTION_QUALITY_SCORE.json
# ---------------------------------------------------------------------------


def _write_scores(
    output_dir: Path,
    records: list["IngestionRecord"],
    assessments: dict[str, "QualityAssessment"],
    run_timestamp: str,
    brain_dir: Path,
) -> Path:
    rec_map = {r.session_id: r for r in records}

    by_verdict = _group_by_verdict(assessments)
    scored = [a.to_dict() for a in sorted(assessments.values(), key=lambda a: -a.overall_score)]

    summary = {
        "run_timestamp": run_timestamp,
        "brain_dir": str(brain_dir),
        "total_sessions": len(assessments),
        "verdicts": {
            "PROMOTE": len(by_verdict.get("PROMOTE", [])),
            "REVIEW": len(by_verdict.get("REVIEW", [])),
            "QUARANTINE": len(by_verdict.get("QUARANTINE", [])),
            "FAILED": len(by_verdict.get("FAILED", [])),
        },
        "average_overall_score": _avg([a.overall_score for a in assessments.values()]),
        "average_transcript_score": _avg([a.transcript.score for a in assessments.values()]),
        "average_workflow_score": _avg([a.workflow.score for a in assessments.values()]),
        "average_notes_score": _avg([a.notes.score for a in assessments.values()]),
    }

    payload = {"summary": summary, "sessions": scored}

    path = output_dir / "EXTRACTION_QUALITY_SCORE.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", path)
    return path


# ---------------------------------------------------------------------------
# LEARNING_RECOMMENDATIONS.md
# ---------------------------------------------------------------------------


def _write_recommendations(
    output_dir: Path,
    assessments: dict[str, "QualityAssessment"],
    by_verdict: dict[str, list[str]],
    run_timestamp: str,
) -> Path:
    lines: list[str] = [
        "# Learning Recommendations",
        "",
        f"_Generated: {run_timestamp}_",
        "",
        "Recommendations are derived from aggregated quality issues across all "
        "sessions in this run.  Address high-frequency issues first.",
        "",
    ]

    if not assessments:
        lines += ["_No sessions analysed — nothing to recommend._", ""]
        path = output_dir / "LEARNING_RECOMMENDATIONS.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # Aggregate issues by dimension
    issue_counts: dict[str, int] = {}
    for a in assessments.values():
        for dim in (a.transcript, a.workflow, a.notes, a.authenticity):
            for issue in dim.issues:
                key = f"[{dim.name}] {issue}"
                issue_counts[key] = issue_counts.get(key, 0) + 1

    # Verdict summary
    promote = len(by_verdict.get("PROMOTE", []))
    review = len(by_verdict.get("REVIEW", []))
    quarantine = len(by_verdict.get("QUARANTINE", []))
    failed = len(by_verdict.get("FAILED", []))
    total = len(assessments)

    lines += [
        "## Run Summary",
        "",
        f"| Verdict | Count | % |",
        f"|---------|-------|---|",
        f"| PROMOTE | {promote} | {_pct(promote, total)} |",
        f"| REVIEW | {review} | {_pct(review, total)} |",
        f"| QUARANTINE | {quarantine} | {_pct(quarantine, total)} |",
        f"| FAILED | {failed} | {_pct(failed, total)} |",
        f"| **Total** | **{total}** | |",
        "",
    ]

    if issue_counts:
        lines += ["## Top Issues (by frequency)", ""]
        top_issues = sorted(issue_counts.items(), key=lambda x: -x[1])[:15]
        for issue, count in top_issues:
            lines.append(f"- ({count}×) {issue}")
        lines.append("")

    # Transcript recommendations
    transcript_failures = sum(
        1 for a in assessments.values() if a.transcript.score < 40
    )
    if transcript_failures:
        lines += [
            "## Transcript Extraction",
            "",
            f"**{transcript_failures}/{total}** sessions have low transcript scores.",
            "",
            "Recommended actions:",
            "- Verify the video source is accessible and has captions/audio",
            "- Check the transcript extraction tool for rate limiting or format errors",
            "- Prefer videos with auto-generated captions as a fallback",
            "- Review universal-skill-learner logs for extraction errors",
            "",
        ]

    # Workflow recommendations
    workflow_failures = sum(
        1 for a in assessments.values() if a.workflow.score < 40
    )
    if workflow_failures:
        lines += [
            "## Workflow Quality",
            "",
            f"**{workflow_failures}/{total}** sessions have weak or missing workflows.",
            "",
            "Recommended actions:",
            "- Ensure the workflow extraction prompt requires ≥ 3 concrete, numbered steps",
            "- Reject workflows that contain vague steps ('do the thing', 'repeat', etc.)",
            "- Pass extracted workflows through the semantic-authenticity-gate before saving",
            "- Prefer ingesting tutorial/procedural content over commentary-only videos",
            "",
        ]

    # Duplicate recommendations
    duplicates = sum(1 for a in assessments.values() if a.is_duplicate)
    if duplicates:
        lines += [
            "## Duplicate Ingestions",
            "",
            f"**{duplicates}** duplicate session(s) detected.",
            "",
            "Recommended actions:",
            "- Add a URL deduplication check before triggering ingestion",
            "- Keep only the highest-scoring ingestion per video URL",
            "- Prune duplicate sessions from the memory store",
            "",
        ]

    # General quality bar reminder
    lines += [
        "## Quality Policy Reminder",
        "",
        "- **Prefer one high-quality ingestion over many weak ones**",
        "- Do not promote sessions with score < 70 without human review",
        "- All quarantined artifacts are preserved — re-ingest rather than fabricate",
        "- Authenticity gate must pass before workflow steps are treated as executable",
        "",
    ]

    path = output_dir / "LEARNING_RECOMMENDATIONS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", path)
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _group_by_verdict(
    assessments: dict[str, "QualityAssessment"],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for sid, a in assessments.items():
        groups.setdefault(a.verdict, []).append(sid)
    return groups


def _flat_issues(assessment: "QualityAssessment") -> list[str]:
    issues = []
    for dim in (
        assessment.transcript,
        assessment.workflow,
        assessment.notes,
        assessment.authenticity,
    ):
        for issue in dim.issues:
            issues.append(f"[{dim.name}] {issue}")
    return issues


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _pct(n: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{round(100 * n / total)}%"
