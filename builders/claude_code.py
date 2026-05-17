from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class ClaudeCodeBuilder:
    """Generates and executes Python code via the claude CLI."""

    def build_and_run(self, task: str) -> str:
        code = self._generate_code(task)
        return self._execute(code)

    def _generate_code(self, task: str) -> str:
        result = subprocess.run(
            ["claude", "-p", f"Write a self-contained Python script that: {task}. Output only the code.", "--output-format", "text"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _execute(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            result = subprocess.run(
                ["python3", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout or result.stderr
        finally:
            tmp_path.unlink(missing_ok=True)

        return output
