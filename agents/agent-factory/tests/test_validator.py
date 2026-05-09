"""Tests for workflow validation rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from models import WorkflowSpec
from workflow_validator import validate_workflow

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_valid() -> WorkflowSpec:
    return WorkflowSpec.from_dict(json.loads((FIXTURE_DIR / "sample_workflow.json").read_text()))


def load_invalid() -> dict:
    return json.loads((FIXTURE_DIR / "invalid_workflow.json").read_text())


class TestValidWorkflow:
    def test_valid_fixture_passes(self):
        spec = load_valid()
        result = validate_workflow(spec, set())
        assert result.is_valid is True

    def test_no_errors_on_valid(self):
        spec = load_valid()
        result = validate_workflow(spec, set())
        assert result.errors == []


class TestAgentNameValidation:
    def test_rejects_single_word_no_hyphen(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["agent_name"] = "x"
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("agent_name" in e for e in result.errors)

    def test_rejects_spaces(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["agent_name"] = "deal scorer"
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid

    def test_rejects_special_chars(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["agent_name"] = "deal_scorer!"
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid

    def test_accepts_kebab_case(self):
        spec = load_valid()
        result = validate_workflow(spec, set())
        assert result.is_valid

    def test_rejects_too_short(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["agent_name"] = "a"
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid


class TestWorkflowIdValidation:
    def test_rejects_empty_id(self):
        d = load_invalid()
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("workflow_id" in e for e in result.errors)

    def test_accepts_non_empty_id(self):
        spec = load_valid()
        result = validate_workflow(spec, set())
        assert result.is_valid


class TestValidatedFlag:
    def test_rejects_unvalidated(self):
        d = load_invalid()
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("validated" in e for e in result.errors)


class TestInputsValidation:
    def test_requires_at_least_one_input(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["inputs"] = []
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("input" in e.lower() for e in result.errors)

    def test_requires_required_flag_on_some_input(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        for inp in d["inputs"]:
            inp["required"] = False
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid


class TestPipelineValidation:
    def test_requires_at_least_two_steps(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["pipeline_steps"] = [{"name": "only", "function": "fn", "description": "solo"}]
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("pipeline" in e.lower() or "step" in e.lower() for e in result.errors)


class TestOutputsValidation:
    def test_requires_at_least_one_output(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["outputs"] = []
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid


class TestSignalValidation:
    def test_rejects_non_upper_snake_case_name(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["signals"] = [{"name": "bad signal name", "weight": 20, "description": "x"}]
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("signal" in e.lower() for e in result.errors)

    def test_rejects_weight_above_100(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["signals"] = [{"name": "MY_SIGNAL", "weight": 200, "description": "x"}]
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid

    def test_rejects_weight_zero(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["signals"] = [{"name": "MY_SIGNAL", "weight": 0, "description": "x"}]
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid

    def test_accepts_valid_signals(self):
        spec = load_valid()
        result = validate_workflow(spec, set())
        assert result.is_valid


class TestRiskLevelValidation:
    def test_rejects_invalid_risk_level(self):
        d = load_invalid()
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert not result.is_valid
        assert any("risk" in e.lower() for e in result.errors)

    def test_accepts_low(self):
        spec = load_valid()
        result = validate_workflow(spec, set())
        assert result.is_valid


class TestQuarantinedSources:
    def test_rejects_quarantined_memory_source(self):
        spec = load_valid()
        quarantined = {"builder-verification"}
        result = validate_workflow(spec, quarantined)
        assert not result.is_valid
        assert any("quarantine" in e.lower() for e in result.errors)

    def test_no_quarantine_on_clean_sources(self):
        spec = load_valid()
        result = validate_workflow(spec, {"some-other-source"})
        assert result.is_valid


class TestWarnings:
    def test_warns_when_no_signals(self):
        d = json.loads((FIXTURE_DIR / "sample_workflow.json").read_text())
        d["signals"] = []
        spec = WorkflowSpec.from_dict(d)
        result = validate_workflow(spec, set())
        assert any("signal" in w.lower() for w in result.warnings)
