"""
LLM router for AMARA DEED crew.
Primary: Hermes3 via Ollama at localhost:11434.
Hard fail with error dict if Ollama is down (no silent fallback).
"""

import json
import logging
import os

import requests

from config import OLLAMA_BASE, OLLAMA_MODEL

log = logging.getLogger(__name__)


def _check_ollama() -> tuple[bool, str]:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, f"Ollama up — models: {models}"
        return False, f"Ollama HTTP {r.status_code}"
    except Exception as e:
        return False, f"Ollama unreachable: {e}"


def require_ollama() -> None:
    """Hard fail if Ollama is not reachable. Caller must handle."""
    ok, msg = _check_ollama()
    if not ok:
        raise RuntimeError(f"HARD FAIL — Ollama down: {msg}")


def complete(system_prompt: str, user_prompt: str, expect_json: bool = True) -> dict:
    """
    Call Hermes3 via Ollama. Returns dict.
    On failure returns {"error": ..., "detail": ...} — never raises.
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if expect_json:
            payload["format"] = "json"

        r = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        content = r.json()["message"]["content"]
        if expect_json:
            return json.loads(content)
        return {"response": content}

    except requests.exceptions.ConnectionError as e:
        return {"error": "ollama_unavailable", "detail": str(e)}
    except requests.exceptions.Timeout:
        return {"error": "ollama_timeout", "detail": "timed out after 120s"}
    except Exception as e:
        return {"error": "ollama_error", "detail": str(e)}


def is_available() -> bool:
    ok, _ = _check_ollama()
    return ok
