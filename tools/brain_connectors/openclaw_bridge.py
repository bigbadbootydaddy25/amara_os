#!/usr/bin/env python3
"""OpenClaw/Ollama bridge — calls Ollama as the primary AI backend."""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parents[2]))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip()
OLLAMA_MODEL = os.environ.get("OLLAMA_FAST_MODEL", "llama3.2:3b").strip()
AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def _query_ollama(prompt: str, model: str = OLLAMA_MODEL) -> dict:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def status() -> dict:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            return {
                "tool": "OpenClaw_Bridge",
                "backend": "Ollama",
                "status": "connected" if models else "no_models",
                "base_url": OLLAMA_BASE_URL,
                "model": OLLAMA_MODEL,
                "available_models": models,
            }
    except Exception as e:
        return {
            "tool": "OpenClaw_Bridge",
            "backend": "Ollama",
            "status": "not_configured",
            "message": f"connector placeholder ready — Ollama unreachable: {e}",
        }


def test() -> dict:
    return status()


def write_proof(data: dict, filename: str = "openclaw_status.json") -> Path:
    proof_dir = AMARA_BRAIN_BASE / "Tools" / "OpenClaw"
    proof_dir.mkdir(parents=True, exist_ok=True)
    path = proof_dir / filename
    data["timestamp"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path


def run_prompt(prompt: str) -> dict:
    result: dict = {
        "tool": "OpenClaw_Bridge",
        "backend": "Ollama",
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        raw = _query_ollama(prompt)
        result["status"] = "success"
        result["response"] = raw.get("response", "")
        result["eval_count"] = raw.get("eval_count", 0)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["message"] = "connector placeholder ready — Ollama unreachable"

    proof_path = write_proof(result, "openclaw_ollama_test.json")
    result["proof_file"] = str(proof_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw/Ollama Bridge")
    parser.add_argument("--prompt", help="Prompt to send via OpenClaw/Ollama bridge")
    parser.add_argument("--status", action="store_true", help="Check bridge status")
    args = parser.parse_args()

    if args.prompt:
        print(json.dumps(run_prompt(args.prompt), indent=2))
    elif args.status:
        print(json.dumps(status(), indent=2))
    else:
        parser.print_help()
