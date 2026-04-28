#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip()
AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def status() -> dict:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            return {
                "tool": "Ollama",
                "status": "connected",
                "base_url": OLLAMA_BASE_URL,
                "models": models,
            }
    except Exception as e:
        return {
            "tool": "Ollama",
            "status": "not_configured",
            "message": f"connector placeholder ready — Ollama unreachable at {OLLAMA_BASE_URL}: {e}",
        }


def test() -> dict:
    s = status()
    if s["status"] != "connected":
        return s
    try:
        payload = json.dumps(
            {"model": "llama3.2:3b", "prompt": "ping", "stream": False}
        ).encode()
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return {
                "tool": "Ollama",
                "status": "ok",
                "response_snippet": data.get("response", "")[:80],
            }
    except Exception as e:
        return {"tool": "Ollama", "status": "error", "message": str(e)}


def write_proof(data: dict) -> Path:
    proof_dir = AMARA_BRAIN_BASE / "Tools" / "Ollama"
    proof_dir.mkdir(parents=True, exist_ok=True)
    path = proof_dir / "ollama_status.json"
    data["timestamp"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path
