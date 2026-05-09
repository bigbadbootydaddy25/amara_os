"""
Risk assessment engine for workflow specifications.

Computes a numeric risk score and maps it to LOW / MEDIUM / HIGH.
Human approval is always required regardless of risk level (per spec rules).

Scoring table:
  Memory sources         +2 per source beyond the first
  Pipeline length        +2 per step beyond 4
  HIGH self-declared     +5 flat
  MEDIUM self-declared   +2 flat
  Outputs count          +1 per output beyond 2
  No signals             +3 (opaque scoring)
  External inputs        +3 per external input
  Unvalidated flag       +10 (should already be blocked by validator)

Risk bands:
  0–4   → LOW
  5–9   → MEDIUM
  10+   → HIGH
"""
from __future__ import annotations

from models import RiskAssessment, WorkflowSpec

_LOW_MAX = 4
_MEDIUM_MAX = 9


def assess_risk(spec: WorkflowSpec) -> RiskAssessment:
    score = 0
    factors: list[str] = []

    # Self-declared risk level contributes to score
    if spec.risk_level == "HIGH":
        score += 5
        factors.append("Workflow self-declares HIGH risk level (+5)")
    elif spec.risk_level == "MEDIUM":
        score += 2
        factors.append("Workflow self-declares MEDIUM risk level (+2)")

    # Memory sources
    n_sources = len(spec.memory_sources)
    if n_sources > 1:
        extra = (n_sources - 1) * 2
        score += extra
        factors.append(
            f"{n_sources} memory sources (extra sources add complexity, +{extra})"
        )
    elif n_sources == 1:
        factors.append(f"1 memory source: {spec.memory_sources[0]} (no penalty)")

    # Pipeline depth
    n_steps = len(spec.pipeline_steps)
    if n_steps > 4:
        extra = (n_steps - 4) * 2
        score += extra
        factors.append(f"{n_steps} pipeline steps (> 4 adds +{extra})")

    # Output count
    n_outputs = len(spec.outputs)
    if n_outputs > 2:
        extra = n_outputs - 2
        score += extra
        factors.append(f"{n_outputs} outputs (> 2 adds +{extra})")

    # No signals — opaque black-box scoring
    if not spec.signals:
        score += 3
        factors.append("No signals defined — scoring logic is opaque (+3)")

    # External inputs
    external = [i for i in spec.inputs if i.input_type == "external"]
    if external:
        extra = len(external) * 3
        score += extra
        factors.append(
            f"{len(external)} external input(s) — requires network/API (+{extra})"
        )

    # Not validated
    if not spec.validated:
        score += 10
        factors.append("Workflow is NOT validated — should be blocked (+10)")

    # Derive level
    if score <= _LOW_MAX:
        level = "LOW"
    elif score <= _MEDIUM_MAX:
        level = "MEDIUM"
    else:
        level = "HIGH"

    if not factors:
        factors.append("No elevated risk factors detected")

    return RiskAssessment(
        risk_level=level,
        risk_score=score,
        risk_factors=factors,
        requires_approval=True,   # always required per spec rules
    )
