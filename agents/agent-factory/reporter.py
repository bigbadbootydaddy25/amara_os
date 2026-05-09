"""
Factory output report generator.

Produces the two factory-level reports after an agent is generated:
  GENERATED_AGENT_SPEC.md  — full spec breakdown + file manifest
  AGENT_RISK_REPORT.md     — risk assessment and approval checklist
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from models import AgentRegistration, GeneratedFile, RiskAssessment, ValidationResult, WorkflowSpec


# ---------------------------------------------------------------------------
# GENERATED_AGENT_SPEC.md
# ---------------------------------------------------------------------------

def write_agent_spec(
    spec: WorkflowSpec,
    files: List[GeneratedFile],
    registration: AgentRegistration,
    output_dir: Path,
) -> Path:
    path = output_dir / "GENERATED_AGENT_SPEC.md"

    lines: List[str] = [
        f"# Generated Agent Spec: {spec.display_name}",
        "",
        f"_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "---",
        "",
        "## Identity",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Agent Name | `{spec.agent_name}` |",
        f"| Display Name | {spec.display_name} |",
        f"| Workflow ID | `{spec.workflow_id}` |",
        f"| Version | {spec.version} |",
        f"| Author | {spec.author} |",
        f"| Status | `{registration.status}` |",
        f"| Risk Level | {registration.risk_level} |",
        f"| Tags | {', '.join(spec.tags) if spec.tags else '_(none)_'} |",
        "",
        "## Description",
        "",
        spec.description or "_No description provided._",
        "",
        "---",
        "",
        "## Inputs",
        "",
        "| Flag | Required | Type | Description |",
        "|------|----------|------|-------------|",
    ]
    for inp in spec.inputs:
        req = "✓" if inp.required else "—"
        lines.append(f"| `{inp.flag}` | {req} | {inp.input_type} | {inp.description} |")

    lines += [
        "",
        "## Pipeline Steps",
        "",
        "| # | Name | Function | Description |",
        "|---|------|----------|-------------|",
    ]
    for i, step in enumerate(spec.pipeline_steps, 1):
        lines.append(f"| {i} | {step.name} | `{step.function}()` | {step.description} |")

    lines += [
        "",
        "## Outputs",
        "",
        "| File | Type | Description |",
        "|------|------|-------------|",
    ]
    for out in spec.outputs:
        lines.append(f"| `{out.name}` | {out.output_type} | {out.description} |")

    if spec.signals:
        lines += [
            "",
            "## Signals",
            "",
            "| Signal | Weight | Description |",
            "|--------|--------|-------------|",
        ]
        for sig in spec.signals:
            lines.append(f"| `{sig.name}` | {sig.weight} | {sig.description} |")
        total_w = sum(s.weight for s in spec.signals)
        lines.append(f"\n_Total signal weight: {total_w} | Confidence cap: 100_")
    else:
        lines += ["", "## Signals", "", "_No signals defined — scorer is a stub._"]

    lines += [
        "",
        "## Memory Sources",
        "",
    ]
    if spec.memory_sources:
        for src in spec.memory_sources:
            lines.append(f"- `{src}`")
    else:
        lines.append("_None specified_")

    lines += [
        "",
        "---",
        "",
        "## Generated File Manifest",
        "",
        "| File | Type | Lines |",
        "|------|------|-------|",
    ]
    for gf in sorted(files, key=lambda f: f.path):
        n_lines = len(gf.content.splitlines())
        lines.append(f"| `{gf.path}` | {gf.file_type} | {n_lines} |")

    lines += [
        "",
        "---",
        "",
        "## Activation",
        "",
        "This agent is in `PENDING_APPROVAL` status.",
        "Human review and approval is required before the agent can run in production.",
        "",
        "```bash",
        f"python agents/agent-factory/run.py --activate {spec.agent_name}",
        "```",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AGENT_RISK_REPORT.md
# ---------------------------------------------------------------------------

def write_risk_report(
    spec: WorkflowSpec,
    validation: ValidationResult,
    risk: RiskAssessment,
    output_dir: Path,
) -> Path:
    path = output_dir / "AGENT_RISK_REPORT.md"

    status_icon = "✅" if validation.is_valid else "❌"
    risk_icon = risk.colour

    lines: List[str] = [
        f"# Agent Risk Report: {spec.display_name}",
        "",
        f"_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "---",
        "",
        "## Validation",
        "",
        f"**Result:** {status_icon} {'VALID' if validation.is_valid else 'INVALID'}",
        "",
    ]

    if validation.errors:
        lines += ["**Errors:**", ""]
        for e in validation.errors:
            lines.append(f"- ❌ {e}")
        lines.append("")

    if validation.warnings:
        lines += ["**Warnings:**", ""]
        for w in validation.warnings:
            lines.append(f"- ⚠️  {w}")
        lines.append("")

    if validation.is_valid and not validation.errors:
        lines.append("_No validation errors._")
        lines.append("")

    lines += [
        "---",
        "",
        "## Risk Assessment",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Risk Level | {risk_icon} {risk.risk_level} |",
        f"| Risk Score | {risk.risk_score} |",
        f"| Requires Approval | {'Yes' if risk.requires_approval else 'No'} |",
        "",
        "**Risk Factors:**",
        "",
    ]
    for factor in risk.risk_factors:
        lines.append(f"- {factor}")

    lines += [
        "",
        "---",
        "",
        "## Pre-Activation Checklist",
        "",
        "Complete all items before activating this agent:",
        "",
        f"- [ ] Review generated code in `{spec.agent_name}/`",
        f"- [ ] Implement signal detectors in `{spec.agent_name}/signals.py`",
        f"- [ ] Verify model fields in `{spec.agent_name}/models.py` match your data schema",
        f"- [ ] Run tests: `python -m pytest {spec.agent_name}/tests/ -v`",
        f"- [ ] Review outputs in `{spec.agent_name}/reports/`",
        f"- [ ] Confirm memory sources are not quarantined: {spec.memory_sources or '(none)'}",
        f"- [ ] Sign off on risk level: {risk.risk_level}",
        f"- [ ] Run activation: `python agents/agent-factory/run.py --activate {spec.agent_name}`",
        "",
        "---",
        "",
        "## Source Evidence",
        "",
        f"- Workflow ID: `{spec.workflow_id}`",
        f"- Validated flag: `{spec.validated}`",
        f"- Pipeline steps: {len(spec.pipeline_steps)}",
        f"- Signals defined: {len(spec.signals)}",
        f"- Memory sources: {spec.memory_sources or '[]'}",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_factory_reports(
    spec: WorkflowSpec,
    files: List[GeneratedFile],
    registration: AgentRegistration,
    validation: ValidationResult,
    risk: RiskAssessment,
    output_dir: Path,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "GENERATED_AGENT_SPEC": write_agent_spec(spec, files, registration, output_dir),
        "AGENT_RISK_REPORT": write_risk_report(spec, validation, risk, output_dir),
    }
