"""
Deployment utilities for amara-brain services.
"""

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent


def restart_services() -> None:
    """Restarts the amara-brain run.py process."""
    subprocess.run([sys.executable, str(_ROOT / "run.py"), "--restart"], check=False)


def status() -> dict:
    """Returns basic health status of amara-brain components."""
    import requests

    components = {
        "openclaw": False,
        "neo4j": False,
    }
    try:
        r = requests.get("http://127.0.0.1:18789/v1/models", timeout=5)
        components["openclaw"] = r.status_code == 200
    except Exception:
        pass
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", __import__("os").getenv("NEO4J_PASSWORD", "")),
        )
        driver.verify_connectivity()
        components["neo4j"] = True
        driver.close()
    except Exception:
        pass
    return components
