"""
Workflow spec validator.

Rules enforced:
  - agent_name: kebab-case, 2–40 chars, starts with letter
  - workflow_id: format WF-\d+ or any non-empty string
  - validated flag: must be True (never generate from quarantined memory)
  - inputs: at least 1 defined, each must have name + flag
  - pipeline_steps: at least 2 steps
  - outputs: at least 1 defined
  - signals: weights must be 1–100; names must be UPPER_SNAKE_CASE
  - risk_level: LOW | MEDIUM | HIGH
  - memory_sources: must not include known quarantined agents
"""
from __future__ import annotations

import re
from typing import List, Set

from models import ValidationResult, WorkflowSpec

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KEBAB_RE = re.compile(r"^[a-z][a-z0-9\-]{1,38}[a-z0-9]$")
_SIGNAL_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,49}$")
_VALID_RISK_LEVELS: Set[str] = {"LOW", "MEDIUM", "HIGH"}
_QUARANTINED_SOURCES: Set[str] = set()  # populated from registry at runtime


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_workflow(
    spec: WorkflowSpec,
    quarantined_sources: Set[str] | None = None,
) -> ValidationResult:
    """
    Full validation of a WorkflowSpec. Returns a ValidationResult with
    all errors and warnings collected (does not raise on failure).
    """
    result = ValidationResult(is_valid=True)
    _check = quarantined_sources or _QUARANTINED_SOURCES

    _validate_agent_name(spec, result)
    _validate_workflow_id(spec, result)
    _validate_not_quarantined(spec, result)
    _validate_inputs(spec, result)
    _validate_pipeline(spec, result)
    _validate_outputs(spec, result)
    _validate_signals(spec, result)
    _validate_risk_level(spec, result)
    _validate_memory_sources(spec, result, _check)
    _check_warnings(spec, result)

    return result


# ---------------------------------------------------------------------------
# Individual rule checkers
# ---------------------------------------------------------------------------

def _validate_agent_name(spec: WorkflowSpec, result: ValidationResult) -> None:
    name = spec.agent_name
    if not name:
        result.add_error("agent_name is required")
        return
    if not _KEBAB_RE.match(name):
        result.add_error(
            f"agent_name '{name}' must be kebab-case (lowercase letters, digits, "
            f"hyphens; 3–40 chars; start and end with letter/digit)"
        )
    reserved = {"agent-factory", "run", "models", "tests", "reports"}
    if name in reserved:
        result.add_error(f"agent_name '{name}' is a reserved name")


def _validate_workflow_id(spec: WorkflowSpec, result: ValidationResult) -> None:
    if not spec.workflow_id:
        result.add_error("workflow_id is required")
    elif len(spec.workflow_id) < 3:
        result.add_error("workflow_id is too short (min 3 characters)")


def _validate_not_quarantined(spec: WorkflowSpec, result: ValidationResult) -> None:
    if not spec.validated:
        result.add_error(
            "workflow 'validated' flag is False — only validated workflows may "
            "generate agents (quarantined memory blocked)"
        )


def _validate_inputs(spec: WorkflowSpec, result: ValidationResult) -> None:
    if not spec.inputs:
        result.add_error("at least 1 input must be defined")
        return
    for i, inp in enumerate(spec.inputs):
        if not inp.name:
            result.add_error(f"inputs[{i}].name is required")
        elif not re.match(r"^[a-z][a-z0-9_]{0,39}$", inp.name):
            result.add_error(
                f"inputs[{i}].name '{inp.name}' must be snake_case"
            )
        if not inp.flag:
            result.add_error(f"inputs[{i}].flag is required")
        elif not inp.flag.startswith("--"):
            result.add_error(
                f"inputs[{i}].flag '{inp.flag}' must start with '--'"
            )
    required_inputs = [i for i in spec.inputs if i.required]
    if not required_inputs:
        result.add_error("at least 1 input must be marked required:true")


def _validate_pipeline(spec: WorkflowSpec, result: ValidationResult) -> None:
    if len(spec.pipeline_steps) < 2:
        result.add_error(
            f"pipeline_steps must have at least 2 steps (got {len(spec.pipeline_steps)})"
        )
    for i, step in enumerate(spec.pipeline_steps):
        if not step.name:
            result.add_error(f"pipeline_steps[{i}].name is required")
        if not step.function:
            result.add_error(f"pipeline_steps[{i}].function is required")
        elif not re.match(r"^[a-z][a-z0-9_]{1,49}$", step.function):
            result.add_error(
                f"pipeline_steps[{i}].function '{step.function}' must be a "
                f"valid Python function name"
            )


def _validate_outputs(spec: WorkflowSpec, result: ValidationResult) -> None:
    if not spec.outputs:
        result.add_error("at least 1 output must be defined")
        return
    for i, out in enumerate(spec.outputs):
        if not out.name:
            result.add_error(f"outputs[{i}].name is required")


def _validate_signals(spec: WorkflowSpec, result: ValidationResult) -> None:
    for i, sig in enumerate(spec.signals):
        if not _SIGNAL_NAME_RE.match(sig.name):
            result.add_error(
                f"signals[{i}].name '{sig.name}' must be UPPER_SNAKE_CASE"
            )
        if not (1 <= sig.weight <= 100):
            result.add_error(
                f"signals[{i}].weight {sig.weight} must be 1–100"
            )
    total_weight = sum(s.weight for s in spec.signals)
    if spec.signals and total_weight > 500:
        result.add_warning(
            f"Total signal weight {total_weight} is very high — "
            "consider normalising weights so they sum to ~100"
        )


def _validate_risk_level(spec: WorkflowSpec, result: ValidationResult) -> None:
    if spec.risk_level not in _VALID_RISK_LEVELS:
        result.add_error(
            f"risk_level '{spec.risk_level}' must be one of: "
            f"{', '.join(sorted(_VALID_RISK_LEVELS))}"
        )


def _validate_memory_sources(
    spec: WorkflowSpec,
    result: ValidationResult,
    quarantined: Set[str],
) -> None:
    for src in spec.memory_sources:
        if src in quarantined:
            result.add_error(
                f"memory_source '{src}' is quarantined — "
                "agents may not be generated from quarantined memory"
            )


def _check_warnings(spec: WorkflowSpec, result: ValidationResult) -> None:
    if not spec.description:
        result.add_warning("description is empty — consider adding one")
    if not spec.tags:
        result.add_warning("no tags defined — consider adding tags for discoverability")
    if len(spec.pipeline_steps) > 8:
        result.add_warning(
            f"{len(spec.pipeline_steps)} pipeline steps detected — "
            "consider splitting into multiple focused agents"
        )
    if not spec.signals:
        result.add_warning(
            "no signals defined — the generated scorer will be a stub; "
            "add signal definitions for a working scoring engine"
        )
    if spec.min_confidence_threshold < 10:
        result.add_warning(
            f"min_confidence_threshold {spec.min_confidence_threshold} is very low — "
            "low-quality matches may surface in outputs"
        )
