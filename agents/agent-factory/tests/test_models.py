"""Tests for data model construction and derived properties."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from models import (
    AgentRegistration,
    PipelineStep,
    RiskAssessment,
    ValidationResult,
    WorkflowInput,
    WorkflowOutput,
    WorkflowSignal,
    WorkflowSpec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_workflow.json"


def load_spec() -> WorkflowSpec:
    return WorkflowSpec.from_dict(json.loads(FIXTURE.read_text()))


class TestWorkflowSpec:
    def test_loads_from_fixture(self):
        spec = load_spec()
        assert spec.agent_name == "deal-scorer"
        assert spec.workflow_id == "WF-TEST-001"
        assert spec.validated is True

    def test_module_name_snake_case(self):
        spec = load_spec()
        assert spec.module_name == "deal_scorer"

    def test_model_class_pascal_case(self):
        spec = load_spec()
        assert spec.model_class == "DealScorerRecord"

    def test_primary_input_is_required_first(self):
        spec = load_spec()
        assert spec.primary_input is not None
        assert spec.primary_input.name == "deals"
        assert spec.primary_input.required is True

    def test_primary_input_attr(self):
        spec = load_spec()
        assert spec.primary_input_attr == "deals"

    def test_json_outputs_filtered(self):
        spec = load_spec()
        json_outs = spec.json_outputs
        assert all(o.output_type == "json" for o in json_outs)
        assert len(json_outs) == 2

    def test_markdown_outputs_filtered(self):
        spec = load_spec()
        md_outs = spec.markdown_outputs
        assert all(o.output_type == "markdown" for o in md_outs)

    def test_signals_loaded(self):
        spec = load_spec()
        assert len(spec.signals) == 5
        names = [s.name for s in spec.signals]
        assert "PRICE_SIGNAL" in names
        assert "ARV_SPREAD" in names

    def test_pipeline_steps_loaded(self):
        spec = load_spec()
        assert len(spec.pipeline_steps) == 5
        fns = [s.function for s in spec.pipeline_steps]
        assert "load_records" in fns
        assert "score_all" in fns


class TestWorkflowInput:
    def test_from_dict(self):
        d = {"name": "parcels", "flag": "--parcels", "required": True, "type": "file"}
        inp = WorkflowInput.from_dict(d)
        assert inp.name == "parcels"
        assert inp.flag == "--parcels"
        assert inp.required is True

    def test_defaults(self):
        inp = WorkflowInput.from_dict({"name": "x", "flag": "--x"})
        assert inp.short_flag == ""
        assert inp.input_type == "file"


class TestWorkflowSignal:
    def test_name_uppercased(self):
        sig = WorkflowSignal.from_dict({"name": "my_signal", "weight": 15})
        assert sig.name == "MY_SIGNAL"

    def test_weight_parsed(self):
        sig = WorkflowSignal.from_dict({"name": "SIG", "weight": 25})
        assert sig.weight == 25


class TestValidationResult:
    def test_starts_valid(self):
        r = ValidationResult(is_valid=True)
        assert r.is_valid is True
        assert r.errors == []

    def test_add_error_sets_invalid(self):
        r = ValidationResult(is_valid=True)
        r.add_error("something wrong")
        assert r.is_valid is False
        assert len(r.errors) == 1

    def test_add_warning_keeps_valid(self):
        r = ValidationResult(is_valid=True)
        r.add_warning("minor issue")
        assert r.is_valid is True
        assert len(r.warnings) == 1


class TestRiskAssessment:
    def test_colour_mapping(self):
        assert RiskAssessment("LOW", 0).colour == "🟢"
        assert RiskAssessment("MEDIUM", 5).colour == "🟡"
        assert RiskAssessment("HIGH", 10).colour == "🔴"
        assert RiskAssessment("UNKNOWN", 0).colour == "⚪"

    def test_requires_approval_always_true(self):
        r = RiskAssessment("LOW", 0, requires_approval=True)
        assert r.requires_approval is True


class TestAgentRegistration:
    def test_round_trip(self):
        reg = AgentRegistration(
            agent_name="test-agent",
            workflow_id="WF-001",
            version="0.1.0",
            risk_level="LOW",
        )
        d = reg.to_dict()
        restored = AgentRegistration.from_dict(d)
        assert restored.agent_name == "test-agent"
        assert restored.workflow_id == "WF-001"
        assert restored.status == "PENDING_APPROVAL"

    def test_generated_at_auto_set(self):
        reg = AgentRegistration(agent_name="x", workflow_id="WF-X", version="0.1")
        assert reg.generated_at != ""
