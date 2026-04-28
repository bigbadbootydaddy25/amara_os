#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
AMARA_BRAIN_BASE = Path(__file__).parents[2] / "AMARA_BRAIN"


def status() -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {
            "tool": "Supabase",
            "status": "not_configured",
            "message": "connector placeholder ready — set SUPABASE_URL and SUPABASE_ANON_KEY",
        }
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            return {
                "tool": "Supabase",
                "status": "connected",
                "url": SUPABASE_URL,
                "http_status": resp.status,
            }
    except urllib.error.HTTPError as e:
        if e.code in (200, 204):
            return {"tool": "Supabase", "status": "connected", "url": SUPABASE_URL}
        return {"tool": "Supabase", "status": "error", "http_code": e.code, "message": str(e)}
    except Exception as e:
        return {"tool": "Supabase", "status": "error", "message": str(e)}


def test() -> dict:
    return status()


def write_proof(data: dict) -> Path:
    proof_dir = AMARA_BRAIN_BASE / "Tools" / "Supabase"
    proof_dir.mkdir(parents=True, exist_ok=True)
    path = proof_dir / "supabase_status.json"
    data["timestamp"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path
