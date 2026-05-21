"""
Feedback loop — records real-world outcomes and drives weekly learning.
Called after a call converts/fails, or after a frac date is confirmed.
"""

import os
import requests as http
from datetime import datetime, timezone, timedelta
from pathlib import Path

from neural import accuracy_tracker

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
_TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT2_TOKEN", "")
_TELEGRAM_CHAT = os.getenv("TELEGRAM_BOT2_CHAT_ID", "")
_OBSIDIAN_PATH = Path("/Users/user/obsidian-vault/amara/neural")

PROPHET_QUEUE_FILE = Path(__file__).parent / "prophet_retraining_queue.json"

AGENTS = ["Jade", "Red", "Dakota", "Oracle", "Geo"]


def _supabase_headers() -> dict:
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _update_supabase_decision(decision_id: str, outcome: str, notes: str) -> None:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return
    http.patch(
        f"{_SUPABASE_URL}/rest/v1/decision_log",
        headers={**_supabase_headers(), "Prefer": "return=minimal"},
        params={"decision_id": f"eq.{decision_id}"},
        json={"outcome": outcome, "notes": notes,
              "outcome_recorded_at": datetime.now(timezone.utc).isoformat()},
        timeout=15,
    )


def _send_telegram(message: str) -> None:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT:
        return
    try:
        http.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception:
        pass


def _add_to_prophet_queue(entry: dict) -> None:
    import json
    queue = []
    if PROPHET_QUEUE_FILE.exists():
        with open(PROPHET_QUEUE_FILE) as f:
            try:
                queue = json.load(f)
            except Exception:
                queue = []
    queue.append(entry)
    with open(PROPHET_QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)


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
    Called when real-world outcome is confirmed.
    outcome: CORRECT | INCORRECT | PARTIAL
    """
    _update_supabase_decision(decision_id, outcome, notes)
    accuracy_tracker.log_outcome(decision_id, agent_id, outcome)

    accuracy = accuracy_tracker.get_agent_accuracy(agent_id, last_n=30)
    if accuracy is not None and accuracy < 0.60:
        from claude_code_interface import build_request
        build_request.file_build_request(
            trigger="ACCURACY_BELOW_THRESHOLD",
            agent_id=agent_id,
            problem=f"Agent {agent_id} accuracy dropped to {accuracy:.1%} over last 30 decisions.",
            evidence_summary=(
                f"decision_id={decision_id} outcome={outcome}. "
                f"Trailing accuracy={accuracy:.3f}"
            ),
            suggested_solution=(
                f"Review {agent_id} system prompt and evidence weighting. "
                f"Consider DSPy re-optimization with latest outcomes."
            ),
        )

    if entity_id:
        try:
            from graph import graphiti_client
            delta = 0.05 if outcome == "CORRECT" else (-0.15 if outcome == "INCORRECT" else -0.05)
            graphiti_client.adjust_edge_weight(
                node_id=entity_id,
                relationship="agent_prediction",
                delta=delta,
            )
        except Exception:
            pass

    if decision_type == "FRAC_WINDOW" and frac_date:
        _add_to_prophet_queue({
            "frac_date": frac_date,
            "decision_id": decision_id,
            "agent_id": agent_id,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })


def _pull_weekly_decisions() -> list:
    """Returns decisions from the past 7 days with known outcomes from Supabase."""
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        resp = http.get(
            f"{_SUPABASE_URL}/rest/v1/decision_log",
            headers=_supabase_headers(),
            params={
                "select": "*",
                "outcome": "not.is.null",
                "created_at": f"gte.{since}",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _write_obsidian_report(report: str, date_str: str) -> None:
    try:
        _OBSIDIAN_PATH.mkdir(parents=True, exist_ok=True)
        report_file = _OBSIDIAN_PATH / f"weekly_learning_{date_str}.md"
        report_file.write_text(report)
    except Exception:
        pass


def weekly_learning_run() -> None:
    """Scheduled: Sunday midnight CT."""
    import json as _json
    from neural import dspy_optimizer

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    decisions = _pull_weekly_decisions()

    agent_stats: dict[str, dict] = {a: {"decisions": 0, "correct": 0.0} for a in AGENTS}
    for d in decisions:
        agent = d.get("agent_id", "")
        if agent not in agent_stats:
            continue
        agent_stats[agent]["decisions"] += 1
        outcome = d.get("outcome", "")
        if outcome == "CORRECT":
            agent_stats[agent]["correct"] += 1.0
        elif outcome == "PARTIAL":
            agent_stats[agent]["correct"] += 0.5

    frac_dates_added = []
    for d in decisions:
        if d.get("decision_type") == "FRAC_WINDOW" and d.get("frac_date"):
            _add_to_prophet_queue({
                "frac_date": d["frac_date"],
                "decision_id": d.get("decision_id"),
                "agent_id": d.get("agent_id"),
                "queued_at": datetime.now(timezone.utc).isoformat(),
            })
            frac_dates_added.append(d["frac_date"])

    optimized_agents = []
    for agent in AGENTS:
        acc = accuracy_tracker.get_agent_accuracy(agent, last_n=30)
        if acc is not None and acc < 0.70:
            dspy_optimizer.optimize_agent(agent)
            optimized_agents.append(agent)

    rows = ""
    best_name, best_rate, worst_name, worst_rate = "", 0.0, "", 1.0
    for agent, stats in agent_stats.items():
        n = stats["decisions"]
        c = stats["correct"]
        rate = (c / n) if n > 0 else 0.0
        rows += f"| {agent:<7} | {n:<9} | {int(c):<7} | {rate:.0%}   |\n"
        if rate > best_rate:
            best_rate, best_name = rate, agent
        if n > 0 and rate < worst_rate:
            worst_rate, worst_name = rate, agent

    report = f"""# AMARA Neural Learning Report {date_str}

## Agent Accuracy This Week
| Agent   | Decisions | Correct | Rate |
|---------|-----------|---------|------|
{rows.rstrip()}

## Prophet Model Updates
Frac dates queued for retraining: {len(frac_dates_added)}
{chr(10).join(frac_dates_added) if frac_dates_added else 'None'}

## DSPy Optimizations Run
Agents optimized: {', '.join(optimized_agents) if optimized_agents else 'None — all above threshold'}

## Build Requests Filed
See claude_code_interface/build_log.json

## Next Week Focus
{'Re-optimize: ' + ', '.join(optimized_agents) if optimized_agents else 'All agents performing above 70% threshold.'}
"""

    _write_obsidian_report(report, date_str)

    telegram_msg = (
        f"🧠 AMARA WEEKLY LEARNING\n"
        f"Week: {date_str}\n"
        f"Best agent: {best_name} {best_rate:.0%}\n"
        f"Needs work: {worst_name} {worst_rate:.0%}\n"
        f"Prophet models retrained: {len(frac_dates_added)}\n"
        f"DSPy optimizations: {len(optimized_agents)}\n"
        f"Build requests filed: see build_log.json"
    )
    _send_telegram(telegram_msg)
