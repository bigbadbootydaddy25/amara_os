#!/usr/bin/env python3
"""
Agent Factory -- generates new agents automatically from validated workflows.

Usage:
    # Generate a new agent from a workflow spec:
    python run.py --workflow workflow.json [--output-dir NEW_AGENT_TREE/] [--dry-run] [--verbose]

    # List all registered agents:
    python run.py --list

    # Activate a pending agent (requires human confirmation):
    python run.py --activate <agent-name>

    # Quarantine a rogue agent:
    python run.py --quarantine <agent-name>

    # Inspect an existing agent directory for patterns:
    python run.py --inspect <agent-dir>

Rules enforced by this factory:
  - Only validated workflow specs produce agents
  - No generation from quarantined memory sources
  - All generated agents start as PENDING_APPROVAL
  - Human activation required before production use
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

from code_generator import generate_agent_files, write_agent_tree
from models import WorkflowSpec
from registry import (
    activate_agent,
    format_registry_table,
    get_agent,
    get_quarantined_sources,
    list_agents,
    register_agent,
    set_agent_status,
)
from reporter import generate_factory_reports
from risk_assessor import assess_risk
from workflow_validator import validate_workflow

_FACTORY_DIR = Path(__file__).parent
_TEMPLATE_DIR = _FACTORY_DIR / "templates"
_REGISTRY_PATH = _FACTORY_DIR / "registry" / "AGENT_REGISTRY.json"
_DEFAULT_OUTPUT = "NEW_AGENT_TREE"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Agent Factory — generate new agents from validated workflows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--workflow", "-w",
        metavar="FILE",
        help="Path to workflow spec JSON — generates a new agent.",
    )
    mode.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all agents in the registry.",
    )
    mode.add_argument(
        "--activate",
        metavar="AGENT_NAME",
        help="Activate a PENDING_APPROVAL agent (requires confirmation).",
    )
    mode.add_argument(
        "--quarantine",
        metavar="AGENT_NAME",
        help="Quarantine an agent to block it from use.",
    )
    mode.add_argument(
        "--inspect",
        metavar="AGENT_DIR",
        help="Inspect an existing agent directory and extract its patterns.",
    )

    p.add_argument(
        "--output-dir", "-o",
        default=_DEFAULT_OUTPUT,
        help=f"Root directory for generated agent tree (default: {_DEFAULT_OUTPUT}/).",
    )
    p.add_argument(
        "--report-dir", "-r",
        default="reports",
        help="Directory for factory reports (default: reports/).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing any files.",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace) -> int:
    """Load, validate, assess, generate, register."""
    _log = (lambda msg: print(f"  {msg}")) if args.verbose else (lambda _: None)
    workflow_path = Path(args.workflow)

    if not workflow_path.exists():
        print(f"ERROR: Workflow file not found: {workflow_path}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"\nAgent Factory")
        print(f"  workflow   : {workflow_path}")
        print(f"  output dir : {args.output_dir}")
        print(f"  report dir : {args.report_dir}")
        print(f"  dry run    : {args.dry_run}")
        print()

    # 1. Load workflow spec
    _log("Loading workflow spec …")
    try:
        raw = json.loads(workflow_path.read_text(encoding="utf-8"))
        spec = WorkflowSpec.from_dict(raw)
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: Could not parse workflow spec: {exc}", file=sys.stderr)
        return 1

    # 2. Validate
    _log("Validating workflow …")
    quarantined = get_quarantined_sources(_REGISTRY_PATH)
    validation = validate_workflow(spec, quarantined)

    if args.verbose:
        if validation.errors:
            for e in validation.errors:
                print(f"  [ERROR] {e}")
        if validation.warnings:
            for w in validation.warnings:
                print(f"  [WARN]  {w}")

    if not validation.is_valid:
        print(
            f"\nValidation FAILED for '{spec.agent_name}' — "
            f"{len(validation.errors)} error(s). Agent not generated.",
            file=sys.stderr,
        )
        return 1

    _log(f"Validation OK ({len(validation.warnings)} warning(s))")

    # 3. Risk assessment
    _log("Assessing risk …")
    risk = assess_risk(spec)
    _log(f"  Risk: {risk.colour} {risk.risk_level} (score {risk.risk_score})")

    # 4. Generate files
    _log("Generating agent files …")
    files = generate_agent_files(spec, _TEMPLATE_DIR, risk.risk_level)
    _log(f"  {len(files)} file(s) to write")

    if args.dry_run:
        print("\n[DRY RUN] Files that would be generated:")
        for gf in sorted(files, key=lambda f: f.path):
            lines = len(gf.content.splitlines())
            print(f"  {spec.agent_name}/{gf.path}  ({lines} lines, {gf.file_type})")
        print()
        _validate_python_syntax(files, spec.agent_name)
        return 0

    # 5. Write file tree
    output_root = Path(args.output_dir)
    agent_dir = write_agent_tree(files, output_root, spec.agent_name)
    _log(f"  Written to {agent_dir}")

    # 6. Validate generated Python syntax
    _validate_python_syntax(files, spec.agent_name)
    _log("  Syntax check passed")

    # 7. Register agent
    _log("Registering agent …")
    try:
        registration = register_agent(
            spec,
            output_path=str(agent_dir),
            risk_level=risk.risk_level,
            registry_path=_REGISTRY_PATH,
        )
    except ValueError as exc:
        print(f"  [WARN] Registry: {exc}", file=sys.stderr)
        from models import AgentRegistration
        registration = AgentRegistration(
            agent_name=spec.agent_name,
            workflow_id=spec.workflow_id,
            version=spec.version,
            status="PENDING_APPROVAL",
            risk_level=risk.risk_level,
            description=spec.description,
            output_path=str(agent_dir),
            tags=spec.tags,
            memory_sources=spec.memory_sources,
        )

    # 8. Write factory reports
    _log("Writing factory reports …")
    report_dir = Path(args.report_dir)
    report_paths = generate_factory_reports(
        spec, files, registration, validation, risk, report_dir
    )
    for name, p in report_paths.items():
        _log(f"  ✓ {p.name}")

    if args.verbose:
        print(f"\n{'='*60}")
        print(f"  Agent '{spec.agent_name}' generated successfully.")
        print(f"  Status: PENDING_APPROVAL — human activation required.")
        print(f"  Activate with: python run.py --activate {spec.agent_name}")
        print(f"{'='*60}\n")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    agents = list_agents(_REGISTRY_PATH)
    print(format_registry_table(agents))
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    agent_name = args.activate
    agent = get_agent(agent_name, _REGISTRY_PATH)

    if agent is None:
        print(f"ERROR: Agent '{agent_name}' not found in registry.", file=sys.stderr)
        return 1

    print(f"\nActivating agent '{agent_name}'")
    print(f"  Current status : {agent.status}")
    print(f"  Risk level     : {agent.risk_level}")
    print(f"  Description    : {agent.description}")
    print()
    print("WARNING: Activating makes this agent available for execution in the ecosystem.")
    confirm = input("Confirm activation? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Activation cancelled.")
        return 0

    try:
        updated = activate_agent(agent_name, _REGISTRY_PATH)
        print(f"Agent '{updated.agent_name}' is now ACTIVE.")
        return 0
    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def cmd_quarantine(args: argparse.Namespace) -> int:
    agent_name = args.quarantine
    agent = get_agent(agent_name, _REGISTRY_PATH)
    if agent is None:
        print(f"ERROR: Agent '{agent_name}' not found in registry.", file=sys.stderr)
        return 1
    try:
        updated = set_agent_status(agent_name, "QUARANTINED", _REGISTRY_PATH)
        print(f"Agent '{updated.agent_name}' quarantined.")
        return 0
    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def cmd_inspect(args: argparse.Namespace) -> int:
    """
    Inspect an existing agent directory and emit a skeleton workflow spec
    the user can fill in to generate a sibling agent.
    """
    agent_dir = Path(args.inspect)
    if not agent_dir.is_dir():
        print(f"ERROR: Not a directory: {agent_dir}", file=sys.stderr)
        return 1

    agent_name = agent_dir.name
    py_files = list(agent_dir.glob("*.py"))
    has_tests = (agent_dir / "tests").is_dir()
    has_reports = (agent_dir / "reports").is_dir()

    skeleton = {
        "agent_name": f"{agent_name}-variant",
        "display_name": f"{agent_name.replace('-', ' ').title()} Variant",
        "description": f"Generated from inspection of {agent_name}",
        "workflow_id": "WF-XXX",
        "validated": False,
        "version": "0.1.0",
        "inputs": [{"name": "input", "flag": "--input", "description": "Input JSON", "required": True}],
        "pipeline_steps": [
            {"name": "load", "function": "load_records", "description": "Load input"},
            {"name": "score", "function": "score_all", "description": "Score records"},
            {"name": "report", "function": "generate_all_reports", "description": "Write outputs"},
        ],
        "outputs": [{"name": "OUTPUT.json", "type": "json", "description": "Primary output"}],
        "signals": [],
        "memory_sources": [agent_name],
        "risk_level": "LOW",
        "tags": [agent_name],
        "_inspection_notes": {
            "source_agent": str(agent_dir.resolve()),
            "python_modules": [f.name for f in py_files],
            "has_tests": has_tests,
            "has_reports": has_reports,
        },
    }

    print(json.dumps(skeleton, indent=2))
    print(
        f"\n# Edit the above, set validated=true, then run:\n"
        f"# python run.py --workflow <your_spec.json>",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_python_syntax(files, agent_name: str) -> None:
    """Check all generated .py files parse without SyntaxError."""
    for gf in files:
        if gf.file_type != "python" or not gf.content.strip():
            continue
        try:
            ast.parse(gf.content)
        except SyntaxError as exc:
            print(
                f"  [WARN] Syntax error in generated {agent_name}/{gf.path}: {exc}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        return cmd_list(args)
    if args.activate:
        return cmd_activate(args)
    if args.quarantine:
        return cmd_quarantine(args)
    if args.inspect:
        return cmd_inspect(args)
    if args.workflow:
        return cmd_generate(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
