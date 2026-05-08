"""
Per-source inspectors for the Learning Ingestion Supervisor.

Each inspector understands the output layout of one upstream agent and
returns a list of IngestionRecord objects for the supervisor to assess.

Expected AI Brain directory layout
───────────────────────────────────
<brain_dir>/
  agents/
    universal-skill-learner/outputs/<session_id>/
        metadata.json          video URL, title, timestamp, status
        transcript.txt         raw transcript
        notes.md               generated notes
        workflow.md            extracted workflow (optional)

    video-ingestion-orchestrator/reports/<YYYY-MM-DD>/
        run_summary.json       overall run stats
        <video_id>.json        per-video ingestion record

    cognitive-gym/scores/
        <session_id>.json      comprehension / retention scores

    semantic-authenticity-gate/results/
        <session_id>.json      authenticity verdict + confidence + flags

    memory-repair/results/
        <session_id>.json      repair operations applied to session
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IngestionRecord — the common unit passed to the supervisor
# ---------------------------------------------------------------------------


@dataclass
class IngestionRecord:
    session_id: str
    source_agent: str
    video_url: Optional[str] = None
    video_title: Optional[str] = None
    ingested_at: Optional[str] = None  # ISO timestamp string

    # Artifact paths (None = not provided by this source)
    transcript_path: Optional[Path] = None
    notes_path: Optional[Path] = None
    workflow_path: Optional[Path] = None

    # Enrichment blobs loaded from sibling agents
    cognitive_gym_score: Optional[dict] = None
    authenticity_result: Optional[dict] = None
    memory_repair_result: Optional[dict] = None

    raw_metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"IngestionRecord(id={self.session_id!r}, "
            f"source={self.source_agent!r}, "
            f"url={self.video_url!r})"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not parse %s: %s", path, exc)
        return None


def _agent_dir(brain_dir: Path, *parts: str) -> Path:
    return brain_dir / "agents" / Path(*parts)


# ---------------------------------------------------------------------------
# Universal Skill Learner inspector
# ---------------------------------------------------------------------------


class UniversalSkillLearnerInspector:
    """
    Discovers sessions produced by the universal-skill-learner agent.
    Each session lives in its own subdirectory under outputs/.
    """

    SOURCE = "universal-skill-learner"

    def __init__(self, brain_dir: Path) -> None:
        self.outputs_dir = _agent_dir(brain_dir, "universal-skill-learner", "outputs")

    def collect(self) -> list[IngestionRecord]:
        if not self.outputs_dir.exists():
            log.warning("USL outputs dir not found: %s", self.outputs_dir)
            return []

        records: list[IngestionRecord] = []
        for session_dir in sorted(self.outputs_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            record = self._parse_session(session_dir)
            if record:
                records.append(record)

        log.info("USL inspector: found %d session(s)", len(records))
        return records

    def _parse_session(self, session_dir: Path) -> Optional[IngestionRecord]:
        metadata_path = session_dir / "metadata.json"
        metadata: dict = {}
        if metadata_path.exists():
            metadata = _load_json(metadata_path) or {}

        session_id = metadata.get("session_id") or session_dir.name

        transcript = session_dir / "transcript.txt"
        notes = session_dir / "notes.md"
        workflow = session_dir / "workflow.md"

        return IngestionRecord(
            session_id=session_id,
            source_agent=self.SOURCE,
            video_url=metadata.get("video_url"),
            video_title=metadata.get("title"),
            ingested_at=metadata.get("timestamp"),
            transcript_path=transcript if transcript.exists() else None,
            notes_path=notes if notes.exists() else None,
            workflow_path=workflow if workflow.exists() else None,
            raw_metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Video Ingestion Orchestrator inspector
# ---------------------------------------------------------------------------


class VideoIngestionOrchestratorInspector:
    """
    Reads per-run report directories from the video-ingestion-orchestrator.
    Each dated run directory may contain a run_summary.json plus individual
    <video_id>.json files.
    """

    SOURCE = "video-ingestion-orchestrator"

    def __init__(self, brain_dir: Path) -> None:
        self.reports_dir = _agent_dir(brain_dir, "video-ingestion-orchestrator", "reports")

    def collect(self) -> list[IngestionRecord]:
        if not self.reports_dir.exists():
            log.warning("VIO reports dir not found: %s", self.reports_dir)
            return []

        records: list[IngestionRecord] = []
        for run_dir in sorted(self.reports_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            records.extend(self._parse_run(run_dir))

        log.info("VIO inspector: found %d record(s)", len(records))
        return records

    def _parse_run(self, run_dir: Path) -> list[IngestionRecord]:
        records = []
        for json_file in sorted(run_dir.glob("*.json")):
            if json_file.name == "run_summary.json":
                continue
            data = _load_json(json_file)
            if not data:
                continue

            session_id = data.get("session_id") or data.get("video_id") or json_file.stem
            base = _resolve_artifact_base(data, run_dir)

            records.append(
                IngestionRecord(
                    session_id=session_id,
                    source_agent=self.SOURCE,
                    video_url=data.get("video_url"),
                    video_title=data.get("title"),
                    ingested_at=data.get("timestamp"),
                    transcript_path=_find_artifact(base, data, "transcript_path", ["transcript.txt"]),
                    notes_path=_find_artifact(base, data, "notes_path", ["notes.md"]),
                    workflow_path=_find_artifact(base, data, "workflow_path", ["workflow.md"]),
                    raw_metadata=data,
                )
            )
        return records


def _resolve_artifact_base(data: dict, fallback: Path) -> Path:
    """Return the directory where artifacts for this record live."""
    if "artifact_dir" in data:
        p = Path(data["artifact_dir"])
        if p.is_dir():
            return p
    return fallback


def _find_artifact(
    base: Path, data: dict, key: str, fallback_names: list[str]
) -> Optional[Path]:
    """Resolve an artifact path from a metadata key or well-known filename."""
    if key in data:
        p = Path(data[key])
        if not p.is_absolute():
            p = base / p
        if p.exists():
            return p
    for name in fallback_names:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Cognitive Gym inspector (enrichment only — no primary records)
# ---------------------------------------------------------------------------


class CognitiveGymInspector:
    """
    Loads comprehension/retention scores from cognitive-gym.
    Returns a mapping of session_id → score dict for enrichment.
    """

    def __init__(self, brain_dir: Path) -> None:
        self.scores_dir = _agent_dir(brain_dir, "cognitive-gym", "scores")

    def load_scores(self) -> dict[str, dict]:
        if not self.scores_dir.exists():
            log.warning("Cognitive Gym scores dir not found: %s", self.scores_dir)
            return {}

        scores: dict[str, dict] = {}
        for json_file in self.scores_dir.glob("*.json"):
            data = _load_json(json_file)
            if not data:
                continue
            sid = data.get("session_id") or json_file.stem
            scores[sid] = data

        log.info("CognitiveGym: loaded scores for %d session(s)", len(scores))
        return scores


# ---------------------------------------------------------------------------
# Semantic Authenticity Gate inspector (enrichment only)
# ---------------------------------------------------------------------------


class SemanticAuthenticityGateInspector:
    """
    Loads authenticity gate results.
    Returns a mapping of session_id → result dict for enrichment.
    """

    def __init__(self, brain_dir: Path) -> None:
        self.results_dir = _agent_dir(brain_dir, "semantic-authenticity-gate", "results")

    def load_results(self) -> dict[str, dict]:
        if not self.results_dir.exists():
            log.warning("SAG results dir not found: %s", self.results_dir)
            return {}

        results: dict[str, dict] = {}
        for json_file in self.results_dir.glob("*.json"):
            data = _load_json(json_file)
            if not data:
                continue
            sid = data.get("session_id") or json_file.stem
            results[sid] = data

        log.info("SAG: loaded results for %d session(s)", len(results))
        return results


# ---------------------------------------------------------------------------
# Memory Repair inspector (enrichment only)
# ---------------------------------------------------------------------------


class MemoryRepairInspector:
    """
    Loads memory repair logs.  A repaired session may have had its artifacts
    patched — we record that for diagnostic context but don't alter scores.
    Returns a mapping of session_id → repair dict.
    """

    def __init__(self, brain_dir: Path) -> None:
        self.results_dir = _agent_dir(brain_dir, "memory-repair", "results")

    def load_results(self) -> dict[str, dict]:
        if not self.results_dir.exists():
            log.warning("MemoryRepair results dir not found: %s", self.results_dir)
            return {}

        results: dict[str, dict] = {}
        for json_file in self.results_dir.glob("*.json"):
            data = _load_json(json_file)
            if not data:
                continue
            sid = data.get("session_id") or json_file.stem
            results[sid] = data

        log.info("MemoryRepair: loaded results for %d session(s)", len(results))
        return results


# ---------------------------------------------------------------------------
# Duplicate detector
# ---------------------------------------------------------------------------


def detect_duplicates(records: list[IngestionRecord]) -> dict[str, str]:
    """
    Returns a mapping of duplicate session_id → canonical session_id.

    Duplicates are defined as: same video_url ingested more than once.
    The first seen record (by session_id sort order) is treated as canonical.
    """
    url_to_canonical: dict[str, str] = {}
    duplicates: dict[str, str] = {}

    for record in sorted(records, key=lambda r: r.session_id):
        url = (record.video_url or "").strip().lower()
        if not url:
            continue
        if url in url_to_canonical:
            duplicates[record.session_id] = url_to_canonical[url]
        else:
            url_to_canonical[url] = record.session_id

    return duplicates
