"""
Quarantine management for the Learning Ingestion Supervisor.

Quarantine copies weak/failed ingestion artifacts into an isolated directory
so they are preserved (not deleted) while being excluded from memory promotion.
A quarantine log tracks every routed session with the reason and timestamp.

Quarantine directory layout
────────────────────────────
<brain_dir>/data/quarantine/
  <session_id>/
    _quarantine_reason.txt   human-readable reason
    transcript.txt           (copied if present)
    notes.md                 (copied if present)
    workflow.md              (copied if present)
    metadata.json            (copied if present)
  quarantine_log.jsonl       append-only log of all quarantine events
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from inspectors import IngestionRecord
from quality import QualityAssessment

log = logging.getLogger(__name__)

QUARANTINE_LOG_NAME = "quarantine_log.jsonl"


class QuarantineManager:
    def __init__(self, quarantine_dir: Path, dry_run: bool = False) -> None:
        self.quarantine_dir = quarantine_dir
        self.dry_run = dry_run
        self._events: list[dict] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def route(self, record: IngestionRecord, assessment: QualityAssessment) -> None:
        """
        Copy the record's artifacts into quarantine and append a log entry.
        Safe to call multiple times — subsequent calls for the same session_id
        will overwrite the quarantine slot (idempotent).
        """
        reason = assessment.verdict_reason
        issues = _all_issues(assessment)

        event = {
            "session_id": record.session_id,
            "quarantined_at": _now_iso(),
            "verdict": assessment.verdict,
            "overall_score": assessment.overall_score,
            "reason": reason,
            "issues": issues,
            "source_agent": record.source_agent,
            "video_url": record.video_url,
            "video_title": record.video_title,
        }
        self._events.append(event)

        if self.dry_run:
            log.info(
                "[DRY RUN] Would quarantine %s (score=%.1f, verdict=%s)",
                record.session_id,
                assessment.overall_score,
                assessment.verdict,
            )
            return

        slot = self.quarantine_dir / record.session_id
        slot.mkdir(parents=True, exist_ok=True)

        # Write reason file
        reason_text = (
            f"Session:  {record.session_id}\n"
            f"Verdict:  {assessment.verdict}\n"
            f"Score:    {assessment.overall_score}/100\n"
            f"Reason:   {reason}\n"
            f"Quarantined: {event['quarantined_at']}\n\n"
            "Issues:\n" + "\n".join(f"  - {i}" for i in issues)
        )
        (slot / "_quarantine_reason.txt").write_text(reason_text, encoding="utf-8")

        # Copy available artifacts (preserve source evidence — never delete originals)
        self._copy_artifact(record.transcript_path, slot / "transcript.txt")
        self._copy_artifact(record.notes_path, slot / "notes.md")
        self._copy_artifact(record.workflow_path, slot / "workflow.md")

        if record.raw_metadata:
            (slot / "metadata.json").write_text(
                json.dumps(record.raw_metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        log.info(
            "Quarantined %s → %s (score=%.1f)",
            record.session_id,
            slot,
            assessment.overall_score,
        )

    def flush_log(self) -> None:
        """Append all pending events to quarantine_log.jsonl."""
        if not self._events:
            return
        if self.dry_run:
            log.info("[DRY RUN] Would append %d event(s) to quarantine log", len(self._events))
            return

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.quarantine_dir / QUARANTINE_LOG_NAME
        with log_path.open("a", encoding="utf-8") as fh:
            for event in self._events:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")

        log.info("Quarantine log updated: %d new event(s) → %s", len(self._events), log_path)
        self._events.clear()

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _copy_artifact(src: Optional[Path], dst: Path) -> None:
        if src and src.exists():
            try:
                shutil.copy2(src, dst)
            except OSError as exc:
                log.warning("Could not copy %s → %s: %s", src, dst, exc)


# ------------------------------------------------------------------
# Rerun helpers
# ------------------------------------------------------------------


def build_rerun_manifest(
    failed_records: list[IngestionRecord],
    output_path: Path,
) -> None:
    """
    Write a JSON manifest of failed sessions that should be rerun.
    The manifest is intentionally minimal — it lists only what the
    upstream agents need to re-ingest, not internal supervisor state.
    """
    manifest = {
        "generated_at": _now_iso(),
        "failed_sessions": [
            {
                "session_id": r.session_id,
                "source_agent": r.source_agent,
                "video_url": r.video_url,
                "video_title": r.video_title,
                "ingested_at": r.ingested_at,
            }
            for r in failed_records
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Rerun manifest written: %s (%d session(s))", output_path, len(failed_records))


# ------------------------------------------------------------------
# Internal utilities
# ------------------------------------------------------------------


def _all_issues(assessment: QualityAssessment) -> list[str]:
    issues: list[str] = []
    for dim in (
        assessment.transcript,
        assessment.workflow,
        assessment.notes,
        assessment.authenticity,
    ):
        for issue in dim.issues:
            issues.append(f"[{dim.name}] {issue}")
    return issues


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
