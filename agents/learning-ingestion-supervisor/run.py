"""
Learning Ingestion Supervisor Agent

Inspects outputs from the AI_BRAIN ingestion pipeline and gates memory promotion
based on evidence quality. Quarantines weak extractions, scores learning quality,
and produces diagnostic reports without fabricating content.

Inspects artifacts from:
  - universal-skill-learner
  - video-ingestion-orchestrator
  - cognitive-gym
  - semantic-authenticity-gate
  - memory-repair
"""

from __future__ import annotations

import json
import hashlib
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Thresholds and patterns
# ---------------------------------------------------------------------------

MIN_TRANSCRIPT_WORDS = 50
MIN_WORKFLOW_STEPS = 2
QUALITY_PASS_THRESHOLD = 0.65

# Patterns that indicate auto-generated or missing content, not real extraction
_PLACEHOLDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\[placeholder\]",
        r"\[insert\s+\w+(\s+\w+)*\s+here\]",
        r"lorem ipsum",
        r"\btodo:?\s",
        r"\bfixme\b",
        r"<transcript\s+unavailable>",
        r"\[auto.generated\s+summary\]",
        r"transcript\s+not\s+available",
        r"no\s+transcript\s+found",
        r"extraction\s+failed",
        r"\[summary\s+pending\]",
        r"placeholder\s+note",
    ]
]

# Weight breakdown for the 0.0–1.0 quality score
_W_TRANSCRIPT = 0.35
_W_NO_PLACEHOLDER = 0.20
_W_WORKFLOW = 0.20
_W_EXTERNAL = 0.15  # cognitive-gym + authenticity-gate combined
_W_EVIDENCE = 0.10


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class IngestionStatus(str, Enum):
    VERIFIED = "verified"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    PENDING_RERUN = "pending_rerun"


@dataclass
class QualitySignals:
    has_transcript: bool = False
    transcript_word_count: int = 0
    has_placeholder_content: bool = False
    placeholder_matches: list[str] = field(default_factory=list)
    workflow_step_count: int = 0
    has_executable_workflows: bool = False
    cognitive_gym_score: float | None = None
    authenticity_gate_passed: bool | None = None
    is_duplicate: bool = False
    duplicate_of: str | None = None
    source_evidence_preserved: bool = False


@dataclass
class IngestionRecord:
    ingestion_id: str
    title: str
    agent_source: str
    signals: QualitySignals = field(default_factory=QualitySignals)
    quality_score: float = 0.0
    status: IngestionStatus = IngestionStatus.PENDING_RERUN
    failure_reasons: list[str] = field(default_factory=list)
    source_url: str | None = None
    raw_path: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SupervisorReport:
    run_timestamp: str
    total_inspected: int
    verified: list[IngestionRecord]
    quarantined: list[IngestionRecord]
    failed: list[IngestionRecord]
    pending_rerun: list[IngestionRecord]
    overall_pass_rate: float
    recommendations: list[str]


# ---------------------------------------------------------------------------
# Signal extraction helpers
# ---------------------------------------------------------------------------


def _detect_placeholders(text: str) -> list[str]:
    """Return list of placeholder pattern matches found in text."""
    matches: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        for m in pattern.findall(text):
            matches.append(m if isinstance(m, str) else m[0])
    return matches


def _count_words(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _content_fingerprint(text: str) -> str:
    """Stable fingerprint of normalised text for duplicate detection."""
    normalised = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalised.encode()).hexdigest()


def _extract_signals(artifact: dict[str, Any]) -> QualitySignals:
    """
    Extract quality signals from a raw ingestion artifact dict.

    Expected top-level keys (all optional, gracefully missing):
      transcript          str
      notes               str | list[str]
      workflows           list[dict]  (each must have 'steps': list)
      cognitive_gym_score float       (0.0–1.0)
      authenticity_gate   bool | dict (True/False or {"passed": bool})
      source_url          str
      source_evidence     any         (presence is enough)
      duplicate_of        str         (ingestion_id of original)
    """
    sig = QualitySignals()

    # --- Transcript ---
    transcript: str = artifact.get("transcript", "") or ""
    sig.has_transcript = bool(transcript.strip())
    sig.transcript_word_count = _count_words(transcript)

    # --- Notes / summaries ---
    notes_raw = artifact.get("notes", "")
    if isinstance(notes_raw, list):
        notes_text = "\n".join(str(n) for n in notes_raw)
    else:
        notes_text = str(notes_raw) if notes_raw else ""

    # Check both transcript and notes for placeholders
    combined_text = f"{transcript}\n{notes_text}"
    sig.placeholder_matches = _detect_placeholders(combined_text)
    sig.has_placeholder_content = bool(sig.placeholder_matches)

    # --- Workflows ---
    workflows: list[dict] = artifact.get("workflows", []) or []
    total_steps = 0
    any_executable = False
    for wf in workflows:
        steps = wf.get("steps", []) or []
        total_steps += len(steps)
        if len(steps) >= MIN_WORKFLOW_STEPS:
            any_executable = True
    sig.workflow_step_count = total_steps
    sig.has_executable_workflows = any_executable

    # --- External scores ---
    gym_score = artifact.get("cognitive_gym_score")
    if gym_score is not None:
        try:
            sig.cognitive_gym_score = float(gym_score)
        except (TypeError, ValueError):
            pass

    auth_gate = artifact.get("authenticity_gate")
    if isinstance(auth_gate, bool):
        sig.authenticity_gate_passed = auth_gate
    elif isinstance(auth_gate, dict):
        sig.authenticity_gate_passed = bool(auth_gate.get("passed"))

    # --- Source evidence ---
    sig.source_evidence_preserved = bool(
        artifact.get("source_url") or artifact.get("source_evidence")
    )

    # --- Duplicate detection ---
    dup_of = artifact.get("duplicate_of")
    if dup_of:
        sig.is_duplicate = True
        sig.duplicate_of = str(dup_of)

    return sig


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score(sig: QualitySignals) -> float:
    """
    Compute a 0.0–1.0 quality score from extracted signals.

    The score is intentionally conservative — we'd rather quarantine a genuine
    ingestion than promote a fabricated one.
    """
    score = 0.0

    # Transcript quality (0–0.35)
    if sig.has_transcript:
        word_ratio = min(sig.transcript_word_count / MIN_TRANSCRIPT_WORDS, 1.0)
        score += _W_TRANSCRIPT * word_ratio

    # No placeholder content (0–0.20) — only awarded when there's actual content
    # to evaluate; an empty artifact cannot earn "clean content" credit.
    has_content = sig.has_transcript or sig.workflow_step_count > 0
    if has_content and not sig.has_placeholder_content:
        score += _W_NO_PLACEHOLDER

    # Workflow quality (0–0.20)
    if sig.has_executable_workflows:
        score += _W_WORKFLOW
    elif sig.workflow_step_count > 0:
        # Partial credit for any workflow content
        score += _W_WORKFLOW * 0.4

    # External signals (0–0.15 split between two gates)
    external = 0.0
    if sig.cognitive_gym_score is not None:
        external += sig.cognitive_gym_score * (_W_EXTERNAL / 2)
    if sig.authenticity_gate_passed is True:
        external += _W_EXTERNAL / 2
    elif sig.authenticity_gate_passed is False:
        # Hard veto — authenticity failure caps score below pass threshold
        external -= _W_EXTERNAL
    score += external

    # Source evidence (0–0.10)
    if sig.source_evidence_preserved:
        score += _W_EVIDENCE

    return max(0.0, min(1.0, round(score, 4)))


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _determine_status(
    sig: QualitySignals, score: float
) -> tuple[IngestionStatus, list[str]]:
    """
    Return (status, reasons) based on signals and score.

    Routing rules (applied in priority order):
    1. Duplicate → QUARANTINED
    2. Authenticity gate hard-failed → QUARANTINED
    3. Placeholder content present → QUARANTINED
    4. No transcript at all → FAILED (rerun candidate)
    5. Score below pass threshold → QUARANTINED
    6. Otherwise → VERIFIED
    """
    reasons: list[str] = []

    if sig.is_duplicate:
        reasons.append(f"duplicate of {sig.duplicate_of}")
        return IngestionStatus.QUARANTINED, reasons

    if sig.authenticity_gate_passed is False:
        reasons.append("authenticity gate rejected this ingestion")
        return IngestionStatus.QUARANTINED, reasons

    if sig.has_placeholder_content:
        reasons.append(
            f"placeholder content detected: {sig.placeholder_matches[:3]}"
        )
        return IngestionStatus.QUARANTINED, reasons

    if not sig.has_transcript:
        reasons.append("transcript extraction produced no content")
        return IngestionStatus.FAILED, reasons

    if sig.transcript_word_count < MIN_TRANSCRIPT_WORDS:
        reasons.append(
            f"transcript too short ({sig.transcript_word_count} words, "
            f"minimum {MIN_TRANSCRIPT_WORDS})"
        )

    if not sig.has_executable_workflows:
        reasons.append(
            f"no executable workflows found (steps across all workflows: "
            f"{sig.workflow_step_count})"
        )

    if score < QUALITY_PASS_THRESHOLD:
        reasons.append(
            f"quality score {score:.3f} below pass threshold "
            f"{QUALITY_PASS_THRESHOLD}"
        )
        return IngestionStatus.QUARANTINED, reasons

    # Passed all gates
    return IngestionStatus.VERIFIED, reasons


# ---------------------------------------------------------------------------
# Core supervisor
# ---------------------------------------------------------------------------


class LearningIngestionSupervisor:
    """
    Inspects a batch of ingestion artifacts and produces a supervision report.

    Usage:
        supervisor = LearningIngestionSupervisor(reports_dir=Path("reports"))
        report = supervisor.run(artifacts)
        supervisor.write_outputs(report)
    """

    def __init__(self, reports_dir: Path | None = None) -> None:
        self.reports_dir = reports_dir or (
            Path(__file__).parent / "reports"
        )
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Maps content fingerprint → ingestion_id for duplicate detection
        self._seen_fingerprints: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, artifacts: list[dict[str, Any]]) -> SupervisorReport:
        """
        Inspect a list of raw ingestion artifact dicts and return a report.

        Each artifact dict must contain at minimum:
            ingestion_id  str
            title         str
            agent_source  str  ("universal-skill-learner" | "video-ingestion-orchestrator" | …)

        All other fields are optional and scored if present.
        """
        self._seen_fingerprints.clear()

        records: list[IngestionRecord] = []
        for raw in artifacts:
            record = self._inspect_artifact(raw)
            records.append(record)

        verified = [r for r in records if r.status == IngestionStatus.VERIFIED]
        quarantined = [r for r in records if r.status == IngestionStatus.QUARANTINED]
        failed = [r for r in records if r.status == IngestionStatus.FAILED]
        pending = [r for r in records if r.status == IngestionStatus.PENDING_RERUN]

        pass_rate = len(verified) / len(records) if records else 0.0

        return SupervisorReport(
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            total_inspected=len(records),
            verified=verified,
            quarantined=quarantined,
            failed=failed,
            pending_rerun=pending,
            overall_pass_rate=round(pass_rate, 4),
            recommendations=self._build_recommendations(
                verified, quarantined, failed, pending
            ),
        )

    def write_outputs(self, report: SupervisorReport) -> None:
        """Write all four output documents to reports_dir."""
        self._write_verified_learning(report)
        self._write_ingestion_failures(report)
        self._write_extraction_quality_score(report)
        self._write_learning_recommendations(report)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def _inspect_artifact(self, raw: dict[str, Any]) -> IngestionRecord:
        ingestion_id: str = str(raw.get("ingestion_id", "unknown"))
        title: str = str(raw.get("title", "(untitled)"))
        agent_source: str = str(raw.get("agent_source", "unknown"))

        sig = _extract_signals(raw)

        # Cross-ingestion duplicate detection via transcript fingerprint
        transcript: str = raw.get("transcript", "") or ""
        if transcript.strip() and not sig.is_duplicate:
            fp = _content_fingerprint(transcript)
            if fp in self._seen_fingerprints:
                sig.is_duplicate = True
                sig.duplicate_of = self._seen_fingerprints[fp]
            else:
                self._seen_fingerprints[fp] = ingestion_id

        score = _score(sig)
        status, reasons = _determine_status(sig, score)

        return IngestionRecord(
            ingestion_id=ingestion_id,
            title=title,
            agent_source=agent_source,
            signals=sig,
            quality_score=score,
            status=status,
            failure_reasons=reasons,
            source_url=raw.get("source_url"),
            raw_path=raw.get("raw_path"),
        )

    # ------------------------------------------------------------------
    # Report writers
    # ------------------------------------------------------------------

    def _write_verified_learning(self, report: SupervisorReport) -> None:
        lines = [
            "# VERIFIED_LEARNING",
            "",
            f"_Generated: {report.run_timestamp}_",
            f"_Verified: {len(report.verified)} / {report.total_inspected}_",
            "",
        ]

        if not report.verified:
            lines.append(
                "> No ingestions reached verified status in this run.\n"
            )
        else:
            for r in report.verified:
                lines += [
                    f"## {r.title}",
                    "",
                    f"- **ID**: `{r.ingestion_id}`",
                    f"- **Source agent**: {r.agent_source}",
                    f"- **Quality score**: {r.quality_score:.3f}",
                    f"- **Transcript words**: {r.signals.transcript_word_count}",
                    f"- **Workflow steps**: {r.signals.workflow_step_count}",
                ]
                if r.source_url:
                    lines.append(f"- **Source URL**: {r.source_url}")
                if r.signals.cognitive_gym_score is not None:
                    lines.append(
                        f"- **Cognitive gym score**: "
                        f"{r.signals.cognitive_gym_score:.3f}"
                    )
                lines.append("")

        self._write(self.reports_dir / "VERIFIED_LEARNING.md", "\n".join(lines))

    def _write_ingestion_failures(self, report: SupervisorReport) -> None:
        problem_records = report.quarantined + report.failed

        lines = [
            "# INGESTION_FAILURES",
            "",
            f"_Generated: {report.run_timestamp}_",
            f"_Problems: {len(problem_records)} / {report.total_inspected}_",
            "",
        ]

        if not problem_records:
            lines.append("> No ingestion failures in this run.\n")
        else:
            for r in sorted(problem_records, key=lambda x: x.quality_score):
                lines += [
                    f"## {r.title}",
                    "",
                    f"- **ID**: `{r.ingestion_id}`",
                    f"- **Status**: `{r.status}`",
                    f"- **Quality score**: {r.quality_score:.3f}",
                    f"- **Agent**: {r.agent_source}",
                ]
                if r.failure_reasons:
                    lines.append("- **Reasons**:")
                    for reason in r.failure_reasons:
                        lines.append(f"  - {reason}")
                if r.signals.is_duplicate and r.signals.duplicate_of:
                    lines.append(
                        f"- **Duplicate of**: `{r.signals.duplicate_of}`"
                    )
                if r.signals.placeholder_matches:
                    lines.append(
                        f"- **Placeholders found**: "
                        f"`{r.signals.placeholder_matches[:5]}`"
                    )
                lines.append("")

        self._write(
            self.reports_dir / "INGESTION_FAILURES.md", "\n".join(lines)
        )

    def _write_extraction_quality_score(self, report: SupervisorReport) -> None:
        all_records = (
            report.verified
            + report.quarantined
            + report.failed
            + report.pending_rerun
        )
        scores = [r.quality_score for r in all_records]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        payload = {
            "run_timestamp": report.run_timestamp,
            "overall_pass_rate": report.overall_pass_rate,
            "average_quality_score": round(avg_score, 4),
            "threshold": QUALITY_PASS_THRESHOLD,
            "counts": {
                "total": report.total_inspected,
                "verified": len(report.verified),
                "quarantined": len(report.quarantined),
                "failed": len(report.failed),
                "pending_rerun": len(report.pending_rerun),
            },
            "per_ingestion": [
                {
                    "ingestion_id": r.ingestion_id,
                    "title": r.title,
                    "agent_source": r.agent_source,
                    "quality_score": r.quality_score,
                    "status": r.status,
                    "transcript_word_count": r.signals.transcript_word_count,
                    "workflow_step_count": r.signals.workflow_step_count,
                    "has_placeholder_content": r.signals.has_placeholder_content,
                    "is_duplicate": r.signals.is_duplicate,
                    "cognitive_gym_score": r.signals.cognitive_gym_score,
                    "authenticity_gate_passed": r.signals.authenticity_gate_passed,
                }
                for r in all_records
            ],
        }

        self._write(
            self.reports_dir / "EXTRACTION_QUALITY_SCORE.json",
            json.dumps(payload, indent=2),
        )

    def _write_learning_recommendations(
        self, report: SupervisorReport
    ) -> None:
        lines = [
            "# LEARNING_RECOMMENDATIONS",
            "",
            f"_Generated: {report.run_timestamp}_",
            "",
            "## Summary",
            "",
            f"- Pass rate: **{report.overall_pass_rate:.1%}** "
            f"({len(report.verified)}/{report.total_inspected} verified)",
            "",
            "## Recommendations",
            "",
        ]

        if report.recommendations:
            for rec in report.recommendations:
                lines.append(f"- {rec}")
        else:
            lines.append("- No recommendations at this time.")

        lines += [
            "",
            "## Quarantine actions required",
            "",
        ]

        if report.quarantined:
            lines.append(
                "The following ingestions require manual review before "
                "memory promotion:\n"
            )
            for r in report.quarantined:
                reasons_str = "; ".join(r.failure_reasons) or "see quality score"
                lines.append(
                    f"- `{r.ingestion_id}` — **{r.title}** "
                    f"(score {r.quality_score:.3f}): {reasons_str}"
                )
        else:
            lines.append("> No quarantined ingestions.\n")

        lines += [
            "",
            "## Rerun candidates",
            "",
        ]

        if report.failed:
            lines.append(
                "The following ingestions failed and should be re-queued:\n"
            )
            for r in report.failed:
                lines.append(
                    f"- `{r.ingestion_id}` — **{r.title}** "
                    f"(agent: {r.agent_source})"
                )
        else:
            lines.append("> No failed ingestions requiring rerun.\n")

        self._write(
            self.reports_dir / "LEARNING_RECOMMENDATIONS.md", "\n".join(lines)
        )

    # ------------------------------------------------------------------
    # Recommendation engine
    # ------------------------------------------------------------------

    def _build_recommendations(
        self,
        verified: list[IngestionRecord],
        quarantined: list[IngestionRecord],
        failed: list[IngestionRecord],
        pending: list[IngestionRecord],
    ) -> list[str]:
        recs: list[str] = []
        total = len(verified) + len(quarantined) + len(failed) + len(pending)
        if total == 0:
            return recs

        pass_rate = len(verified) / total

        if pass_rate < 0.5:
            recs.append(
                "Pass rate is below 50% — review upstream ingestion pipeline "
                "health before promoting any new memories."
            )

        placeholder_count = sum(
            1 for r in quarantined if r.signals.has_placeholder_content
        )
        if placeholder_count > 0:
            recs.append(
                f"{placeholder_count} ingestion(s) contain placeholder content — "
                "the transcript extractor or note generator may be producing "
                "stub outputs. Inspect universal-skill-learner logs."
            )

        duplicate_count = sum(
            1 for r in quarantined if r.signals.is_duplicate
        )
        if duplicate_count > 0:
            recs.append(
                f"{duplicate_count} duplicate ingestion(s) detected — "
                "prefer the highest-scoring original and discard duplicates."
            )

        no_transcript_count = sum(
            1 for r in failed if not r.signals.has_transcript
        )
        if no_transcript_count > 0:
            recs.append(
                f"{no_transcript_count} ingestion(s) produced no transcript — "
                "check video-ingestion-orchestrator for extraction errors and "
                "requeue with a forced extraction pass."
            )

        weak_wf_count = sum(
            1
            for r in quarantined
            if not r.signals.has_executable_workflows
            and r.signals.has_transcript
        )
        if weak_wf_count > 0:
            recs.append(
                f"{weak_wf_count} ingestion(s) have valid transcripts but no "
                "executable workflows — cognitive-gym may need re-scoring or "
                "the workflow extraction prompt needs tuning."
            )

        auth_failed_count = sum(
            1
            for r in quarantined
            if r.signals.authenticity_gate_passed is False
        )
        if auth_failed_count > 0:
            recs.append(
                f"{auth_failed_count} ingestion(s) failed the semantic "
                "authenticity gate — review semantic-authenticity-gate thresholds "
                "or source material quality."
            )

        if len(verified) >= 1:
            recs.append(
                f"{len(verified)} verified ingestion(s) are ready for memory "
                "promotion — run memory-repair on these to index them."
            )

        return recs

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _load_artifacts_from_path(path: Path) -> list[dict[str, Any]]:
    """
    Load ingestion artifacts from a JSON file or directory of JSON files.
    """
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))

    artifacts: list[dict[str, Any]] = []
    for json_file in sorted(path.glob("**/*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                artifacts.extend(data)
            elif isinstance(data, dict):
                artifacts.append(data)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Skipping malformed JSON {json_file}: {exc}", file=sys.stderr)
    return artifacts


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Learning Ingestion Supervisor — quality gate for AI_BRAIN ingestion pipeline"
    )
    parser.add_argument(
        "artifacts",
        nargs="?",
        help=(
            "Path to a JSON file containing a list of ingestion artifacts, "
            "or a directory tree of individual JSON artifacts. "
            "If omitted, reads from stdin."
        ),
    )
    parser.add_argument(
        "--reports-dir",
        default=None,
        help="Directory to write output reports (default: agents/learning-ingestion-supervisor/reports/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report summary to stdout without writing files.",
    )
    args = parser.parse_args(argv)

    # Load artifacts
    if args.artifacts:
        p = Path(args.artifacts)
        if not p.exists():
            print(f"[ERROR] Artifacts path not found: {p}", file=sys.stderr)
            return 1
        raw_artifacts = _load_artifacts_from_path(p)
    else:
        try:
            raw_artifacts = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Failed to parse JSON from stdin: {exc}", file=sys.stderr)
            return 1

    reports_dir = (
        Path(args.reports_dir)
        if args.reports_dir
        else Path(__file__).parent / "reports"
    )

    supervisor = LearningIngestionSupervisor(reports_dir=reports_dir)
    report = supervisor.run(raw_artifacts)

    # Always print summary to stdout
    print(f"\nLearning Ingestion Supervisor — {report.run_timestamp}")
    print(f"  Inspected : {report.total_inspected}")
    print(f"  Verified  : {len(report.verified)}")
    print(f"  Quarantined: {len(report.quarantined)}")
    print(f"  Failed    : {len(report.failed)}")
    print(f"  Pass rate : {report.overall_pass_rate:.1%}")
    if report.recommendations:
        print("\nRecommendations:")
        for rec in report.recommendations:
            print(f"  • {rec}")

    if not args.dry_run:
        supervisor.write_outputs(report)
        print(f"\nReports written to: {reports_dir}/")

    return 0 if report.overall_pass_rate > 0 or report.total_inspected == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
