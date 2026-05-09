"""
Data models for the Agent Factory.

WorkflowSpec       — the validated input spec for a new agent
ValidationResult   — output of workflow validation
RiskAssessment     — risk analysis of a workflow
GeneratedFile      — a file ready to be written to disk
AgentRegistration  — registry entry for a generated agent
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Workflow input schema
# ---------------------------------------------------------------------------

@dataclass
class WorkflowInput:
    name: str                       # argparse attribute name  e.g. "deals"
    flag: str                       # e.g. "--deals"
    description: str = ""
    required: bool = True
    short_flag: str = ""            # e.g. "-d"
    input_type: str = "file"        # file | value

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowInput":
        return cls(
            name=str(d.get("name", "")).strip(),
            flag=str(d.get("flag", "")).strip(),
            description=str(d.get("description", "")).strip(),
            required=bool(d.get("required", True)),
            short_flag=str(d.get("short_flag", "")).strip(),
            input_type=str(d.get("type", "file")).strip(),
        )


@dataclass
class WorkflowOutput:
    name: str                       # e.g. "SCORED_DEALS.json"
    description: str = ""
    output_type: str = "json"       # json | markdown | text

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowOutput":
        ext = str(d.get("name", "")).rsplit(".", 1)[-1].lower()
        inferred = "markdown" if ext == "md" else ("json" if ext == "json" else "text")
        return cls(
            name=str(d.get("name", "")).strip(),
            description=str(d.get("description", "")).strip(),
            output_type=str(d.get("type", inferred)).strip(),
        )


@dataclass
class WorkflowSignal:
    name: str                       # e.g. "PRICE_SIGNAL"
    weight: int = 10
    description: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowSignal":
        return cls(
            name=str(d.get("name", "")).strip().upper(),
            weight=int(d.get("weight", 10)),
            description=str(d.get("description", "")).strip(),
        )


@dataclass
class PipelineStep:
    name: str
    function: str
    description: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineStep":
        return cls(
            name=str(d.get("name", "")).strip(),
            function=str(d.get("function", "")).strip(),
            description=str(d.get("description", "")).strip(),
        )


@dataclass
class WorkflowSpec:
    agent_name: str                                         # kebab-case
    display_name: str
    description: str
    workflow_id: str
    validated: bool
    version: str = "0.1.0"
    author: str = "agent-factory"
    inputs: List[WorkflowInput] = field(default_factory=list)
    pipeline_steps: List[PipelineStep] = field(default_factory=list)
    outputs: List[WorkflowOutput] = field(default_factory=list)
    signals: List[WorkflowSignal] = field(default_factory=list)
    memory_sources: List[str] = field(default_factory=list)
    risk_level: str = "LOW"
    tags: List[str] = field(default_factory=list)
    min_confidence_threshold: int = 30
    raw: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------------------
    # Derived naming helpers
    # ---------------------------------------------------------------------------

    @property
    def module_name(self) -> str:
        """snake_case version of agent_name: deal-scorer → deal_scorer"""
        return self.agent_name.replace("-", "_")

    @property
    def model_class(self) -> str:
        """PascalCase + Record: deal-scorer → DealRecord"""
        parts = self.agent_name.split("-")
        return "".join(p.title() for p in parts) + "Record"

    @property
    def primary_input(self) -> Optional[WorkflowInput]:
        required = [i for i in self.inputs if i.required]
        return required[0] if required else (self.inputs[0] if self.inputs else None)

    @property
    def primary_input_attr(self) -> str:
        inp = self.primary_input
        return inp.name if inp else "input"

    @property
    def json_outputs(self) -> List[WorkflowOutput]:
        return [o for o in self.outputs if o.output_type == "json"]

    @property
    def markdown_outputs(self) -> List[WorkflowOutput]:
        return [o for o in self.outputs if o.output_type == "markdown"]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowSpec":
        return cls(
            agent_name=str(d.get("agent_name", "")).strip().lower(),
            display_name=str(d.get("display_name", "")).strip(),
            description=str(d.get("description", "")).strip(),
            workflow_id=str(d.get("workflow_id", "")).strip(),
            validated=bool(d.get("validated", False)),
            version=str(d.get("version", "0.1.0")).strip(),
            author=str(d.get("author", "agent-factory")).strip(),
            inputs=[WorkflowInput.from_dict(i) for i in d.get("inputs", [])],
            pipeline_steps=[PipelineStep.from_dict(s) for s in d.get("pipeline_steps", [])],
            outputs=[WorkflowOutput.from_dict(o) for o in d.get("outputs", [])],
            signals=[WorkflowSignal.from_dict(s) for s in d.get("signals", [])],
            memory_sources=d.get("memory_sources", []),
            risk_level=str(d.get("risk_level", "LOW")).upper(),
            tags=d.get("tags", []),
            min_confidence_threshold=int(d.get("min_confidence_threshold", 30)),
            raw=d,
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

@dataclass
class RiskAssessment:
    risk_level: str          # LOW | MEDIUM | HIGH
    risk_score: int
    risk_factors: List[str] = field(default_factory=list)
    requires_approval: bool = True   # always True per spec rules

    @property
    def colour(self) -> str:
        return {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(self.risk_level, "⚪")


# ---------------------------------------------------------------------------
# Generated file
# ---------------------------------------------------------------------------

@dataclass
class GeneratedFile:
    path: str                # relative to agent output root
    content: str
    file_type: str = "python"  # python | markdown | json | text

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()


# ---------------------------------------------------------------------------
# Registry entry
# ---------------------------------------------------------------------------

VALID_STATUSES = {"PENDING_APPROVAL", "ACTIVE", "QUARANTINED", "RETIRED"}

@dataclass
class AgentRegistration:
    agent_name: str
    workflow_id: str
    version: str
    status: str = "PENDING_APPROVAL"
    generated_at: str = ""
    risk_level: str = "LOW"
    description: str = ""
    output_path: str = ""
    tags: List[str] = field(default_factory=list)
    memory_sources: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "workflow_id": self.workflow_id,
            "version": self.version,
            "status": self.status,
            "generated_at": self.generated_at,
            "risk_level": self.risk_level,
            "description": self.description,
            "output_path": self.output_path,
            "tags": self.tags,
            "memory_sources": self.memory_sources,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentRegistration":
        return cls(
            agent_name=d.get("agent_name", ""),
            workflow_id=d.get("workflow_id", ""),
            version=d.get("version", ""),
            status=d.get("status", "PENDING_APPROVAL"),
            generated_at=d.get("generated_at", ""),
            risk_level=d.get("risk_level", "LOW"),
            description=d.get("description", ""),
            output_path=d.get("output_path", ""),
            tags=d.get("tags", []),
            memory_sources=d.get("memory_sources", []),
        )
