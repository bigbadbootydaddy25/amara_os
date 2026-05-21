"""
Central inference router — all agent calls go through here.
Calls OpenClaw at 127.0.0.1:18789 (OpenAI-compatible endpoint).
If unavailable, returns a structured error dict — never hallucinate.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

OPENCLAW_BASE = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789")
_LOG_DIR = Path(__file__).parent.parent / "Brain" / "Logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_ERROR_LOG = _LOG_DIR / "openclaw_error.log"

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


def _log_error(task_type: str, error: str) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} | {task_type} | {error}\n"
    with open(_ERROR_LOG, "a") as f:
        f.write(line)
    log.error("OpenClaw error [%s]: %s", task_type, error)


def _get_model(task_type: str) -> str:
    return TASK_MODEL_MAP.get(task_type, "hermes3")


def is_available() -> bool:
    """Returns True if OpenClaw is reachable."""
    try:
        r = requests.get(f"{OPENCLAW_BASE}/v1/models", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def route(
    task_type: str,
    messages: list,
    output_format: str = "json",
) -> dict:
    """
    Routes inference through OpenClaw.
    Returns parsed dict from model response.
    If OpenClaw is unavailable, returns:
      {"error": "openclaw_unavailable", "detail": "<reason>", "task_type": task_type}
    Never hallucinates a response.
    """
    model = _get_model(task_type)

    try:
        response = requests.post(
            f"{OPENCLAW_BASE}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            },
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    except requests.exceptions.ConnectionError as e:
        detail = str(e)
        _log_error(task_type, f"ConnectionError: {detail}")
        return {
            "error": "openclaw_unavailable",
            "detail": f"OpenClaw not reachable at {OPENCLAW_BASE}",
            "task_type": task_type,
        }
    except requests.exceptions.Timeout as e:
        detail = str(e)
        _log_error(task_type, f"Timeout: {detail}")
        return {
            "error": "openclaw_timeout",
            "detail": f"OpenClaw timed out after 90s",
            "task_type": task_type,
        }
    except Exception as e:
        detail = str(e)
        _log_error(task_type, f"Unexpected: {detail}")
        return {
            "error": "openclaw_error",
            "detail": detail,
            "task_type": task_type,
        }
