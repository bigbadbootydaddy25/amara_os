"""pgvector similarity retrieval over the outcome log.

This is the Phase 1 self-learning loop: before FOREMAN acts, it asks
`similar_outcomes` for what happened last time on similar tasks -- including
any correction Scott attached -- and prepends that as "relevant history"
in the prompt. Zero model training required.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.config import Workspace
from app.memory.outcome_log import SupabaseLike


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


async def similar_outcomes(
    *,
    task_type: str,
    text: str,
    workspace: Workspace,
    client: SupabaseLike,
    embedder: Embedder,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Return the k outcome_log rows most similar to `text`, scoped to `workspace`.

    Never crosses workspaces: `workspace` is required and passed straight
    through to the match_outcomes RPC, which filters on it server-side.
    """
    embedding = await embedder.embed(text)
    result = (
        client.rpc(
            "match_outcomes",
            {
                "query_embedding": embedding,
                "match_workspace": workspace,
                "match_task_type": task_type,
                "match_count": k,
            },
        ).execute()
    )
    return result.data
