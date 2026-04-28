#!/usr/bin/env python3
import json
import os
from pathlib import Path
from datetime import datetime

OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def status() -> dict:
    if not OBSIDIAN_VAULT_PATH:
        return {
            "tool": "Obsidian",
            "status": "not_configured",
            "message": "connector placeholder ready — set OBSIDIAN_VAULT_PATH",
        }
    vault = Path(OBSIDIAN_VAULT_PATH)
    if vault.exists() and vault.is_dir():
        md_count = len(list(vault.rglob("*.md")))
        return {
            "tool": "Obsidian",
            "status": "vault_accessible",
            "vault_path": OBSIDIAN_VAULT_PATH,
            "markdown_files": md_count,
        }
    return {
        "tool": "Obsidian",
        "status": "not_configured",
        "message": f"vault path not found or not a directory: {OBSIDIAN_VAULT_PATH}",
    }


def test() -> dict:
    return status()


def write_proof(data: dict) -> Path:
    proof_dir = AMARA_BRAIN_BASE / "Tools" / "Obsidian"
    proof_dir.mkdir(parents=True, exist_ok=True)
    path = proof_dir / "obsidian_status.json"
    data["timestamp"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path
