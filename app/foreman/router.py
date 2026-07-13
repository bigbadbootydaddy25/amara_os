"""FOREMAN v0 -- a rule-based task router. No autonomous multi-step
planning in Phase 1.

Pipeline per task: retrieve similar outcomes -> build prompt (persona +
history + payload) -> call provider -> run output through the guard rails
-> write an outcome_log row -> return the response envelope.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, Workspace
from app.foreman.tasks import TaskResult, task_spec_for
from app.guards.output_filter import OutputFilterViolation, run_output_filter
from app.identity import load_persona
from app.llm.provider import LLMProvider
from app.memory.outcome_log import OutcomeLogStore
from app.memory.retrieval import Embedder, similar_outcomes

RESPONSE_INSTRUCTIONS = (
    "Respond with ONLY a JSON object of the form "
    '{"text": "<full written response>", "speakable_text": '
    '"<concise spoken-register version of the same response>"}. '
    "No markdown fences, no commentary outside the JSON object."
)


class ForemanTaskRejected(Exception):
    """Raised when the output guard rails reject a result. Callers map this to HTTP 422."""

    def __init__(self, violation: OutputFilterViolation) -> None:
        self.violation = violation
        super().__init__(str(violation))


class Foreman:
    def __init__(
        self,
        *,
        settings: Settings,
        providers: dict[str, LLMProvider],
        outcome_store: OutcomeLogStore,
        embedder: Embedder,
    ) -> None:
        self.settings = settings
        self.providers = providers
        self.outcome_store = outcome_store
        self.embedder = embedder

    async def run_task(
        self, *, workspace: Workspace, task_type: str, payload: dict[str, Any]
    ) -> TaskResult:
        spec = task_spec_for(task_type)
        route = self.settings.llm.route_for(task_type)
        provider = self.providers[route.provider]

        input_summary = summarize_payload(payload)

        history = await similar_outcomes(
            task_type=task_type,
            text=input_summary,
            workspace=workspace,
            client=self.outcome_store.client,
            embedder=self.embedder,
            k=5,
        )

        prompt = build_prompt(
            workspace=workspace, task_type=task_type, payload=payload, history=history
        )

        raw = await provider.complete(prompt, model=route.model)
        text, speakable_text = parse_response(raw)

        try:
            run_output_filter(
                text,
                client_deliverable=spec.client_deliverable,
                blacklist_terms=self.settings.guards.blacklist_terms,
                ai_names=self.settings.guards.ai_names,
            )
            run_output_filter(
                speakable_text,
                client_deliverable=spec.client_deliverable,
                blacklist_terms=self.settings.guards.blacklist_terms,
                ai_names=self.settings.guards.ai_names,
            )
        except OutputFilterViolation as violation:
            raise ForemanTaskRejected(violation) from violation

        row = self.outcome_store.write(
            workspace=workspace,
            agent="foreman",
            task_type=task_type,
            input_summary=input_summary,
            action_taken=text,
            metadata={"payload": payload},
        )

        return TaskResult(
            text=text, speakable_text=speakable_text, workspace=workspace, task_id=row["id"]
        )


def summarize_payload(payload: dict[str, Any]) -> str:
    for key in ("summary", "text", "prompt"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value[:280]
    return json.dumps(payload)[:280]


def build_prompt(
    *,
    workspace: Workspace,
    task_type: str,
    payload: dict[str, Any],
    history: list[dict[str, Any]],
) -> str:
    persona = load_persona()

    if history:
        history_lines = []
        for row in history:
            line = f"- [{row.get('outcome_status', 'pending')}] {row.get('input_summary', '')}"
            if row.get("action_taken"):
                line += f" -> {row['action_taken']}"
            if row.get("correction"):
                line += f" (correction: {row['correction']})"
            history_lines.append(line)
        history_block = "\n".join(history_lines)
    else:
        history_block = "(none found)"

    return (
        f"{persona}\n\n"
        f"---\n"
        f"Workspace: {workspace}\n"
        f"Task type: {task_type}\n\n"
        f"Relevant history from the outcome log:\n{history_block}\n\n"
        f"Task payload:\n{json.dumps(payload, indent=2)}\n\n"
        f"{RESPONSE_INSTRUCTIONS}"
    )


_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def parse_response(raw: str) -> tuple[str, str]:
    """Extract (text, speakable_text) from the provider's raw completion.

    Providers are asked to return JSON; this falls back to treating the
    whole response as `text` (with a naive speakable_text) if a model
    doesn't comply -- Phase 1 providers are not guaranteed to be
    instruction-tuned for structured output.
    """
    candidate = raw.strip()
    match = _JSON_OBJECT_PATTERN.search(candidate)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "text" in parsed and "speakable_text" in parsed:
                return str(parsed["text"]), str(parsed["speakable_text"])
        except json.JSONDecodeError:
            pass

    text = candidate
    first_sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0] if text.strip() else ""
    return text, first_sentence
