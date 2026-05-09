"""Tests for code generation logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ast
import json
from models import WorkflowSpec
from code_generator import generate_agent_files, write_agent_tree
import tempfile

FIXTURE = Path(__file__).parent / "fixtures" / "sample_workflow.json"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def load_spec() -> WorkflowSpec:
    return WorkflowSpec.from_dict(json.loads(FIXTURE.read_text()))


class TestGenerateAgentFiles:
    def test_returns_nonempty_list(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        assert len(files) > 0

    def test_includes_run_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert "run.py" in paths

    def test_includes_models_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert "models.py" in paths

    def test_includes_signals_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert "signals.py" in paths

    def test_includes_scorer_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert "scorer.py" in paths

    def test_includes_reporter_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert "reporter.py" in paths

    def test_includes_readme(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert "README.md" in paths

    def test_includes_test_file(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        paths = [f.path for f in files]
        assert any("test" in p for p in paths)


class TestSubstitution:
    def _get_file(self, files, path):
        return next(f for f in files if f.path == path)

    def test_agent_name_in_readme(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        readme = self._get_file(files, "README.md")
        assert "deal-scorer" in readme.content

    def test_model_class_in_models_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        models = self._get_file(files, "models.py")
        assert "DealScorerRecord" in models.content

    def test_signal_names_in_signals_py(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        signals = self._get_file(files, "signals.py")
        assert "PRICE_SIGNAL" in signals.content
        assert "ARV_SPREAD" in signals.content

    def test_workflow_id_in_readme(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        readme = self._get_file(files, "README.md")
        assert "WF-TEST-001" in readme.content

    def test_risk_level_in_readme(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        readme = self._get_file(files, "README.md")
        assert "LOW" in readme.content

    def test_no_unresolved_placeholders_in_python(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        for f in files:
            if f.file_type == "python":
                assert "${" not in f.content, f"{f.path} has unresolved placeholder"


class TestSyntaxValidity:
    def test_all_python_files_parse(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        for f in files:
            if f.file_type == "python" and f.content.strip():
                try:
                    ast.parse(f.content)
                except SyntaxError as exc:
                    raise AssertionError(f"SyntaxError in {f.path}: {exc}")


class TestWriteAgentTree:
    def test_writes_files_to_disk(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = write_agent_tree(files, Path(tmp), spec.agent_name)
            assert agent_dir.is_dir()
            written = list(agent_dir.rglob("*"))
            assert len(written) > 0

    def test_agent_dir_named_correctly(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = write_agent_tree(files, Path(tmp), spec.agent_name)
            assert agent_dir.name == spec.agent_name

    def test_run_py_written(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = write_agent_tree(files, Path(tmp), spec.agent_name)
            assert (agent_dir / "run.py").exists()

    def test_content_matches(self):
        spec = load_spec()
        files = generate_agent_files(spec, TEMPLATE_DIR, "LOW")
        run_file = next(f for f in files if f.path == "run.py")
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = write_agent_tree(files, Path(tmp), spec.agent_name)
            written = (agent_dir / "run.py").read_text()
            assert written == run_file.content
