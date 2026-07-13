"""Task schema and the task-type registry FOREMAN routes against."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from app.config import Workspace
from app.memory.outcome_log import OutcomeStatus


class TaskRequest(BaseModel):
    workspace: Workspace
    task_type: str
    payload: dict[str, Any]


class TaskResult(BaseModel):
    """The response envelope every FOREMAN task returns.

    `speakable_text` is a concise spoken-register version of `text`,
    generated in the same LLM call. Phase 2 pipes it to TTS untouched.
    """

    text: str
    speakable_text: str
    workspace: Workspace
    task_id: str


class OutcomePatchRequest(BaseModel):
    outcome_status: OutcomeStatus
    outcome: str | None = None
    correction: str | None = None


@dataclass(frozen=True)
class TaskSpec:
    # Whether this task_type's output is a client-facing deliverable --
    # controls whether the AI-name guard runs on it.
    client_deliverable: bool = False


TASK_REGISTRY: dict[str, TaskSpec] = {
    "draft_email": TaskSpec(client_deliverable=True),
    "draft": TaskSpec(client_deliverable=False),
    "deal_analysis": TaskSpec(client_deliverable=False),
    "deed_read": TaskSpec(client_deliverable=False),
}
DEFAULT_TASK_SPEC = TaskSpec(client_deliverable=False)


def task_spec_for(task_type: str) -> TaskSpec:
    return TASK_REGISTRY.get(task_type, DEFAULT_TASK_SPEC)
