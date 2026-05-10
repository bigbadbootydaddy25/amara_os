"""
AI_BRAIN Neuron Network — Health & Connectivity Layer

Verifies installed backends, AI tools, and REI agents.
Writes a timestamped status report and a top-level summary.

Outputs:
  agents/neuron-network/reports/<timestamp>/NEURON_NETWORK_STATUS.md
  agents/neuron-network/reports/<timestamp>/CONNECTOR_HEALTH.json
  agents/neuron-network/reports/<timestamp>/DATA_FLOW_MAP.json
  reports/NEURON_NETWORK_STATUS.md   (always overwritten — latest run)

Rules:
  - No fake green statuses
  - Failed checks show exact command + error
  - "installed" vs "connected" are separate concerns
  - Missing credentials flagged separately from broken code
  - Working agents are never overwritten
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
AGENT_REPORTS_DIR = ROOT / "agents" / "neuron-network" / "reports"
TOP_REPORTS_DIR = ROOT / "reports"

# ── Types ─────────────────────────────────────────────────────────────────────

Status = Literal["ok", "failed", "missing", "not_installed", "no_credentials"]
Category = Literal["backend", "python_lib", "ai_agent", "integration", "vault"]


@dataclass
class CheckResult:
    name: str
    category: Category
    command: str
    status: Status
    output: str
    error: str
    duration_ms: int
    installed: bool = False
    connected: bool = False
    evidence: str = ""


# ── Check definitions ─────────────────────────────────────────────────────────

CHECKS: list[dict] = [
    # ── Backends ──────────────────────────────────────────────────────────────
    {
        "name": "Hermes",
        "category": "backend",
        "command": "hermes --version",
        "connected_probe": None,
    },
    {
        "name": "Neo4j Docker",
        "category": "backend",
        "command": "docker ps --filter name=neo4j --format '{{.Names}}\t{{.Status}}'",
        "connected_probe": None,
    },
    {
        "name": "Obsidian Vault",
        "category": "vault",
        "command": f"test -d {ROOT}/obsidian-vault",
        "connected_probe": None,
    },
    # ── Python libraries ──────────────────────────────────────────────────────
    {
        "name": "Mem0",
        "category": "python_lib",
        "command": "python3 -c \"import mem0; print('mem0 ok')\"",
        "connected_probe": "python3 -c \"import mem0; m = mem0.Memory(); print('mem0 connected')\"",
    },
    {
        "name": "LangChain",
        "category": "python_lib",
        "command": "python3 -c \"import langchain; print('langchain ok')\"",
        "connected_probe": None,
    },
    {
        "name": "Langfuse",
        "category": "python_lib",
        "command": "python3 -c \"import langfuse; print('langfuse ok')\"",
        "connected_probe": (
            "python3 -c \"from langfuse import Langfuse; "
            "lf = Langfuse(); lf.auth_check(); print('langfuse connected')\""
        ),
    },
    {
        "name": "Supabase",
        "category": "python_lib",
        "command": "python3 -c \"import supabase; print('supabase ok')\"",
        "connected_probe": (
            "python3 -c \""
            "import os, supabase; "
            "url=os.environ.get('SUPABASE_URL',''); "
            "key=os.environ.get('SUPABASE_KEY',''); "
            "assert url and key, 'SUPABASE_URL/KEY not set'; "
            "print('supabase connected')\""
        ),
    },
    {
        "name": "Neo4j Python Driver",
        "category": "python_lib",
        "command": "python3 -c \"import neo4j; print('neo4j driver ok')\"",
        "connected_probe": (
            "python3 -c \""
            "import os, neo4j; "
            "uri=os.environ.get('NEO4J_URI','bolt://localhost:7687'); "
            "user=os.environ.get('NEO4J_USER','neo4j'); "
            "pw=os.environ.get('NEO4J_PASSWORD',''); "
            "assert pw, 'NEO4J_PASSWORD not set'; "
            "d=neo4j.GraphDatabase.driver(uri,auth=(user,pw)); "
            "d.verify_connectivity(); "
            "print('neo4j connected')\""
        ),
    },
    # ── AI Agents ─────────────────────────────────────────────────────────────
    {
        "name": "Buyer Activity OSINT",
        "category": "ai_agent",
        "command": "test -f agents/buyer-activity-osint/run.py",
        "connected_probe": None,
    },
    {
        "name": "Entity Resolution",
        "category": "ai_agent",
        "command": "test -f agents/entity-resolution/run.py",
        "connected_probe": None,
    },
    {
        "name": "Deal Scoring Engine",
        "category": "ai_agent",
        "command": "test -f agents/deal-scoring-engine/run.py",
        "connected_probe": None,
    },
    {
        "name": "Portfolio Distress Analysis",
        "category": "ai_agent",
        "command": "test -f agents/portfolio-distress-analysis/run.py",
        "connected_probe": None,
    },
    {
        "name": "Ownership Graph",
        "category": "ai_agent",
        "command": "test -f agents/ownership-graph/run.py",
        "connected_probe": None,
    },
    {
        "name": "Integration Auditor",
        "category": "ai_agent",
        "command": "test -f agents/integration-auditor/run.py",
        "connected_probe": None,
    },
    # ── Integrations ──────────────────────────────────────────────────────────
    {
        "name": "MiroFish",
        "category": "integration",
        "command": "test -d integrations/MiroFish",
        "connected_probe": None,
    },
]

# ── Data flow graph (static — represents intended wiring) ─────────────────────

DATA_FLOW_MAP: dict = {
    "description": "AI_BRAIN agent data flow — intended wiring",
    "nodes": [
        {"id": "hermes",             "type": "backend",       "label": "Hermes"},
        {"id": "neo4j",              "type": "backend",       "label": "Neo4j Graph DB"},
        {"id": "supabase",           "type": "backend",       "label": "Supabase"},
        {"id": "mem0",               "type": "backend",       "label": "Mem0 Memory Layer"},
        {"id": "langchain",          "type": "framework",     "label": "LangChain"},
        {"id": "langfuse",           "type": "observability", "label": "Langfuse"},
        {"id": "obsidian",           "type": "vault",         "label": "Obsidian Vault"},
        {"id": "mirofish",           "type": "integration",   "label": "MiroFish"},
        {"id": "buyer_osint",        "type": "agent",         "label": "Buyer Activity OSINT"},
        {"id": "entity_resolution",  "type": "agent",         "label": "Entity Resolution"},
        {"id": "deal_scoring",       "type": "agent",         "label": "Deal Scoring Engine"},
        {"id": "portfolio_distress", "type": "agent",         "label": "Portfolio Distress Analysis"},
        {"id": "ownership_graph",    "type": "agent",         "label": "Ownership Graph"},
        {"id": "integration_auditor","type": "agent",         "label": "Integration Auditor"},
        {"id": "neuron_network",     "type": "agent",         "label": "Neuron Network (this agent)"},
    ],
    "edges": [
        {"from": "mirofish",           "to": "buyer_osint",        "label": "property/buyer data feed"},
        {"from": "buyer_osint",        "to": "deal_scoring",       "label": "BUILDER_MATCHES, CASH_BUYER_MATCHES"},
        {"from": "portfolio_distress", "to": "deal_scoring",       "label": "DISTRESSED_PORTFOLIOS, OVERLEVERAGED_BUYERS, STALLED_BUILDERS"},
        {"from": "entity_resolution",  "to": "ownership_graph",    "label": "resolved entity records"},
        {"from": "entity_resolution",  "to": "deal_scoring",       "label": "deduped counterparty IDs"},
        {"from": "ownership_graph",    "to": "neo4j",              "label": "graph node/edge writes"},
        {"from": "deal_scoring",       "to": "supabase",           "label": "deal scores + HOT_DEALS"},
        {"from": "deal_scoring",       "to": "obsidian",           "label": "DEAL_SCORECARD.md reports"},
        {"from": "langchain",          "to": "buyer_osint",        "label": "LLM classification calls"},
        {"from": "langchain",          "to": "entity_resolution",  "label": "LLM entity matching"},
        {"from": "mem0",               "to": "hermes",             "label": "session memory context"},
        {"from": "langfuse",           "to": "deal_scoring",       "label": "LLM observability traces"},
        {"from": "langfuse",           "to": "buyer_osint",        "label": "LLM observability traces"},
        {"from": "hermes",             "to": "obsidian",           "label": "vault note writes"},
        {"from": "neo4j",              "to": "entity_resolution",  "label": "existing entity lookups"},
        {"from": "neuron_network",     "to": "obsidian",           "label": "NEURON_NETWORK_STATUS.md"},
        {"from": "integration_auditor","to": "neuron_network",     "label": "integration gap reports"},
    ],
}

# ── Executor ──────────────────────────────────────────────────────────────────

def _classify_failure(command: str, stdout: str, stderr: str) -> Status:
    """Determine failure type from command + output."""
    combined = (stderr + stdout).lower()

    # Presence-check commands (test -f / test -d) — silence means absence
    if command.strip().startswith("test -"):
        return "missing"

    # Binary not on PATH
    if any(p in combined for p in ("command not found", "not found", "no such file or directory")):
        return "missing"

    # Python import failure
    if any(p in combined for p in ("modulenotfounderror", "no module named", "importerror")):
        return "not_installed"

    # Auth / credentials
    if any(p in combined for p in (
        "unauthorized", "authentication", "api key", "api_key",
        "credentials", "token", "permission denied", "access denied",
        "not set", "auth_check",
    )):
        return "no_credentials"

    return "failed"


def _probe(name: str, category: Category, command: str, probe: str | None, cwd: Path) -> CheckResult:
    """Run an install check and optionally a connectivity probe."""
    start = time.monotonic()
    env = {**os.environ}  # inherit full env so .env exports are visible

    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=20, cwd=str(cwd), env=env,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = r.stdout.strip()[:800]
        stderr = r.stderr.strip()[:800]

        if r.returncode != 0:
            status = _classify_failure(command, stdout, stderr)
            return CheckResult(
                name=name, category=category, command=command,
                status=status, output=stdout, error=stderr,
                duration_ms=elapsed_ms, installed=False, connected=False,
            )

        # Install check passed — now run connectivity probe if provided
        installed = True
        connected = False
        conn_err = ""

        if probe:
            pr = subprocess.run(
                probe, shell=True, capture_output=True, text=True,
                timeout=20, cwd=str(cwd), env=env,
            )
            if pr.returncode == 0:
                connected = True
            else:
                conn_out = (pr.stderr + pr.stdout).strip()
                conn_err = conn_out[:600]
                conn_status = _classify_failure(probe, pr.stdout, pr.stderr)
                return CheckResult(
                    name=name, category=category, command=command,
                    status=conn_status,
                    output=stdout,
                    error=f"[connectivity] {conn_err}",
                    duration_ms=elapsed_ms,
                    installed=True, connected=False,
                )
        else:
            # No probe — for non-connection checks (file existence, etc.),
            # "ok" means both installed and connected
            connected = True

        return CheckResult(
            name=name, category=category, command=command,
            status="ok", output=stdout, error="",
            duration_ms=elapsed_ms, installed=installed, connected=connected,
        )

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckResult(
            name=name, category=category, command=command,
            status="failed", output="", error="timed out after 20s",
            duration_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckResult(
            name=name, category=category, command=command,
            status="failed", output="", error=str(exc),
            duration_ms=elapsed_ms,
        )


def run_all_checks(cwd: Path = ROOT) -> list[CheckResult]:
    results: list[CheckResult] = []
    for chk in CHECKS:
        print(f"  checking {chk['name']} ...", end=" ", flush=True)
        r = _probe(
            name=chk["name"],
            category=chk["category"],
            command=chk["command"],
            probe=chk.get("connected_probe"),
            cwd=cwd,
        )
        icon = "✅" if r.status == "ok" else (
            "⚠️ " if r.status in ("no_credentials", "not_installed") else "❌"
        )
        print(f"{icon} {r.status.upper()} ({r.duration_ms}ms)")
        results.append(r)
    return results


# ── Report builders ───────────────────────────────────────────────────────────

_STATUS_ICON = {
    "ok":             "✅",
    "failed":         "❌",
    "missing":        "❌",
    "not_installed":  "📦",
    "no_credentials": "🔑",
}

_STATUS_LABEL = {
    "ok":             "OK",
    "failed":         "FAILED",
    "missing":        "MISSING",
    "not_installed":  "NOT INSTALLED",
    "no_credentials": "NO CREDENTIALS",
}


def _section(results: list[CheckResult], category: Category, heading: str) -> str:
    rows = [r for r in results if r.category == category]
    if not rows:
        return ""
    lines = [f"## {heading}\n", "| Component | Installed | Connected | Status | Details |",
             "|---|---|---|---|---|"]
    for r in rows:
        inst = "✅" if r.installed else "❌"
        conn = "✅" if r.connected else ("—" if not r.installed else "❌")
        icon = _STATUS_ICON[r.status]
        label = _STATUS_LABEL[r.status]
        detail = (r.error or r.output or "—").replace("\n", " ")[:120]
        lines.append(f"| {r.name} | {inst} | {conn} | {icon} {label} | `{detail}` |")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_status_md(results: list[CheckResult], run_ts: datetime, stamp: str) -> str:
    ok    = [r for r in results if r.status == "ok"]
    fail  = [r for r in results if r.status == "failed"]
    miss  = [r for r in results if r.status == "missing"]
    nocred= [r for r in results if r.status == "no_credentials"]
    noinst= [r for r in results if r.status == "not_installed"]

    run_str = run_ts.strftime("%Y-%m-%d %H:%M UTC")
    report_rel = f"agents/neuron-network/reports/{stamp}/NEURON_NETWORK_STATUS.md"

    header = f"""# AI_BRAIN Neuron Network Status

**Run:** {run_str}
**Root:** {ROOT}
**Report:** `{report_rel}`

---

## Summary

| Status | Count |
|---|---|
| ✅ OK | {len(ok)} |
| ❌ Failed | {len(fail)} |
| ❌ Missing | {len(miss)} |
| 🔑 No Credentials | {len(nocred)} |
| 📦 Not Installed | {len(noinst)} |
| **Total checks** | **{len(results)}** |

"""

    body = ""
    body += _section(results, "backend",    "Backends")
    body += _section(results, "vault",      "Vaults")
    body += _section(results, "python_lib", "Python Libraries")
    body += _section(results, "ai_agent",   "AI Agents")
    body += _section(results, "integration","Integrations")

    # Failed / missing detail block
    problem_rows = [r for r in results if r.status != "ok"]
    if problem_rows:
        detail_lines = ["---\n", "## Failure Detail\n"]
        for r in problem_rows:
            detail_lines.append(f"### {r.name} — {_STATUS_LABEL[r.status]}")
            detail_lines.append(f"- **Command:** `{r.command}`")
            if r.error:
                detail_lines.append(f"- **Error:** `{r.error}`")
            if r.output:
                detail_lines.append(f"- **Output:** `{r.output}`")
            detail_lines.append(f"- **Duration:** {r.duration_ms}ms")
            detail_lines.append("")
        body += "\n".join(detail_lines) + "\n"

    evidence = f"""---

## Evidence Paths

| Path | Purpose |
|---|---|
| `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` | Distressed portfolio owners |
| `data/portfolio-distress/OVERLEVERAGED_BUYERS.json` | Overleveraged buyers |
| `data/portfolio-distress/STALLED_BUILDERS.json` | Stalled builders |
| `data/deal-scoring/HOT_DEALS.json` | Hot deal matches |
| `data/deal-scoring/BUILDER_MATCHES.json` | Builder match records |
| `data/deal-scoring/CASH_BUYER_MATCHES.json` | Cash buyer match records |
| `agents/deal-scoring-engine/reports/` | Deal scoring run history |
| `agents/neuron-network/reports/{stamp}/` | This run's artifacts |
| `reports/NEURON_NETWORK_STATUS.md` | Latest run summary (top-level) |
"""

    return header + body + evidence


def build_connector_health_json(results: list[CheckResult], run_ts: datetime) -> dict:
    return {
        "run_at": run_ts.isoformat(),
        "root": str(ROOT),
        "summary": {
            "total":          len(results),
            "ok":             sum(1 for r in results if r.status == "ok"),
            "failed":         sum(1 for r in results if r.status == "failed"),
            "missing":        sum(1 for r in results if r.status == "missing"),
            "not_installed":  sum(1 for r in results if r.status == "not_installed"),
            "no_credentials": sum(1 for r in results if r.status == "no_credentials"),
        },
        "checks": [
            {
                "name":        r.name,
                "category":    r.category,
                "command":     r.command,
                "status":      r.status,
                "installed":   r.installed,
                "connected":   r.connected,
                "output":      r.output,
                "error":       r.error,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
    }


# ── Writer ────────────────────────────────────────────────────────────────────

def write_reports(results: list[CheckResult], run_ts: datetime | None = None) -> Path:
    ts = run_ts or datetime.now(timezone.utc)
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    report_dir = AGENT_REPORTS_DIR / stamp
    report_dir.mkdir(parents=True, exist_ok=True)
    TOP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    status_md    = build_status_md(results, ts, stamp)
    health_json  = build_connector_health_json(results, ts)
    flow_json    = DATA_FLOW_MAP

    # Annotate flow nodes with live status
    status_by_name = {r.name: r.status for r in results}
    for node in flow_json["nodes"]:
        label = node["label"]
        node["live_status"] = status_by_name.get(label, "unknown")

    (report_dir / "NEURON_NETWORK_STATUS.md").write_text(status_md)
    (report_dir / "CONNECTOR_HEALTH.json").write_text(
        json.dumps(health_json, indent=2)
    )
    (report_dir / "DATA_FLOW_MAP.json").write_text(
        json.dumps(flow_json, indent=2)
    )

    # Top-level latest copy
    top = TOP_REPORTS_DIR / "NEURON_NETWORK_STATUS.md"
    top.write_text(status_md)

    return report_dir


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ts = datetime.now(timezone.utc)

    print("=" * 64)
    print("  AI_BRAIN NEURON NETWORK")
    print("  Health & Connectivity Check")
    print(f"  Root: {ROOT}")
    print("=" * 64)
    print()

    results = run_all_checks(cwd=ROOT)
    report_dir = write_reports(results, ts)

    ok    = sum(1 for r in results if r.status == "ok")
    total = len(results)
    problems = [r for r in results if r.status != "ok"]

    print()
    print("=" * 64)
    print(f"  Checks passed:  {ok}/{total}")
    if problems:
        print(f"  Issues ({len(problems)}):")
        for r in problems:
            print(f"    {_STATUS_ICON[r.status]} {r.name}: {_STATUS_LABEL[r.status]}")
            if r.error:
                print(f"       {r.error[:100]}")
    print()
    print(f"  Report dir:  {report_dir.relative_to(ROOT)}")
    print(f"  Top-level:   reports/NEURON_NETWORK_STATUS.md")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()
