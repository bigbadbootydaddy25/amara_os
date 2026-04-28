#!/usr/bin/env python3
import base64
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

NEO4J_URI = os.environ.get("NEO4J_URI", "").strip()
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j").strip()
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "").strip()
AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def status() -> dict:
    if not NEO4J_URI or not NEO4J_PASSWORD:
        return {
            "tool": "Neo4j",
            "status": "not_configured",
            "message": "connector placeholder ready — set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD",
        }
    try:
        http_uri = (
            NEO4J_URI.replace("bolt://", "http://")
            .replace("neo4j://", "http://")
            .rstrip("/")
        )
        creds = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()
        payload = json.dumps({"statements": [{"statement": "RETURN 1"}]}).encode()
        req = urllib.request.Request(
            f"{http_uri}/db/neo4j/tx/commit",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {creds}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
            errors = data.get("errors", [])
            if errors:
                return {"tool": "Neo4j", "status": "error", "errors": errors}
            return {"tool": "Neo4j", "status": "connected", "uri": NEO4J_URI}
    except Exception as e:
        return {"tool": "Neo4j", "status": "error", "message": str(e)}


def test() -> dict:
    return status()


def write_proof(data: dict) -> Path:
    proof_dir = AMARA_BRAIN_BASE / "Tools" / "Neo4j"
    proof_dir.mkdir(parents=True, exist_ok=True)
    path = proof_dir / "neo4j_status.json"
    data["timestamp"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path
