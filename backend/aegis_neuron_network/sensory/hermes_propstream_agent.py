"""Hermes PropStream Agent — checks for PropStream session files and creates tasks."""
from datetime import datetime, timezone
from typing import Dict

from ..config import MAIN_PROJECT_ROOT, OPENCLAW_TASKS_DIR
from ..events import make_event
from ..event_store import append_event

# PropStream-related files expected in the project
PROPSTREAM_FILES = {
    "propstream_processor": MAIN_PROJECT_ROOT / "backend" / "propstream_processor.py",
    "propstream_browser_agent": MAIN_PROJECT_ROOT / "amara-govcon-os" / "backend" / "propstream_browser_agent.py",
    "propstream_session_checker": MAIN_PROJECT_ROOT / "amara-govcon-os" / "backend" / "propstream_session_checker.py",
    "propstream_extractors": MAIN_PROJECT_ROOT / "amara-govcon-os" / "backend" / "propstream_extractors.py",
}


class HermesPropstreamAgent:
    """
    Checks for PropStream session/authentication files.
    Does NOT run PropStream unless a confirmed authenticated session exists.
    """

    def run(self) -> Dict:
        found_files = {}
        missing_files = {}

        for name, path in PROPSTREAM_FILES.items():
            if path.exists():
                found_files[name] = str(path)
            else:
                missing_files[name] = str(path)

        # Session check: we only run PropStream if session checker exists and is confirmed
        session_confirmed = "propstream_session_checker" in found_files

        task_file_path = OPENCLAW_TASKS_DIR / "propstream_session_task.md"

        if not session_confirmed:
            # Write task file — do not attempt to run PropStream
            OPENCLAW_TASKS_DIR.mkdir(parents=True, exist_ok=True)
            task_content = f"""# PropStream Session Task
Generated: {datetime.now(timezone.utc).isoformat()}
Status: PROPSTREAM_SESSION_NEEDED

## Required Actions
1. Confirm PropStream authenticated session before any data extraction
2. Do NOT bypass CAPTCHA or login
3. Do NOT run PropStream without a verified session

## Files Found
{chr(10).join(f'- {k}: {v}' for k, v in found_files.items()) if found_files else '- None'}

## Files Missing
{chr(10).join(f'- {k}: {v}' for k, v in missing_files.items()) if missing_files else '- None'}

## Next Steps
- Install/locate propstream_session_checker.py at expected path
- Verify session is active and authenticated
- Only then run HermesPropstreamAgent again

## Verification Status
SOURCE_NEEDED — PropStream session not confirmed
"""
            task_file_path.write_text(task_content, encoding="utf-8")

        ev = make_event(
            event_type="OPENCLAW_TASKS_CREATED",
            source="HermesPropstreamAgent",
            payload={
                "status": "PROPSTREAM_SESSION_NEEDED" if not session_confirmed else "SESSION_FOUND",
                "found_files": list(found_files.keys()),
                "missing_files": list(missing_files.keys()),
                "task_file": str(task_file_path) if not session_confirmed else None,
                "session_confirmed": session_confirmed,
            },
            source_file=str(task_file_path),
            verification_status="SOURCE_NEEDED",
            status="PENDING" if not session_confirmed else "COMPLETED",
            notes="PropStream not run — session must be confirmed first.",
        )
        append_event(ev)

        return {
            "agent": "HermesPropstreamAgent",
            "status": "PROPSTREAM_SESSION_NEEDED" if not session_confirmed else "SESSION_FOUND",
            "session_confirmed": session_confirmed,
            "found_files": found_files,
            "missing_files": missing_files,
            "task_file": str(task_file_path) if not session_confirmed else None,
        }
