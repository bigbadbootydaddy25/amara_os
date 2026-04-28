#!/usr/bin/env python3
"""AMARA Brain Connector Router — status and test runner for all brain connectors."""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parents[2]))

AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def load_connectors() -> dict:
    from tools.brain_connectors import (
        ollama_connector,
        openclaw_bridge,
        supabase_connector,
        neo4j_connector,
        obsidian_connector,
        mem0_connector,
        mirofish_connector,
        notebooklm_connector,
        karpathy_llm_wiki_connector,
    )
    return {
        "Ollama": ollama_connector,
        "OpenClaw_Bridge": openclaw_bridge,
        "Supabase": supabase_connector,
        "Neo4j": neo4j_connector,
        "Obsidian": obsidian_connector,
        "Mem0": mem0_connector,
        "MiroFish": mirofish_connector,
        "NotebookLM": notebooklm_connector,
        "Karpathy_LLM_Wiki": karpathy_llm_wiki_connector,
    }


def _write_log(data: dict) -> Path:
    logs_dir = AMARA_BRAIN_BASE / "Tools" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "brain_connector_status.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def run_status() -> None:
    connectors = load_connectors()
    results = {}
    for name, conn in connectors.items():
        try:
            results[name] = conn.status()
        except Exception as e:
            results[name] = {"tool": name, "status": "error", "message": str(e)}

    output = {
        "brain_connector_status": "complete",
        "timestamp": datetime.now().isoformat(),
        "connectors": results,
    }
    proof_path = _write_log(output)
    print(json.dumps(output, indent=2))
    print(f"\n[Proof written to: {proof_path}]", file=sys.stderr)


def run_test_all() -> None:
    connectors = load_connectors()
    results = {}
    for name, conn in connectors.items():
        try:
            result = conn.test()
            results[name] = result
            conn.write_proof(result.copy())
        except Exception as e:
            results[name] = {"tool": name, "status": "error", "message": str(e)}

    output = {
        "brain_test_all": "complete",
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
    proof_path = _write_log(output)
    print(json.dumps(output, indent=2))
    print(f"\n[Proof written to: {proof_path}]", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AMARA Brain Connector Router")
    parser.add_argument("--status", action="store_true", help="Show status of all connectors")
    parser.add_argument("--test-all", action="store_true", help="Run test on all connectors and write proofs")
    args = parser.parse_args()

    if args.status:
        run_status()
    elif args.test_all:
        run_test_all()
    else:
        parser.print_help()
