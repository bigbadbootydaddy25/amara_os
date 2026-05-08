"""
Shared pytest fixtures for the Learning Ingestion Supervisor test suite.

Each fixture builds a minimal but realistic directory tree that mirrors
the actual AI Brain layout.  Tests receive the root brain_dir path and
can pass it directly to inspectors, the supervisor, or quality functions.
"""

import json
import sys
from pathlib import Path

import pytest

# Make the parent package importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _usl_session(brain_dir: Path, session_id: str, **overrides) -> Path:
    """Create a universal-skill-learner output session directory."""
    session_dir = brain_dir / "agents" / "universal-skill-learner" / "outputs" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "session_id": session_id,
        "video_url": overrides.get("video_url", f"https://example.com/video/{session_id}"),
        "title": overrides.get("title", f"Test Video {session_id}"),
        "timestamp": "2024-01-15T10:00:00Z",
        "status": overrides.get("status", "completed"),
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    if "transcript" in overrides:
        (session_dir / "transcript.txt").write_text(overrides["transcript"], encoding="utf-8")

    if "notes" in overrides:
        (session_dir / "notes.md").write_text(overrides["notes"], encoding="utf-8")

    if "workflow" in overrides:
        (session_dir / "workflow.md").write_text(overrides["workflow"], encoding="utf-8")

    return session_dir


def _sag_result(brain_dir: Path, session_id: str, verdict: str, confidence: float, flags=None):
    result_dir = brain_dir / "agents" / "semantic-authenticity-gate" / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": session_id,
        "verdict": verdict,
        "confidence": confidence,
        "flags": flags or [],
    }
    (result_dir / f"{session_id}.json").write_text(json.dumps(data), encoding="utf-8")


GOOD_TRANSCRIPT = """\
In this tutorial we're going to cover the fundamentals of async/await in Python.
Async programming allows you to write concurrent code using a single thread.
The key concept is that while waiting for I/O operations, other code can run.

First, let's understand what coroutines are. A coroutine is a function defined
with async def. When called, it returns a coroutine object that must be awaited.

To run an async function, you need an event loop. The asyncio.run() function
creates a new event loop, runs the coroutine, and closes the loop.

Here's a simple example. We define an async function called fetch_data.
Inside it, we use await asyncio.sleep to simulate a network call.
The sleep doesn't block the thread — other coroutines can run during that time.

Tasks allow multiple coroutines to run concurrently. You create a task with
asyncio.create_task() and then await it. Multiple tasks can run in parallel.

The gather() function runs multiple coroutines concurrently and waits for all
of them to complete. This is useful when you have independent async operations.

Exception handling works the same as synchronous code. You wrap your await
calls in try/except blocks to handle errors from async operations.

Always remember to properly close resources. Use async context managers with
the async with statement to ensure cleanup happens even if exceptions occur.
""" * 2  # double to comfortably exceed 100 words


GOOD_NOTES = """\
# Async/Await in Python — Study Notes

## Core Concepts

- **Coroutine**: function defined with `async def`; returns a coroutine object
- **Event loop**: orchestrates execution of coroutines
- **Task**: wraps a coroutine for concurrent execution

## Key Functions

| Function | Purpose |
|---|---|
| `asyncio.run()` | entry point; creates + closes event loop |
| `asyncio.create_task()` | schedule coroutine as concurrent task |
| `asyncio.gather()` | run multiple coroutines concurrently |

## Pattern: Concurrent Fetch

```python
async def main():
    results = await asyncio.gather(fetch(url1), fetch(url2))
```

## Gotchas

- Forgetting `await` returns a coroutine object, not a result
- Blocking calls (time.sleep) block the whole event loop
- Use `async with` for resource cleanup
"""

GOOD_WORKFLOW = """\
# Workflow: Implementing Async/Await in a Python Project

1. Define your I/O-bound functions with `async def`
2. Replace blocking calls (requests.get, time.sleep) with async equivalents
3. Create an entry point using `asyncio.run(main())`
4. Use `asyncio.create_task()` to run independent operations concurrently
5. Collect results with `asyncio.gather()` when all tasks must complete
6. Wrap resource acquisition in `async with` context managers
7. Test each coroutine in isolation using `asyncio.run()` in your test suite
"""


# ---------------------------------------------------------------------------
# Fixture: failed transcript
# ---------------------------------------------------------------------------


@pytest.fixture()
def failed_transcript_brain(tmp_path):
    """Session where transcript.txt exists but is empty."""
    _usl_session(
        tmp_path,
        "session-failed-tx",
        transcript="",  # empty
        notes=GOOD_NOTES,
        workflow=GOOD_WORKFLOW,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture: placeholder notes
# ---------------------------------------------------------------------------


@pytest.fixture()
def placeholder_notes_brain(tmp_path):
    """Session where notes contain placeholder text."""
    _usl_session(
        tmp_path,
        "session-placeholder",
        transcript=GOOD_TRANSCRIPT,
        notes=(
            "# Video Notes\n\n"
            "TODO: insert content here\n\n"
            "## Summary\n\nplaceholder — notes not generated yet\n"
        ),
        workflow=GOOD_WORKFLOW,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture: duplicate videos
# ---------------------------------------------------------------------------


@pytest.fixture()
def duplicate_videos_brain(tmp_path):
    """Two sessions ingesting the same video URL.

    IDs are chosen so "session-canonical" sorts before "session-zz-duplicate"
    alphabetically, making "session-canonical" the canonical record.
    """
    shared_url = "https://example.com/video/shared-tutorial"
    _usl_session(
        tmp_path,
        "session-canonical",
        video_url=shared_url,
        transcript=GOOD_TRANSCRIPT,
        notes=GOOD_NOTES,
        workflow=GOOD_WORKFLOW,
    )
    _usl_session(
        tmp_path,
        "session-zz-duplicate",
        video_url=shared_url,
        transcript=GOOD_TRANSCRIPT,
        notes=GOOD_NOTES,
        workflow=GOOD_WORKFLOW,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture: weak workflow
# ---------------------------------------------------------------------------


@pytest.fixture()
def weak_workflow_brain(tmp_path):
    """Session with a workflow that has vague, fabricated steps."""
    _usl_session(
        tmp_path,
        "session-weak-wf",
        transcript=GOOD_TRANSCRIPT,
        notes=GOOD_NOTES,
        workflow=(
            "# Workflow\n\n"
            "1. Do the thing\n"
            "2. Follow steps\n"
            "3. Repeat as needed\n"
        ),
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture: successful real workflow ingestion
# ---------------------------------------------------------------------------


@pytest.fixture()
def successful_ingestion_brain(tmp_path):
    """High-quality ingestion with all artifacts present and SAG passing."""
    _usl_session(
        tmp_path,
        "session-success",
        transcript=GOOD_TRANSCRIPT,
        notes=GOOD_NOTES,
        workflow=GOOD_WORKFLOW,
    )
    _sag_result(tmp_path, "session-success", verdict="AUTHENTIC", confidence=0.92)
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture: mixed run (all cases together)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mixed_brain(tmp_path):
    """All five scenarios in a single brain directory for end-to-end tests."""
    shared_url = "https://example.com/video/shared"

    # Failed transcript
    _usl_session(tmp_path, "s-failed-tx", transcript="", notes=GOOD_NOTES, workflow=GOOD_WORKFLOW)

    # Placeholder notes
    _usl_session(
        tmp_path,
        "s-placeholder",
        transcript=GOOD_TRANSCRIPT,
        notes="TODO: insert content here\nplaceholder",
        workflow=GOOD_WORKFLOW,
    )

    # Duplicates
    _usl_session(tmp_path, "s-original", video_url=shared_url,
                 transcript=GOOD_TRANSCRIPT, notes=GOOD_NOTES, workflow=GOOD_WORKFLOW)
    _usl_session(tmp_path, "s-duplicate", video_url=shared_url,
                 transcript=GOOD_TRANSCRIPT, notes=GOOD_NOTES, workflow=GOOD_WORKFLOW)

    # Weak workflow
    _usl_session(tmp_path, "s-weak-wf", transcript=GOOD_TRANSCRIPT, notes=GOOD_NOTES,
                 workflow="1. Do the thing\n2. Repeat\n")

    # Successful
    _usl_session(tmp_path, "s-success", transcript=GOOD_TRANSCRIPT,
                 notes=GOOD_NOTES, workflow=GOOD_WORKFLOW)
    _sag_result(tmp_path, "s-success", verdict="AUTHENTIC", confidence=0.95)

    return tmp_path
