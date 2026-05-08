"""
Learning Ingestion Supervisor — core orchestration.

Responsibilities
────────────────
1.  Collect ingestion records from all source agents
2.  Enrich records with cognitive-gym, SAG, and memory-repair data
3.  Detect duplicate video URLs
4.  Score each record across transcript / workflow / notes / authenticity
5.  Route weak/failed records to quarantine
6.  Optionally trigger reruns for failed jobs
7.  Produce all four output reports
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from inspectors import (
    CognitiveGymInspector,
    IngestionRecord,
    MemoryRepairInspector,
    SemanticAuthenticityGateInspector,
    UniversalSkillLearnerInspector,
    VideoIngestionOrchestratorInspector,
    detect_duplicates,
)
from quality import (
    QualityAssessment,
    VERDICT_FAILED,
    VERDICT_QUARANTINE,
    compute_overall,
    score_authenticity,
    score_notes,
    score_transcript,
    score_workflow,
)
from quarantine import QuarantineManager, build_rerun_manifest
from reports import generate_all

log = logging.getLogger(__name__)


class LearningIngestionSupervisor:
    """
    Orchestrates a full supervision run over the AI Brain ingestion pipeline.

    Parameters
    ----------
    brain_dir:         Root of the AI Brain directory tree.
    output_dir:        Where supervisor reports are written.
    min_quality_score: Sessions below this score are quarantined (default 60).
                       Must be >= REVIEW_THRESHOLD (40) from quality.py.
    dry_run:           If True, no files are written outside output_dir.
    """

    def __init__(
        self,
        brain_dir: Path,
        output_dir: Path,
        min_quality_score: float = 60.0,
        dry_run: bool = False,
    ) -> None:
        self.brain_dir = brain_dir
        self.output_dir = output_dir
        self.min_quality_score = max(0.0, min(100.0, min_quality_score))
        self.dry_run = dry_run

        quarantine_dir = brain_dir / "data" / "quarantine"
        self.quarantine = QuarantineManager(quarantine_dir, dry_run=dry_run)

        # Populated during run()
        self.records: list[IngestionRecord] = []
        self.assessments: dict[str, QualityAssessment] = {}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, rerun_failed: bool = False) -> int:
        """
        Execute a full supervision run.

        Returns 0 on success (even if some sessions are quarantined).
        Returns 1 if a hard error prevents the run from completing.
        """
        run_ts = _now_iso()
        log.info("=== Learning Ingestion Supervisor starting — %s ===", run_ts)
        log.info("Brain dir:  %s", self.brain_dir)
        log.info("Output dir: %s", self.output_dir)
        log.info("Dry run:    %s", self.dry_run)

        try:
            # 1. Collect
            self.records = self._collect_records()
            if not self.records:
                log.warning("No ingestion records found — nothing to supervise")

            # 2. Enrich
            self._enrich_records()

            # 3. Detect duplicates
            duplicate_map = detect_duplicates(self.records)

            # 4. Score
            self.assessments = self._score_all(duplicate_map)

            # 5. Route quarantine
            self._route_quarantine()
            self.quarantine.flush_log()

            # 6. Optional rerun
            if rerun_failed:
                self._trigger_reruns()

            # 7. Reports
            written = generate_all(
                output_dir=self.output_dir,
                records=self.records,
                assessments=self.assessments,
                brain_dir=self.brain_dir,
                run_timestamp=run_ts,
            )

            self._print_summary(written)
            return 0

        except Exception:
            log.exception("Supervisor run failed with unhandled exception")
            return 1

    # ------------------------------------------------------------------
    # Step 1 — collect
    # ------------------------------------------------------------------

    def _collect_records(self) -> list[IngestionRecord]:
        collectors = [
            UniversalSkillLearnerInspector(self.brain_dir),
            VideoIngestionOrchestratorInspector(self.brain_dir),
        ]
        all_records: list[IngestionRecord] = []
        seen: set[str] = set()

        for collector in collectors:
            for record in collector.collect():
                if record.session_id in seen:
                    log.debug("Skipping duplicate session_id from %s: %s", collector.__class__.__name__, record.session_id)
                    continue
                seen.add(record.session_id)
                all_records.append(record)

        log.info("Collected %d unique ingestion record(s)", len(all_records))
        return all_records

    # ------------------------------------------------------------------
    # Step 2 — enrich
    # ------------------------------------------------------------------

    def _enrich_records(self) -> None:
        cg_scores = CognitiveGymInspector(self.brain_dir).load_scores()
        sag_results = SemanticAuthenticityGateInspector(self.brain_dir).load_results()
        mr_results = MemoryRepairInspector(self.brain_dir).load_results()

        for record in self.records:
            sid = record.session_id
            if sid in cg_scores:
                record.cognitive_gym_score = cg_scores[sid]
                log.debug("Enriched %s with CognitiveGym score", sid)
            if sid in sag_results:
                record.authenticity_result = sag_results[sid]
                log.debug("Enriched %s with SAG result", sid)
            if sid in mr_results:
                record.memory_repair_result = mr_results[sid]
                log.debug("Enriched %s with MemoryRepair result", sid)

    # ------------------------------------------------------------------
    # Step 3+4 — score
    # ------------------------------------------------------------------

    def _score_all(
        self, duplicate_map: dict[str, str]
    ) -> dict[str, QualityAssessment]:
        assessments: dict[str, QualityAssessment] = {}

        for record in self.records:
            is_dup = record.session_id in duplicate_map
            dup_of: Optional[str] = duplicate_map.get(record.session_id)

            t_score = score_transcript(record.transcript_path)
            w_score = score_workflow(record.workflow_path)
            n_score = score_notes(record.notes_path)
            a_score = score_authenticity(record.authenticity_result)

            assessment = compute_overall(
                session_id=record.session_id,
                transcript=t_score,
                workflow=w_score,
                notes=n_score,
                authenticity=a_score,
                is_duplicate=is_dup,
                duplicate_of=dup_of,
            )

            # Apply caller-configured minimum quality override
            if (
                assessment.verdict not in (VERDICT_FAILED,)
                and assessment.overall_score < self.min_quality_score
                and assessment.verdict not in (VERDICT_QUARANTINE,)
            ):
                assessment.verdict = VERDICT_QUARANTINE
                assessment.verdict_reason = (
                    f"Score {assessment.overall_score}/100 below configured "
                    f"minimum ({self.min_quality_score})"
                )

            assessments[record.session_id] = assessment
            log.debug(
                "Scored %s: %.1f/100 → %s",
                record.session_id,
                assessment.overall_score,
                assessment.verdict,
            )

        log.info(
            "Scored %d session(s). Verdicts: %s",
            len(assessments),
            _verdict_summary(assessments),
        )
        return assessments

    # ------------------------------------------------------------------
    # Step 5 — quarantine
    # ------------------------------------------------------------------

    def _route_quarantine(self) -> None:
        rec_map = {r.session_id: r for r in self.records}
        routed = 0

        for sid, assessment in self.assessments.items():
            if assessment.verdict in (VERDICT_QUARANTINE, VERDICT_FAILED):
                record = rec_map.get(sid)
                if record:
                    self.quarantine.route(record, assessment)
                    routed += 1

        log.info("Quarantined %d session(s)", routed)

    # ------------------------------------------------------------------
    # Step 6 — rerun failed jobs
    # ------------------------------------------------------------------

    def _trigger_reruns(self) -> None:
        failed_records = [
            r
            for r in self.records
            if self.assessments.get(r.session_id) and
               self.assessments[r.session_id].verdict == VERDICT_FAILED
        ]

        if not failed_records:
            log.info("No FAILED sessions to rerun")
            return

        manifest_path = self.output_dir / "rerun_manifest.json"
        if not self.dry_run:
            build_rerun_manifest(failed_records, manifest_path)
            log.info(
                "Rerun manifest written for %d session(s): %s",
                len(failed_records),
                manifest_path,
            )
        else:
            log.info(
                "[DRY RUN] Would write rerun manifest for %d session(s)",
                len(failed_records),
            )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(self, written: dict[str, Path]) -> None:
        summary = _verdict_summary(self.assessments)
        print("\n─── Learning Ingestion Supervisor — Run Complete ───")
        print(f"  Brain dir:    {self.brain_dir}")
        print(f"  Sessions:     {len(self.records)}")
        for verdict, count in sorted(summary.items()):
            print(f"  {verdict:<12} {count}")
        print(f"\n  Reports:")
        for name, path in written.items():
            print(f"    {name}: {path}")
        print("────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verdict_summary(assessments: dict[str, QualityAssessment]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in assessments.values():
        counts[a.verdict] = counts.get(a.verdict, 0) + 1
    return counts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Configure logging when used as a library
# ---------------------------------------------------------------------------


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )
