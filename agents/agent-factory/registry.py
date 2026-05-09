"""
Agent registry — persists and manages the lifecycle of all factory-generated agents.

Registry file: registry/AGENT_REGISTRY.json

Lifecycle:
  PENDING_APPROVAL → ACTIVE      (requires human --activate)
  ACTIVE           → QUARANTINED (via --quarantine)
  QUARANTINED      → RETIRED     (via --retire)
  any              → RETIRED     (via --retire)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from models import AgentRegistration, VALID_STATUSES, WorkflowSpec

_REGISTRY_FILE = Path(__file__).parent / "registry" / "AGENT_REGISTRY.json"

_EMPTY_REGISTRY: Dict = {
    "agents": [],
    "quarantined_workflows": [],
    "last_updated": "",
}


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_registry(registry_path: Path | None = None) -> Dict:
    path = registry_path or _REGISTRY_FILE
    if not path.exists():
        return _EMPTY_REGISTRY.copy()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _EMPTY_REGISTRY.copy()


def save_registry(data: Dict, registry_path: Path | None = None) -> None:
    path = registry_path or _REGISTRY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def list_agents(
    registry_path: Path | None = None,
) -> List[AgentRegistration]:
    data = load_registry(registry_path)
    return [AgentRegistration.from_dict(a) for a in data.get("agents", [])]


def get_agent(
    agent_name: str,
    registry_path: Path | None = None,
) -> Optional[AgentRegistration]:
    for agent in list_agents(registry_path):
        if agent.agent_name == agent_name:
            return agent
    return None


def get_quarantined_sources(registry_path: Path | None = None) -> Set[str]:
    data = load_registry(registry_path)
    quarantined_agents = {
        a["agent_name"]
        for a in data.get("agents", [])
        if a.get("status") == "QUARANTINED"
    }
    quarantined_workflows = set(data.get("quarantined_workflows", []))
    return quarantined_agents | quarantined_workflows


def workflow_id_exists(
    workflow_id: str,
    registry_path: Path | None = None,
) -> bool:
    return any(a.workflow_id == workflow_id for a in list_agents(registry_path))


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def register_agent(
    spec: WorkflowSpec,
    output_path: str,
    risk_level: str,
    registry_path: Path | None = None,
) -> AgentRegistration:
    """
    Add a new agent entry with PENDING_APPROVAL status.
    Raises ValueError if the workflow_id is already registered.
    """
    if workflow_id_exists(spec.workflow_id, registry_path):
        raise ValueError(
            f"Workflow '{spec.workflow_id}' is already registered. "
            "Use a unique workflow_id."
        )

    registration = AgentRegistration(
        agent_name=spec.agent_name,
        workflow_id=spec.workflow_id,
        version=spec.version,
        status="PENDING_APPROVAL",
        risk_level=risk_level,
        description=spec.description,
        output_path=output_path,
        tags=spec.tags,
        memory_sources=spec.memory_sources,
    )

    data = load_registry(registry_path)
    data["agents"].append(registration.to_dict())
    save_registry(data, registry_path)
    return registration


def set_agent_status(
    agent_name: str,
    new_status: str,
    registry_path: Path | None = None,
) -> AgentRegistration:
    """Change an agent's status. Returns the updated registration."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {VALID_STATUSES}")

    data = load_registry(registry_path)
    for entry in data["agents"]:
        if entry["agent_name"] == agent_name:
            entry["status"] = new_status
            entry["last_updated"] = datetime.utcnow().isoformat() + "Z"
            save_registry(data, registry_path)
            return AgentRegistration.from_dict(entry)

    raise KeyError(f"Agent '{agent_name}' not found in registry")


def activate_agent(
    agent_name: str,
    registry_path: Path | None = None,
) -> AgentRegistration:
    agent = get_agent(agent_name, registry_path)
    if agent is None:
        raise KeyError(f"Agent '{agent_name}' not found in registry")
    if agent.status == "ACTIVE":
        raise ValueError(f"Agent '{agent_name}' is already ACTIVE")
    if agent.status == "QUARANTINED":
        raise ValueError(
            f"Agent '{agent_name}' is QUARANTINED and cannot be activated directly. "
            "Retire it and generate a new agent instead."
        )
    return set_agent_status(agent_name, "ACTIVE", registry_path)


# ---------------------------------------------------------------------------
# Formatting helpers (for --list output)
# ---------------------------------------------------------------------------

def format_registry_table(agents: List[AgentRegistration]) -> str:
    if not agents:
        return "No agents registered."

    col_widths = {
        "name": max(len("Name"), max(len(a.agent_name) for a in agents)),
        "wf": max(len("Workflow"), max(len(a.workflow_id) for a in agents)),
        "ver": max(len("Version"), max(len(a.version) for a in agents)),
        "status": max(len("Status"), max(len(a.status) for a in agents)),
        "risk": max(len("Risk"), max(len(a.risk_level) for a in agents)),
    }

    def row(name, wf, ver, status, risk, tags=""):
        return (
            f"{name:<{col_widths['name']}}  "
            f"{wf:<{col_widths['wf']}}  "
            f"{ver:<{col_widths['ver']}}  "
            f"{status:<{col_widths['status']}}  "
            f"{risk:<{col_widths['risk']}}  "
            f"{tags}"
        )

    sep = "-" * (sum(col_widths.values()) + 14)
    lines = [
        "\nAgent Registry",
        "=" * 14,
        row("Name", "Workflow", "Version", "Status", "Risk", "Tags"),
        sep,
    ]
    for a in agents:
        lines.append(row(
            a.agent_name,
            a.workflow_id,
            a.version,
            a.status,
            a.risk_level,
            ", ".join(a.tags[:3]),
        ))
    return "\n".join(lines) + "\n"
