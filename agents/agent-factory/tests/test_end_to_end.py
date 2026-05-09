"""End-to-end pipeline tests for agent factory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ast
import json
import tempfile
from models import WorkflowSpec
from workflow_validator import validate_workflow
from risk_assessor import assess_risk
from code_generator import generate_agent_files, write_agent_tree
from registry import register_agent, list_agents
from reporter import generate_factory_reports

FIXTURE = Path(__file__).parent / "fixtures" / "sample_workflow.json"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
INVALID_FIXTURE = Path(__file__).parent / "fixtures" / "invalid_workflow.json"


def _run_pipeline(tmp_root: Path):
    """Full pipeline: load → validate → risk → generate → write → register → report."""
    raw = json.loads(FIXTURE.read_text())
    spec = WorkflowSpec.from_dict(raw)

    validation = validate_workflow(spec, set())
    assert validation.is_valid, f"Validation failed: {validation.errors}"

    risk = assess_risk(spec)

    files = generate_agent_files(spec, TEMPLATE_DIR, risk.risk_level)
    agent_dir = write_agent_tree(files, tmp_root / "agents", spec.agent_name)

    registry_path = tmp_root / "registry" / "AGENT_REGISTRY.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps({"agents": []}))

    registration = register_agent(
        spec,
        output_path=str(agent_dir),
        risk_level=risk.risk_level,
        registry_path=registry_path,
    )

    report_dir = tmp_root / "reports"
    report_paths = generate_factory_reports(spec, files, registration, validation, risk, report_dir)

    return spec, files, agent_dir, registration, risk, report_paths


class TestFullPipeline:
    def test_pipeline_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, files, agent_dir, reg, risk, reports = _run_pipeline(Path(tmp))
            assert agent_dir.is_dir()

    def test_agent_dir_has_run_py(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, agent_dir, *_ = _run_pipeline(Path(tmp))
            assert (agent_dir / "run.py").exists()

    def test_agent_dir_has_models_py(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, agent_dir, *_ = _run_pipeline(Path(tmp))
            assert (agent_dir / "models.py").exists()

    def test_agent_dir_has_signals_py(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, agent_dir, *_ = _run_pipeline(Path(tmp))
            assert (agent_dir / "signals.py").exists()

    def test_agent_dir_has_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, agent_dir, *_ = _run_pipeline(Path(tmp))
            assert (agent_dir / "README.md").exists()

    def test_all_python_syntactically_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, files, *_ = _run_pipeline(Path(tmp))
            for f in files:
                if f.file_type == "python" and f.content.strip():
                    try:
                        ast.parse(f.content)
                    except SyntaxError as exc:
                        raise AssertionError(f"SyntaxError in generated {f.path}: {exc}")

    def test_registration_pending_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, registration, *_ = _run_pipeline(Path(tmp))
            assert registration.status == "PENDING_APPROVAL"

    def test_registration_matches_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, _, _, registration, *_ = _run_pipeline(Path(tmp))
            assert registration.agent_name == spec.agent_name
            assert registration.workflow_id == spec.workflow_id

    def test_reports_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, _, report_paths = _run_pipeline(Path(tmp))
            for name, p in report_paths.items():
                assert p.exists(), f"Report not written: {name}"

    def test_agent_spec_report_contains_agent_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, _, _, _, _, report_paths = _run_pipeline(Path(tmp))
            spec_report = report_paths.get("GENERATED_AGENT_SPEC")
            assert spec_report is not None
            content = spec_report.read_text()
            assert spec.agent_name in content

    def test_risk_report_contains_risk_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, risk, report_paths = _run_pipeline(Path(tmp))
            risk_report = report_paths.get("AGENT_RISK_REPORT")
            assert risk_report is not None
            content = risk_report.read_text()
            assert risk.risk_level in content

    def test_registry_entry_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _run_pipeline(tmp_path)
            registry_path = tmp_path / "registry" / "AGENT_REGISTRY.json"
            agents = list_agents(registry_path)
            assert len(agents) == 1
            assert agents[0].agent_name == "deal-scorer"

    def test_duplicate_workflow_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _run_pipeline(tmp_path)
            raw = json.loads(FIXTURE.read_text())
            spec = WorkflowSpec.from_dict(raw)
            registry_path = tmp_path / "registry" / "AGENT_REGISTRY.json"
            try:
                register_agent(spec, output_path="/tmp/x", risk_level="LOW", registry_path=registry_path)
                assert False, "Expected ValueError for duplicate workflow_id"
            except ValueError:
                pass


class TestInvalidWorkflowBlocked:
    def test_invalid_workflow_fails_validation(self):
        raw = json.loads(INVALID_FIXTURE.read_text())
        spec = WorkflowSpec.from_dict(raw)
        result = validate_workflow(spec, set())
        assert not result.is_valid

    def test_invalid_workflow_has_multiple_errors(self):
        raw = json.loads(INVALID_FIXTURE.read_text())
        spec = WorkflowSpec.from_dict(raw)
        result = validate_workflow(spec, set())
        assert len(result.errors) >= 3


class TestRiskAssessment:
    def test_low_risk_for_valid_spec(self):
        spec = WorkflowSpec.from_dict(json.loads(FIXTURE.read_text()))
        risk = assess_risk(spec)
        assert risk.risk_level in ("LOW", "MEDIUM")

    def test_risk_has_colour(self):
        spec = WorkflowSpec.from_dict(json.loads(FIXTURE.read_text()))
        risk = assess_risk(spec)
        assert risk.colour in ("🟢", "🟡", "🔴", "⚪")
