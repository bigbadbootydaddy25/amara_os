"""
Records real-world outcomes to AMARA_BRAIN/Outcomes/outcomes.jsonl.
Drives weekly learning reports and Telegram summaries.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_AMARA_BRAIN = Path(os.getenv("AMARA_BRAIN", str(Path(__file__).parent.parent / "Brain")))
_OUTCOMES_FILE = _AMARA_BRAIN / "Outcomes" / "outcomes.jsonl"

VALID_OUTCOMES = {"CORRECT", "INCORRECT", "PARTIAL"}


def _ensure_outcomes_dir() -> None:
    _OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)


def record_outcome(
    decision_id: str,
    agent_id: str,
    outcome: str,
    notes: str = "",
    decision_type: str = "",
    entity_id: str = None,
    frac_date: str = None,
) -> None:
    """
    Records a real-world outcome to AMARA_BRAIN/Outcomes/outcomes.jsonl.
    outcome: CORRECT | INCORRECT | PARTIAL
    Raises ValueError on invalid outcome to prevent silent bad data.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(
            f"Invalid outcome '{outcome}'. Must be one of {VALID_OUTCOMES}"
        )

    _ensure_outcomes_dir()

    entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "decision_id": decision_id,
        "agent_id": agent_id,
        "outcome": outcome,
        "notes": notes,
        "decision_type": decision_type,
        "entity_id": entity_id,
        "frac_date": frac_date,
    }

    with open(_OUTCOMES_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    log.info("Outcome recorded: decision=%s agent=%s outcome=%s", decision_id, agent_id, outcome)

    _check_accuracy_threshold(agent_id)

    if decision_type == "FRAC_WINDOW" and frac_date:
        _queue_prophet_retraining(frac_date, decision_id, agent_id)


def _load_recent_outcomes(agent_id: str, last_n: int = 30) -> list:
    """Returns the last N outcome records for an agent with known outcomes."""
    if not _OUTCOMES_FILE.exists():
        return []
    entries = []
    with open(_OUTCOMES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("agent_id") == agent_id and entry.get("outcome") in VALID_OUTCOMES:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries[-last_n:]


def get_agent_accuracy(agent_id: str, last_n: int = 30) -> float | None:
    """Returns accuracy over last N outcomes. None if fewer than 10 known."""
    outcomes = _load_recent_outcomes(agent_id, last_n)
    if len(outcomes) < 10:
        return None
    scores = []
    for o in outcomes:
        v = o.get("outcome")
        scores.append(1.0 if v == "CORRECT" else (0.5 if v == "PARTIAL" else 0.0))
    return sum(scores) / len(scores)


def _check_accuracy_threshold(agent_id: str) -> None:
    accuracy = get_agent_accuracy(agent_id, last_n=30)
    if accuracy is not None and accuracy < 0.60:
        from claude_code_interface.build_request import file_build_request
        file_build_request(
            trigger="ACCURACY_BELOW_THRESHOLD",
            agent_id=agent_id,
            problem=f"Agent {agent_id} accuracy = {accuracy:.1%} over last 30 decisions.",
            evidence_summary=f"Trailing accuracy below 0.60 threshold. See outcomes.jsonl.",
            suggested_solution=(
                f"Re-run DSPy optimization for {agent_id}. "
                "Review system prompt and evidence weighting."
            ),
        )


def _queue_prophet_retraining(frac_date: str, decision_id: str, agent_id: str) -> None:
    queue_file = _AMARA_BRAIN / "prophet_retraining_queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "frac_date": frac_date,
        "decision_id": decision_id,
        "agent_id": agent_id,
    }
    with open(queue_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def weekly_learning_run() -> None:
    """
    Scheduled: Sunday midnight CT.
    Computes weekly accuracy, queues Prophet retraining, runs DSPy
    optimization for low performers, writes Obsidian report.
    """
    from neural import dspy_optimizer

    agents = ["Jade", "Red", "Dakota", "Oracle", "Geo"]
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    stats = {}

    for agent in agents:
        recent = _load_recent_outcomes(agent, last_n=30)
        n = len(recent)
        correct = sum(
            1.0 if o["outcome"] == "CORRECT" else (0.5 if o["outcome"] == "PARTIAL" else 0.0)
            for o in recent
        )
        rate = correct / n if n > 0 else 0.0
        stats[agent] = {"n": n, "correct": correct, "rate": rate}
        if n >= 10 and rate < 0.70:
            dspy_optimizer.optimize_agent(agent)

    rows = "\n".join(
        f"| {a:<7} | {s['n']:<9} | {int(s['correct']):<7} | {s['rate']:.0%}   |"
        for a, s in stats.items()
    )
    sorted_agents = [(a, s["rate"]) for a, s in stats.items() if s["n"] > 0]
    best = max(sorted_agents, key=lambda x: x[1], default=("N/A", 0.0))
    worst = min(sorted_agents, key=lambda x: x[1], default=("N/A", 0.0))

    report = f"""# AMARA Neural Learning Report {date_str}

## Agent Accuracy This Week
| Agent   | Decisions | Correct | Rate |
|---------|-----------|---------|------|
{rows}

## Prophet Model Updates
See Brain/prophet_retraining_queue.jsonl

## DSPy Optimizations Run
Agents below 70% threshold processed.

## Build Requests Filed
See Brain/Build_Requests/

## Next Week Focus
{'Re-optimize: ' + ', '.join(a for a, s in stats.items() if s['n'] >= 10 and s['rate'] < 0.70)}
"""

    obsidian_root = Path(os.getenv("OBSIDIAN_VAULT", "")) / "amara" / "neural"
    try:
        obsidian_root.mkdir(parents=True, exist_ok=True)
        (obsidian_root / f"weekly_learning_{date_str}.md").write_text(report)
    except Exception as e:
        log.warning("Could not write Obsidian report: %s", e)

    local_report = _AMARA_BRAIN / "Reports" / f"weekly_learning_{date_str}.md"
    local_report.parent.mkdir(parents=True, exist_ok=True)
    local_report.write_text(report)
    log.info("Weekly learning report written: %s", local_report)

    _send_telegram_summary(date_str, best, worst, stats)


def _send_telegram_summary(date_str, best, worst, stats) -> None:
    token = os.getenv("TELEGRAM_BOT2_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_BOT2_CHAT_ID", "")
    if not token or not chat_id:
        return
    optimized = [a for a, s in stats.items() if s["n"] >= 10 and s["rate"] < 0.70]
    msg = (
        f"🧠 AMARA WEEKLY LEARNING\n"
        f"Week: {date_str}\n"
        f"Best agent: {best[0]} {best[1]:.0%}\n"
        f"Needs work: {worst[0]} {worst[1]:.0%}\n"
        f"DSPy optimizations: {len(optimized)}\n"
        f"See Brain/Reports/ for full report."
    )
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10,
        )
    except Exception:
        pass
