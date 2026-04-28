#!/usr/bin/env python3
import json
import os
from pathlib import Path
from datetime import datetime

MEM0_API_KEY = os.environ.get("MEM0_API_KEY", "").strip()
AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def status() -> dict:
    if not MEM0_API_KEY:
        return {
            "tool": "Mem0",
            "status": "not_configured",
            "message": "connector placeholder ready — set MEM0_API_KEY when Mem0 is installed",
        }
    return {
        "tool": "Mem0",
        "status": "configured",
        "message": "API key present — install mem0ai package to activate",
    }


def test() -> dict:
    return status()


def write_proof(data: dict) -> Path:
    proof_dir = AMARA_BRAIN_BASE / "Tools" / "Mem0"
    proof_dir.mkdir(parents=True, exist_ok=True)
    path = proof_dir / "mem0_status.json"
    data["timestamp"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path
