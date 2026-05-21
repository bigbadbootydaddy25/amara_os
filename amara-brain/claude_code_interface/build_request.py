"""
AMARA files build requests autonomously when it detects a gap it cannot handle.
You review build_log.json and paste the generated spec into Claude Code.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_BUILD_LOG = _BASE_DIR / "build_log.json"
_SPECS_DIR = _BASE_DIR / "specs"
_SPECS_DIR.mkdir(parents=True, exist_ok=True)

_TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT2_TOKEN", "")
_TELEGRAM_CHAT = os.getenv("TELEGRAM_BOT2_CHAT_ID", "")

BUILD_TRIGGERS = {
    "ACCURACY_BELOW_THRESHOLD": 0.60,
    "NEW_DATA_SOURCE_DETECTED":  None,
    "NEW_FAILURE_PATTERN":       None,
    "OPERATOR_OUTSIDE_PATTERN":  None,
}


def _load_log() -> list:
    if _BUILD_LOG.exists():
        with open(_BUILD_LOG) as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def _save_log(entries: list) -> None:
    with open(_BUILD_LOG, "w") as f:
        json.dump(entries, f, indent=2)


def _send_telegram(message: str) -> None:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception:
        pass


def _write_spec(request_id: str, trigger: str, agent_id: str,
                problem: str, evidence_summary: str, suggested_solution: str) -> Path:
    spec_file = _SPECS_DIR / f"build_{request_id}.md"
    content = f"""# AMARA Build Request — {request_id}

**Filed:** {datetime.now(timezone.utc).isoformat()}
**Trigger:** {trigger}
**Agent:** {agent_id}

## Problem
{problem}

## Evidence
{evidence_summary}

## Suggested Fix
{suggested_solution}

---
*Paste this file into Claude Code to begin implementation.*
"""
    spec_file.write_text(content)
    return spec_file


def file_build_request(
    trigger: str,
    agent_id: str,
    problem: str,
    evidence_summary: str,
    suggested_solution: str,
) -> str:
    """
    AMARA calls this autonomously when it detects a gap it cannot handle.
    Appends to build_log.json, fires Telegram alert, writes build spec.
    Returns request_id.
    """
    request_id = str(uuid.uuid4())
    entry = {
        "request_id": request_id,
        "filed_at": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "agent_id": agent_id,
        "problem": problem,
        "evidence": evidence_summary,
        "suggested_solution": suggested_solution,
        "status": "PENDING",
    }

    log = _load_log()
    log.append(entry)
    _save_log(log)

    spec_file = _write_spec(
        request_id, trigger, agent_id, problem, evidence_summary, suggested_solution
    )

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
        f"Action: Review build_log.json\n"
        f"then run Claude Code with\n"
        f"the attached specification."
    )
    _send_telegram(telegram_msg)

    return request_id
