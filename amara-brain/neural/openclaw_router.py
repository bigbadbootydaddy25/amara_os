"""
Central inference router — ALL agent inference calls go through here.
No agent calls Ollama directly. No agent calls Anthropic directly.
OpenClaw is the spine.
"""

import json
import requests
from datetime import datetime, timezone
from pathlib import Path

from neural import model_selector, accuracy_tracker

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_ERROR_LOG = _LOG_DIR / "openclaw_error.log"

OPENCLAW_BASE = "http://127.0.0.1:18789"


def route(
    task_type: str,
    messages: list,
    output_format: str = "json",
) -> dict:
    """
    Routes inference through OpenClaw.
    Logs every call to accuracy_tracker.
    Raises RuntimeError on non-200 — never silently fails.
    """
    model = model_selector.get_best_model(task_type)

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

        accuracy_tracker.log_inference(
            task_type=task_type,
            model=model,
            tokens_in=data["usage"]["prompt_tokens"],
            tokens_out=data["usage"]["completion_tokens"],
        )

        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

    except Exception as e:
        with open(_ERROR_LOG, "a") as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} | {task_type} | {str(e)}\n"
            )
        raise RuntimeError(f"OpenClaw routing failed: {e}")
