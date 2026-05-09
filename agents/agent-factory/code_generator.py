"""
Code generator: loads templates and performs substitution to produce
all files for a new agent directory tree.

Template syntax: ${PLACEHOLDER} (Python string.Template safe_substitute).
All-caps placeholders are reserved for factory substitution.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template
from typing import Any, Dict, List

from models import GeneratedFile, WorkflowSpec

# ---------------------------------------------------------------------------
# Template map: template filename → relative output path
# ---------------------------------------------------------------------------

TEMPLATE_MAP: Dict[str, str] = {
    "run_py.tmpl":             "run.py",
    "models_py.tmpl":          "models.py",
    "signals_py.tmpl":         "signals.py",
    "scorer_py.tmpl":          "scorer.py",
    "reporter_py.tmpl":        "reporter.py",
    "test_end_to_end_py.tmpl": "tests/test_end_to_end.py",
    "README_md.tmpl":          "README.md",
}

# Static file contents (not template-driven)
_REQUIREMENTS = "pytest>=7.0\n"
_INIT_PY = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_agent_files(
    spec: WorkflowSpec,
    template_dir: Path,
    risk_level: str = "LOW",
) -> List[GeneratedFile]:
    """
    Load all templates, substitute placeholders, return ready-to-write files.
    Also generates static files (requirements.txt, __init__.py, .gitkeep).
    """
    subs = _build_substitutions(spec, risk_level)
    files: List[GeneratedFile] = []

    for tmpl_name, out_path in TEMPLATE_MAP.items():
        tmpl_path = template_dir / tmpl_name
        if not tmpl_path.exists():
            continue
        raw = tmpl_path.read_text(encoding="utf-8")
        content = Template(raw).safe_substitute(subs)
        file_type = _infer_type(out_path)
        files.append(GeneratedFile(path=out_path, content=content, file_type=file_type))

    # Static files
    files += [
        GeneratedFile("requirements.txt", _REQUIREMENTS, "text"),
        GeneratedFile("tests/__init__.py", _INIT_PY, "python"),
        GeneratedFile("reports/.gitkeep", "", "text"),
        GeneratedFile(
            "tests/fixtures/sample_input.json",
            _generate_sample_fixture(spec),
            "json",
        ),
    ]

    return files


def write_agent_tree(
    files: List[GeneratedFile],
    output_root: Path,
    agent_name: str,
) -> Path:
    """Write all GeneratedFile objects under output_root/agent_name/."""
    agent_dir = output_root / agent_name
    for gf in files:
        dest = agent_dir / gf.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(gf.content, encoding="utf-8")
    return agent_dir


# ---------------------------------------------------------------------------
# Substitution dict builder
# ---------------------------------------------------------------------------

def _build_substitutions(spec: WorkflowSpec, risk_level: str) -> Dict[str, str]:
    from datetime import datetime

    primary = spec.primary_input

    # Parser args block
    parser_args = _build_parser_args(spec)

    # Usage line
    usage_parts = []
    for inp in spec.inputs:
        flag = inp.flag
        if inp.required:
            usage_parts.append(f"{flag} <file>")
        else:
            usage_parts.append(f"[{flag} <file>]")
    usage_flags = " ".join(usage_parts)
    usage_lines = f"    python run.py {usage_flags} [--output-dir reports/] [--verbose]"

    # Signal weights dict
    signal_weights_lines = "\n".join(
        f'    "{s.name}": {s.weight},'
        for s in spec.signals
    ) or '    # No signals defined — add signal weights here'

    # Signal detector functions
    detector_fns = _build_signal_detectors(spec)

    # detect_all_signals calls
    detect_calls = "\n".join(
        f"    signals += detect_{sig.name.lower()}(record)"
        for sig in spec.signals
    ) or "    pass  # TODO: add signal detectors"

    # Model fields (dataclass)
    model_fields = _build_model_fields(spec)
    from_dict_fields = _build_from_dict_fields(spec)

    # Output doclines
    output_doclines = "\n".join(f"  {o.name}  — {o.description}" for o in spec.outputs)

    # Writer functions + dispatch
    writer_fns, report_dispatch = _build_reporter_parts(spec)

    # Output table for README
    output_table_rows = "\n".join(
        f"| `{o.name}` | {o.output_type} | {o.description} |"
        for o in spec.outputs
    )

    # Signal table for README
    signal_table_rows = "\n".join(
        f"| `{s.name}` | {s.weight} | {s.description} |"
        for s in spec.signals
    ) or "| _(none defined)_ | — | Add signals to the workflow spec |"

    # Input table for README
    input_table = _build_input_table(spec)

    # Pipeline diagram
    pipeline_diagram = " → ".join(
        f"[{step.name}]" for step in spec.pipeline_steps
    )

    # Memory sources list
    if spec.memory_sources:
        mem_list = "\n".join(f"- `{s}`" for s in spec.memory_sources)
    else:
        mem_list = "_None specified_"

    # Extra e2e tests
    extra_tests = _build_extra_tests(spec)

    # Fabrication check block
    fab_check = _build_fabrication_check(spec)

    return {
        "DISPLAY_NAME": spec.display_name,
        "DESCRIPTION": spec.description,
        "WORKFLOW_ID": spec.workflow_id,
        "VERSION": spec.version,
        "AGENT_NAME": spec.agent_name,
        "MODULE_NAME": spec.module_name,
        "MODEL_CLASS": spec.model_class,
        "PRIMARY_INPUT_ATTR": primary.name if primary else "input_file",
        "PRIMARY_INPUT_FLAG": primary.flag if primary else "--input",
        "PARSER_ARGS": parser_args,
        "USAGE_FLAGS": usage_flags,
        "USAGE_LINES": usage_lines,
        "MIN_THRESHOLD": str(spec.min_confidence_threshold),
        "SIGNAL_WEIGHTS_DICT": signal_weights_lines,
        "SIGNAL_DETECTOR_FUNCTIONS": detector_fns,
        "DETECT_ALL_CALLS": detect_calls,
        "MODEL_FIELDS": model_fields,
        "FROM_DICT_FIELDS": from_dict_fields,
        "OUTPUT_DOCLINES": output_doclines,
        "WRITER_FUNCTIONS": writer_fns,
        "REPORT_DISPATCH": report_dispatch,
        "OUTPUT_TABLE_ROWS": output_table_rows,
        "SIGNAL_TABLE_ROWS": signal_table_rows,
        "INPUT_TABLE": input_table,
        "PIPELINE_DIAGRAM": pipeline_diagram,
        "MEMORY_SOURCES_LIST": mem_list,
        "RISK_LEVEL": risk_level,
        "GENERATED_DATE": datetime.utcnow().strftime("%Y-%m-%d"),
        "AUTHOR": spec.author,
        "TAGS": ", ".join(spec.tags) if spec.tags else "none",
        "EXTRA_TESTS": extra_tests,
        "FABRICATION_CHECK": fab_check,
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_parser_args(spec: WorkflowSpec) -> str:
    lines = []
    for inp in spec.inputs:
        flags = f'"{inp.flag}"'
        if inp.short_flag:
            flags = f'"{inp.short_flag}", {flags}'
        req = "True" if inp.required else "False"
        desc = inp.description or inp.name
        lines.append(
            f'    p.add_argument({flags},\n'
            f'                   required={req},\n'
            f'                   help="{desc}")'
        )
    return "\n".join(lines)


def _build_signal_detectors(spec: WorkflowSpec) -> str:
    if not spec.signals:
        return "# No signals defined — add detector functions here\n"
    blocks = []
    for sig in spec.signals:
        fn_name = f"detect_{sig.name.lower()}"
        blocks.append(
            f"def {fn_name}(record) -> List[ScoredSignal]:\n"
            f'    """Detect {sig.name}: {sig.description}\n\n'
            f"    TODO: implement detection logic.\n"
            f'    """\n'
            f"    # Example: return a signal if a condition is met\n"
            f"    # if <condition on record>:\n"
            f"    #     return [ScoredSignal(\n"
            f'    #         signal_type="{sig.name}",\n'
            f"    #         value=\"<triggering value>\",\n"
            f"    #         weight={sig.weight},\n"
            f'    #         evidence=f"<human-readable evidence string>",\n'
            f"    #     )]\n"
            f"    return []"
        )
    return "\n\n\n".join(blocks)


def _build_model_fields(spec: WorkflowSpec) -> str:
    """Generates sensible stub fields based on workflow inputs."""
    lines = [
        "    # --- Input-derived fields ---",
        "    # Populate from your actual data schema:",
        "    name: str = \"\"",
        "    category: str = \"\"",
        "    value: float = 0.0",
        "    notes: str = \"\"",
    ]
    return "\n".join(lines)


def _build_from_dict_fields(spec: WorkflowSpec) -> str:
    lines = [
        '            name=str(d.get("name", "")).strip(),',
        '            category=str(d.get("category", "")).strip(),',
        '            value=float(d.get("value", 0) or 0),',
        '            notes=str(d.get("notes", "")).strip(),',
    ]
    return "\n".join(lines)


def _build_reporter_parts(spec: WorkflowSpec) -> tuple[str, str]:
    """Generate writer functions and dispatch table for reporter.py."""
    writer_fns: List[str] = []
    dispatch_lines: List[str] = []

    for out in spec.outputs:
        safe_name = re.sub(r"[^a-z0-9]", "_", out.name.lower()).strip("_")
        fn_name = f"write_{safe_name}"
        out_file = out.name

        if out.output_type == "json":
            fn = (
                f"def {fn_name}(\n"
                f"    ranked: List[{spec.model_class}],\n"
                f"    all_records: List[{spec.model_class}],\n"
                f"    output_dir: Path,\n"
                f") -> Path:\n"
                f'    path = output_dir / "{out_file}"\n'
                f"    payload = {{\n"
                f'        "generated_at": datetime.utcnow().isoformat() + "Z",\n'
                f'        "total_records": len(all_records),\n'
                f'        "ranked_count": len(ranked),\n'
                f'        "records": [_record_to_dict(r) for r in ranked],\n'
                f"    }}\n"
                f"    _write_json(path, payload)\n"
                f"    return path"
            )
        else:
            # Markdown writer
            fn = (
                f"def {fn_name}(\n"
                f"    ranked: List[{spec.model_class}],\n"
                f"    all_records: List[{spec.model_class}],\n"
                f"    output_dir: Path,\n"
                f") -> Path:\n"
                f'    path = output_dir / "{out_file}"\n'
                f'    lines = [\n'
                f'        "# {spec.display_name} Report",\n'
                f'        "",\n'
                f'        f"_Generated: {{datetime.utcnow().strftime(\'%Y-%m-%d %H:%M UTC\')}}_",\n'
                f'        "",\n'
                f'        "---",\n'
                f'        "",\n'
                f'        f"Total records: {{len(all_records)}} | '
                f'Above threshold: {{len(ranked)}}",\n'
                f'        "",\n'
                f'    ]\n'
                f'    for record in ranked:\n'
                f'        lines += [\n'
                f'            f"## {{record.record_id}} (score {{record.confidence_score}}/100)",\n'
                f'            "",\n'
                f'        ]\n'
                f'        for sig in record.signals:\n'
                f'            lines.append(f"- `{{sig.signal_type}}` — {{sig.evidence}}")\n'
                f'        lines.append("")\n'
                f'    path.write_text("\\n".join(lines), encoding="utf-8")\n'
                f"    return path"
            )

        writer_fns.append(fn)
        dispatch_lines.append(
            f'        "{safe_name.upper()}": {fn_name}(ranked, all_records, output_dir),'
        )

    return "\n\n\n".join(writer_fns), "\n".join(dispatch_lines)


def _build_input_table(spec: WorkflowSpec) -> str:
    rows = ["| Flag | Required | Description |", "|------|----------|-------------|"]
    for inp in spec.inputs:
        req = "Yes" if inp.required else "No"
        rows.append(f"| `{inp.flag}` | {req} | {inp.description} |")
    return "\n".join(rows)


def _build_extra_tests(spec: WorkflowSpec) -> str:
    """Generate one extra test class per JSON output."""
    blocks = []
    for out in spec.outputs:
        if out.output_type != "json":
            continue
        safe = re.sub(r"[^a-zA-Z0-9]", "_", out.name).strip("_")
        cls_name = f"Test{safe.title().replace('_', '')}"
        blocks.append(
            f"class {cls_name}:\n"
            f'    def test_structure(self):\n'
            f'        records = load_records(FIXTURES)\n'
            f'        with tempfile.TemporaryDirectory() as tmp:\n'
            f'            paths = run_pipeline(records, Path(tmp))\n'
            f'            import json\n'
            f'            matched = [p for p in paths.values() if "{out.name}" in str(p)]\n'
            f'        if matched:\n'
            f'            data = json.loads(matched[0].read_text())\n'
            f'            assert "generated_at" in data\n'
            f'            assert "records" in data\n'
        )
    return "\n\n".join(blocks)


def _build_fabrication_check(spec: WorkflowSpec) -> str:
    json_outputs = spec.json_outputs
    if not json_outputs:
        return "        pass  # No JSON outputs to validate"
    out = json_outputs[0]
    return (
        f"        with tempfile.TemporaryDirectory() as tmp:\n"
        f"            paths = run_pipeline(load_records(FIXTURES), Path(tmp))\n"
        f"            matched = [p for p in paths.values() if '{out.name}' in str(p)]\n"
        f"        if matched:\n"
        f"            import json\n"
        f"            data = json.loads(matched[0].read_text())\n"
        f"            for rec in data.get('records', []):\n"
        f"                assert rec['record_id'] in original_ids or not original_ids\n"
    )


def _generate_sample_fixture(spec: WorkflowSpec) -> str:
    """Generates a minimal but realistic sample input JSON array."""
    sample = [
        {
            "id": "SAMPLE-001",
            "name": f"Sample {spec.display_name} Record A",
            "category": "example",
            "value": 150000.0,
            "notes": "First sample record for testing",
        },
        {
            "id": "SAMPLE-002",
            "name": f"Sample {spec.display_name} Record B",
            "category": "example",
            "value": 85000.0,
            "notes": "Second sample record for testing",
        },
        {
            "id": "SAMPLE-003",
            "name": f"Sample {spec.display_name} Record C",
            "category": "priority",
            "value": 250000.0,
            "notes": "Third sample record — higher value",
        },
    ]
    return json.dumps(sample, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_type(path: str) -> str:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".md"):
        return "markdown"
    if path.endswith(".json"):
        return "json"
    return "text"
