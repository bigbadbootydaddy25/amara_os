"""
Tracks per-agent, per-task inference performance.
Writes to neural/accuracy_log.csv — real outcomes only.
"""

import csv
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = Path(__file__).parent / "accuracy_log.csv"
_FIELDNAMES = [
    "timestamp", "agent_id", "task_type", "model",
    "tokens_in", "tokens_out", "decision_id",
    "outcome", "correct",
]

TASK_MODEL_MAP = {
    "pain_point_analysis":  "hermes3",
    "monday_debrief":       "hermes3",
    "logistics_risk":       "hermes3",
    "market_intelligence":  "hermes3",
    "harvey_synthesis":     "hermes3",
    "premortem_check":      "hermes3",
    "prompt_optimization":  "hermes3",
    "build_request":        "hermes3",
}


def _ensure_header() -> None:
    if not _LOG_PATH.exists():
        with open(_LOG_PATH, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=_FIELDNAMES).writeheader()


def log_inference(
    task_type: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    decision_id: str = None,
    agent_id: str = None,
) -> str:
    """Appends one row to accuracy_log.csv. Returns the decision_id."""
    _ensure_header()
    if decision_id is None:
        decision_id = str(uuid.uuid4())
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id or "",
        "task_type": task_type,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "decision_id": decision_id,
        "outcome": "",
        "correct": "",
    }
    with open(_LOG_PATH, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_FIELDNAMES).writerow(row)
    return decision_id


def log_outcome(decision_id: str, agent_id: str, outcome: str) -> None:
    """
    Updates the row matching decision_id with the known outcome.
    outcome: CORRECT | INCORRECT | PARTIAL
    """
    _ensure_header()
    rows = []
    updated = False
    with open(_LOG_PATH, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["decision_id"] == decision_id:
                row["outcome"] = outcome
                row["agent_id"] = agent_id
                row["correct"] = "1" if outcome == "CORRECT" else (
                    "0.5" if outcome == "PARTIAL" else "0"
                )
                updated = True
            rows.append(row)

    if updated:
        with open(_LOG_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)


def get_agent_accuracy(agent_id: str, last_n: int = 30) -> float | None:
    """
    Returns accuracy rate over the last N decisions with known outcomes.
    Returns None if fewer than 10 outcomes are known.
    """
    _ensure_header()
    if not _LOG_PATH.exists():
        return None
    decided = []
    with open(_LOG_PATH, "r", newline="") as f:
        for row in csv.DictReader(f):
            if row["agent_id"] == agent_id and row["correct"] != "":
                decided.append(float(row["correct"]))
    recent = decided[-last_n:]
    if len(recent) < 10:
        return None
    return sum(recent) / len(recent)


def get_best_model(task_type: str) -> str:
    """
    Inspects accuracy_log for the best-performing model on task_type.
    Falls back to TASK_MODEL_MAP default when data is thin.
    """
    _ensure_header()
    if not _LOG_PATH.exists():
        return TASK_MODEL_MAP.get(task_type, "hermes3")

    model_scores: dict[str, list[float]] = {}
    with open(_LOG_PATH, "r", newline="") as f:
        for row in csv.DictReader(f):
            if row["task_type"] == task_type and row["correct"] != "":
                m = row["model"]
                model_scores.setdefault(m, []).append(float(row["correct"]))

    best_model = TASK_MODEL_MAP.get(task_type, "hermes3")
    best_score = -1.0
    for model, scores in model_scores.items():
        if len(scores) >= 10:
            avg = sum(scores) / len(scores)
            if avg > best_score:
                best_score = avg
                best_model = model
    return best_model
