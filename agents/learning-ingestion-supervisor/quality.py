"""
Quality scoring for learning ingestion records.

Scores are 0–100. Thresholds:
  PROMOTE    >= 70  — safe for memory promotion
  REVIEW     40–69  — needs human review before promotion
  QUARANTINE  < 40  — route to quarantine, do not promote
  FAILED       0    — missing critical artifacts, treat as extraction failure
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------

PROMOTE_THRESHOLD = 70.0
REVIEW_THRESHOLD = 40.0

VERDICT_PROMOTE = "PROMOTE"
VERDICT_REVIEW = "REVIEW"
VERDICT_QUARANTINE = "QUARANTINE"
VERDICT_FAILED = "FAILED"

# Placeholder patterns that signal auto-generated or unfilled content
PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bplaceholder\b",
    r"\binsert\s+(content|text|summary|notes)\s+here\b",
    r"\[.*?(placeholder|todo|tbd|coming soon).*?\]",
    r"lorem ipsum",
    r"\bN/A\b",
    r"<no\s+(transcript|content|notes|workflow)>",
    r"transcript\s+not\s+(available|found|extracted)",
    r"failed\s+to\s+(extract|generate|transcribe)",
]

# Vague workflow step patterns that indicate fabricated or low-effort steps
VAGUE_STEP_PATTERNS = [
    r"^(step\s+\d+\s*:?\s*)?(do\s+the\s+thing|follow\s+steps?|repeat|etc\.?|and\s+so\s+on)",
    r"^(step\s+\d+\s*:?\s*)?[^:]{0,20}$",  # steps shorter than 20 chars
    r"\bsomehow\b",
    r"\bsomething\b",
    r"\bvarious\s+steps\b",
    r"\bappropriate\s+action\b",
]

_PLACEHOLDER_RE = re.compile(
    "|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE | re.MULTILINE
)
_VAGUE_STEP_RE = re.compile(
    "|".join(VAGUE_STEP_PATTERNS), re.IGNORECASE | re.MULTILINE
)


def _find_placeholders(text: str) -> list[str]:
    """Return full matched placeholder strings (avoids tuple issue from findall with groups)."""
    return [m.group(0) for m in _PLACEHOLDER_RE.finditer(text)]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    name: str
    score: float  # 0–100
    issues: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # what we observed

    def add_issue(self, msg: str, penalty: float = 0.0) -> float:
        self.issues.append(msg)
        return penalty


@dataclass
class QualityAssessment:
    session_id: str
    transcript: DimensionScore
    workflow: DimensionScore
    notes: DimensionScore
    authenticity: DimensionScore
    overall_score: float
    verdict: str
    verdict_reason: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "overall_score": round(self.overall_score, 2),
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "dimensions": {
                "transcript": _dim_to_dict(self.transcript),
                "workflow": _dim_to_dict(self.workflow),
                "notes": _dim_to_dict(self.notes),
                "authenticity": _dim_to_dict(self.authenticity),
            },
        }


def _dim_to_dict(d: DimensionScore) -> dict:
    return {
        "score": round(d.score, 2),
        "issues": d.issues,
        "evidence": d.evidence,
    }


# ---------------------------------------------------------------------------
# Transcript scoring
# ---------------------------------------------------------------------------

MIN_TRANSCRIPT_WORDS = 100
GOOD_TRANSCRIPT_WORDS = 500


def score_transcript(transcript_path: Optional[Path]) -> DimensionScore:
    dim = DimensionScore(name="transcript", score=100.0)

    if transcript_path is None:
        dim.score = 0.0
        dim.add_issue("No transcript path provided")
        return dim

    if not transcript_path.exists():
        dim.score = 0.0
        dim.add_issue(f"Transcript file missing: {transcript_path.name}")
        return dim

    text = transcript_path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        dim.score = 0.0
        dim.add_issue("Transcript file is empty")
        return dim

    dim.evidence.append(f"File size: {len(text)} chars")

    # Check for placeholder signals
    placeholder_hits = _find_placeholders(text)
    if placeholder_hits:
        dim.score -= 40.0
        dim.add_issue(
            f"Placeholder/error text detected ({len(placeholder_hits)} matches): "
            + ", ".join(dict.fromkeys(placeholder_hits[:5]))
        )

    # Word count check
    words = text.split()
    word_count = len(words)
    dim.evidence.append(f"Word count: {word_count}")

    if word_count < 10:
        dim.score = max(0.0, dim.score - 60.0)
        dim.add_issue(f"Transcript too short ({word_count} words) — likely failed extraction")
    elif word_count < MIN_TRANSCRIPT_WORDS:
        penalty = 30.0 * (1 - word_count / MIN_TRANSCRIPT_WORDS)
        dim.score = max(0.0, dim.score - penalty)
        dim.add_issue(f"Transcript below minimum length ({word_count} words, min {MIN_TRANSCRIPT_WORDS})")

    # Timestamps-only check: lines that are only timestamps with no speech
    lines = text.splitlines()
    timestamp_lines = sum(1 for l in lines if re.match(r"^\s*\[?\d{1,2}:\d{2}(:\d{2})?\]?\s*$", l))
    if lines and timestamp_lines / max(len(lines), 1) > 0.5:
        dim.score = max(0.0, dim.score - 55.0)
        dim.add_issue("Over 50% of lines are bare timestamps — speech extraction likely failed")

    # Check for repetitive content (copy-paste artifact)
    unique_lines = len(set(l.strip() for l in lines if l.strip()))
    if lines and unique_lines / max(len(lines), 1) < 0.3:
        dim.score = max(0.0, dim.score - 25.0)
        dim.add_issue("High line repetition — possible extraction artifact")

    dim.score = max(0.0, min(100.0, dim.score))
    return dim


# ---------------------------------------------------------------------------
# Workflow scoring
# ---------------------------------------------------------------------------

MIN_WORKFLOW_STEPS = 3
MIN_STEP_WORDS = 5


def score_workflow(workflow_path: Optional[Path]) -> DimensionScore:
    dim = DimensionScore(name="workflow", score=100.0)

    if workflow_path is None:
        # Workflow is optional — penalise but don't fail
        dim.score = 50.0
        dim.add_issue("No workflow file provided (optional but preferred)")
        return dim

    if not workflow_path.exists():
        dim.score = 30.0
        dim.add_issue(f"Workflow file missing: {workflow_path.name}")
        return dim

    text = workflow_path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        dim.score = 0.0
        dim.add_issue("Workflow file is empty")
        return dim

    dim.evidence.append(f"File size: {len(text)} chars")

    # Check for placeholder signals
    placeholder_hits = _find_placeholders(text)
    if placeholder_hits:
        dim.score -= 40.0
        dim.add_issue(
            f"Placeholder text in workflow ({len(placeholder_hits)} matches)"
        )

    # Extract steps — lines starting with digits, bullets, or markdown list markers
    step_lines = [
        l.strip()
        for l in text.splitlines()
        if re.match(r"^\s*(\d+[\.\):]|\*|-|•)\s+\S", l)
    ]
    step_count = len(step_lines)
    dim.evidence.append(f"Detected steps: {step_count}")

    if step_count == 0:
        dim.score = max(0.0, dim.score - 50.0)
        dim.add_issue("No recognisable workflow steps found (expected numbered/bulleted list)")
    elif step_count < MIN_WORKFLOW_STEPS:
        dim.score = max(0.0, dim.score - 30.0)
        dim.add_issue(
            f"Too few workflow steps ({step_count}, minimum {MIN_WORKFLOW_STEPS}) — may be incomplete"
        )

    # Vague step check
    vague_steps = [s for s in step_lines if _VAGUE_STEP_RE.search(s)]
    if vague_steps:
        penalty = min(40.0, len(vague_steps) * 10.0)
        dim.score = max(0.0, dim.score - penalty)
        dim.add_issue(
            f"{len(vague_steps)} vague/fabricated step(s) detected: "
            + "; ".join(vague_steps[:3])
        )

    # Short steps check
    short_steps = [s for s in step_lines if len(s.split()) < MIN_STEP_WORDS]
    if short_steps:
        penalty = min(20.0, len(short_steps) * 5.0)
        dim.score = max(0.0, dim.score - penalty)
        dim.add_issue(f"{len(short_steps)} steps are under {MIN_STEP_WORDS} words")

    dim.score = max(0.0, min(100.0, dim.score))
    return dim


# ---------------------------------------------------------------------------
# Notes scoring
# ---------------------------------------------------------------------------

MIN_NOTES_WORDS = 80
REQUIRED_NOTES_SECTIONS = ["##", "**", "-"]  # at least some structure


def score_notes(notes_path: Optional[Path]) -> DimensionScore:
    dim = DimensionScore(name="notes", score=100.0)

    if notes_path is None:
        dim.score = 0.0
        dim.add_issue("No notes file provided")
        return dim

    if not notes_path.exists():
        dim.score = 0.0
        dim.add_issue(f"Notes file missing: {notes_path.name}")
        return dim

    text = notes_path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        dim.score = 0.0
        dim.add_issue("Notes file is empty")
        return dim

    dim.evidence.append(f"File size: {len(text)} chars")

    # Placeholder check
    placeholder_hits = _find_placeholders(text)
    if placeholder_hits:
        dim.score -= 50.0
        dim.add_issue(
            f"Placeholder text in notes ({len(placeholder_hits)} matches): "
            + ", ".join(dict.fromkeys(placeholder_hits[:5]))
        )

    words = text.split()
    word_count = len(words)
    dim.evidence.append(f"Word count: {word_count}")

    if word_count < 20:
        dim.score = max(0.0, dim.score - 60.0)
        dim.add_issue(f"Notes critically short ({word_count} words)")
    elif word_count < MIN_NOTES_WORDS:
        penalty = 25.0 * (1 - word_count / MIN_NOTES_WORDS)
        dim.score = max(0.0, dim.score - penalty)
        dim.add_issue(f"Notes below minimum length ({word_count} words, min {MIN_NOTES_WORDS})")

    # Structure check
    has_structure = any(marker in text for marker in REQUIRED_NOTES_SECTIONS)
    if not has_structure:
        dim.score = max(0.0, dim.score - 20.0)
        dim.add_issue("Notes have no markdown structure (no headers, bullets, or bold)")

    # Title-only check: a single line with no body
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) <= 2:
        dim.score = max(0.0, dim.score - 30.0)
        dim.add_issue("Notes appear to be title-only with no body content")

    dim.score = max(0.0, min(100.0, dim.score))
    return dim


# ---------------------------------------------------------------------------
# Authenticity scoring (from semantic-authenticity-gate)
# ---------------------------------------------------------------------------


def score_authenticity(authenticity_result: Optional[dict]) -> DimensionScore:
    dim = DimensionScore(name="authenticity", score=100.0)

    if authenticity_result is None:
        # No gate result — neutral, mild penalty
        dim.score = 60.0
        dim.add_issue("No semantic-authenticity-gate result available")
        return dim

    confidence = authenticity_result.get("confidence", None)
    verdict = authenticity_result.get("verdict", "").upper()
    flags = authenticity_result.get("flags", [])

    if confidence is not None:
        dim.evidence.append(f"Gate confidence: {confidence:.2f}")
        dim.score = float(confidence) * 100.0

    if verdict in ("FABRICATED", "HALLUCINATED", "REJECTED"):
        dim.score = max(0.0, dim.score - 50.0)
        dim.add_issue(f"Authenticity gate verdict: {verdict}")

    for flag in flags:
        dim.score = max(0.0, dim.score - 10.0)
        dim.add_issue(f"Authenticity flag: {flag}")

    dim.score = max(0.0, min(100.0, dim.score))
    return dim


# ---------------------------------------------------------------------------
# Overall assessment
# ---------------------------------------------------------------------------

# Dimension weights — must sum to 1.0
WEIGHTS = {
    "transcript": 0.40,
    "workflow": 0.25,
    "notes": 0.20,
    "authenticity": 0.15,
}


def compute_overall(
    session_id: str,
    transcript: DimensionScore,
    workflow: DimensionScore,
    notes: DimensionScore,
    authenticity: DimensionScore,
    is_duplicate: bool = False,
    duplicate_of: Optional[str] = None,
) -> QualityAssessment:
    weighted = (
        transcript.score * WEIGHTS["transcript"]
        + workflow.score * WEIGHTS["workflow"]
        + notes.score * WEIGHTS["notes"]
        + authenticity.score * WEIGHTS["authenticity"]
    )

    # Hard failures: missing transcript or notes collapse the overall score
    if transcript.score == 0.0:
        weighted = min(weighted, 20.0)
    if notes.score == 0.0:
        weighted = min(weighted, 30.0)

    # Fabricated/vague workflow steps are a hard block on promotion
    if any("vague" in i.lower() or "fabricat" in i.lower() for i in workflow.issues):
        weighted = min(weighted, PROMOTE_THRESHOLD - 1.0)

    # Duplicate penalty
    if is_duplicate:
        weighted = min(weighted, 35.0)

    overall = round(max(0.0, min(100.0, weighted)), 2)

    if transcript.score == 0.0:
        verdict = VERDICT_FAILED
        reason = "Transcript extraction failed — no source evidence preserved"
    elif is_duplicate:
        verdict = VERDICT_QUARANTINE
        reason = f"Duplicate of {duplicate_of} — prefer one high-quality ingestion"
    elif overall >= PROMOTE_THRESHOLD:
        verdict = VERDICT_PROMOTE
        reason = f"Quality score {overall}/100 meets promotion threshold ({PROMOTE_THRESHOLD})"
    elif overall >= REVIEW_THRESHOLD:
        verdict = VERDICT_REVIEW
        reason = f"Quality score {overall}/100 requires human review before promotion"
    else:
        verdict = VERDICT_QUARANTINE
        reason = f"Quality score {overall}/100 below quarantine threshold ({REVIEW_THRESHOLD})"

    return QualityAssessment(
        session_id=session_id,
        transcript=transcript,
        workflow=workflow,
        notes=notes,
        authenticity=authenticity,
        overall_score=overall,
        verdict=verdict,
        verdict_reason=reason,
        is_duplicate=is_duplicate,
        duplicate_of=duplicate_of,
    )
