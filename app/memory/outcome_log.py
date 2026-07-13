"""Write/read access to the outcome_log table.

Every FOREMAN task execution writes a row here at status `pending`. Scott
closes the loop later via PATCH /outcomes/{id}. This module is the only
place that talks to the outcome_log table -- callers never build raw
Supabase queries against it, which is what keeps workspace isolation
guaranteed (see `write` / `patch`: workspace is always a required, typed
argument, never optional or inferred).
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from app.config import Workspace

OutcomeStatus = Literal["pending", "success", "partial", "failure", "corrected"]


class SupabaseLike(Protocol):
    """Minimal shape of the supabase-py client this module relies on."""

    def table(self, name: str) -> Any: ...


class OutcomeLogStore:
    def __init__(self, client: SupabaseLike) -> None:
        self.client = client

    def write(
        self,
        *,
        workspace: Workspace,
        agent: str,
        task_type: str,
        input_summary: str,
        action_taken: str,
        metadata: dict | None = None,
        embedding: list[float] | None = None,
        scored_by: Literal["nova"] | None = None,
    ) -> dict:
        row = {
            "workspace": workspace,
            "agent": agent,
            "task_type": task_type,
            "input_summary": input_summary,
            "action_taken": action_taken,
            "outcome_status": "pending",
            "metadata": metadata or {},
        }
        if embedding is not None:
            row["embedding"] = embedding
        if scored_by is not None:
            row["scored_by"] = scored_by

        result = self.client.table("outcome_log").insert(row).execute()
        return result.data[0]

    def patch(
        self,
        outcome_id: str,
        *,
        outcome_status: OutcomeStatus,
        outcome: str | None = None,
        correction: str | None = None,
    ) -> dict:
        update: dict[str, Any] = {"outcome_status": outcome_status}
        if outcome is not None:
            update["outcome"] = outcome
        if correction is not None:
            update["correction"] = correction

        result = (
            self.client.table("outcome_log").update(update).eq("id", outcome_id).execute()
        )
        return result.data[0]
