"""
Central inference router — all agent calls go through OpenClaw.

Protocol findings (from openclaw npm dist inspection):
  - The OpenClaw gateway uses WebSocket-based RPC, NOT HTTP REST.
  - DEFAULT_GATEWAY_PORT is 18789 (WebSocket gateway endpoint).
  - Port 18791 is an authenticated HTTP relay in the local setup.
  - Neither port exposes /v1/chat/completions or /v1/models.
  - Agent invocation requires the `openclaw agent` CLI (WebSocket RPC).
  - Gateway auth env var: OPENCLAW_GATEWAY_TOKEN
  - Config file fallback: ~/.openclaw/openclaw.json → gateway.auth.token
  - CLI flag: openclaw agent --message "..." --token <token> --json

route() always returns a dict — never raises, never hallucinates.
"""

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

OPENCLAW_GATEWAY_HTTP = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18791")
_TOKEN_FILE = Path.home() / ".openclaw" / "openclaw.json"
_LOG_DIR = Path(__file__).parent.parent / "Brain" / "Logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_ERROR_LOG = _LOG_DIR / "openclaw_error.log"

TASK_MODEL_MAP = {
    "pain_point_analysis": "hermes3",
    "monday_debrief":      "hermes3",
    "logistics_risk":      "hermes3",
    "market_intelligence": "hermes3",
    "harvey_synthesis":    "hermes3",
    "premortem_check":     "hermes3",
    "prompt_optimization": "hermes3",
    "build_request":       "hermes3",
}


def _log_error(task_type: str, error: str) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} | {task_type} | {error}\n"
    with open(_ERROR_LOG, "a") as f:
        f.write(line)
    log.error("OpenClaw error [%s]: %s", task_type, error)


def _load_token() -> str | None:
    """
    Load OpenClaw gateway Bearer token.
    Priority: OPENCLAW_GATEWAY_TOKEN env var → ~/.openclaw/openclaw.json → OPENCLAW_API_KEY.
    """
    token = os.getenv("OPENCLAW_GATEWAY_TOKEN", "").strip()
    if token:
        return token
    if _TOKEN_FILE.exists():
        try:
            data = json.loads(_TOKEN_FILE.read_text())
            t = data.get("gateway", {}).get("auth", {}).get("token", "").strip()
            if t:
                return t
        except Exception as e:
            log.warning("Failed to read OpenClaw token file %s: %s", _TOKEN_FILE, e)
    # Legacy fallback used in earlier setup
    legacy = os.getenv("OPENCLAW_API_KEY", "").strip()
    return legacy if legacy and legacy.lower() != "none" else None


def _build_prompt(task_type: str, messages: list) -> str:
    """Flatten messages list to a single prompt string for the CLI."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.insert(0, f"[System: {content}]")
        elif content:
            parts.append(content)
    return "\n".join(parts) if parts else task_type


def _gateway_reachable(token: str | None) -> bool:
    """Check if the HTTP relay at OPENCLAW_GATEWAY_HTTP responds (any 2xx/3xx/4xx)."""
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.get(OPENCLAW_GATEWAY_HTTP + "/", headers=headers, timeout=5)
        return r.status_code < 500
    except Exception:
        return False


def _invoke_via_cli(prompt: str, task_type: str, token: str | None) -> dict:
    """
    Invoke OpenClaw agent via the `openclaw agent` CLI subprocess.
    The CLI speaks WebSocket RPC to the gateway — this is the supported
    Python-to-gateway integration path.
    """
    cli = shutil.which("openclaw")
    if not cli:
        return {
            "error": "openclaw_cli_not_found",
            "detail": (
                "openclaw binary not found in PATH. "
                "Install openclaw (npm install -g openclaw) and ensure it is in PATH."
            ),
            "task_type": task_type,
        }

    cmd = [cli, "agent", "--message", prompt, "--json"]
    if token:
        cmd += ["--token", token]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            err = result.stderr.strip() or f"exit code {result.returncode}"
            _log_error(task_type, f"CLI error: {err}")
            return {
                "error": "openclaw_cli_error",
                "detail": err,
                "task_type": task_type,
            }

        raw = result.stdout.strip()
        if not raw:
            _log_error(task_type, "CLI returned empty output")
            return {
                "error": "openclaw_cli_empty_output",
                "detail": "No output from openclaw agent CLI",
                "task_type": task_type,
            }

        try:
            data = json.loads(raw)
            # Gateway payload fields: text, status, sessionKey, runId
            text = data.get("text") or data.get("response") or raw
            return {
                "model": "openclaw/agent",
                "response": text,
                "task_type": task_type,
                "session_key": data.get("sessionKey"),
                "run_id": data.get("runId"),
            }
        except json.JSONDecodeError:
            return {
                "model": "openclaw/agent",
                "response": raw,
                "task_type": task_type,
            }

    except subprocess.TimeoutExpired:
        _log_error(task_type, "CLI timed out after 120s")
        return {
            "error": "openclaw_cli_timeout",
            "detail": "openclaw agent CLI timed out after 120s",
            "task_type": task_type,
        }
    except Exception as e:
        _log_error(task_type, f"CLI exception: {e}")
        return {
            "error": "openclaw_cli_exception",
            "detail": str(e),
            "task_type": task_type,
        }


def is_available() -> bool:
    """Returns True if the OpenClaw CLI is in PATH."""
    return shutil.which("openclaw") is not None


def route(
    task_type: str,
    messages: list,
    output_format: str = "json",
) -> dict:
    """
    Routes inference through OpenClaw via the `openclaw agent` CLI.

    OpenClaw uses WebSocket-based RPC — there is no /v1/chat/completions
    or /v1/models REST endpoint. The CLI is the supported integration path.

    Returns a dict on all paths — never raises, never hallucinates.
    """
    token = _load_token()
    prompt = _build_prompt(task_type, messages)

    if shutil.which("openclaw"):
        return _invoke_via_cli(prompt, task_type, token)

    # CLI not in PATH — check if HTTP relay is reachable to give a precise error
    if _gateway_reachable(token):
        _log_error(task_type, "gateway reachable but CLI missing")
        return {
            "error": "openclaw_gateway_reachable_but_no_chat_route_found",
            "detail": (
                f"OpenClaw HTTP relay is reachable at {OPENCLAW_GATEWAY_HTTP} "
                "but exposes no REST chat endpoint (not OpenAI-compatible). "
                "The openclaw CLI is required for agent invocation via WebSocket RPC. "
                "Install openclaw (npm install -g openclaw) and ensure it is in PATH."
            ),
            "task_type": task_type,
            "gateway_url": OPENCLAW_GATEWAY_HTTP,
        }

    _log_error(task_type, f"openclaw CLI not found and HTTP relay at {OPENCLAW_GATEWAY_HTTP} unreachable")
    return {
        "error": "openclaw_unavailable",
        "detail": (
            f"openclaw CLI not found in PATH and HTTP relay at "
            f"{OPENCLAW_GATEWAY_HTTP} is not reachable."
        ),
        "task_type": task_type,
    }
