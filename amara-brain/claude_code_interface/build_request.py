"""
AMARA files build requests autonomously when it detects a gap it cannot handle.
Writes real markdown specs to AMARA_BRAIN/Build_Requests/.
Fires Telegram alert to Bot2.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_AMARA_BRAIN = Path(os.getenv("AMARA_BRAIN", str(Path(__file__).parent.parent / "Brain")))
_BUILD_REQUESTS_DIR = _AMARA_BRAIN / "Build_Requests"
_BUILD_LOG = _BUILD_REQUESTS_DIR / "build_log.json"

BUILD_TRIGGERS = {
    "ACCURACY_BELOW_THRESHOLD": 0.60,
    "NEW_DATA_SOURCE_DETECTED":  None,
    "NEW_FAILURE_PATTERN":       None,
    "OPERATOR_OUTSIDE_PATTERN":  None,
}


def _ensure_dir() -> None:
    _BUILD_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_log() -> list:
    _ensure_dir()
    if _BUILD_LOG.exists():
        try:
            return json.loads(_BUILD_LOG.read_text())
        except Exception:
            return []
    return []


def _save_log(entries: list) -> None:
    _ensure_dir()
    _BUILD_LOG.write_text(json.dumps(entries, indent=2))


def _write_spec(
    request_id: str,
    trigger: str,
    agent_id: str,
    problem: str,
    evidence_summary: str,
    suggested_solution: str,
    filed_at: str,
) -> Path:
    _ensure_dir()
    spec_file = _BUILD_REQUESTS_DIR / f"build_{request_id}.md"
    content = f"""# AMARA Build Request

**Request ID:** {request_id}
**Filed:** {filed_at}
**Trigger:** {trigger}
**Agent:** {agent_id}

## Problem
{problem}

## Evidence
{evidence_summary}

## Suggested Fix
{suggested_solution}

---

## Instructions for Claude Code
Paste this file into Claude Code to begin implementation.
The problem above was detected autonomously by AMARA.
Do not modify the problem statement.
Implement the suggested fix, test it, and push to the feature branch.
"""
    spec_file.write_text(content)
    return spec_file


def _send_telegram(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT2_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_BOT2_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
    except Exception as e:
        log.warning("Telegram alert failed: %s", e)


def file_build_request(
    trigger: str,
    agent_id: str,
    problem: str,
    evidence_summary: str,
    suggested_solution: str,
) -> str:
    """
    Files a build request. Writes to build_log.json and a markdown spec file.
    Fires Telegram alert to Bot2. Returns request_id.
    """
    if trigger not in BUILD_TRIGGERS:
        log.warning("Unknown trigger '%s' — filing anyway", trigger)

    request_id = str(uuid.uuid4())
    filed_at = datetime.now(timezone.utc).isoformat()

    entry = {
        "request_id": request_id,
        "filed_at": filed_at,
        "trigger": trigger,
        "agent_id": agent_id,
        "problem": problem,
        "evidence": evidence_summary,
        "suggested_solution": suggested_solution,
        "status": "PENDING",
    }
    log_entries = _load_log()
    log_entries.append(entry)
    _save_log(log_entries)

    spec_file = _write_spec(
        request_id, trigger, agent_id, problem, evidence_summary, suggested_solution, filed_at
    )

    log.info("Build request filed: %s (%s / %s)", request_id, trigger, agent_id)

    telegram_msg = (
        f"🔧 AMARA BUILD REQUEST\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Trigger: {trigger}\n"
        f"Agent: {agent_id}\n"
        f"Problem: {problem}\n"
        f"Evidence: {evidence_summary}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Suggested fix:\n{suggested_solution}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Review: {spec_file.name}"
    )
    _send_telegram(telegram_msg)

    return request_id


def list_pending() -> list:
    """Returns all PENDING build requests from build_log.json."""
    return [e for e in _load_log() if e.get("status") == "PENDING"]


def mark_resolved(request_id: str, resolution: str = "RESOLVED") -> None:
    """Updates a build request status in build_log.json."""
    entries = _load_log()
    for e in entries:
        if e.get("request_id") == request_id:
            e["status"] = resolution
            e["resolved_at"] = datetime.now(timezone.utc).isoformat()
    _save_log(entries)
