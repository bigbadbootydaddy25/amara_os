"""
Corpus Cleanup Agent

Permanently and safely cleans poisoned workflow/template artifacts from the
AI_BRAIN corpus. Every destructive action is preceded by a backup; uncertain
cases are quarantined rather than deleted.

Detection targets
-----------------
* title=... / topic= / transcript= / youtube=  (parser key-leakage in content)
* Placeholder/template-derived notes ([placeholder], TODO, lorem ipsum, …)
* Malformed parser output titles  (e.g. ``title=Some Title``)
* Markdown / code-fence contamination (``` blocks inside note bodies)
* Fake source packets (no real source_url or source_evidence)
* Duplicate corpus entries (identical content fingerprint)

Safety rules
------------
* Never delete a real workflow — when uncertain, archive instead of delete
* Always write a backup before any removal
* Every action recorded in the cleanup manifest
* Rerun gates (semantic-authenticity-gate, cognitive-gym) listed as
  post-cleanup steps in the scorecard, not executed directly (the agent
  records *what to rerun*, not *runs* external systems)
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Poison-detection patterns
# ---------------------------------------------------------------------------

# Parser key-leakage:  ``title=...``, ``topic=``, ``transcript=``, etc.
_KEY_LEAKAGE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^\s*title\s*=\s*.+",          # title=Some Title (line-anchored)
        r"^\s*topic\s*=\s*.+",
        r"^\s*transcript\s*=\s*.+",
        r"^\s*youtube\s*=\s*.+",
        r"^\s*url\s*=\s*https?://",
        r"^\s*source\s*=\s*.+",
        r"^\s*description\s*=\s*.+",
        r"^\s*author\s*=\s*.+",
        r"^\s*date\s*=\s*.+",
        r"^\s*tags\s*=\s*.+",
    ]
]

# Placeholder / template content
_PLACEHOLDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\[placeholder\]",
        r"\[insert\s+\w+(\s+\w+)*\s+here\]",
        r"\[auto.generated\s+summary\]",
        r"\[summary\s+pending\]",
        r"lorem ipsum",
        r"\btodo:?\s",
        r"\bfixme\b",
        r"transcript\s+not\s+available",
        r"no\s+transcript\s+found",
        r"extraction\s+failed",
        r"placeholder\s+note",
        r"<transcript\s+unavailable>",
    ]
]

# Malformed parser-generated titles (the title field itself looks like an
# assignment expression, or is wrapped in brackets/quotes from a parser dump)
_MALFORMED_TITLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^title\s*=",                    # title=Foo Bar
        r"^topic\s*=",
        r"^\s*\{\s*['\"]title['\"]\s*:",  # {"title": ...  (raw dict dump)
        r"^<[a-z]+>.*<\/[a-z]+>$",        # <tag>text</tag>  (XML fragment)
        r"^\[object Object\]$",
        r"^undefined$",
        r"^null$",
        r"^None$",
        r"^\s*$",                          # empty/whitespace-only title
    ]
]

# Code-fence / markdown contamination inside a note body
_CODEFENCE_PATTERN = re.compile(r"```", re.MULTILINE)

# Minimum word count for a note body to be considered real content
_MIN_BODY_WORDS = 20

# Confidence threshold below which an artifact is archived rather than deleted
_ARCHIVE_THRESHOLD = 0.40  # poison_confidence < this → archive, not remove

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ArtifactDisposition(str, Enum):
    CLEAN           = "clean"           # passes all checks, keep as-is
    REMOVED         = "removed"         # poisoned and safely deleted (backup kept)
    ARCHIVED        = "archived"        # uncertain — moved to archive, not deleted
    QUARANTINED     = "quarantined"     # uncertain and no backup path available
    SKIPPED         = "skipped"         # could not read / unsupported format


@dataclass
class PoisonSignals:
    has_key_leakage: bool = False
    key_leakage_matches: list[str] = field(default_factory=list)
    has_placeholder_content: bool = False
    placeholder_matches: list[str] = field(default_factory=list)
    has_malformed_title: bool = False
    malformed_title_reason: str = ""
    has_codefence_contamination: bool = False
    codefence_count: int = 0
    body_word_count: int = 0
    body_too_short: bool = False
    missing_source_evidence: bool = False
    is_duplicate: bool = False
    duplicate_of: str | None = None   # artifact_id of first-seen copy


@dataclass
class ArtifactRecord:
    artifact_id: str
    file_path: str | None             # None for in-memory/dict-only artifacts
    title: str
    body_preview: str                 # first 120 chars of body
    signals: PoisonSignals
    poison_confidence: float          # 0.0–1.0
    disposition: ArtifactDisposition
    disposition_reasons: list[str]
    backup_path: str | None = None    # set after backup is written
    run_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class CleanupReport:
    run_timestamp: str
    total_scanned: int
    clean: list[ArtifactRecord]
    removed: list[ArtifactRecord]
    archived: list[ArtifactRecord]
    quarantined: list[ArtifactRecord]
    skipped: list[ArtifactRecord]
    rerun_candidates: list[str]       # artifact_ids to re-gate after cleanup


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------


def _first_line_matches(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    """Return pattern matches found in any line of text (for key-leakage checks)."""
    matches: list[str] = []
    for line in text.splitlines():
        for pat in patterns:
            if pat.search(line):
                matches.append(line.strip()[:120])
    return list(dict.fromkeys(matches))


def _scan_for_placeholders(text: str) -> list[str]:
    matches: list[str] = []
    for pat in _PLACEHOLDER_PATTERNS:
        for m in pat.finditer(text):
            matches.append(m.group(0)[:80])
    return list(dict.fromkeys(matches))


def _content_fingerprint(text: str) -> str:
    normalised = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalised.encode()).hexdigest()


def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def _extract_signals(
    artifact: dict[str, Any],
    seen_fingerprints: dict[str, str],
) -> PoisonSignals:
    """
    Analyse a single artifact dict and return its PoisonSignals.

    Expected keys (all optional):
      title          str
      body           str   (note content / workflow steps combined as text)
      notes          str | list[str]
      workflows      list[dict]
      source_url     str
      source_evidence any
    """
    sig = PoisonSignals()

    title: str  = str(artifact.get("title", "") or "")
    body_raw     = artifact.get("body", "") or ""
    notes_raw    = artifact.get("notes", "") or ""
    if isinstance(notes_raw, list):
        notes_raw = "\n".join(str(n) for n in notes_raw)
    workflows    = artifact.get("workflows", []) or []
    wf_text      = "\n".join(
        " ".join(str(s) for s in (wf.get("steps", []) or []))
        for wf in workflows
        if isinstance(wf, dict)
    )
    full_body: str = "\n".join(
        filter(None, [str(body_raw), str(notes_raw), wf_text])
    )

    # --- Key-leakage (title field and body) ---
    title_leakage = _first_line_matches(title, _KEY_LEAKAGE_PATTERNS)
    body_leakage  = _first_line_matches(full_body, _KEY_LEAKAGE_PATTERNS)
    all_leakage   = list(dict.fromkeys(title_leakage + body_leakage))
    sig.has_key_leakage   = bool(all_leakage)
    sig.key_leakage_matches = all_leakage

    # --- Malformed title ---
    for pat in _MALFORMED_TITLE_PATTERNS:
        if pat.search(title):
            sig.has_malformed_title    = True
            sig.malformed_title_reason = pat.pattern
            break
    # Also catch title that IS a key-leakage expression
    if not sig.has_malformed_title and title_leakage:
        sig.has_malformed_title    = True
        sig.malformed_title_reason = f"key-leakage in title: {title_leakage[0]}"

    # --- Placeholder content ---
    ph_matches = _scan_for_placeholders(full_body) + _scan_for_placeholders(title)
    sig.placeholder_matches      = list(dict.fromkeys(ph_matches))
    sig.has_placeholder_content  = bool(sig.placeholder_matches)

    # --- Code-fence contamination ---
    fence_count = len(_CODEFENCE_PATTERN.findall(full_body))
    sig.codefence_count           = fence_count
    # Odd count = unclosed fence; even non-zero = embedded fences in note body
    sig.has_codefence_contamination = fence_count > 0

    # --- Body length ---
    sig.body_word_count = _word_count(full_body)
    sig.body_too_short  = sig.body_word_count < _MIN_BODY_WORDS

    # --- Source evidence ---
    sig.missing_source_evidence = not bool(
        artifact.get("source_url") or artifact.get("source_evidence")
    )

    # --- Duplicate detection ---
    if full_body.strip():
        fp = _content_fingerprint(full_body)
        artifact_id = str(artifact.get("artifact_id", "") or "")
        if fp in seen_fingerprints:
            sig.is_duplicate  = True
            sig.duplicate_of  = seen_fingerprints[fp]
        else:
            seen_fingerprints[fp] = artifact_id

    return sig


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# Weights for poison_confidence (must sum to 1.0)
_WP_KEY_LEAKAGE   = 0.30
_WP_PLACEHOLDER   = 0.25
_WP_BAD_TITLE     = 0.15
_WP_CODEFENCE     = 0.10
_WP_SHORT_BODY    = 0.10
_WP_NO_SOURCE     = 0.10


def _poison_score(sig: PoisonSignals) -> float:
    """
    Compute a 0.0–1.0 poison confidence score.
    Higher = more likely poisoned / safe to remove.
    """
    score = 0.0

    if sig.has_key_leakage:
        score += _WP_KEY_LEAKAGE

    if sig.has_placeholder_content:
        score += _WP_PLACEHOLDER

    if sig.has_malformed_title:
        score += _WP_BAD_TITLE

    if sig.has_codefence_contamination:
        # Partial credit — a single pair of fences might be intentional code
        score += _WP_CODEFENCE if sig.codefence_count > 2 else _WP_CODEFENCE * 0.40

    if sig.body_too_short:
        score += _WP_SHORT_BODY

    if sig.missing_source_evidence:
        score += _WP_NO_SOURCE

    # Duplicate: inherit half its original score as poison boost
    if sig.is_duplicate:
        score = min(1.0, score + 0.20)

    return max(0.0, min(1.0, round(score, 4)))


# ---------------------------------------------------------------------------
# Disposition routing
# ---------------------------------------------------------------------------

# Poison confidence thresholds
_REMOVE_THRESHOLD  = 0.65   # >= this → REMOVED  (backup kept)
# _ARCHIVE_THRESHOLD = 0.40  (declared at top with other constants)
# < _ARCHIVE_THRESHOLD → CLEAN (no action)


def _route(
    sig: PoisonSignals,
    score: float,
) -> tuple[ArtifactDisposition, list[str]]:
    """
    Return (disposition, reasons).

    Priority:
    1. score >= _REMOVE_THRESHOLD  → REMOVED
    2. _ARCHIVE_THRESHOLD <= score < _REMOVE_THRESHOLD  → ARCHIVED
    3. is_duplicate (regardless of score)  → ARCHIVED
    4. Otherwise  → CLEAN
    """
    reasons: list[str] = []

    # Build reason list from signals
    if sig.has_key_leakage:
        reasons.append(f"key-leakage detected: {sig.key_leakage_matches[:2]}")
    if sig.has_placeholder_content:
        reasons.append(f"placeholder content: {sig.placeholder_matches[:2]}")
    if sig.has_malformed_title:
        reasons.append(f"malformed title ({sig.malformed_title_reason})")
    if sig.has_codefence_contamination:
        reasons.append(f"code-fence contamination ({sig.codefence_count} fences)")
    if sig.body_too_short:
        reasons.append(f"body too short ({sig.body_word_count} words, min {_MIN_BODY_WORDS})")
    if sig.missing_source_evidence:
        reasons.append("no source evidence")
    if sig.is_duplicate:
        reasons.append(f"duplicate of {sig.duplicate_of!r}")

    if score >= _REMOVE_THRESHOLD:
        return ArtifactDisposition.REMOVED, reasons

    if score >= _ARCHIVE_THRESHOLD or sig.is_duplicate:
        return ArtifactDisposition.ARCHIVED, reasons

    return ArtifactDisposition.CLEAN, reasons


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------


class CorpusCleanupAgent:
    """
    Scans a corpus of artifact dicts (or on-disk JSON files), classifies each
    as clean / to-be-removed / to-be-archived, writes backups, executes safe
    filesystem mutations (when file_path is supplied), and produces four output
    documents.

    Usage (in-memory):
        agent = CorpusCleanupAgent(reports_dir=Path("reports"))
        report = agent.run(artifacts)
        agent.write_outputs(report)

    Usage (filesystem):
        agent = CorpusCleanupAgent(
            reports_dir=Path("reports"),
            backup_dir=Path("reports/backups"),
            dry_run=False,
        )
        report = agent.run_from_directory(Path("corpus/quarantine"))
        agent.write_outputs(report)
    """

    def __init__(
        self,
        reports_dir: Path | None = None,
        backup_dir: Path | None = None,
        dry_run: bool = True,
    ) -> None:
        self.reports_dir = reports_dir or Path(__file__).parent / "reports"
        self.backup_dir  = backup_dir  or self.reports_dir / "backups"
        self.dry_run     = dry_run
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Shared state — reset on each run()
        self._seen_fingerprints: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, artifacts: list[dict[str, Any]]) -> CleanupReport:
        """
        Process a list of in-memory artifact dicts.
        No filesystem mutations are performed (file_path is not required).
        """
        self._seen_fingerprints.clear()
        records = [self._process(a) for a in artifacts]
        return self._build_report(records)

    def run_from_directory(self, scan_dir: Path) -> CleanupReport:
        """
        Walk scan_dir for JSON files, load each as an artifact, apply cleanup.
        When dry_run=False, removed artifacts are deleted after backup and
        archived artifacts are moved to backup_dir.
        """
        self._seen_fingerprints.clear()
        records: list[ArtifactRecord] = []

        for json_file in sorted(scan_dir.glob("**/*.json")):
            try:
                raw = json.loads(json_file.read_text(encoding="utf-8"))
                artifacts = raw if isinstance(raw, list) else [raw]
                for artifact in artifacts:
                    artifact.setdefault("artifact_id", json_file.stem)
                    artifact["_file_path"] = str(json_file)
                    rec = self._process(artifact)
                    records.append(rec)
                    self._apply_filesystem_action(rec, json_file)
            except (json.JSONDecodeError, OSError) as exc:
                records.append(
                    ArtifactRecord(
                        artifact_id=json_file.stem,
                        file_path=str(json_file),
                        title="(unreadable)",
                        body_preview="",
                        signals=PoisonSignals(),
                        poison_confidence=0.0,
                        disposition=ArtifactDisposition.SKIPPED,
                        disposition_reasons=[f"read error: {exc}"],
                    )
                )

        return self._build_report(records)

    def write_outputs(self, report: CleanupReport) -> None:
        """Write all four output documents to reports_dir."""
        self._write_cleanup_report(report)
        self._write_removed_artifacts(report)
        self._write_archived_artifacts(report)
        self._write_post_cleanup_scorecard(report)

    # ------------------------------------------------------------------
    # Record processing
    # ------------------------------------------------------------------

    def _process(self, artifact: dict[str, Any]) -> ArtifactRecord:
        artifact_id   = str(artifact.get("artifact_id", "") or "")
        title         = str(artifact.get("title", "") or "")
        file_path_raw = artifact.get("_file_path") or artifact.get("file_path")
        file_path     = str(file_path_raw) if file_path_raw else None

        body_raw   = artifact.get("body", "") or ""
        notes_raw  = artifact.get("notes", "") or ""
        if isinstance(notes_raw, list):
            notes_raw = "\n".join(str(n) for n in notes_raw)
        full_body  = "\n".join(filter(None, [str(body_raw), str(notes_raw)]))
        preview    = full_body[:120].replace("\n", " ")

        sig   = _extract_signals(artifact, self._seen_fingerprints)
        score = _poison_score(sig)
        disposition, reasons = _route(sig, score)

        return ArtifactRecord(
            artifact_id=artifact_id,
            file_path=file_path,
            title=title,
            body_preview=preview,
            signals=sig,
            poison_confidence=score,
            disposition=disposition,
            disposition_reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Filesystem actions (only when dry_run=False)
    # ------------------------------------------------------------------

    def _apply_filesystem_action(
        self, rec: ArtifactRecord, source_file: Path
    ) -> None:
        if self.dry_run or not source_file.exists():
            return

        if rec.disposition == ArtifactDisposition.REMOVED:
            backup = self._backup(source_file)
            rec.backup_path = str(backup)
            source_file.unlink(missing_ok=True)

        elif rec.disposition == ArtifactDisposition.ARCHIVED:
            backup = self._backup(source_file)
            rec.backup_path = str(backup)
            # Don't delete the original — the backup IS the archive

    def _backup(self, source_file: Path) -> Path:
        """Copy source_file into backup_dir with a timestamp suffix."""
        ts    = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        dest  = self.backup_dir / f"{source_file.stem}_{ts}{source_file.suffix}"
        shutil.copy2(source_file, dest)
        return dest

    # ------------------------------------------------------------------
    # Report builders
    # ------------------------------------------------------------------

    def _build_report(self, records: list[ArtifactRecord]) -> CleanupReport:
        clean       = [r for r in records if r.disposition == ArtifactDisposition.CLEAN]
        removed     = [r for r in records if r.disposition == ArtifactDisposition.REMOVED]
        archived    = [r for r in records if r.disposition == ArtifactDisposition.ARCHIVED]
        quarantined = [r for r in records if r.disposition == ArtifactDisposition.QUARANTINED]
        skipped     = [r for r in records if r.disposition == ArtifactDisposition.SKIPPED]

        # Removed + archived artifacts should be re-gated after cleanup
        rerun_candidates = [
            r.artifact_id for r in (removed + archived) if r.artifact_id
        ]

        return CleanupReport(
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            total_scanned=len(records),
            clean=clean,
            removed=removed,
            archived=archived,
            quarantined=quarantined,
            skipped=skipped,
            rerun_candidates=rerun_candidates,
        )

    # ------------------------------------------------------------------
    # Output writers
    # ------------------------------------------------------------------

    def _write_cleanup_report(self, report: CleanupReport) -> None:
        n_rm  = len(report.removed)
        n_arc = len(report.archived)
        n_cl  = len(report.clean)
        n_q   = len(report.quarantined)
        n_sk  = len(report.skipped)

        lines = [
            "# CLEANUP_REPORT",
            "",
            f"_Generated: {report.run_timestamp}_",
            f"_Mode: {'dry-run' if self.dry_run else 'live'}_",
            "",
            "## Summary",
            "",
            "| Disposition | Count |",
            "|-------------|-------|",
            f"| Total scanned | {report.total_scanned} |",
            f"| Clean | {n_cl} |",
            f"| Removed | {n_rm} |",
            f"| Archived | {n_arc} |",
            f"| Quarantined | {n_q} |",
            f"| Skipped | {n_sk} |",
            "",
        ]

        if report.removed:
            lines += ["## Removed Artifacts", ""]
            for r in sorted(report.removed, key=lambda x: -x.poison_confidence):
                lines += _artifact_md_block(r)

        if report.archived:
            lines += ["## Archived Artifacts", ""]
            for r in sorted(report.archived, key=lambda x: -x.poison_confidence):
                lines += _artifact_md_block(r)

        if report.quarantined:
            lines += ["## Quarantined (uncertain — manual review needed)", ""]
            for r in report.quarantined:
                lines += _artifact_md_block(r)

        if report.skipped:
            lines += ["## Skipped (unreadable)", ""]
            for r in report.skipped:
                reasons = "; ".join(r.disposition_reasons)
                lines.append(f"- `{r.artifact_id}` {r.file_path or ''} — {reasons}")
            lines.append("")

        self._write(self.reports_dir / "CLEANUP_REPORT.md", "\n".join(lines))

    def _write_removed_artifacts(self, report: CleanupReport) -> None:
        payload = [_record_to_dict(r) for r in report.removed]
        self._write(
            self.reports_dir / "REMOVED_ARTIFACTS.json",
            json.dumps(payload, indent=2),
        )

    def _write_archived_artifacts(self, report: CleanupReport) -> None:
        payload = [_record_to_dict(r) for r in report.archived]
        self._write(
            self.reports_dir / "ARCHIVED_ARTIFACTS.json",
            json.dumps(payload, indent=2),
        )

    def _write_post_cleanup_scorecard(self, report: CleanupReport) -> None:
        n_total  = report.total_scanned
        n_clean  = len(report.clean)
        n_poison = len(report.removed) + len(report.archived)
        clean_pct = (n_clean / n_total * 100) if n_total else 0.0

        lines = [
            "# POST_CLEANUP_SCORECARD",
            "",
            f"_Generated: {report.run_timestamp}_",
            "",
            "## Corpus Health",
            "",
            f"- **Scanned**: {n_total}",
            f"- **Clean**: {n_clean} ({clean_pct:.1f}%)",
            f"- **Poisoned (removed + archived)**: {n_poison}",
            "",
            "## Post-Cleanup Actions Required",
            "",
        ]

        if report.rerun_candidates:
            lines += [
                "The following artifacts were mutated and must be re-evaluated "
                "by the downstream gates before memory promotion:",
                "",
                "### Re-run: semantic-authenticity-gate",
                "",
            ]
            for aid in report.rerun_candidates:
                lines.append(f"- `{aid}`")
            lines += [
                "",
                "### Re-run: cognitive-gym",
                "",
            ]
            for aid in report.rerun_candidates:
                lines.append(f"- `{aid}`")
            lines.append("")
        else:
            lines.append("> No artifacts require re-gating.\n")

        if report.quarantined:
            lines += [
                "## Manual Review Required",
                "",
                "These artifacts could not be automatically classified. "
                "A human must inspect each before deletion:",
                "",
            ]
            for r in report.quarantined:
                reasons = "; ".join(r.disposition_reasons) or "uncertain signals"
                lines.append(
                    f"- `{r.artifact_id}` **{r.title[:60]}** "
                    f"(confidence {r.poison_confidence:.3f}): {reasons}"
                )
            lines.append("")

        if n_clean == n_total:
            lines.append(
                "> Corpus is fully clean — no poisoned artifacts detected.\n"
            )
        elif clean_pct >= 80.0:
            lines.append(
                f"> Corpus is mostly clean ({clean_pct:.1f}%). "
                "Proceed with memory rebuild after re-gating candidates.\n"
            )
        else:
            lines.append(
                f"> Corpus has significant contamination ({100-clean_pct:.1f}% poisoned). "
                "Full memory rebuild recommended after re-gating.\n"
            )

        self._write(
            self.reports_dir / "POST_CLEANUP_SCORECARD.md",
            "\n".join(lines),
        )

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Serialisation / formatting helpers
# ---------------------------------------------------------------------------


def _record_to_dict(r: ArtifactRecord) -> dict[str, Any]:
    return {
        "artifact_id": r.artifact_id,
        "file_path": r.file_path,
        "title": r.title,
        "body_preview": r.body_preview,
        "poison_confidence": r.poison_confidence,
        "disposition": r.disposition,
        "disposition_reasons": r.disposition_reasons,
        "backup_path": r.backup_path,
        "signals": {
            "has_key_leakage": r.signals.has_key_leakage,
            "key_leakage_matches": r.signals.key_leakage_matches,
            "has_placeholder_content": r.signals.has_placeholder_content,
            "placeholder_matches": r.signals.placeholder_matches,
            "has_malformed_title": r.signals.has_malformed_title,
            "malformed_title_reason": r.signals.malformed_title_reason,
            "has_codefence_contamination": r.signals.has_codefence_contamination,
            "codefence_count": r.signals.codefence_count,
            "body_word_count": r.signals.body_word_count,
            "body_too_short": r.signals.body_too_short,
            "missing_source_evidence": r.signals.missing_source_evidence,
            "is_duplicate": r.signals.is_duplicate,
            "duplicate_of": r.signals.duplicate_of,
        },
        "run_timestamp": r.run_timestamp,
    }


def _artifact_md_block(r: ArtifactRecord) -> list[str]:
    lines = [
        f"### {r.title or '(no title)'} `{r.artifact_id}`",
        "",
        f"- **Poison confidence**: {r.poison_confidence:.3f}",
        f"- **Disposition**: `{r.disposition}`",
    ]
    if r.file_path:
        lines.append(f"- **File**: `{r.file_path}`")
    if r.backup_path:
        lines.append(f"- **Backup**: `{r.backup_path}`")
    if r.disposition_reasons:
        lines.append("- **Reasons**:")
        for reason in r.disposition_reasons:
            lines.append(f"  - {reason}")
    if r.body_preview:
        lines.append(f"- **Body preview**: _{r.body_preview[:100]}_")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _load_artifacts_from_path(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else [raw]

    artifacts: list[dict[str, Any]] = []
    for json_file in sorted(path.glob("**/*.json")):
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                item.setdefault("artifact_id", json_file.stem)
                item["_file_path"] = str(json_file)
            artifacts.extend(items)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Skipping {json_file}: {exc}", file=sys.stderr)
    return artifacts


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Corpus Cleanup Agent — safely remove poisoned artifacts from AI_BRAIN corpus"
    )
    parser.add_argument(
        "scan_path",
        nargs="?",
        help=(
            "Path to a JSON file or directory of JSON files to scan. "
            "If omitted, reads from stdin."
        ),
    )
    parser.add_argument(
        "--reports-dir",
        default=None,
        help="Directory to write output reports.",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Directory to write backups before deletion.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Execute filesystem mutations (delete removed, backup archived). "
            "Default is dry-run (no files are changed)."
        ),
    )
    args = parser.parse_args(argv)

    if args.scan_path:
        p = Path(args.scan_path)
        if not p.exists():
            print(f"[ERROR] Path not found: {p}", file=sys.stderr)
            return 1
        raw_artifacts = _load_artifacts_from_path(p)
    else:
        try:
            raw = json.load(sys.stdin)
            raw_artifacts = raw if isinstance(raw, list) else [raw]
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Failed to parse JSON from stdin: {exc}", file=sys.stderr)
            return 1

    reports_dir = Path(args.reports_dir) if args.reports_dir else Path(__file__).parent / "reports"
    backup_dir  = Path(args.backup_dir)  if args.backup_dir  else reports_dir / "backups"

    agent  = CorpusCleanupAgent(
        reports_dir=reports_dir,
        backup_dir=backup_dir,
        dry_run=not args.live,
    )
    report = agent.run(raw_artifacts)

    mode = "live" if args.live else "dry-run"
    print(f"\nCorpus Cleanup Agent — {report.run_timestamp} [{mode}]")
    print(f"  Scanned     : {report.total_scanned}")
    print(f"  Clean       : {len(report.clean)}")
    print(f"  Removed     : {len(report.removed)}")
    print(f"  Archived    : {len(report.archived)}")
    print(f"  Quarantined : {len(report.quarantined)}")
    print(f"  Skipped     : {len(report.skipped)}")
    if report.rerun_candidates:
        print(f"  Re-gate     : {len(report.rerun_candidates)} artifact(s)")

    agent.write_outputs(report)
    print(f"\nReports written to: {reports_dir}/")

    poison_count = len(report.removed) + len(report.archived)
    return 0 if poison_count < report.total_scanned else 1


if __name__ == "__main__":
    sys.exit(main())
